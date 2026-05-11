# Architecture

How GIAE actually works.

This doc covers the data flow, the evidence model, the hypothesis tier
system, and the confidence math. If you want to extend GIAE or
understand why a particular gene got the score it got, start here.

---

## Pipeline overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Parsing                                                          │
│    GenBank or FASTA → Genome (with sequence + optional pre-annot.) │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. Gene discovery                                                   │
│    a) Curator-supplied genes (GenBank only)                         │
│    b) pyrodigal ORF prediction (always, when density < 0.3 g/kb)   │
│    c) ShortOrfRescue — RBS + codon-usage gate (default on)         │
│    d) NestedOrfFinder — phage_mode opt-in                           │
│    e) Aragorn (tRNA) + Barrnap (rRNA) — when binaries present      │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Evidence extraction (per gene, in parallel)                      │
│    • PROSITE motif scan                                             │
│    • Pfam / HMMER domain hits                                       │
│    • Diamond / BLAST+ homology                                      │
│    • UniProt + InterPro / EBI HMMER (online, cached)                │
│    • ESM-2 protein language model (optional)                        │
│    • GenBank curator annotations (product / function / note)        │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. Aggregation                                                      │
│    EvidenceAggregator groups by type, computes diversity metrics    │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. Hypothesis generation                                            │
│    HypothesisGenerator runs five tiers in priority order:           │
│      Tier 1: GenBank annotation                                     │
│      Tier 2: Homology (BLAST / UniProt / GenBank product)           │
│      Tier 3: Domain hits (Pfam)                                     │
│      Tier 4: Motifs (PROSITE) — only if Tiers 1-3 produced nothing │
│      Tier 5: Combined-evidence boost when ≥2 evidence types agree   │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. Confidence scoring + conflict detection                          │
│    ConfidenceScorer applies bonuses/penalties; ConflictResolver     │
│    flags disagreements between hypotheses                           │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 7. Functional annotation                                            │
│    FunctionalAnnotator adds COG / GO / normalised product           │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 8. Novelty scoring                                                  │
│    NoveltyScorer ranks unannotated genes for research priority      │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
                     Interpretation per gene
                     + GenomeInterpretationSummary
                     + NovelGeneReport
```

---

## The evidence model

The whole system is built around one idea: **evidence is typed,
weighted, and traceable**. Every observation gets wrapped in an
`Evidence` object before it can influence a prediction.

```python
Evidence(
    evidence_type=EvidenceType.DOMAIN_HIT,
    gene_id=gene.id,
    description="Pfam PF01381 (HTH_3, e-value 1.2e-9)",
    confidence=0.94,
    raw_data={"pfam_id": "PF01381", "evalue": 1.2e-9, ...},
    provenance=EvidenceProvenance(
        tool_name="pyhmmer",
        tool_version="0.10.15",
        database="Pfam-A 36.0",
    ),
)
```

Every evidence object carries:

- **Type** — what kind of signal it is
- **Confidence** — 0.0 to 1.0, computed by the producing tool
- **Description** — human-readable for reasoning chains
- **Raw data** — the underlying numbers (e-values, identities, scores)
- **Provenance** — what produced it, what version, what database

Evidence objects are the **atoms**. Hypotheses, confidence scores, and
reasoning chains are all derived from them.

---

## The hypothesis tier system

`HypothesisGenerator.generate()` runs five tiers in priority order. The
ordering encodes *epistemic strength* — curator-supplied annotations
are stronger evidence than motif hits.

### Tier 1 — GenBank annotation (`SEQUENCE_FEATURE`)

When a GenBank file already has a `/product`, `/function`, or `/note`
qualifier, those are the most authoritative annotations available.
GIAE wraps them as evidence and generates hypotheses with reasoning
text like:

> *"GenBank product annotation: DNA polymerase III subunit alpha.
> Curator-assigned product name from the submitted GenBank record."*

These get the highest base confidence (0.85 for product, 0.80 for
function, 0.60 for note).

### Tier 2 — Homology (`BLAST_HOMOLOGY`)

UniProt hits, Diamond hits, BLAST+ hits. The reasoning chain captures
the underlying score:

> *"BLAST homology hit: P03034 (Lambda phage repressor CI, 96% identity).
> E-value 2.1e-87 indicates near-certain homology."*

Top 3 hits per gene generate hypotheses.

### Tier 3 — Domain hits (`DOMAIN_HIT`)

Pfam / HMMER profile HMM matches. More specific than motifs because
each Pfam domain maps to a well-characterised protein family.

### Tier 4 — Motifs (`MOTIF_MATCH`)

PROSITE patterns. Treated as **supporting** evidence, not a primary
source. Motif-only hypotheses are silently discarded if any
higher-tier hypothesis exists. When no other evidence is available,
they're capped at confidence 0.45 (LOW) so they don't masquerade as
moderate signals.

### Tier 5 — Combined-evidence boost

When ≥ 2 distinct evidence types converge on the same function, a
combined hypothesis gets a bonus. This is the central
*convergence-equals-confidence* rule.

---

## Confidence model

Confidence is a calibrated number, not a vibe.

### Base score

The base score for a hypothesis comes from the strongest single
evidence type backing it:

| Evidence type | Typical base score |
|---|---|
| GenBank product | 0.85 |
| UniProt Swiss-Prot reviewed | 0.90 |
| Pfam HMMER domain hit | 0.85 – 0.95 (e-value-driven) |
| Diamond / BLAST hit | 0.70 – 0.95 (identity-driven) |
| GenBank function | 0.80 |
| GenBank note | 0.60 |
| PROSITE motif | 0.50 – 0.70 |

### Adjustments

The `ConfidenceScorer` then applies explicit adjustments:

| Condition | Adjustment | Why |
|---|---|---|
| ≥ 2 evidence types agree | **+0.10** | Convergence is meaningful |
| Strong homology (≥ 80% identity) | **+0.05** | Direct sequence match |
| High-confidence Pfam domain | **+0.08** | Domain-level certainty |
| Limited evidence (< 2 sources) | **−0.10** | Single signals are weaker |
| Hypothetical homolog | **−0.15** | "Hypothetical X" isn't a real assignment |
| Single-evidence motif-only | **cap at 0.85** | One PROSITE hit ≠ HIGH |
| Conflict detected | **× 0.80** | Disagreement reduces certainty |

Every adjustment is recorded in the `reasoning_chain` so the user can
audit *why* the score is what it is.

### Levels

The numerical score maps to a named level:

| Score | Level |
|---|---|
| ≥ 0.80 | `HIGH` |
| 0.50 – 0.79 | `MODERATE` |
| 0.30 – 0.49 | `LOW` |
| 0.05 – 0.29 | `SPECULATIVE` |
| < 0.05 | `NONE` (dark matter) |

---

## Conflict detection

When two hypotheses for the same gene have:

- **Different categories** (e.g. one says "transcription", the other
  says "metabolism"), and
- **Comparable confidence** (within `conflict_threshold`, default 0.15)

…the `ConflictResolver` flags it as a conflict. Conflicts result in:

1. A penalty (×0.80) on the winning hypothesis
2. An entry in `interpretation.uncertainty_sources`
3. The losing hypothesis kept as a `competing_hypothesis`

Conflicts don't get hidden. They're surfaced explicitly.

---

## ORF discovery layers

Modern GIAE uses three complementary ORF finders, each tuned for
different cases:

### Layer 1 — pyrodigal

The Python port of Prodigal. State-of-the-art ORF prediction for
bacteria, archaea, and phages. Default on. Penalises overlaps in its
probabilistic model — meaning it won't find genes nested inside other
genes.

### Layer 2 — `ShortOrfRescue`

Recovers genes pyrodigal drops. Two-signal evidence gate:

- **Tight Shine-Dalgarno detection** — window −14 to −4 bp upstream of
  the start codon, motifs `AGGAGG`, `GGAGG`, `AGGAG` only (5–6 bp
  cores; shorter motifs produce too many random hits)
- **Codon usage similarity** — average frequency under the genome's
  codon distribution, threshold 0.012

Both signals must pass. ATG-only starts (no GTG/TTG) to keep the false
positive rate low. Default on.

### Layer 3 — `NestedOrfFinder` (phage mode)

Recovers overlapping / nested genes pyrodigal won't touch. Used only
when `phage_mode=True` (or `--phage`). Strictly tighter gate than
ShortOrfRescue:

- **Position-weighted Shine-Dalgarno** — peak at −9 bp, falling to 0
  at −3 and −15 bp. AGGAGG at peak position scores 1.0; GGAGG at peak
  scores 0.75; anything weaker is rejected.
- **Codon usage** — same as Layer 2 but with a 0.012 threshold
- **Boundary margin** — ORFs whose start AND end are within 9 bp of
  an existing gene's boundary (on the same strand) are treated as
  near-duplicates and rejected.
- **Min length** — 50 aa (vs. 20 aa for Layer 2; nested scanning
  produces many spurious candidates per genome).

This finds genes like λ rIIB inside rIIA, but **not** PhiX174's
overlapping genes. PhiX174 uses translational coupling instead of
canonical SD signals — that's a documented biological feature of
compact phages, not a tunable problem.

---

## Functional annotation depth

After the `Interpretation` is built, the `FunctionalAnnotator` enriches
it with three more pieces of metadata:

### 1. Normalised product name

`ProductNormalizer` strips `"putative"`, `"probable"`, `"[partial]"`,
EC suffixes; collapses whitespace; preserves placeholder strings
(`"hypothetical protein"`) untouched.

### 2. COG category

Two paths, in priority order:

1. **Pfam → COG lookup.** If supporting evidence carries a Pfam
   accession (PFxxxxx), the bundled
   [`data/functional/pfam_categories.tsv`](https://github.com/Ayo-Cyber/GIAE/blob/main/data/functional/pfam_categories.tsv)
   gives a direct answer. Marked `cog_source = "pfam"`.

2. **Category → COG fallback.** If no Pfam ID is available, the
   hypothesis's GIAE keyword category (replication, transcription,
   …) maps to its closest COG letter. Marked
   `cog_source = "inferred"`.

### 3. GO terms

Pulled from the same Pfam table when `pfam_id` is present. Empty
otherwise.

The bundled table covers ~100 common phage and bacterial Pfam IDs.
For full Pfam coverage, point `FunctionalAnnotator` at the complete
Pfam2GO mapping (~5,000 entries, ~2 MB).

---

## Novelty scoring

Genes that *can't* be interpreted are themselves a useful signal.
`NoveltyScorer` produces a `NovelGeneReport` with three categories:

| Category | Definition |
|---|---|
| `dark_matter` | No evidence from any source |
| `weak_signal` | Some evidence, but final confidence < 0.35 |
| `conflicting` | Multiple sources disagree (conflict flagged in interpretation) |

Each candidate is ranked by length, conservation potential, and
genomic context. The output includes suggested experiments scaled to
protein length and category.

This turns "hypothetical protein" — usually the end of the line — into
a research priority list.

---

## Reasoning chain

Every `Interpretation` carries a `reasoning_chain: list[str]` that
captures *why* the prediction is what it is. A typical chain:

```text
1. Pfam HTH_3 hit (e-value 1.2e-9) is diagnostic for transcriptional regulators
2. UniProt P03034 is a Swiss-Prot reviewed entry for the same gene in the same organism
3. Three independent evidence types converge on the same function
4. Conflict-free; no competing hypothesis above threshold
5. Functional category resolved to COG K (Transcription) via Pfam mapping
```

Reasoning chains are not generated by an LLM. They're built
deterministically from the evidence aggregation, hypothesis tier, and
confidence-adjustment steps. Same input → same chain, byte-for-byte.

---

## Concurrency model

### CLI

`Interpreter.interpret_genome` runs gene-level interpretation in a
`ThreadPoolExecutor` (default 8 workers, capped at `len(genome.genes)`).
Each gene is independent at the per-gene stage, so threading scales
linearly until the network or CPU saturates.

### Worker

The Celery worker uses the **threads** pool, not prefork — `pyhmmer`
and `torch` are C extensions that aren't fork-safe. Each thread runs
one full `Interpreter.interpret_genome` call.

Two pre-built `Interpreter` instances (default + phage mode) are
shared across all jobs to avoid the per-job cost of parsing PROSITE
patterns and loading plugins.

---

## Where to look in the code

| Concept | File |
|---|---|
| Pipeline orchestrator | [`src/giae/engine/interpreter.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/interpreter.py) |
| Evidence aggregation | [`src/giae/engine/aggregator.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/aggregator.py) |
| Hypothesis generation (tier system) | [`src/giae/engine/hypothesis.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/hypothesis.py) |
| Confidence scoring | [`src/giae/engine/confidence.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/confidence.py) |
| Conflict detection | [`src/giae/engine/conflict.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/conflict.py) |
| ORF rescue + nested | [`src/giae/analysis/short_orf_rescue.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/analysis/short_orf_rescue.py), [`nested_orf_finder.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/analysis/nested_orf_finder.py) |
| Functional annotation | [`src/giae/analysis/functional_annotator.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/analysis/functional_annotator.py) |
| Novelty scoring | [`src/giae/engine/novelty.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/novelty.py) |

If you want to change scoring or add a new evidence tier, that's the
map.
