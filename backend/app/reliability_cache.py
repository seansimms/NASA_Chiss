from __future__ import annotations
import json, csv, hashlib, io, time
from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np
from fastapi import HTTPException, Response

CACHE_SUBDIR = "reliability"
DEFAULT_BINS = 15

def _sha256_bytes(b: bytes)->str:
    return hashlib.sha256(b).hexdigest()

def _write(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return _sha256_bytes(content)

def build_cache_for_run(run_id: str, bins:int=DEFAULT_BINS)->Dict:
    """Compute and write reliability cache for a run. Returns manifest dict."""
    from .reliability import _run_artifacts_dir, _load_oof, _calibration_bins, _pr_curve
    artdir = _run_artifacts_dir(run_id)
    outdir = artdir / CACHE_SUBDIR
    df = _load_oof(run_id)
    y = df["y"].to_numpy()
    # ENS
    cal_ens = _calibration_bins(y, df["p_ens"].to_numpy(), bins=bins)
    pr_ens = _pr_curve(y, df["p_ens"].to_numpy())
    # H1 optional
    cal_h1 = pr_h1 = None
    if "p_h1" in df.columns:
        cal_h1 = _calibration_bins(y, df["p_h1"].to_numpy(), bins=bins)
        pr_h1 = _pr_curve(y, df["p_h1"].to_numpy())
    # Write JSON
    files = {}
    tnow = time.time()
    cal_ens_json = json.dumps({"model":"ens","bins":bins,"data":cal_ens,"created_at":tnow}).encode()
    files["calibration_ens_bins15.json"] = _write(outdir / "calibration_ens_bins15.json", cal_ens_json)
    pr_ens_json = json.dumps({"model":"ens","data":pr_ens,"created_at":tnow}).encode()
    files["pr_ens.json"] = _write(outdir / "pr_ens.json", pr_ens_json)
    # CSV (ens)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["bin_mid","conf_mean","acc","count","ece"])
    for i in range(len(cal_ens["bin_mid"])):
        w.writerow([cal_ens["bin_mid"][i], cal_ens["conf_mean"][i], cal_ens["acc"][i], cal_ens["count"][i], cal_ens["ece"]])
    files["calibration_ens_bins15.csv"] = _write(outdir / "calibration_ens_bins15.csv", buf.getvalue().encode())
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["recall","precision","auprc"])
    for r,p in zip(pr_ens["recall"], pr_ens["precision"]):
        w.writerow([r,p,pr_ens["auprc"]])
    files["pr_ens.csv"] = _write(outdir / "pr_ens.csv", buf.getvalue().encode())
    # H1 outputs if present
    if cal_h1 is not None and pr_h1 is not None:
        cal_h1_json = json.dumps({"model":"h1","bins":bins,"data":cal_h1,"created_at":tnow}).encode()
        files["calibration_h1_bins15.json"] = _write(outdir / "calibration_h1_bins15.json", cal_h1_json)
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(["bin_mid","conf_mean","acc","count","ece"])
        for i in range(len(cal_h1["bin_mid"])):
            w.writerow([cal_h1["bin_mid"][i], cal_h1["conf_mean"][i], cal_h1["acc"][i], cal_h1["count"][i], cal_h1["ece"]])
        files["calibration_h1_bins15.csv"] = _write(outdir / "calibration_h1_bins15.csv", buf.getvalue().encode())
        pr_h1_json = json.dumps({"model":"h1","data":pr_h1,"created_at":tnow}).encode()
        files["pr_h1.json"] = _write(outdir / "pr_h1.json", pr_h1_json)
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(["recall","precision","auprc"])
        for r,p in zip(pr_h1["recall"], pr_h1["precision"]):
            w.writerow([r,p,pr_h1["auprc"]])
        files["pr_h1.csv"] = _write(outdir / "pr_h1.csv", buf.getvalue().encode())
    # Manifest
    manifest = {
        "run_id": run_id,
        "bins": bins,
        "created_at": tnow,
        "files": files
    }
    _write(outdir / "manifest.json", json.dumps(manifest, indent=2).encode())
    return manifest

def _cached_path(run_id: str, name: str)->Optional[Path]:
    try:
        from .reliability import _run_artifacts_dir
        artdir = _run_artifacts_dir(run_id)
        p = artdir / CACHE_SUBDIR / name
        return p if p.exists() else None
    except HTTPException:
        return None

def serve_cached_or_404(path: Path, media_type:str)->Response:
    data = path.read_bytes()
    etag = _sha256_bytes(data)
    headers = {"ETag": etag, "Cache-Control":"public, max-age=3600"}
    return Response(content=data, media_type=media_type, headers=headers)
