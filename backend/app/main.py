from __future__ import annotations
import os, json, asyncio, io, csv, hashlib
from pathlib import Path
from typing import List
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Body, Response, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from .models import StartJobRequest, JobInfo, JobList
from .storage import create_job, load_job, list_jobs, has_duplicate_running, mark_cancel
from .jobs import ARTIFACTS_ROOT
from .contracts import MetricsSummary, BenchmarkReport, CandidatePage
from .metrics import read_metrics, read_benchmarks, list_candidates
from .orchestrator import orchestrator
from .db import init_db, list_incomplete_jobs, list_metrics as db_list_metrics, count_metrics as db_count_metrics, get_metrics_summary as db_get_metrics_summary, get_metrics_detail as db_get_metrics_detail, count_candidates_by_run as db_count_candidates_by_run, bulk_index_dir
from .storage import load_job
from .workbench import get_raw_lightcurve, get_phase_curve, get_oddeven, get_centroid
from .reliability import api_calibration, api_ece_bins, api_pr_overlay, api_pr_curve, pr_interp_on_grid, api_calibration_bins
from .reliability_cache import build_cache_for_run, _cached_path, serve_cached_or_404
from .db import list_artifacts_for_star
from .security import verify_key, role_at_least, PUBLIC_READ
from .alerts_store import list_recent as alerts_list_recent, append_event as alerts_append_event, rules_get as alerts_rules_get, upsert_rule as alerts_upsert_rule, delete_rule as alerts_delete_rule, set_rule_muted as alerts_set_rule_muted, channel_health as alerts_channel_health, outbox_write as alerts_outbox_write
import asyncio, os, time, pathlib
import contextlib

PORT = int(os.environ.get("PORT","8000"))
ALLOWED = os.environ.get("ALLOWED_ORIGINS","http://localhost:5173").split(",")

app = FastAPI(title="Chiss Dashboard API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# -------- Auth middleware --------
# Toggle authentication for NASA demo deployment
AUTH_REQUIRED = os.environ.get("AUTH_REQUIRED", "false").lower() == "true"

@app.middleware("http")
async def rbac_guard(request: Request, call_next):
    method = request.method.upper()
    
    # Allow CORS preflight requests (OPTIONS) without authentication
    if method == "OPTIONS":
        return await call_next(request)
    
    # If AUTH_REQUIRED=false (NASA demo mode), bypass all authentication
    if not AUTH_REQUIRED:
        request.state.role = "operator"  # Grant operator role to all requests
        return await call_next(request)
    
    # Standard authentication flow
    token = request.headers.get("X-API-Key","").strip()
    role = "anonymous"
    if token:
        v = verify_key(token)
        if v:
            role = v[1]
    request.state.role = role
    # Enforce on mutations or when PUBLIC_READ is disabled
    if method != "GET" or (not PUBLIC_READ):
        if role == "anonymous":
            return Response(status_code=401, content="API key required")
        # Require operator for mutations
        if method != "GET" and not role_at_least(role, "operator"):
            return Response(status_code=403, content="insufficient role")
    return await call_next(request)

# Helper to enforce admin on specific routes
def require_admin(request: Request):
    role = getattr(request.state, "role", "anonymous")
    if not role_at_least(role, "admin"):
        raise HTTPException(403, "admin role required")

@app.on_event("startup")
async def _startup():
    init_db()
    # Recover jobs that were queued or running previously
    try:
        for job_id in list_incomplete_jobs():
            j = load_job(job_id)
            if j:
                # Re-enqueue without duplication; orchestrator handles queueing
                await orchestrator.enqueue(j)
    except Exception:
        pass
    await orchestrator.start()

@app.on_event("shutdown")
async def _shutdown():
    await orchestrator.stop()

@app.get("/api/health")
def health():
    return {"status":"ok","artifacts_root":str(ARTIFACTS_ROOT), "orchestrator": orchestrator.stats()}

@app.post("/api/jobs", response_model=JobInfo)
async def start_job(req: StartJobRequest):
    # idempotency: avoid duplicate running job with identical params
    dup = has_duplicate_running(req.job_type, req.params)
    if dup:
        raise HTTPException(status_code=409, detail={"message":"duplicate job already running","job_id":dup.job_id})
    info = create_job(req.job_type, req.params, ARTIFACTS_ROOT)
    await orchestrator.enqueue(info)
    return info

@app.get("/api/jobs", response_model=JobList)
def get_jobs():
    return JobList(jobs=list_jobs())

@app.get("/api/jobs/{job_id}", response_model=JobInfo)
def get_job(job_id: str):
    j = load_job(job_id)
    if not j: raise HTTPException(404, "job not found")
    return j

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    j = load_job(job_id)
    if not j: raise HTTPException(404, "job not found")
    if j.state not in ("queued","running"):
        raise HTTPException(400, "job not running or queued")
    mark_cancel(job_id)
    return {"status":"cancelling"}

@app.delete("/api/jobs/clear")
async def clear_all_jobs():
    """Clear all jobs from database AND filesystem (for demo reset)."""
    import sqlite3
    import os
    import shutil
    from pathlib import Path
    
    # Clear database
    db_path = os.environ.get("DB_PATH", "/tmp/chiss.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs")
    conn.commit()
    db_count = cursor.rowcount
    conn.close()
    
    # Clear filesystem job directories
    job_root = Path(os.environ.get("JOB_ROOT", Path(__file__).parent.parent / "jobdata"))
    fs_count = 0
    if job_root.exists():
        for job_dir in job_root.glob("job-*"):
            if job_dir.is_dir():
                shutil.rmtree(job_dir)
                fs_count += 1
    
    return {"status":"cleared", "db_count": db_count, "fs_count": fs_count, "total": db_count + fs_count}

@app.get("/api/orchestrator/stats")
def orch_stats():
    return orchestrator.stats()

# ===== Discoveries API =====
from .discoveries import (
    list_discoveries, 
    get_discovery_detail,
    get_lightcurve_data,
    get_phase_fold_data,
    get_vetting_data,
    get_diagnostics_data
)

@app.get("/api/discoveries")
def get_discoveries():
    """List all completed multi-sector searches with key metrics."""
    return {"discoveries": list_discoveries()}

@app.get("/api/discoveries/{job_id}")
def get_discovery(job_id: str):
    """Get detailed results for a specific multi-sector search."""
    detail = get_discovery_detail(job_id)
    if not detail:
        raise HTTPException(404, "discovery not found")
    return detail

@app.get("/api/discoveries/{job_id}/lightcurve")
def get_discovery_lightcurve_endpoint(job_id: str, max_points: int = 10000):
    """Get decimated light curve data for visualization."""
    data = get_lightcurve_data(job_id, max_points=max_points)
    if not data:
        raise HTTPException(404, "light curve not found")
    if 'error' in data:
        raise HTTPException(500, data['error'])
    return data

@app.get("/api/discoveries/{job_id}/phase")
def get_discovery_phase_fold_endpoint(job_id: str, n_bins: int = 200):
    """Get phase-folded light curve data for transit visualization."""
    data = get_phase_fold_data(job_id, n_bins=n_bins)
    if not data:
        raise HTTPException(404, "phase fold data not found")
    if 'error' in data:
        raise HTTPException(500, data['error'])
    return data

@app.get("/api/discoveries/{job_id}/vetting")
def get_discovery_vetting_endpoint(job_id: str):
    """Get comprehensive vetting report for a discovery."""
    data = get_vetting_data(job_id)
    if not data:
        raise HTTPException(404, "vetting data not found")
    if 'error' in data:
        raise HTTPException(500, data['error'])
    return data

@app.get("/api/discoveries/{job_id}/diagnostics")
def get_discovery_diagnostics_endpoint(job_id: str):
    """Get advanced diagnostic tests for a discovery."""
    data = get_diagnostics_data(job_id)
    if not data:
        raise HTTPException(404, "diagnostics data not found")
    if 'error' in data:
        raise HTTPException(500, data['error'])
    return data

@app.websocket("/api/jobs/{job_id}/logs")
async def ws_logs(ws: WebSocket, job_id: str):
    await ws.accept()
    j = load_job(job_id)
    if not j:
        await ws.send_text("ERROR job not found")
        await ws.close()
        return
    log_path = pathlib.Path(j.log_path) if j.log_path else None
    # Tail file: send existing tail then poll for new lines
    try:
        last_size = 0
        while True:
            if log_path and log_path.exists():
                with contextlib.suppress(Exception):
                    with log_path.open("r", encoding="utf-8") as f:
                        f.seek(last_size)
                        chunk = f.read()
                        if chunk:
                            last_size += len(chunk.encode("utf-8"))
                            for line in chunk.splitlines():
                                await ws.send_text(line)
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return
    except Exception as e:
        with contextlib.suppress(Exception):
            await ws.send_text(f"ERROR {e}")
        with contextlib.suppress(Exception):
            await ws.close()

def _safe_rel(path: Path)->str:
    try: return str(path.relative_to(ARTIFACTS_ROOT))
    except Exception: return str(path)

@app.get("/api/jobs/{job_id}/artifacts")
def list_artifacts(job_id: str):
    j = load_job(job_id)
    if not j: raise HTTPException(404, "job not found")
    root = Path(j.artifacts_dir)
    if not root.exists(): return {"files":[]}
    files = []
    for p in root.rglob("*"):
        if p.is_file():
            files.append({"path": _safe_rel(p), "size": p.stat().st_size})
    return {"root": _safe_rel(root), "files": files}

@app.get("/api/artifacts/{full_path:path}")
def get_artifact(full_path: str):
    real = ARTIFACTS_ROOT / full_path
    if not real.exists() or not real.is_file(): raise HTTPException(404, "artifact not found")
    return FileResponse(real)

@app.get("/api/metrics/latest", response_model=MetricsSummary)
def metrics_latest():
    return read_metrics(ARTIFACTS_ROOT)

@app.get("/api/benchmarks/latest", response_model=BenchmarkReport)
def benchmarks_latest():
    return read_benchmarks(ARTIFACTS_ROOT)

@app.get("/api/candidates", response_model=CandidatePage)
def candidates(limit: int = 50, min_p: float = 0.0):
    if limit < 1 or limit > 1000:
        raise HTTPException(400, "limit must be 1..1000")
    if min_p < 0 or min_p > 1:
        raise HTTPException(400, "min_p must be 0..1")
    return list_candidates(ARTIFACTS_ROOT, limit=limit, min_p=min_p)

@app.get("/api/dossiers/{star_id}")
def dossier(star_id: str):
    # Try flat file, else nested dirs; both are served via artifact route
    cand = ARTIFACTS_ROOT / "dossiers" / f"{star_id}.html"
    if cand.exists():
        return FileResponse(cand)
    # fallback: any html matching star_id under dossiers/
    for p in (ARTIFACTS_ROOT/"dossiers").rglob(f"*{star_id}*.html"):
        return FileResponse(p)
    raise HTTPException(404, "dossier not found")

@app.get("/api/workbench/lightcurve/{star_id}")
def wb_lightcurve(star_id: str):
    return get_raw_lightcurve(ARTIFACTS_ROOT, star_id)

@app.get("/api/workbench/phase/{star_id}")
def wb_phase(star_id: str):
    return get_phase_curve(ARTIFACTS_ROOT, star_id)

@app.get("/api/workbench/oddeven/{star_id}")
def wb_oddeven(star_id: str):
    return get_oddeven(ARTIFACTS_ROOT, star_id)

@app.get("/api/workbench/centroid/{star_id}")
def wb_centroid(star_id: str):
    return get_centroid(ARTIFACTS_ROOT, star_id)

@app.get("/api/workbench/index/{star_id}")
def wb_index(star_id: str):
    rows = list_artifacts_for_star(star_id)
    if not rows:
        # targeted scan (read-only) then return
        try:
            from .workbench import _targeted_scan
            _ = _targeted_scan(ARTIFACTS_ROOT, star_id)
            rows = list_artifacts_for_star(star_id)
        except Exception:
            pass
    return {"star": star_id.upper(), "artifacts": rows}

# -------- Reliability analytics --------
@app.get("/api/reliability/run/{run_id}/calibration")
def reliability_calibration(run_id: str, bins:int=15, model:str="ens"):
    if model not in ("ens","h1"):
        raise HTTPException(422, "model must be 'ens' or 'h1'")
    # Serve cached JSON if present and matches default bins
    if bins == 15:
        cached = _cached_path(run_id, f"calibration_{model}_bins15.json")
        if cached:
            return json.loads(cached.read_text())
    return api_calibration(run_id, bins=bins, model=model)

@app.get("/api/reliability/run/{run_id}/ece_bins")
def reliability_ece(run_id: str, bins:int=15, model:str="ens"):
    if model not in ("ens","h1"):
        raise HTTPException(422, "model must be 'ens' or 'h1'")
    if bins == 15:
        cached = _cached_path(run_id, f"calibration_{model}_bins15.json")
        if cached:
            return json.loads(cached.read_text())
    return api_ece_bins(run_id, bins=bins, model=model)

@app.get("/api/reliability/run/{run_id}/pr_overlay")
def reliability_pr_overlay(run_id: str):
    # If cached curves exist, assemble overlay from cached files
    ens = _cached_path(run_id, "pr_ens.json")
    h1  = _cached_path(run_id, "pr_h1.json")
    if ens:
        curves = {"ens": json.loads(ens.read_text())["data"]}
        if h1:
            curves["h1"] = json.loads(h1.read_text())["data"]
        from .reliability import _try_load_baseline_curves
        return {"curves": curves, "baselines": _try_load_baseline_curves()}
    return api_pr_overlay(run_id)

# ---------- CSV Exports ----------
@app.get("/api/metrics/history.csv")
def metrics_history_csv(limit:int=100, offset:int=0):
    items = db_list_metrics(limit=limit, offset=offset)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["run_id","n","n_pos","auprc","brier","ece","recall_small_at_1pct","source","created_at"])
    for it in items:
        w.writerow([it.get("run_id"), it.get("n"), it.get("n_pos"),
                    it.get("auprc"), it.get("brier"), it.get("ece"),
                    it.get("recall_small_at_1pct"), it.get("source"), it.get("created_at")])
    return Response(content=buf.getvalue(), media_type="text/csv")

@app.get("/api/metrics/history_compact")
def metrics_history_compact(limit:int=100, offset:int=0):
    """
    Compact history for sparklines: run_id, created_at, auprc, brier, ece.
    If db_list_metrics already returns these, pass-through; else enrich via per-run summary.
    """
    items = db_list_metrics(limit=limit, offset=offset) or []
    out = []
    for it in items:
        rid = it.get("run_id")
        created = it.get("created_at") or it.get("ts") or it.get("created") or None
        auprc = it.get("auprc")
        brier = it.get("brier")
        ece = it.get("ece")
        if auprc is None or brier is None or ece is None:
            try:
                s = db_get_metrics_summary(rid) or {}
                auprc = s.get("auprc", auprc)
                brier = s.get("brier", brier)
                ece = s.get("ece", ece)
                if not created:
                    created = s.get("created_at")
            except Exception:
                pass
        out.append({"run_id": rid, "created_at": created, "auprc": auprc, "brier": brier, "ece": ece})
    # Sort oldest→newest for sparkline construction client-side
    out.sort(key=lambda x: (x.get("created_at") or ""))
    return {"items": out, "limit": limit, "offset": offset}

@app.get("/api/reliability/run/{run_id}/calibration.csv")
def reliability_calibration_csv(run_id: str, bins:int=15, model:str="ens"):
    if model not in ("ens","h1"):
        raise HTTPException(422, "model must be 'ens' or 'h1'")
    # Serve cached CSV if present
    if bins == 15:
        cached = _cached_path(run_id, f"calibration_{model}_bins15.csv")
        if cached:
            return serve_cached_or_404(cached, "text/csv")
    cal = api_calibration(run_id, bins=bins, model=model)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["bin_mid","conf_mean","acc","count","ece"])
    for i in range(len(cal["bin_mid"])):
        w.writerow([cal["bin_mid"][i], cal["conf_mean"][i], cal["acc"][i], cal["count"][i], cal["ece"]])
    out = buf.getvalue().encode()
    return Response(content=out, media_type="text/csv")

@app.get("/api/reliability/run/{run_id}/pr_curve.csv")
def reliability_pr_curve_csv(run_id: str, model:str="ens"):
    if model not in ("ens","h1"):
        raise HTTPException(422, "model must be 'ens' or 'h1'")
    # Serve cached CSV if present
    cached = _cached_path(run_id, f"pr_{model}.csv")
    if cached:
        return serve_cached_or_404(cached, "text/csv")
    pr = api_pr_curve(run_id, model=model)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["recall","precision","auprc"])
    for r,p in zip(pr["recall"], pr["precision"]):
        w.writerow([r, p, pr["auprc"]])
    out = buf.getvalue().encode()
    return Response(content=out, media_type="text/csv")

# -------- Metrics history & drilldown --------
@app.get("/api/metrics/history")
def metrics_history(limit:int=100, offset:int=0):
    items = db_list_metrics(limit=limit, offset=offset)
    total = db_count_metrics()
    return {"total": total, "items": items}

@app.get("/api/metrics/run/{run_id}")
def metrics_run_detail(run_id: str):
    summary = db_get_metrics_summary(run_id)
    if not summary:
        raise HTTPException(404, "run_id not found")
    detail = db_get_metrics_detail(run_id)
    job = load_job(run_id)
    cand_n = db_count_candidates_by_run(run_id)
    # minimal job exposure (no paths)
    job_view = None
    if job:
        job_view = {
            "job_id": job.job_id, "job_type": job.job_type, "state": job.state,
            "created_at": job.created_at, "started_at": job.started_at, "finished_at": job.finished_at,
            "attempts": job.attempts, "max_retries": job.max_retries,
        }
    return {"summary": summary, "detail": detail, "job": job_view, "candidates_count": cand_n}

# -------- Auth endpoints --------
@app.get("/api/auth/whoami")
def whoami(request: Request):
    role = getattr(request.state, "role", "anonymous")
    return {"role": role, "public_read": PUBLIC_READ}

# -------- Admin ops (secured) --------
@app.post("/api/admin/reindex")
def admin_reindex(request: Request):
    require_admin(request)
    # reindex current ARTIFACTS_ROOT recursively
    bulk_index_dir(run_id="__admin__", root=ARTIFACTS_ROOT, star_hint=None)
    return {"status":"ok","indexed_root": str(ARTIFACTS_ROOT)}

# ---------- Admin cache builders ----------
@app.post("/api/reliability/run/{run_id}/cache")
def reliability_cache_build_one(request: Request, run_id: str):
    require_admin(request)
    manifest = build_cache_for_run(run_id, bins=15)
    return {"status":"ok","manifest":manifest}

@app.post("/api/reliability/cache_recent")
def reliability_cache_build_recent(request: Request, limit:int=50):
    require_admin(request)
    items = db_list_metrics(limit=limit, offset=0)
    built = []
    for it in items:
        rid = it.get("run_id")
        try:
            manifest = build_cache_for_run(rid, bins=15)
            built.append({"run_id": rid, "ok": True})
        except Exception as e:
            built.append({"run_id": rid, "ok": False, "error": str(e)})
    return {"status":"ok","built": built}

# ---------- Run Comparator ----------
@app.get("/api/metrics/compare")
def metrics_compare(run_a: str, run_b: str):
    a = db_get_metrics_summary(run_a)
    b = db_get_metrics_summary(run_b)
    if not a or not b:
        raise HTTPException(404, "one or both run IDs not found")
    keys = ["n","n_pos","auprc","brier","ece","recall_small_at_1pct"]
    deltas = {k: (b.get(k) - a.get(k)) if (k in a and k in b and isinstance(a.get(k),(int,float)) and isinstance(b.get(k),(int,float))) else None for k in keys}
    return {"run_a": a, "run_b": b, "delta_b_minus_a": deltas}

@app.get("/api/gates/compare")
def gates_compare(run_a: str, run_b: str):
     da = db_get_metrics_detail(run_a) or {}
     dbb = db_get_metrics_detail(run_b) or {}
     ga = (da.get("gates") if isinstance(da.get("gates"), dict) else {})
     gb = (dbb.get("gates") if isinstance(dbb.get("gates"), dict) else {})
     keys = sorted(set(list(ga.keys())+list(gb.keys())))
     changes = {k: {"a": bool(ga.get(k, False)), "b": bool(gb.get(k, False))} for k in keys}
     return {"gates_a": ga, "gates_b": gb, "changes": changes}

@app.get("/api/gates/delta.csv")
def gates_delta_csv(run_a: str, run_b: str):
    return Response(content=buf.getvalue(), media_type="text/csv")

# -------------------- ALERT CENTER --------------------
def _require_operator():
    u = whoami()
    role = (u or {}).get("role","anonymous")
    if role not in ("admin","operator"):
        raise HTTPException(403, "operator or admin role required")
    return u

@app.get("/api/alerts/recent")
def api_alerts_recent(limit:int=100, status:str="all"):
    if status not in ("all","sent","failed"):
        raise HTTPException(422, "status must be all|sent|failed")
    items = alerts_list_recent(limit=limit, status=status)
    return {"items": items, "limit": limit, "status": status}

@app.get("/api/alerts/recent.csv")
def api_alerts_recent_csv(limit:int=100, status:str="all"):
    j = api_alerts_recent(limit=limit, status=status)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["id","ts","star","run_id","p_final","p_std","channels","sent","status","message","url"])
    for it in j["items"]:
        w.writerow([it.get("id"), it.get("ts"), it.get("star"), it.get("run_id"), it.get("p_final"), it.get("p_std"), ",".join(it.get("channels",[])), it.get("sent"), it.get("status"), it.get("message",""), it.get("url","")])
    return Response(content=buf.getvalue(), media_type="text/csv")

@app.get("/api/alerts/rules")
def api_alerts_rules():
    return {"rules": alerts_rules_get(), "channels": alerts_channel_health()}

@app.post("/api/alerts/rules")
def api_alerts_rules_upsert(payload: dict, user=Depends(_require_operator)):
    # expected keys: id?(optional), name, p_min, p_std_max, run_scope, channels{slack_webhook, webhook_url}, muted
    required = ("name","p_min","p_std_max")
    for k in required:
        if k not in payload: raise HTTPException(422, f"missing field: {k}")
    rule = alerts_upsert_rule(payload)
    return {"ok": True, "rule": rule}

@app.post("/api/alerts/rules/{rule_id}/mute")
def api_alerts_rule_mute(rule_id:str, user=Depends(_require_operator)):
    ok = alerts_set_rule_muted(rule_id, True)
    if not ok: raise HTTPException(404, "rule not found")
    return {"ok": True, "id": rule_id, "muted": True}

@app.post("/api/alerts/rules/{rule_id}/unmute")
def api_alerts_rule_unmute(rule_id:str, user=Depends(_require_operator)):
    ok = alerts_set_rule_muted(rule_id, False)
    if not ok: raise HTTPException(404, "rule not found")
    return {"ok": True, "id": rule_id, "muted": False}

@app.delete("/api/alerts/rules/{rule_id}")
def api_alerts_rule_delete(rule_id:str, user=Depends(_require_operator)):
    ok = alerts_delete_rule(rule_id)
    if not ok: raise HTTPException(404, "rule not found")
    return {"ok": True, "id": rule_id}

def _send_to_slack(webhook:str, payload:dict)->(bool,str):
    try:
        import urllib.request, urllib.error
        req = urllib.request.Request(webhook, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            code = resp.getcode()
            return (200 <= code < 300, f"HTTP {code}")
    except Exception as e:
        alerts_outbox_write("slack_fail", {"webhook": webhook, "payload": payload, "error": str(e)})
        return (False, f"error: {e}")

def _post_webhook(url:str, payload:dict)->(bool,str):
    try:
        import urllib.request, urllib.error
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            code = resp.getcode()
            return (200 <= code < 300, f"HTTP {code}")
    except Exception as e:
        alerts_outbox_write("webhook_fail", {"url": url, "payload": payload, "error": str(e)})
        return (False, f"error: {e}")

@app.post("/api/alerts/test_send")
def api_alerts_test_send(payload: dict, user=Depends(_require_operator)):
    """
    Body:
      {
        "star": "TIC123",
        "run_id": "run-uuid",
        "p_final": 0.91,
        "p_std": 0.07,
        "url": "/dossiers/TIC123.html",
        "channels": {
            "slack_webhook": "...optional...",
            "webhook_url": "...optional..."
        }
      }
    """
    star = payload.get("star") or "UNKNOWN"
    run_id = payload.get("run_id") or "UNKNOWN"
    p_final = float(payload.get("p_final", 0.0))
    p_std   = float(payload.get("p_std", 1.0))
    url     = payload.get("url", "")
    ch = payload.get("channels", {}) or {}
    msg = {
        "text": f"Chiss candidate: {star}  p={p_final:.3f}  σ={p_std:.3f}  run={run_id}",
        "star": star, "run_id": run_id, "p_final": p_final, "p_std": p_std, "url": url, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    sent_any = False
    statuses = []
    if ch.get("slack_webhook"):
        ok, info = _send_to_slack(ch["slack_webhook"], msg)
        statuses.append({"channel":"slack","ok":ok,"info":info})
        sent_any = sent_any or ok
    if ch.get("webhook_url"):
        ok, info = _post_webhook(ch["webhook_url"], msg)
        statuses.append({"channel":"webhook","ok":ok,"info":info})
        sent_any = sent_any or ok
    if not statuses:
        # fallback to outbox only
        p = alerts_outbox_write("test_alert", msg)
        statuses.append({"channel":"outbox","ok":True,"info":str(p)})
    ev = alerts_append_event({
        "star": star, "run_id": run_id, "p_final": p_final, "p_std": p_std,
        "channels": [s["channel"] for s in statuses],
        "sent": bool(sent_any or any(s["ok"] for s in statuses)),
        "status": "; ".join([f"{s['channel']}:{'ok' if s['ok'] else 'fail'}" for s in statuses]),
        "message": "test_send",
        "url": url
    })
    return {"ok": True, "event": ev, "statuses": statuses}

# -------- Auth endpoints --------

@app.get("/api/reliability/compare_pr")
def reliability_compare_pr(run_a: str, run_b: str, model: str="ens"):
    if model not in ("ens","h1"):
        raise HTTPException(422, "model must be 'ens' or 'h1'")
    pra = api_pr_curve(run_a, model=model)
    prb = api_pr_curve(run_b, model=model)
    grid = np.linspace(0.0, 1.0, 101)
    pa = pr_interp_on_grid(pra, grid)
    pb = pr_interp_on_grid(prb, grid)
    return {
        "recall": grid.tolist(),
        "precision_a": pa.tolist(),
        "precision_b": pb.tolist(),
        "delta_precision": (pb - pa).tolist(),
        "auprc_a": float(pra["auprc"]),
        "auprc_b": float(prb["auprc"])
    }

@app.get("/api/reliability/compare_pr.csv")
def reliability_compare_pr_csv(run_a: str, run_b: str, model: str="ens"):
    if model not in ("ens","h1"):
        raise HTTPException(422, "model must be 'ens' or 'h1'")
    j = reliability_compare_pr(run_a, run_b, model)  # reuse above
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["recall","precision_a","precision_b","delta_precision","auprc_a","auprc_b"])
    for i,r in enumerate(j["recall"]):
        w.writerow([r, j["precision_a"][i], j["precision_b"][i], j["delta_precision"][i], j["auprc_a"], j["auprc_b"]])
    return Response(content=buf.getvalue(), media_type="text/csv")

@app.get("/api/reliability/compare_cal")
def reliability_compare_cal(run_a: str, run_b: str, model: str="ens", bins: int=15):
    if model not in ("ens","h1"):
        raise HTTPException(422, "model must be 'ens' or 'h1'")
    a = api_calibration_bins(run_a, model=model, bins=bins)
    b = api_calibration_bins(run_b, model=model, bins=bins)
    # They share the same edges by construction (fixed-grid). Use centers from A.
    def _delta_list(la, lb):
        out = []
        for x,y in zip(la, lb):
            if x is None or y is None: out.append(None)
            else: out.append(float(y - x))
        return out
    delta_gap = _delta_list(a["gap"], b["gap"])
    delta_acc = _delta_list(a["accuracy"], b["accuracy"])
    delta_conf = _delta_list(a["confidence"], b["confidence"])
    return {
        "bins": int(bins),
        "centers": a["centers"],
        "confidence_a": a["confidence"], "confidence_b": b["confidence"], "delta_conf": delta_conf,
        "accuracy_a": a["accuracy"],   "accuracy_b": b["accuracy"],     "delta_acc": delta_acc,
        "gap_a": a["gap"],             "gap_b": b["gap"],               "delta_gap": delta_gap,
        "count_a": a["count"],         "count_b": b["count"],
        "ece_a": a["ece"], "ece_b": b["ece"], "delta_ece": float(b["ece"] - a["ece"])
    }

@app.get("/api/reliability/compare_cal.csv")
def reliability_compare_cal_csv(run_a: str, run_b: str, model: str="ens", bins: int=15):
    j = reliability_compare_cal(run_a, run_b, model=model, bins=bins)  # reuse above
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["bin_center","conf_a","acc_a","gap_a","count_a","conf_b","acc_b","gap_b","count_b","delta_conf","delta_acc","delta_gap","ece_a","ece_b","delta_ece"])
    for i in range(len(j["centers"])):
        def g(key):
            v = j.get(key);
            if isinstance(v, list):
                return v[i]
            return v
        row = [
            j["centers"][i],
            g("confidence_a"), g("accuracy_a"), g("gap_a"), j["count_a"][i],
            g("confidence_b"), g("accuracy_b"), g("gap_b"), j["count_b"][i],
            g("delta_conf"), g("delta_acc"), g("delta_gap"),
            j["ece_a"], j["ece_b"], j["delta_ece"]
        ]
        w.writerow(row)
    return Response(content=buf.getvalue(), media_type="text/csv")

# ---------- Run Compare Exportable Report ----------
def _sha256_path_or_none(p):
    if not p: return None
    try:
        b = p.read_bytes()
        return hashlib.sha256(b).hexdigest()
    except Exception:
        return None

@app.get("/api/compare/report.csv")
def compare_report_csv(run_a: str, run_b: str):
    a = db_get_metrics_summary(run_a)
    b = db_get_metrics_summary(run_b)
    if not a or not b:
        raise HTTPException(404, "one or both run IDs not found")
    # PR stats (ensemble)
    pr_json = reliability_compare_pr(run_a, run_b, model="ens")
    # Δ-PR area (trapezoid integral of delta precision over recall grid)
    recall = pr_json["recall"]; dprec = pr_json["delta_precision"]
    area = 0.0
    for i in range(1, len(recall)):
        dx = recall[i] - recall[i-1]
        area += 0.5 * (dprec[i] + dprec[i-1]) * dx
    # Build CSV
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["field","A","B","delta_B_minus_A"])
    def row(k, fmt="{:.3f}"):
        av=a.get(k,None); bv=b.get(k,None); dv=(None if av is None or bv is None else (bv-av))
        def fmtv(v):
            if v is None: return ""
            if isinstance(v,(int,)) and not isinstance(v,bool): return str(v)
            if isinstance(v,(float,)): return fmt.format(v)
            return str(v)
        w.writerow([k, fmtv(av), fmtv(bv), fmtv(dv)])
    for k in ["n","n_pos","auprc","brier","ece","recall_small_at_1pct"]:
        row(k)
    # PR extras
    w.writerow(["auprc_pr_ens", f"{pr_json['auprc_a']:.3f}", f"{pr_json['auprc_b']:.3f}", f"{(pr_json['auprc_b']-pr_json['auprc_a']):.3f}"])
    w.writerow(["delta_pr_area_B_minus_A", "", "", f"{area:.3f}"])
    # Gate diffs (flatten)
    gd = gates_compare(run_a, run_b)
    for gk, gv in sorted((gd.get("changes") or {}).items()):
        label = ("PASS→FAIL" if gv["a"] and not gv["b"] else ("FAIL→PASS" if (not gv["a"] and gv["b"]) else ("PASS↔PASS" if gv["a"] else "FAIL↔FAIL")))
        w.writerow([f"gate:{gk}", "PASS" if gv["a"] else "FAIL", "PASS" if gv["b"] else "FAIL", label])
    return Response(content=buf.getvalue(), media_type="text/csv")

@app.get("/api/compare/report.md")
def compare_report_md(run_a: str, run_b: str):
    a = db_get_metrics_summary(run_a)
    b = db_get_metrics_summary(run_b)
    if not a or not b:
        raise HTTPException(404, "one or both run IDs not found")
    prj = reliability_compare_pr(run_a, run_b, model="ens")
    # Δ-PR area
    r = prj["recall"]; dp = prj["delta_precision"]
    area = 0.0
    for i in range(1, len(r)):
        dx = r[i] - r[i-1]; area += 0.5 * (dp[i] + dp[i-1]) * dx
    # Cache checksums (if present)
    a_ens = _cached_path(run_a, "pr_ens.json"); b_ens = _cached_path(run_b, "pr_ens.json")
    sha_a = _sha256_path_or_none(a_ens); sha_b = _sha256_path_or_none(b_ens)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Markdown
    md = []
    md.append(f"# Chiss Run Compare Report\n")
    md.append(f"- Generated: **{now}** UTC")
    md.append(f"- Run A: `{run_a}`  |  Run B: `{run_b}`")
    if sha_a or sha_b:
        md.append(f"- Cache PR checksums — A: `{sha_a or 'n/a'}`, B: `{sha_b or 'n/a'}`")
    md.append("")
    md.append("## Summary")
    md.append(f"- **AUPRC (ens)**: A={prj['auprc_a']:.3f}, B={prj['auprc_b']:.3f}, Δ(B−A)={(prj['auprc_b']-prj['auprc_a']):.3f}")
    md.append(f"- **Δ-PR area (B−A)** over recall∈[0,1]: {area:.3f}")
    md.append("")
    md.append("## Key Metrics")
    md.append("| Metric | A | B | Δ (B−A) |")
    md.append("|---|---:|---:|---:|")
    def row(k):
        av=a.get(k,None); bv=b.get(k,None); dv=(None if av is None or bv is None else (bv-av))
        def fmt(v):
            if v is None: return ""
            return f"{v:.3f}" if isinstance(v,(float,)) else str(v)
        md.append(f"| {k} | {fmt(av)} | {fmt(bv)} | {fmt(dv)} |")
    for k in ["n","n_pos","auprc","brier","ece","recall_small_at_1pct"]:
        row(k)
    md.append("")
    md.append("## Gate Changes")
    gd = gates_compare(run_a, run_b)
    changes = gd.get("changes") or {}
    if not changes:
        md.append("_No gate data available._")
    else:
        md.append("| Gate | A | B | Change |")
        md.append("|---|:--:|:--:|:--:|")
        for gk, gv in sorted(changes.items()):
            label = ("PASS→FAIL" if gv["a"] and not gv["b"] else ("FAIL→PASS" if (not gv["a"] and gv["b"]) else ("PASS↔PASS" if gv["a"] else "FAIL↔FAIL")))
            md.append(f"| {gk} | {'PASS' if gv['a'] else 'FAIL'} | {'PASS' if gv['b'] else 'FAIL'} | {label} |")
    md.append("")
    md.append("## PR/Δ-PR Stats (Ensemble)")
    md.append(f"- CSV grid: `/api/reliability/compare_pr.csv?run_a={run_a}&run_b={run_b}&model=ens`")
    md.append(f"- Overlay permalink: `?tab=compare&run_a={run_a}&run_b={run_b}`")
    md.append("")
    md.append("_Report generated by Chiss dashboard D-14._\n")
    text = "\n".join(md)
    return Response(content=text, media_type="text/markdown; charset=utf-8")

