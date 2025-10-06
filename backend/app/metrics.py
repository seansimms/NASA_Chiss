from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
from fastapi import HTTPException
from .contracts import MetricsSummary, BenchmarkReport, BenchmarkRow, CandidatePage, Candidate
from chiss.metrics.compute import compute_metrics
from .db import latest_metrics, ingest_metrics, query_candidates

def read_metrics(artifacts_root: Path) -> MetricsSummary:
    # Prefer DB if present
    lm = latest_metrics()
    if lm:
        return MetricsSummary(
            n=int(lm["n"]), n_pos=int(lm["n_pos"]),
            auprc=float(lm["auprc"]), brier=float(lm["brier"]), ece=float(lm["ece"]),
            recall_small_at_1pct=(None if lm["recall_small_at_1pct"] is None else float(lm["recall_small_at_1pct"])),
            source=str(lm["source"])
        )
    # Prefer gate report if present, else compute from OOF
    gate = artifacts_root / "release" / "gate_report.json"
    if gate.exists():
        data = json.loads(gate.read_text(encoding="utf-8"))
        # also ingest into DB
        try:
            ingest_metrics("adhoc-latest", {
                "n": int(data.get("counts",{}).get("n",0)),
                "n_pos": int(data.get("counts",{}).get("n_pos",0)),
                "auprc": float(data.get("auprc_ens", data.get("auprc", 0.0))),
                "brier": float(data.get("brier_ens", data.get("brier", 0.0))),
                "ece": float(data.get("ece_ens", data.get("ece", 0.0))),
                "recall_small_at_1pct": (data.get("small_recall_at_1pct") if data.get("small_recall_at_1pct") is not None else None),
                "source": str(gate)
            })
        except Exception:
            pass
        return MetricsSummary(
            n=int(data.get("counts",{}).get("n",0)),
            n_pos=int(data.get("counts",{}).get("n_pos",0)),
            auprc=float(data.get("auprc_ens", data.get("auprc", 0.0))),
            brier=float(data.get("brier_ens", data.get("brier", 0.0))),
            ece=float(data.get("ece_ens", data.get("ece", 0.0))),
            recall_small_at_1pct=float(data.get("small_recall_at_1pct", 0.0)) if data.get("small_recall_at_1pct") is not None else None,
            source=str(gate),
        )
    # Compute from OOF CSV
    preds = artifacts_root / "stage2" / "oof_stage2.csv"
    if not preds.exists():
        raise HTTPException(status_code=404, detail="No metrics available: missing gate_report.json and oof_stage2.csv")
    radius = artifacts_root.parent / "labels" / "star_radius.csv"  # default join, optional
    res = compute_metrics(preds_csv=preds, radius_csv=radius if radius.exists() else None)
    return MetricsSummary(
        n=res.n, n_pos=res.n_pos, auprc=res.auprc, brier=res.brier, ece=res.ece,
        recall_small_at_1pct=res.recall_small_at_1pct, source=str(preds)
    )

def read_benchmarks(artifacts_root: Path) -> BenchmarkReport:
    path = artifacts_root / "benchmarks" / "benchmark_table.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No benchmarks found; run benchmarks-compare job.")
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        out.append(BenchmarkRow(
            id=str(r.get("id","")),
            name=str(r.get("name","")),
            auprc=r.get("auprc"),
            brier=r.get("brier"),
            recall_small_at_1pct=r.get("recall_small_at_1pct"),
        ))
    return BenchmarkReport(rows=out, table_path=str(path))

def list_candidates(artifacts_root: Path, limit:int=50, min_p:float=0.0) -> CandidatePage:
    # Prefer DB
    try:
        total, rows = query_candidates(limit=limit, min_p=min_p, offset=0)
        if total>0:
            items = [Candidate(star=r["star"], label=r["label"], p_final=r["p_final"], extra=r["extra"]) for r in rows]
            return CandidatePage(total=total, items=items)
    except Exception:
        pass
    preds = artifacts_root / "stage2" / "oof_stage2.csv"
    if not preds.exists():
        raise HTTPException(status_code=404, detail="No predictions found; train the model first.")
    df = pd.read_csv(preds)
    if "p_final" not in df.columns or "star" not in df.columns:
        raise HTTPException(status_code=422, detail="oof_stage2.csv missing required columns star,p_final")
    df = df.sort_values("p_final", ascending=False)
    if min_p>0: df = df[df["p_final"]>=min_p]
    total = len(df)
    df = df.head(limit)
    items = []
    keep_extra = [c for c in df.columns if c not in ("star","label","p_final")]
    for _, row in df.iterrows():
        items.append(Candidate(
            star=str(row["star"]),
            label=int(row["label"]) if "label" in df.columns and not pd.isna(row["label"]) else None,
            p_final=float(row["p_final"]),
            extra={k: (None if pd.isna(row[k]) else row[k]) for k in keep_extra}
        ))
    return CandidatePage(total=total, items=items)
