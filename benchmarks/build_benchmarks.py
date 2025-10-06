#!/usr/bin/env python
from __future__ import annotations
import json, math, os, sys
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd
from ruamel.yaml import YAML
y=YAML()

def load_gate_metrics(gate_path: Path) -> Dict[str,Any]:
    if not gate_path.exists():
        return {"status":"MISSING"}
    J = json.loads(gate_path.read_text())
    mH = J.get("metrics",{}).get("h1",{})
    mE = J.get("metrics",{}).get("ens",{})
    ac3 = J.get("gates",{}).get("AC-3",{})
    out = {
        "auprc": mE.get("auprc", None),
        "brier": mE.get("brier", None),
        "ece15": mE.get("ece15", None),
        "p_at_fpr1": mE.get("p_at_fpr", None),
        "recall_small": ac3.get("recall_small_ens", None),
        "auprc_h1": mH.get("auprc", None),
        "brier_h1": mH.get("brier", None),
        "ece15_h1": mH.get("ece15", None),
        "p_at_fpr1_h1": mH.get("p_at_fpr", None),
        "recall_small_h1": ac3.get("recall_small_h1", None),
    }
    return out

def main():
    cfg = y.load(Path("config/benchmarks.yaml").read_text())
    gate = Path(cfg["io"]["gate_report"])
    decl = y.load(Path(cfg["io"]["bench_yaml"]).read_text())
    rows = decl.get("rows", [])
    out_rows=[]
    artifacts = load_gate_metrics(gate)
    for r in rows:
        row = {"id": r["id"], "name": r["name"], "source": r.get("source",""), "status":"OK"}
        if r.get("metrics_from_artifacts", False):
            if artifacts.get("auprc") is None:
                row["status"]="MISSING_ARTIFACTS"
            row["values"] = {k: artifacts.get(k) for k in ["auprc","brier","ece15","p_at_fpr1","recall_small"]}
        else:
            vals = r.get("values", {})
            # require all keys to regard as complete
            needed = ["auprc","brier","ece15","p_at_fpr1","recall_small"]
            if not all(k in vals and vals[k] is not None for k in needed):
                row["status"]="INCOMPLETE"
            row["values"] = {k: vals.get(k, None) for k in needed}
        out_rows.append(row)

    # Emit JSON data
    out_dir = Path(cfg["io"]["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    data = {"rows": out_rows}
    (out_dir/"benchmarks.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Build Markdown table
    def fmt(x, p=4):
        return "—" if x is None or (isinstance(x,float) and (math.isnan(x))) else f"{x:.{p}f}"
    lines=[]
    lines.append("| Method | Source | AUPRC | Brier | ECE(15) | P@FPR≤1% | Recall (Rp≤2.5R⊕) | Status |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for r in out_rows:
        v = r["values"]
        lines.append(f"| {r['name']} | {r.get('source','')} | {fmt(v.get('auprc'))} | {fmt(v.get('brier'))} | {fmt(v.get('ece15'))} | {fmt(v.get('p_at_fpr1'),3)} | {fmt(v.get('recall_small'),3)} | {r['status']} |")
    (out_dir/"benchmarks.md").write_text("\n".join(lines)+"\n", encoding="utf-8")

    # Plots (only if ≥2 complete rows to compare)
    complete = [r for r in out_rows if r["status"]=="OK" and all((r["values"][k] is not None) for k in ["auprc","recall_small"])]
    import matplotlib.pyplot as plt
    if len(complete) >= 1:
        # AUPRC bar
        labels=[r["name"] for r in complete]; au=[r["values"]["auprc"] for r in complete]
        plt.figure(figsize=(cfg["plots"]["width"]/100, cfg["plots"]["height"]/100), dpi=cfg["plots"]["dpi"])
        plt.bar(labels, au)
        plt.ylabel("AUPRC"); plt.title("AUPRC Comparison"); plt.xticks(rotation=20, ha="right"); plt.tight_layout()
        plt.savefig(out_dir/"fig_auprc.png"); plt.close()
        # Small-planet recall bar
        sp=[r["values"]["recall_small"] for r in complete]
        plt.figure(figsize=(cfg["plots"]["width"]/100, cfg["plots"]["height"]/100), dpi=cfg["plots"]["dpi"])
        plt.bar(labels, sp)
        plt.ylabel("Recall (Rp≤2.5 R⊕)"); plt.title("Small-Planet Recall"); plt.xticks(rotation=20, ha="right"); plt.tight_layout()
        plt.savefig(out_dir/"fig_recall_small.png"); plt.close()

    # Status
    overall = "COMPLETE" if all(r["status"]=="OK" for r in out_rows) else ("PARTIAL" if any(r["status"]=="OK" for r in out_rows) else "MISSING")
    print(json.dumps({"status": overall, "rows": len(out_rows), "ok": sum(r["status"]=="OK" for r in out_rows)}, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
