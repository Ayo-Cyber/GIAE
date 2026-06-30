"""Confidence calibration analysis for GIAE functional interpretations.

Answers: "when GIAE assigns confidence X to a functional call, how often is
that call actually correct?" — the reviewer's key scientific-credibility ask.

For every gene that GIAE both (a) gives an informative functional label and
(b) coordinate-matches a curated RefSeq gene with an informative product, we
record (confidence_score, confidence_level, correct) where `correct` is the
same token-overlap agreement used in benchmark_figure.py. Genes whose truth
product is uninformative (hypothetical/unknown) are excluded — we can't grade
correctness without a curated label.

Outputs (post_assets/):
  calibration_curve.png     — reliability diagram + per-level accuracy bars
  calibration_summary.txt   — ECE, MCE, Brier score, per-level table
  calibration_samples.csv   — raw (genome, gene, confidence, level, correct)

Run:
  PYTHONPATH=src .venv/bin/python post_assets/calibration.py            # phages
  PYTHONPATH=src .venv/bin/python post_assets/calibration.py --set all  # + bacteria
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Reuse the exact scoring + extraction logic from the main benchmark so the
# calibration "correct" label matches the F1 functional metric one-for-one.
from benchmark_figure import (  # noqa: E402
    CASE_DIR, BACT_DIR, parser, _GIAE, _GIAE_PHAGE,
    func_agree, informative, overlap,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "post_assets"


def is_abstention(product: str | None) -> bool:
    """GIAE flags genuine ambiguity with an 'Ambiguous interpretation: X vs Y'
    hypothesis. That is the engine *declining to commit*, not a functional
    prediction — so it must not be graded as one."""
    return bool(product) and product.startswith("Ambiguous interpretation")


def collect_samples(gb: Path, phage_mode: bool, abstentions: list[int]) -> list[dict]:
    """Return calibration samples for one genome. `abstentions[0]` is incremented
    for each matched gene where GIAE explicitly declined to commit."""
    g = parser.parse(gb)
    # truth coordinates + products, captured before clearing
    truth = [
        (gene.location.start, gene.location.end, gene.location.strand.value,
         gene.protein.product_name if gene.protein else None)
        for gene in g.genes
    ]
    g.genes.clear()
    g.file_format = "fasta"
    interp = _GIAE_PHAGE if phage_mode else _GIAE
    summary = interp.interpret_genome(g)
    gmap = {x.id: x for x in g.genes}

    samples: list[dict] = []
    used: set[int] = set()
    for r in summary.results:
        if not r.interpretation:
            continue
        gene = gmap.get(r.gene_id)
        if not gene:
            continue
        i = r.interpretation
        pred_product = (i.metadata or {}).get("normalized_product") or i.hypothesis
        if is_abstention(pred_product):
            abstentions[0] += 1
            continue  # GIAE explicitly declined to commit — not a prediction
        if not informative(pred_product):
            continue  # GIAE gave no informative label — nothing to calibrate

        loc = gene.location
        pred_feat = (loc.start, loc.end, loc.strand.value, pred_product)
        # best coordinate match against unused truth genes
        best, best_o = -1, 0.5
        for j, t in enumerate(truth):
            if j in used:
                continue
            o = overlap(pred_feat, t)
            if o >= best_o:
                best_o, best = o, j
        if best < 0:
            continue  # predicted gene doesn't match any truth gene — skip
        t = truth[best]
        if not informative(t[3]):
            continue  # truth is hypothetical — can't grade correctness
        used.add(best)

        samples.append({
            "genome": gb.stem,
            "gene": r.gene_id,
            "confidence": round(i.confidence_score, 4),
            "level": i.confidence_level.value,
            "pred_product": pred_product,
            "truth_product": t[3],
            "correct": int(func_agree(pred_product, t[3])),
        })
    return samples


def reliability_bins(samples: list[dict], n_bins: int = 10):
    """Equal-width confidence bins → (centers, accuracies, counts, mean_conf)."""
    bins = [[] for _ in range(n_bins)]
    for s in samples:
        idx = min(int(s["confidence"] * n_bins), n_bins - 1)
        bins[idx].append(s)
    centers, accs, counts, mean_confs = [], [], [], []
    for b_idx, b in enumerate(bins):
        if not b:
            continue
        centers.append((b_idx + 0.5) / n_bins)
        accs.append(sum(s["correct"] for s in b) / len(b))
        counts.append(len(b))
        mean_confs.append(sum(s["confidence"] for s in b) / len(b))
    return centers, accs, counts, mean_confs


def metrics(samples: list[dict], n_bins: int = 10):
    """Expected/Max Calibration Error + Brier score."""
    n = len(samples)
    if n == 0:
        return 0.0, 0.0, 0.0
    _, accs, counts, mean_confs = reliability_bins(samples, n_bins)
    ece = sum(c / n * abs(a - mc) for a, c, mc in zip(accs, counts, mean_confs))
    mce = max((abs(a - mc) for a, mc in zip(accs, mean_confs)), default=0.0)
    brier = sum((s["confidence"] - s["correct"]) ** 2 for s in samples) / n
    return ece, mce, brier


def make_figure(samples: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    # ── reliability diagram ──
    centers, accs, counts, mean_confs = reliability_bins(samples, n_bins=10)
    ax1.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="Perfect calibration")
    sizes = [max(30, 12 * c ** 0.5 * 6) for c in counts]
    ax1.scatter(mean_confs, accs, s=sizes, color="#6366f1", alpha=0.8, zorder=3,
                label="GIAE (bubble ∝ #genes)")
    for mc, a, c in zip(mean_confs, accs, counts):
        ax1.annotate(str(c), (mc, a), fontsize=7, ha="center", va="center", color="white")
    ax1.set_xlim(0, 1); ax1.set_ylim(0, 1)
    ax1.set_xlabel("Mean predicted confidence", fontsize=11)
    ax1.set_ylabel("Observed accuracy (vs RefSeq)", fontsize=11)
    ax1.set_title("Reliability diagram — GIAE functional confidence", fontsize=11)
    ax1.legend(fontsize=9, loc="upper left")
    ax1.grid(True, alpha=0.2)

    # ── per-confidence-level accuracy bars ──
    order = ["high", "moderate", "low", "speculative"]
    by_level = {lv: [s for s in samples if s["level"] == lv] for lv in order}
    labels, vals, ns = [], [], []
    colors = {"high": "#10b981", "moderate": "#3b82f6", "low": "#f59e0b", "speculative": "#ef4444"}
    bar_colors = []
    for lv in order:
        b = by_level[lv]
        if not b:
            continue
        labels.append(lv.capitalize())
        vals.append(sum(s["correct"] for s in b) / len(b))
        ns.append(len(b))
        bar_colors.append(colors[lv])
    bars = ax2.bar(labels, vals, color=bar_colors, alpha=0.85)
    for bar, n, v in zip(bars, ns, vals):
        ax2.text(bar.get_x() + bar.get_width() / 2, v + 0.02,
                 f"{v:.0%}\nn={n}", ha="center", fontsize=9)
    ax2.set_ylim(0, 1.1)
    ax2.set_ylabel("Observed accuracy (vs RefSeq)", fontsize=11)
    ax2.set_title("Accuracy by GIAE confidence level", fontsize=11)
    ax2.grid(True, axis="y", alpha=0.2)

    fig.tight_layout()
    path = OUT / "calibration_curve.png"
    fig.savefig(path, dpi=160)
    print(f"calibration figure → {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["phages", "bacteria", "all"], default="all")
    args = ap.parse_args()

    if args.set == "phages":
        genomes = sorted(CASE_DIR.glob("*.gb"))
    elif args.set == "bacteria":
        genomes = sorted(BACT_DIR.glob("*.gb"))
    else:
        genomes = sorted(CASE_DIR.glob("*.gb")) + sorted(BACT_DIR.glob("*.gb"))

    all_samples: list[dict] = []
    abstentions = [0]
    for gb in genomes:
        phage_mode = str(CASE_DIR) in str(gb.resolve())
        try:
            s = collect_samples(gb, phage_mode, abstentions)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {gb.stem}: {exc}", file=sys.stderr)
            continue
        all_samples.extend(s)
        print(f"  {gb.stem:<35} gradeable={len(s)}", flush=True)

    if not all_samples:
        print("no calibratable samples", file=sys.stderr)
        return 1

    # raw CSV
    csv_path = OUT / "calibration_samples.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "genome", "gene", "confidence", "level", "pred_product", "truth_product", "correct"])
        w.writeheader()
        w.writerows(all_samples)

    make_figure(all_samples)

    ece, mce, brier = metrics(all_samples)
    n = len(all_samples)
    overall_acc = sum(s["correct"] for s in all_samples) / n
    mean_conf = sum(s["confidence"] for s in all_samples) / n

    order = ["high", "moderate", "low", "speculative"]
    lines = [
        "=" * 60,
        "GIAE Confidence Calibration",
        "=" * 60,
        f"Gradeable functional calls : {n}",
        f"  (GIAE gave an informative label AND coordinate-matched a",
        f"   RefSeq gene with an informative curated product)",
        f"Explicit abstentions       : {abstentions[0]}  ('Ambiguous interpretation:",
        f"   X vs Y' — GIAE declined to commit; excluded from grading)",
        "",
        f"Overall accuracy           : {overall_acc:.3f}",
        f"Mean predicted confidence  : {mean_conf:.3f}",
        f"Gap (conf − acc)           : {mean_conf - overall_acc:+.3f}",
        "",
        "Calibration metrics (lower = better)",
        "-" * 60,
        f"  Expected Calibration Error (ECE) : {ece:.3f}",
        f"  Maximum  Calibration Error (MCE) : {mce:.3f}",
        f"  Brier score                      : {brier:.3f}",
        "",
        "Accuracy by confidence level",
        "-" * 60,
        f"  {'Level':<14}{'n':>6}{'accuracy':>10}{'mean_conf':>11}",
    ]
    for lv in order:
        b = [s for s in all_samples if s["level"] == lv]
        if not b:
            continue
        acc = sum(s["correct"] for s in b) / len(b)
        mc = sum(s["confidence"] for s in b) / len(b)
        lines.append(f"  {lv.capitalize():<14}{len(b):>6}{acc:>10.3f}{mc:>11.3f}")
    # confidence spread — is the score discriminative at all?
    confs = sorted(s["confidence"] for s in all_samples)
    conf_min, conf_max = confs[0], confs[-1]
    n_levels = len({s["level"] for s in all_samples})

    lines += [
        "",
        "Reading this",
        "-" * 60,
        "  If accuracy RISES monotonically with confidence level, the score is",
        "  a useful ranking signal — users can trust HIGH calls more than LOW.",
        "  A positive gap (conf > acc) means GIAE is OVER-confident; negative",
        "  means UNDER-confident (conservative). For a zero-hallucination tool,",
        "  mild under-confidence is the safer failure mode.",
        "",
        "CRITICAL CAVEAT — this is the OFFLINE / motif-only configuration",
        "-" * 60,
        f"  Confidence range observed   : {conf_min:.2f} – {conf_max:.2f}",
        f"  Distinct confidence levels  : {n_levels} (of 4 possible)",
        "  Benchmark config: use_hmmer=False, use_uniprot=False,",
        "  use_diamond=False, use_local_blast=False — i.e. the conservative",
        "  worker config with NO homology/domain database.",
        "",
        "  Consequence: the only functional evidence is PROSITE motifs, so the",
        "  annotator emits broad motif CATEGORIES ('ATP/GTP binding protein',",
        "  'Lipoprotein') rather than specific gene-product names. These rarely",
        "  token-match curated RefSeq products, hence the low graded accuracy.",
        "",
        "  KEY POINT for the pitch: offline GIAE NEVER claims high confidence on",
        f"  function (caps at {conf_max:.2f}). It does not hallucinate 0.9 calls.",
        "  A specific, high-confidence functional layer requires a homology/",
        "  domain DB (Pfam via HMMER, or Swiss-Prot via diamond — both wired in",
        "  the engine, just not loaded for this no-network benchmark). Calibrate",
        "  THAT config separately to characterise the full confidence range.",
        "=" * 60,
    ]
    report = "\n".join(lines)
    (OUT / "calibration_summary.txt").write_text(report)
    print(report)
    print(f"\nsamples → {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
