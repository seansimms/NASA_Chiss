#!/usr/bin/env python
from __future__ import annotations
import json, hashlib, math
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dataclasses import dataclass

RNG = np.random.default_rng(1337)

# ---------- Utilities ----------
def sha256_path(p: Path) -> str:
    h = hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()

def savefig(fig, path_png: Path, path_svg: Path):
    path_png.parent.mkdir(parents=True, exist_ok=True)
    # Keep rendering deterministic
    fig.savefig(path_png, dpi=160, bbox_inches="tight", pad_inches=0.1)
    fig.savefig(path_svg, dpi=160, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)

def compute_ece(y_true, p, n_bins=15):
    y_true = np.asarray(y_true).astype(int)
    p = np.asarray(p).astype(float)
    bins = np.linspace(0.0, 1.0, n_bins+1)
    ece, out = 0.0, []
    for i in range(n_bins):
        m = (p >= bins[i]) & (p < bins[i+1] if i < n_bins-1 else p <= bins[i+1])
        if not np.any(m): 
            out.append((0.5*(bins[i]+bins[i+1]), np.nan, np.nan, 0))
            continue
        conf = float(np.mean(p[m])); acc = float(np.mean(y_true[m]))
        ece += np.sum(m) * abs(acc - conf)
        out.append((0.5*(bins[i]+bins[i+1]), conf, acc, int(np.sum(m))))
    ece /= max(len(y_true), 1)
    return float(ece), out

def pr_curve(y, p, n=200):
    # threshold grid deterministic
    ts = np.linspace(0,1,n)
    P = int(np.sum(y)); 
    prec, rec = [], []
    for t in ts:
        yp = (p >= t).astype(int)
        tp = int(np.sum((yp==1) & (y==1)))
        fp = int(np.sum((yp==1) & (y==0)))
        prec.append( tp / max(tp+fp,1) )
        rec.append( tp / max(P,1) )
    # AUPRC via trapezoidal rule over recall-precision curve
    order = np.argsort(rec)
    auprc = float(np.trapz(np.array(prec)[order], x=np.array(rec)[order]))
    return np.array(rec), np.array(prec), auprc

def thresh_at_fpr(y, p, fpr_target=0.01):
    # ROC-like sweep; deterministic
    ts = np.linspace(0,1,2001)
    best = 0.0
    for t in ts:
        yp = (p >= t).astype(int)
        fp = np.sum((yp==1) & (y==0))
        tn = np.sum(y==0)
        fpr = fp / max(tn,1)
        if fpr <= fpr_target: best = t
    return best

def recall_at_fpr(y, p, fpr_target=0.01):
    thr = thresh_at_fpr(y, p, fpr_target)
    yp = (p >= thr).astype(int)
    tp = np.sum((yp==1)&(y==1)); P = np.sum(y==1)
    return float(tp / max(P,1)), float(thr)

def load_config_paths():
    import ruamel.yaml as ry
    y = ry.YAML()
    d = y.load(open("config/config.yaml", "r", encoding="utf-8"))
    paths = d.get("paths", {})
    return {
        "labels_csv": paths.get("labels_csv",""),
        "labels_extra_csv": paths.get("labels_extra_csv",""),
        "stage2_oof": "artifacts/stage2/oof_stage2.csv",
        "h1_oof": "artifacts/features/oof.parquet"
    }

# ---------- System Diagram ----------
def draw_system_overview(out_png: Path, out_svg: Path):
    import matplotlib.patches as patches
    fig, ax = plt.subplots(figsize=(12,7))
    ax.set_axis_off()
    def box(x,y,w,h,label,color="#e8eef9"):
        rect = patches.FancyBboxPatch((x,y),w,h, boxstyle="round,pad=0.02,rounding_size=0.02", 
                                      edgecolor="#1f4fa3", facecolor=color, linewidth=1.25)
        ax.add_patch(rect)
        ax.text(x+w/2, y+h/2, label, ha="center", va="center", fontsize=10, wrap=True)
    def arrow(x1,y1,x2,y2,txt=None):
        ax.annotate("", xy=(x2,y2), xytext=(x1,y1), 
                    arrowprops=dict(arrowstyle="->", lw=1.2, color="#263238"))
        if txt:
            ax.text((x1+x2)/2, (y1+y2)/2+0.02, txt, ha="center", va="bottom", fontsize=8, color="#263238")
    # Layers
    box(0.05,0.75,0.22,0.15,"MAST / Lightkurve / TESSCut\n(Kepler/K2/TESS)","#f5f5f5")
    box(0.32,0.75,0.22,0.15,"Ingest & Manifests\n(caching, hashing)","#f0fff4")
    box(0.59,0.75,0.22,0.15,"Transit-Preserving Detrend\nwōtan","#fff5f0")
    box(0.86-0.22,0.75,0.22,0.15,"Search (TLS+BLS)\nAlias control","#fffaf0")
    arrow(0.27,0.825,0.32,0.825); arrow(0.54,0.825,0.59,0.825); arrow(0.81,0.825,0.86-0.22,0.825)

    box(0.05,0.47,0.27,0.16,"Physics-Aware Fit (batman)\nInvariants, durations","#f3e8ff")
    box(0.37,0.47,0.27,0.16,"Stage-1 (H1) Tabular Ranker\nLightGBM + monotone + calib","#e0f2ff")
    box(0.69,0.47,0.27,0.16,"Stage-2 Heads (H2 shape, H3 centroid)\nStacker + calibration","#e8f5e9")
    arrow(0.18,0.63,0.18,0.75); arrow(0.32,0.555,0.37,0.555); arrow(0.64,0.555,0.69,0.555)

    box(0.05,0.20,0.27,0.16,"Automated Vetting\nOdd/Even, secondaries,\nρ★ prior, crowding, centroid","#fff3e0")
    box(0.37,0.20,0.27,0.16,"Dossiers (HTML/JSON)\nEvidence package","#ede7f6")
    box(0.69,0.20,0.27,0.16,"MLOps & Release\nDeterminism, SBOM, CI, gates","#e1f5fe")
    arrow(0.18,0.36,0.18,0.47); arrow(0.505,0.36,0.505,0.47); arrow(0.825,0.36,0.825,0.47)

    # Outputs
    ax.text(0.5, 0.06, "Project Chiss — System Overview (PRD v1.1)", ha="center", va="center", fontsize=11, weight="bold")
    savefig(fig, out_png, out_svg)

# ---------- Performance Figures ----------
@dataclass
class Inputs:
    labels_csv: str
    labels_extra_csv: str
    stage2_oof: str
    h1_oof: str

def load_oof(inputs: Inputs) -> pd.DataFrame:
    p2 = Path(inputs.stage2_oof)
    if p2.exists():
        df = pd.read_csv(p2)
        assert {"star","label"}.issubset(df.columns)
        if "h1" not in df.columns and Path(inputs.h1_oof).exists():
            # merge calibrated H1 if needed
            p1 = Path(inputs.h1_oof)
            try:
                dfh1 = pd.read_parquet(p1)
            except Exception:
                dfh1 = pd.read_csv(p1)
            df = df.merge(dfh1[["star","oof_cal"]].rename(columns={"oof_cal":"h1"}), on="star", how="left")
        return df
    # fallback: H1 only
    p1 = Path(inputs.h1_oof)
    try:
        d1 = pd.read_parquet(p1)
    except Exception:
        d1 = pd.read_csv(p1)
    if "label" not in d1.columns and inputs.labels_csv:
        d1 = d1.merge(pd.read_csv(inputs.labels_csv)[["star","label"]], on="star", how="left")
    d1 = d1.rename(columns={"oof_cal":"h1"})
    d1["p_final"] = d1["h1"]
    return d1

def plot_pr(df: pd.DataFrame, out_png: Path, out_svg: Path):
    y = df["label"].to_numpy(int)
    p1 = df["h1"].to_numpy(float)
    pe = df["p_final"].to_numpy(float)
    r1, q1, a1 = pr_curve(y, p1); re, qe, ae = pr_curve(y, pe)
    fig, ax = plt.subplots(figsize=(7,5))
    ax.plot(r1, q1, label=f"H1 (AUPRC={a1:.3f})", lw=1.6)
    ax.plot(re, qe, label=f"Ensemble (AUPRC={ae:.3f})", lw=1.8)
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision"); ax.set_title("Precision–Recall (Holdout OOF)")
    ax.grid(True, alpha=0.3); ax.legend()
    savefig(fig, out_png, out_svg)
    return {"auprc_h1": a1, "auprc_ens": ae}

def plot_reliability(df: pd.DataFrame, out_png: Path, out_svg: Path):
    y = df["label"].to_numpy(int)
    p1 = df["h1"].to_numpy(float); pe = df["p_final"].to_numpy(float)
    e1, b1 = compute_ece(y,p1); ee, be = compute_ece(y,pe)
    fig, ax = plt.subplots(figsize=(7,5))
    for bins,lab in [(b1,"H1"),(be,"Ensemble")]:
        xs = [t[0] for t in bins if t[3]>0]; conf = [t[1] for t in bins if t[3]>0]; acc = [t[2] for t in bins if t[3]>0]
        ax.plot(xs, acc, marker="o", lw=1.0, alpha=0.9, label=f"{lab} (ECE:{e1:.3f})" if lab=="H1" else f"{lab} (ECE:{ee:.3f})")
        ax.plot(xs, conf, lw=0.8, alpha=0.5)
    ax.plot([0,1],[0,1], "--", color="gray", lw=1.0)
    ax.set_xlabel("Confidence"); ax.set_ylabel("Empirical Accuracy"); ax.set_title("Reliability Diagram")
    ax.grid(True, alpha=0.3); ax.legend()
    savefig(fig, out_png, out_svg)
    return {"ece_h1": e1, "ece_ens": ee}

def plot_briers(df: pd.DataFrame, out_png: Path, out_svg: Path):
    y = df["label"].to_numpy(int)
    p1 = df["h1"].to_numpy(float); pe = df["p_final"].to_numpy(float)
    b1 = float(np.mean((p1 - y)**2)); be = float(np.mean((pe - y)**2))

    # Handle NaN values
    if np.isnan(b1) or np.isnan(be):
        print(f"Warning: NaN Brier scores detected. H1: {b1}, Ensemble: {be}")
        valid_scores = [s for s in [b1, be] if not np.isnan(s)]
        if not valid_scores:
            # All NaN, skip plotting
            return {"brier_h1": float('nan'), "brier_ens": float('nan')}
        max_score = max(valid_scores)
    else:
        max_score = max(b1, be)

    fig, ax = plt.subplots(figsize=(6,4))
    bars = ax.bar(["H1","Ensemble"], [b1, be])

    # Color NaN bars differently
    for i, (bar, score) in enumerate(zip(bars, [b1, be])):
        if np.isnan(score):
            bar.set_color('gray')
            bar.set_alpha(0.5)

    ax.set_ylabel("Brier Score"); ax.set_title("Brier Score (lower is better)")

    # Only add text labels for valid scores
    for i, (v, label) in enumerate([(b1, "H1"), (be, "Ensemble")]):
        if not np.isnan(v):
            ax.text(i, v+0.002, f"{v:.3f}", ha="center", va="bottom", fontsize=9)

    ax.set_ylim(0, max_score * 1.15 + 1e-3)
    savefig(fig, out_png, out_svg)
    return {"brier_h1": b1, "brier_ens": be}

def maybe_plot_small_planet(df: pd.DataFrame, inputs: Inputs, out_png: Path, out_svg: Path, fpr_target=0.01):
    # Requires radii: rplanet_rearth <= 2.5
    rcol = None
    labels_extra = Path(inputs.labels_extra_csv) if inputs.labels_extra_csv else None
    if labels_extra and labels_extra.exists():
        extra = pd.read_csv(labels_extra)
        if {"star","rplanet_rearth"}.issubset(extra.columns):
            df = df.merge(extra[["star","rplanet_rearth"]], on="star", how="left")
            rcol = "rplanet_rearth"
    if rcol is None:
        return None
    sub = df[df[rcol] <= 2.5].copy()
    if sub.empty or sub["label"].sum()==0: return None
    y = sub["label"].to_numpy(int)
    p1 = sub["h1"].to_numpy(float); pe = sub["p_final"].to_numpy(float)
    r1,_ = recall_at_fpr(y,p1,fpr_target); re,_ = recall_at_fpr(y,pe,fpr_target)
    fig, ax = plt.subplots(figsize=(5.5,4))
    ax.bar(["H1","Ensemble"], [r1, re])
    ax.set_ylim(0,1); ax.set_ylabel(f"Recall @ FPR≤{int(fpr_target*100)}%")
    ax.set_title("Small-Planet Recall (Rp ≤ 2.5 R⊕)")
    for i,v in enumerate([r1,re]): ax.text(i, v+0.02, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    savefig(fig, out_png, out_svg)
    return {"recall_sp_h1": r1, "recall_sp_ens": re}

def main():
    paths = load_config_paths()
    inputs = Inputs(**paths)
    # 1) System overview diagram
    draw_system_overview(Path("docs/architecture/system_overview.png"), Path("docs/architecture/system_overview.svg"))
    # 2) Performance figures (from artifacts)
    df = load_oof(inputs).dropna(subset=["label","h1","p_final"])
    figs_meta = {}
    m1 = plot_pr(df, Path("docs/figures/performance_pr.png"), Path("docs/figures/performance_pr.svg")); figs_meta.update(m1)
    m2 = plot_reliability(df, Path("docs/figures/performance_reliability.png"), Path("docs/figures/performance_reliability.svg")); figs_meta.update(m2)
    m3 = plot_briers(df, Path("docs/figures/performance_brier.png"), Path("docs/figures/performance_brier.svg")); figs_meta.update(m3)
    m4 = maybe_plot_small_planet(df, inputs, Path("docs/figures/performance_small_planet.png"), Path("docs/figures/performance_small_planet.svg"))
    if m4: figs_meta.update(m4)
    # 3) SOURCES.json with hashes of inputs used
    sources = {}
    for p in ["config/config.yaml", inputs.stage2_oof, inputs.h1_oof, inputs.labels_csv, inputs.labels_extra_csv]:
        if p and Path(p).exists():
            sources[p] = sha256_path(Path(p))
    sources["figures_meta"] = figs_meta
    Path("docs/figures/SOURCES.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": list(sources.keys())}, indent=2))

if __name__ == "__main__":
    main()
