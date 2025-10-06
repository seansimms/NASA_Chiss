from __future__ import annotations
import json, os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from fastapi import HTTPException
from .main import ARTIFACTS_ROOT
from .storage import load_job

def _run_artifacts_dir(run_id: str)->Path:
    job = load_job(run_id)
    if not job or not job.artifacts_dir:
        raise HTTPException(404, f"run_id {run_id} not found or has no artifacts_dir")
    p = Path(job.artifacts_dir)
    if not p.exists():
        raise HTTPException(404, f"artifacts_dir for run {run_id} does not exist")
    return p

def _load_oof(run_id: str)->pd.DataFrame:
    root = _run_artifacts_dir(run_id)
    # primary location
    p = root / "stage2" / "oof_stage2.csv"
    if not p.exists():
        # fallback: global artifacts (legacy)
        p = ARTIFACTS_ROOT / "stage2" / "oof_stage2.csv"
    if not p.exists():
        raise HTTPException(404, f"OOF not found for run {run_id}; expected stage2/oof_stage2.csv")
    try:
        df = pd.read_csv(p)
    except Exception as e:
        raise HTTPException(422, f"Failed to read OOF CSV: {e}")
    # normalize columns
    label_col = next((c for c in df.columns if c.lower() in ("label","y")), None)
    ens_col   = next((c for c in df.columns if c.lower() in ("p_final","p_ens","p")), None)
    h1_col    = next((c for c in df.columns if c.lower() in ("p_h1","h1","p_gbm","p_lgbm")), None)
    if label_col is None or ens_col is None:
        raise HTTPException(422, "OOF CSV must include label and p_final columns")
    out = {
        "y": df[label_col].astype(int).to_numpy(),
        "p_ens": df[ens_col].astype(float).to_numpy()
    }
    if h1_col is not None:
        out["p_h1"] = df[h1_col].astype(float).to_numpy()
    return pd.DataFrame(out)

def _calibration_bins(y: np.ndarray, p: np.ndarray, bins:int=15)->Dict:
    bins = int(max(2, min(100, bins)))
    edges = np.linspace(0.0, 1.0, bins+1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins-1)
    conf_mean = np.zeros(bins, dtype=float)
    acc = np.zeros(bins, dtype=float)
    counts = np.zeros(bins, dtype=int)
    for b in range(bins):
        mask = (idx == b)
        n = int(mask.sum())
        counts[b] = n
        if n > 0:
            conf_mean[b] = float(p[mask].mean())
            acc[b] = float(y[mask].mean())
        else:
            conf_mean[b] = float((edges[b] + edges[b+1]) / 2.0)
            acc[b] = np.nan
    # Expected Calibration Error
    N = len(y)
    gaps = np.abs(acc - conf_mean)
    gaps[np.isnan(gaps)] = 0.0
    ece = float(np.sum((counts / max(1,N)) * gaps))
    mids = (edges[:-1] + edges[1:]) / 2.0
    return {"bin_mid": mids.tolist(), "conf_mean": conf_mean.tolist(), "acc": acc.tolist(), "count": counts.tolist(), "ece": ece}

def _pr_curve(y: np.ndarray, p: np.ndarray)->Dict:
    # sort by score desc
    order = np.argsort(-p)
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    denom = tp + fp
    denom[denom==0] = 1
    precision = tp / denom
    P = max(1, int(y.sum()))
    recall = tp / P
    # prepend (0,1) per convention
    precision = np.concatenate(([1.0], precision))
    recall = np.concatenate(([0.0], recall))
    # AUPRC via trapezoid
    auprc = float(np.trapz(precision, recall))
    return {"precision": precision.tolist(), "recall": recall.tolist(), "auprc": auprc}

def _try_load_baseline_curves()->List[Dict]:
    # Best-effort: scan typical paths for baseline PR curves; ignore on failure
    out=[]
    candidates = [
        Path("docs/benchmarks/robovetter_pr.csv"),
        Path("docs/benchmarks/exominer_pr.csv"),
        ARTIFACTS_ROOT.parent / "docs" / "benchmarks" / "robovetter_pr.csv",
        ARTIFACTS_ROOT.parent / "docs" / "benchmarks" / "exominer_pr.csv",
    ]
    for p in candidates:
        try:
            if p.exists():
                df = pd.read_csv(p)
                rcol = next((c for c in df.columns if "recall" in c.lower()), None)
                pcol = next((c for c in df.columns if "precision" in c.lower()), None)
                name = "robovetter" if "robo" in p.name.lower() else ("exominer" if "exo" in p.name.lower() else p.stem)
                if rcol and pcol:
                    out.append({"name": name, "recall": df[rcol].astype(float).tolist(), "precision": df[pcol].astype(float).tolist()})
        except Exception:
            pass
    return out

def api_calibration(run_id: str, bins:int=15, model:str="ens")->Dict:
    df = _load_oof(run_id)
    y = df["y"].to_numpy()
    if model=="h1":
        if "p_h1" not in df.columns:
            raise HTTPException(404, "H1 probabilities not available in OOF")
        p = df["p_h1"].to_numpy()
    else:
        p = df["p_ens"].to_numpy()
    return _calibration_bins(y, p, bins=bins)

def api_ece_bins(run_id: str, bins:int=15, model:str="ens")->Dict:
    return api_calibration(run_id, bins=bins, model=model)  # same payload; client can render bars

def api_pr_overlay(run_id: str)->Dict:
    df = _load_oof(run_id)
    y = df["y"].to_numpy()
    curves = {"ens": _pr_curve(y, df["p_ens"].to_numpy())}
    if "p_h1" in df.columns:
        curves["h1"] = _pr_curve(y, df["p_h1"].to_numpy())
    baselines = _try_load_baseline_curves()
    return {"curves": curves, "baselines": baselines}

def api_pr_curve(run_id: str, model: str="ens")->Dict:
    df = _load_oof(run_id)
    y = df["y"].to_numpy()
    if model == "h1":
        if "p_h1" not in df.columns:
            from fastapi import HTTPException
            raise HTTPException(404, "H1 probabilities not available")
        p = df["p_h1"].to_numpy()
    else:
        p = df["p_ens"].to_numpy()
    return _pr_curve(y, p)

def pr_interp_on_grid(pr: Dict, grid: np.ndarray)->np.ndarray:
    """Interpolate precision onto a monotonically increasing recall grid."""
    # Ensure recall monotonic increasing for interp
    r = np.asarray(pr["recall"], float)
    p = np.asarray(pr["precision"], float)
    # Deduplicate/monotone: sort by recall then unique
    idx = np.argsort(r)
    r = r[idx]; p = p[idx]
    # Clip recall bounds to [0,1]
    r = np.clip(r, 0.0, 1.0)
    # Interp precision at given recall grid
    return np.interp(grid, r, p, left=p[0], right=p[-1])

def _pick_probs(df, model:str):
    if model == "h1":
        if "p_h1" not in df.columns:
            from fastapi import HTTPException
            raise HTTPException(404, "H1 probabilities not available")
        return df["p_h1"].to_numpy()
    else:
        return df["p_ens"].to_numpy()

def api_calibration_bins(run_id: str, model: str="ens", bins: int = 15)->Dict:
    """
    Compute calibration bins for a given run & model using fixed-width bins in [0,1].
    Returns:
      {
        'edges': [...],           # len = bins+1
        'centers': [...],         # len = bins
        'confidence': [...],      # mean predicted prob per bin (NaN→None)
        'accuracy': [...],        # fraction of positives per bin (NaN→None)
        'gap': [...],             # accuracy - confidence (NaN→None)
        'count': [...],           # samples per bin
        'ece': float              # sum(|acc-conf| * count)/N
      }
    """
    if bins < 2: bins = 2
    df = _load_oof(run_id)
    y = df["y"].to_numpy().astype(float)
    p = _pick_probs(df, model)
    # Fixed bins
    edges = np.linspace(0.0, 1.0, bins+1)
    centers = 0.5*(edges[:-1] + edges[1:])
    idx = np.digitize(p, edges, right=True) - 1
    idx = np.clip(idx, 0, bins-1)
    conf = np.full(bins, np.nan)
    acc  = np.full(bins, np.nan)
    cnt  = np.zeros(bins, dtype=int)
    for b in range(bins):
        m = (idx == b)
        cnt[b] = int(m.sum())
        if cnt[b] > 0:
            pb = p[m]
            yb = y[m]
            conf[b] = float(np.mean(pb))
            acc[b]  = float(np.mean(yb))
    gap = acc - conf
    n = max(int(len(y)), 1)
    ece = float(np.nansum(np.abs(gap) * (cnt / n)))
    # Convert NaNs to None for JSON
    def clean(a): return [ (None if (x is None or (isinstance(x,float) and (np.isnan(x) or not np.isfinite(x)))) else float(x)) for x in a ]
    return {
        "edges": edges.tolist(),
        "centers": centers.tolist(),
        "confidence": clean(conf),
        "accuracy": clean(acc),
        "gap": clean(gap),
        "count": [int(c) for c in cnt],
        "ece": ece
    }
