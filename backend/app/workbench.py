from __future__ import annotations
import json, math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import numpy as np
import pandas as pd
from fastapi import HTTPException
from .db import list_artifacts_for_star, bulk_index_dir
from .db import DB_PATH  # for existence check only
from .db import _guess_kind as _k  # reuse kind guessing

DEFAULT_MAX_POINTS = 20000

@dataclass
class Series:
    time: np.ndarray
    flux: np.ndarray
    source: Path

def _downsample(x: np.ndarray, y: np.ndarray, max_points:int=DEFAULT_MAX_POINTS)->Tuple[np.ndarray,np.ndarray]:
    n = len(x)
    if n <= max_points: return x, y
    step = math.ceil(n / max_points)
    return x[::step], y[::step]

def _detect_gaps(t: np.ndarray, thr_days: float=0.5)->List[Tuple[float,float]]:
    if len(t) < 2: return []
    dt = np.diff(t)
    idx = np.where(dt > thr_days)[0]
    return [(float(t[i]), float(t[i+1])) for i in idx]

def _read_csv_generic(p: Path)->Series:
    df = pd.read_csv(p)
    # column aliases
    tcol = next((c for c in df.columns if c.lower() in ("time","t","bjd","btjd")), None)
    fcol = next((c for c in df.columns if c.lower() in ("flux","f","norm_flux","pdcsap_flux")), None)
    if tcol is None or fcol is None:
        raise ValueError("CSV missing time/flux columns")
    t = df[tcol].to_numpy(dtype=np.float64)
    f = df[fcol].to_numpy(dtype=np.float64)
    return Series(t, f, p)

def _read_json_series(p: Path, key_time="time", key_flux="flux")->Series:
    obj = json.loads(p.read_text(encoding="utf-8"))
    if key_time not in obj or key_flux not in obj:
        raise ValueError("JSON missing time/flux keys")
    t = np.asarray(obj[key_time], dtype=np.float64)
    f = np.asarray(obj[key_flux], dtype=np.float64)
    return Series(t, f, p)

def _targeted_scan(root: Path, star: str)->int:
    """One-time targeted scan of standard roots for a specific star, then persist to DB."""
    roots = [root/"long_period", root/"search", root/"dossiers", root/"vetting", root/"centroid", root/"stage2"/"series", root]
    cnt=0
    for base in roots:
        if base.exists():
            cnt += bulk_index_dir(run_id="adhoc-scan", root=base, star_hint=star.upper())
    return cnt

def get_raw_lightcurve(artifacts_root: Path, star: str)->Dict:
    # Use index first
    idx = list_artifacts_for_star(star)
    cand_path = None
    for row in idx:
        if row["kind"]=="lc_raw":
            cand_path = Path(row["path"]); break
    if not cand_path:
        # targeted scan then reload index
        _targeted_scan(artifacts_root, star)
        idx = list_artifacts_for_star(star)
        for row in idx:
            if row["kind"]=="lc_raw":
                cand_path = Path(row["path"]); break
    if not cand_path:
        raise HTTPException(404, f"No light curve found for {star}; run search/multi-sector first.")
    series: Series
    try:
        if cand_path.suffix.lower()==".csv":
            series = _read_csv_generic(cand_path)
        elif cand_path.suffix.lower()==".json":
            # dossiers data json often embeds arrays
            series = _read_json_series(cand_path, key_time="time", key_flux="flux")
        else:
            raise ValueError("Unsupported file type")
    except Exception as e:
        raise HTTPException(422, f"Failed to parse LC file {cand_path}: {e}")
    t, f = _downsample(series.time, series.flux)
    gaps = _detect_gaps(t)
    return {
        "star": star, "n": int(len(series.time)),
        "time": t.tolist(), "flux": f.tolist(),
        "gaps": gaps, "source": str(series.source),
    }

def get_phase_curve(artifacts_root: Path, star: str)->Dict:
    # Index lookup
    idx = list_artifacts_for_star(star)
    p_phase = None
    # prefer explicit phase, else fit/tls_result
    for pref in ("phase","fit","tls_result"):
        row = next((r for r in idx if r["kind"]==pref), None)
        if row:
            p_phase = Path(row["path"]); break
    if not p_phase:
        _targeted_scan(artifacts_root, star)
        idx = list_artifacts_for_star(star)
        for pref in ("phase","fit","tls_result"):
            row = next((r for r in idx if r["kind"]==pref), None)
            if row:
                p_phase = Path(row["path"]); break
    if not p_phase:
        raise HTTPException(404, f"No phase/fold data found for {star}; ensure search-fit artifacts exist.")
    model = None; period=None; t0=None; dur=None
    try:
        if p_phase.suffix.lower()==".csv":
            df = pd.read_csv(p_phase)
            # expect columns: phase, flux [, model]
            phcol = next((c for c in df.columns if c.lower() in ("phase","phi")), None)
            fxcol = next((c for c in df.columns if c.lower() in ("flux","f","norm_flux")), None)
            if phcol is None or fxcol is None: raise ValueError("CSV missing phase/flux")
            phase = df[phcol].to_numpy(np.float64); flux = df[fxcol].to_numpy(np.float64)
            if "model" in df.columns: model = df["model"].to_numpy(np.float64)
        else:
            obj = json.loads(p_phase.read_text(encoding="utf-8"))
            # Accept different shapes
            if "phase" in obj and "flux" in obj:
                phase = np.asarray(obj["phase"], np.float64); flux = np.asarray(obj["flux"], np.float64)
                model = np.asarray(obj.get("model",[]), np.float64) if "model" in obj else None
            elif "best" in obj and "phase" in obj["best"]:
                phase = np.asarray(obj["best"]["phase"], np.float64); flux = np.asarray(obj["best"]["flux"], np.float64)
                model = np.asarray(obj["best"].get("model",[]), np.float64) if "model" in obj["best"] else None
            else:
                raise ValueError("JSON lacks phase/flux arrays")
            period = obj.get("period") or obj.get("P_days") or (obj.get("best") or {}).get("period")
            t0 = obj.get("t0") or (obj.get("best") or {}).get("t0")
            dur = obj.get("duration") or (obj.get("best") or {}).get("duration")
        phase, flux = _downsample(phase, flux)
        model_list = None
        if model is not None and len(model)>0:
            _, model = _downsample(phase, model)
            model_list = model.tolist()
        return {
            "star": star, "phase": phase.tolist(), "flux": flux.tolist(),
            "model": model_list, "period": period, "t0": t0, "duration": dur, "source": str(p_phase)
        }
    except Exception as e:
        raise HTTPException(422, f"Failed to parse phase data: {e}")

def get_oddeven(artifacts_root: Path, star: str)->Dict:
    idx = list_artifacts_for_star(star)
    row = next((r for r in idx if r["kind"]=="odd_even"), None)
    p = Path(row["path"]) if row else None
    if not p:
        _targeted_scan(artifacts_root, star)
        idx = list_artifacts_for_star(star)
        row = next((r for r in idx if r["kind"]=="odd_even"), None)
        p = Path(row["path"]) if row else None
    if not p:
        raise HTTPException(404, f"No odd/even comparison found for {star}; run vetting.")
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        odd = obj.get("odd") or {}
        even = obj.get("even") or {}
        ret = {
            "odd": {"phase": odd.get("phase"), "flux": odd.get("flux"), "depth": odd.get("depth")},
            "even": {"phase": even.get("phase"), "flux": even.get("flux"), "depth": even.get("depth")},
            "z": obj.get("z"), "source": str(p)
        }
        return ret
    except Exception as e:
        raise HTTPException(422, f"Failed to parse odd/even JSON: {e}")

def get_centroid(artifacts_root: Path, star: str)->Dict:
    idx = list_artifacts_for_star(star)
    row = next((r for r in idx if r["kind"]=="centroid"), None)
    p = Path(row["path"]) if row else None
    if not p:
        _targeted_scan(artifacts_root, star)
        idx = list_artifacts_for_star(star)
        row = next((r for r in idx if r["kind"]=="centroid"), None)
        p = Path(row["path"]) if row else None
    if not p:
        raise HTTPException(404, f"No centroid series found for {star}; enable centroid export in vetting.")
    try:
        if p.suffix.lower()==".csv":
            df = pd.read_csv(p)
            tcol = next((c for c in df.columns if c.lower() in ("time","t","bjd","btjd")), None)
            dxcol = next((c for c in df.columns if "dx" in c.lower() or "col" in c.lower()), None)
            dycol = next((c for c in df.columns if "dy" in c.lower() or "row" in c.lower()), None)
            if tcol is None or dxcol is None or dycol is None:
                raise ValueError("CSV missing time/dx/dy")
            t = df[tcol].to_numpy(np.float64)
            dx = df[dxcol].to_numpy(np.float64)
            dy = df[dycol].to_numpy(np.float64)
        else:
            obj = json.loads(p.read_text(encoding="utf-8"))
            t = np.asarray(obj.get("time"), np.float64)
            dx = np.asarray(obj.get("dx") or obj.get("x") or obj.get("col"), np.float64)
            dy = np.asarray(obj.get("dy") or obj.get("y") or obj.get("row"), np.float64)
        t, dx = _downsample(t, dx)
        _, dy = _downsample(t, dy)
        r = np.sqrt(dx*dx + dy*dy)
        return {"star": star, "time": t.tolist(), "dx": dx.tolist(), "dy": dy.tolist(), "r": r.tolist(), "source": str(p)}
    except Exception as e:
        raise HTTPException(422, f"Failed to parse centroid series: {e}")
