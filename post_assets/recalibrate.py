"""Post-hoc confidence recalibration for GIAE functional calls.

The homology calibration showed GIAE's raw confidence is over-confident: mean
confidence 0.83 vs synonym-adjusted accuracy 0.54. This fits a monotonic
mapping raw_confidence -> P(correct) so the reported number means what it says.

Scientific rigor:
  * Evaluated with 5-fold stratified cross-validation — the calibrator is fit
    on 4 folds and scored on the held-out fold, so the reported improvement is
    out-of-sample, not the in-sample optimism you'd get from fitting and
    testing on the same rows.
  * Two methods compared: isotonic regression (flexible, monotone) and Platt
    scaling (logistic sigmoid). We keep whichever gives the lower CV Brier.
  * Target label = synonym-adjusted correctness (the better estimate of true
    correctness; still a lower bound, so the calibrated probability is
    conservative — see BENCHMARK_METHODOLOGY.md §4).

Outputs (post_assets/):
  recalibration.png            before/after reliability
  recalibration_summary.txt    CV metrics + chosen method
  calibration_mapping.json     portable isotonic knots for the engine (no
                               sklearn needed at runtime)

Run:
  PYTHONPATH=src:post_assets .venv/bin/python post_assets/recalibrate.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from product_synonyms import synonym_agree

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "post_assets"
SAMPLES = OUT / "calibration_samples_homology.csv"
N_BINS = 12
SEED = 0  # fixed — Math.random-free reproducibility


def load():
    conf, y = [], []
    for r in csv.DictReader(SAMPLES.open()):
        conf.append(float(r["confidence"]))
        y.append(int(synonym_agree(r["pred_product"], r["truth_product"])[0]))
    return np.array(conf), np.array(y)


def ece_mce(p, y, n_bins=N_BINS):
    """Expected / Max Calibration Error over equal-width probability bins."""
    edges = np.linspace(0, 1, n_bins + 1)
    ece = mce = 0.0
    n = len(p)
    for i in range(n_bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < n_bins - 1 else p <= edges[i + 1])
        if not m.any():
            continue
        conf_bin = p[m].mean()
        acc_bin = y[m].mean()
        gap = abs(acc_bin - conf_bin)
        ece += m.sum() / n * gap
        mce = max(mce, gap)
    return ece, mce


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def cv_predict(conf, y, method):
    """Out-of-fold calibrated probabilities via 5-fold stratified CV."""
    oof = np.zeros_like(conf, dtype=float)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    for tr, te in skf.split(conf.reshape(-1, 1), y):
        if method == "isotonic":
            m = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            m.fit(conf[tr], y[tr])
            oof[te] = m.predict(conf[te])
        else:  # platt
            m = LogisticRegression()
            m.fit(conf[tr].reshape(-1, 1), y[tr])
            oof[te] = m.predict_proba(conf[te].reshape(-1, 1))[:, 1]
    return oof


def make_figure(conf, y, cal):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=.5, label="Perfect calibration")

    def curve(p, color, label, marker):
        edges = np.linspace(0, 1, N_BINS + 1)
        xs, ys, ss = [], [], []
        for i in range(N_BINS):
            m = (p >= edges[i]) & (p < edges[i + 1] if i < N_BINS - 1 else p <= edges[i + 1])
            if m.sum() < 10:
                continue
            xs.append(p[m].mean()); ys.append(y[m].mean()); ss.append(m.sum())
        ax.plot(xs, ys, marker + "-", color=color, label=label, lw=2, ms=7, alpha=.9)

    curve(conf, "#94a3b8", "Raw confidence (over-confident)", "s")
    curve(cal, "#6366f1", "Recalibrated (out-of-fold)", "o")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted confidence"); ax.set_ylabel("Observed accuracy (synonym-adjusted)")
    ax.set_title("GIAE confidence recalibration\nreliability before vs after (5-fold CV)")
    ax.legend(loc="upper left"); ax.grid(True, alpha=.2)
    fig.tight_layout()
    p = OUT / "recalibration.png"
    fig.savefig(p, dpi=160)
    print(f"figure → {p}")


def main():
    conf, y = load()
    n = len(conf)

    raw_ece, raw_mce = ece_mce(conf, y)
    raw_brier = brier(conf, y)

    results = {}
    for method in ("isotonic", "platt"):
        oof = cv_predict(conf, y, method)
        results[method] = (oof, *ece_mce(oof, y), brier(oof, y))

    # choose lower CV Brier
    best = min(results, key=lambda m: results[m][3])
    oof, ece, mce, br = results[best]

    # fit FINAL calibrator on all data and export a portable mapping
    if best == "isotonic":
        final = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(conf, y)
        xk = final.X_thresholds_.tolist()
        yk = final.y_thresholds_.tolist()
        mapping = {"method": "isotonic", "x": xk, "y": yk,
                   "note": "piecewise-linear: interpolate P(correct) from raw confidence x"}
    else:
        final = LogisticRegression().fit(conf.reshape(-1, 1), y)
        mapping = {"method": "platt",
                   "a": float(final.coef_[0][0]), "b": float(final.intercept_[0]),
                   "note": "P(correct) = 1/(1+exp(-(a*conf + b)))"}
    (OUT / "calibration_mapping.json").write_text(json.dumps(mapping, indent=2))

    make_figure(conf, y, oof)

    def pct(x):
        return f"{x:.3f}"
    lines = [
        "=" * 62,
        "GIAE confidence recalibration (5-fold CV, out-of-sample)",
        "=" * 62,
        f"Samples                 : {n}",
        f"Target                  : synonym-adjusted correctness (lower bound)",
        "",
        f"{'Metric':<10}{'raw':>10}{'isotonic':>12}{'platt':>10}   (lower = better)",
        "-" * 62,
        f"{'ECE':<10}{pct(raw_ece):>10}{pct(results['isotonic'][1]):>12}{pct(results['platt'][1]):>10}",
        f"{'MCE':<10}{pct(raw_mce):>10}{pct(results['isotonic'][2]):>12}{pct(results['platt'][2]):>10}",
        f"{'Brier':<10}{pct(raw_brier):>10}{pct(results['isotonic'][3]):>12}{pct(results['platt'][3]):>10}",
        "",
        f"Chosen method (lower CV Brier): {best.upper()}",
        f"  ECE   {pct(raw_ece)} → {pct(ece)}   ({100*(raw_ece-ece)/raw_ece:+.0f}%)",
        f"  Brier {pct(raw_brier)} → {pct(br)}   ({100*(raw_brier-br)/raw_brier:+.0f}%)",
        "",
        "Mean predicted probability after recalibration aligns with observed",
        f"accuracy: mean_cal={oof.mean():.3f}  vs  accuracy={y.mean():.3f}",
        f"(raw mean confidence was {conf.mean():.3f} — the over-confidence is removed).",
        "",
        "Exported: calibration_mapping.json (portable; engine interpolates without",
        "sklearn at runtime). Because the target is a lower-bound accuracy, the",
        "calibrated probability is conservative — it will not over-state correctness.",
        "=" * 62,
    ]
    report = "\n".join(lines)
    (OUT / "recalibration_summary.txt").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
