# GIAE Benchmark — Methodology, Results, and Honest Caveats

This document is the scientific record behind the GIAE vs Bakta benchmark and
the confidence-calibration study. It is written to be **reviewer-proof**: it
states plainly what the numbers mean, what can be claimed, and — just as
important — what **cannot**.

## TL;DR (the claims that survive scrutiny)

1. **Gene finding: GIAE is on par with Bakta — by construction, not by novelty.**
   Both tools call genes with **pyrodigal (Prodigal)**. Near-identical F1
   (GIAE 0.850 vs Bakta 0.827 over 35 genomes, Wilcoxon p = 0.11, n.s.) is the
   *expected* result of wrapping the same predictor. Do **not** claim "better
   gene finding."
2. **GIAE's genuine engineering contributions** are (a) phage-aware nested /
   short-ORF rescue that recovers overlapping genes standard Prodigal drops,
   (b) an auditable evidence + reasoning layer, and (c) a **calibrated
   confidence score**.
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
- **Over-confidence**: mean confidence (0.83) exceeds adjusted accuracy (0.54),
  so raw confidence over-states correctness. But (i) accuracy here is a lower
  bound, and (ii) HIGH-confidence genuinely means "usually right." A calibrated
  post-hoc mapping (isotonic/Platt) would tighten this — future work.

## 6. Statistical rigor & limitations

- **Gene-finding significance**: Wilcoxon signed-rank on paired F1, p = 0.11
  (all 35), not significant → "statistically equivalent," honestly stated.
- **Underpowered subsets**: only 6 bacteria (2 skipped for selenocysteine `U`,
  1 phage skipped as a CON record with no embedded sequence). Bacteria-only
  Wilcoxon is not meaningful at n = 6.
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
| "Confidence is a modest ranking signal, AUC 0.64" | "GIAE's confidence is well-calibrated" |
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
```
