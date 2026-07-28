# GIAE Benchmark — Methodology, Results, and Honest Caveats

This document is the scientific record behind the GIAE vs Bakta benchmark and
the confidence-calibration study. It is written to be **reviewer-proof**: it
states plainly what the numbers mean, what can be claimed, and — just as
important — what **cannot**.

## TL;DR (the claims that survive scrutiny)

1. **Gene finding: GIAE is on par with Bakta — by construction, not by novelty.**
   All three tools call genes with **pyrodigal (Prodigal)**. Over **52 genomes**
   (41 phages + 11 bacteria across ~7 phyla): mean F1 GIAE **0.871**, Bakta
   **0.850**, raw Prodigal **0.878**. GIAE vs Bakta Wilcoxon **p = 0.051**
   (borderline — GIAE trends better but ≈ Bakta). The tight cluster is the
   *expected* result of a shared predictor. Do **not** claim "better gene
   finding."
2. **A three-tool comparison sharpens the point.** GIAE is statistically
   indistinguishable from raw Prodigal (p = 0.36) — it *preserves* Prodigal-level
   gene finding. **Bakta is significantly *worse* than raw Prodigal (p = 0.011)**
   — its db-light post-filtering degrades gene finding (chiefly the Mycoplasma
   over-prediction). So GIAE's value is not a better caller; it's the layer on
   top: (a) phage-aware nested/short-ORF rescue, (b) an auditable evidence +
   reasoning layer, (c) a **calibrated confidence score**, and (d) zero-config
   robustness (auto genetic-code selection).
3. **Confidence is a genuine — if modest — ranking signal** (AUC 0.59 raw /
   0.64 synonym-adjusted). HIGH-confidence functional calls are correct ≥ 61 %
   of the time (a lower bound; see §4), significantly more than Moderate/Low
   (non-overlapping 95 % CIs).
4. **Speed**: GIAE's offline config annotates a phage in < 1 s vs Bakta's
   ~7.5 s. With homology enabled (batched Diamond), it is seconds per genome.

## 1. What was measured

Three separate things, against the **same** ground truth (curated RefSeq CDS
coordinates + `/product` names):

| Axis | Metric | Config used |
|---|---|---|
| Gene finding | precision / recall / F1, reciprocal overlap ≥ 0.5, same strand | GIAE **offline** vs Bakta db-light |
| Functional accuracy | token-overlap agreement of product name for coord-matched genes | offline (motif) and homology (Diamond) |
| Confidence calibration | accuracy vs confidence for graded functional calls | GIAE **homology** (full Swiss-Prot) |

**Config clarity matters.** The headline F1 uses GIAE *offline* (no homology
DB). The calibration uses GIAE *homology* (Diamond + full Swiss-Prot). These
are different runs; never quote an F1 number and a calibration number as if
from one run.

## 2. No truth leak (verified)

For every genome the harness parses the RefSeq record, captures truth
coordinates/products, then **clears `genome.genes` and re-predicts de novo**
from the DNA sequence alone. Verified in code: with genes cleared,
`interpret_genome` sets `needs_orfs = True` and runs
`ORFFinder.find_orfs(sequence)` (pyrodigal) on the sequence; the
overlap-with-existing-annotation filter is skipped because there are no
existing genes. GIAE never sees the curated annotation before predicting.

## 3. The central caveat — both tools use Prodigal

`GIAE.ORFFinder` → `pyrodigal.GeneFinder(meta=True)`.
`bakta.features.cds` → `pyrodigal.GeneFinder(...)` (single-genome *trained*
mode for genomes ≥ 20 kb, meta mode below that).

Consequences:

- **Gene-finding parity is not a discovery.** It is what you get from the same
  algorithm. The honest framing: *"GIAE matches gold-standard tools on gene
  finding because it uses the same gold-standard predictor, and adds
  phage-aware rescue on top."*
- **The Mycoplasma outlier (GIAE F1 0.92 vs Bakta 0.42) is a translation-table
  / Prodigal-mode difference, not a GIAE algorithmic win — but it is a genuine
  zero-config robustness advantage.** Mycoplasma uses **genetic code 4**
  (UGA = Trp, not stop). GIAE runs pyrodigal **meta mode**, which scores the
  sequence against pre-trained profiles spanning multiple GC contents *and*
  translation tables and auto-selects the best; verified — it picks **table 4
  for all 494 M. genitalium genes**, so it calls genes correctly with no
  configuration. Our Bakta run used the **default table 11** (we did not pass
  `--translation-table 4`), so it self-trained a code-11 model on a code-4
  genome and over-predicted (~1.8× too many CDS → many false positives).
  Honest framing: GIAE's default is robust to non-standard genetic codes out
  of the box; **Bakta would likely match if told the correct table.** This is
  a sensible-defaults win, not a claim about GIAE's core algorithm — and it is
  a property of pyrodigal meta mode, which GIAE wraps rather than invented.

## 4. Functional accuracy is a LOWER BOUND

Graded by token overlap between predicted and curated product names. This
under-counts correct calls whenever the two databases use different
conventions for the same protein. The differences are systematic:

- aminoacyl-tRNA synthetases: `serine--tRNA ligase` (UniProt) = `seryl-tRNA
  synthetase` (RefSeq)
- ribosomal proteins: `small ribosomal subunit protein bS6` = `30S ribosomal
  protein S6`
- synthase/synthetase, capsid/head, portal/connector, …

`product_synonyms.py` normalises these by **rule** (not a cherry-picked
lookup) and every recovered call is attributed:

| Config | Accuracy | Notes |
|---|---|---|
| Raw token overlap | 0.486 | strict lower bound |
| Synonym-adjusted | 0.536 | +405 calls: 297 ribosomal, 84 tRNA-synthetase, 24 curated |
| True accuracy | > 0.536 | expert grading would recover residual phage-specific synonyms |

So the honest statement is a **range**: measured functional accuracy is
0.49–0.54, and the true value is higher but unquantified without expert
grading.

## 5. Confidence calibration (n = 8 026 graded calls, all 35 genomes)

- **Discrimination (AUC)** = 0.586 raw / 0.636 adjusted. Confidence ranks a
  correct call above an incorrect one ~64 % of the time — a **modest** signal.
- **Reliability** (synonym-adjusted, 95 % Wilson CI):

  | Level | n | accuracy | 95 % CI | mean conf |
  |---|---|---|---|---|
  | High | 5 329 | 0.609 | [0.595, 0.622] | 0.973 |
  | Moderate | 1 665 | 0.434 | [0.411, 0.458] | 0.656 |
  | Low | 935 | 0.325 | [0.296, 0.356] | 0.397 |
  | Speculative | 97 | 0.340 | [0.254, 0.439] | 0.249 |

- **What holds**: HIGH is reliably separated from Moderate/Low (CIs don't
  overlap). **What doesn't**: Speculative (n = 97) can't be ranked against Low;
  the apparent non-monotonicity at the bottom is small-sample noise.
- **Over-confidence — measured, then fixed.** Raw mean confidence (0.83) far
  exceeded adjusted accuracy (0.54): raw ECE 0.30. A post-hoc **isotonic**
  recalibration (chosen over Platt by lower CV Brier), evaluated with 5-fold
  stratified cross-validation so the gain is **out-of-sample**, collapses this:
  **ECE 0.301 → 0.004, Brier 0.336 → 0.232**, and mean calibrated probability
  (0.535) now equals observed accuracy (0.535). The mapping is exported to
  `calibration_mapping.json` (portable piecewise-linear knots; the engine
  interpolates with no sklearn at runtime). Because the target label is a
  lower-bound accuracy, the calibrated probability is **conservative** — it
  will not over-state correctness. So the honest post-fix claim is: *"GIAE's
  confidence, after isotonic recalibration, is a calibrated probability of
  correctness (out-of-sample ECE 0.004)."* See `recalibrate.py`.

## 6. Statistical rigor & limitations

- **Gene-finding significance (n = 52)**: Wilcoxon signed-rank on paired F1,
  GIAE vs Bakta p = 0.051 (borderline, n.s. at α = 0.05); GIAE vs raw Prodigal
  p = 0.36 (indistinguishable); Bakta vs raw Prodigal p = 0.011 (Bakta
  significantly worse). Win/tie/loss GIAE-vs-Bakta: 20 / 22 / 10.
- **Three tools, one predictor**: raw pyrodigal is included as a baseline
  (`--prodigal`) precisely because GIAE and Bakta both wrap it. It shows the
  db-light post-processing in Bakta *costs* gene-finding F1, while GIAE's rescue
  is F1-neutral vs vanilla Prodigal (it trades a little precision for recall on
  nested-gene phages). Prokka/DFAST were not run (require a bioconda env).
- **Subsets**: 41 phages + 11 bacteria (6 of 58 fetched genomes skipped —
  CON records with no embedded sequence, or selenocysteine `U`). Bacteria-only
  Wilcoxon (n = 11) is still lightly powered.
- **Lenient matching**: reciprocal overlap ≥ 0.5 counts a gene as found even if
  boundaries differ; it does not require exact stop-codon (frame) agreement.
  This inflates *both* tools equally, so the *comparison* is fair, but absolute
  F1 would drop under strict boundary matching.
- **db-light**: Bakta ran with the light database. Its functional annotation
  (not its gene finding, which is pyrodigal regardless) could improve with the
  full DB. We did not compare functional layers head-to-head.

## 7. Claims table — say this, not that

| ✅ Defensible | ❌ Overclaim |
|---|---|
| "Matches Bakta on gene finding (both use Prodigal); adds phage-aware rescue" | "GIAE's gene finder beats Bakta" |
| "30× faster than Bakta on phages (offline config)" | "30× faster in all configs" (homology adds Diamond cost) |
| "HIGH-confidence functional calls are right ≥ 61 % (lower bound)" | "GIAE is 61 % accurate at annotation" |
| "After isotonic recalibration, confidence is a calibrated probability (out-of-sample ECE 0.004); raw score is a modest ranking signal (AUC 0.64)" | "GIAE's raw confidence is well-calibrated" (raw ECE was 0.30) |
| "On code-4 Mycoplasma, GIAE's default auto-detects the genetic code; Bakta's default (table 11) does not — a zero-config robustness win" | "GIAE beats Bakta 2× on Mycoplasma" (implies algorithmic superiority) |

## 8. Reproduce

```bash
# gene-finding benchmark (offline GIAE vs Bakta db-light)
PYTHONPATH=src .venv/bin/python post_assets/benchmark_figure.py --set all
# figures + Wilcoxon + outliers
PYTHONPATH=src .venv/bin/python post_assets/pitch_figures.py
# homology confidence calibration (needs ~/.giae/diamond/swissprot.dmnd)
PYTHONPATH=src:post_assets .venv/bin/python post_assets/calibration.py --homology --set all
# synonym-adjusted re-grade + AUC/CIs
PYTHONPATH=src:post_assets .venv/bin/python post_assets/calibration_synonym.py
# post-hoc recalibration (isotonic/Platt, 5-fold CV) + portable mapping export
PYTHONPATH=src:post_assets .venv/bin/python post_assets/recalibrate.py
```
