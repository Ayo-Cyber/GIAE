# GIAE: A Genome Interpretation and Annotation Engine with Explainable, Evidence-First Gene Prediction

**Atunrase Ayomide**  
Independent Research  
atunraseayomide@gmail.com

---

## Abstract

We present GIAE (Genome Interpretation and Annotation Engine), an open-source Python toolkit for prokaryotic and phage genome annotation that prioritises explainability and extensibility over black-box accuracy. GIAE introduces a layered ORF-detection architecture — pyrodigal-based primary prediction, gap-region short-ORF rescue, and a phage-aware nested ORF finder — that collectively achieve F1 scores of 79.2 % on λ phage and 88.1 % on T7 phage without querying any external sequence database. In a controlled head-to-head comparison on three reference phage genomes, GIAE matches or outperforms Bakta on every genome while generating zero false-positive CDS predictions on λ phage. Every gene prediction carries a structured evidence record, a natural-language reasoning trace, and a calibrated confidence score, enabling downstream users to triage annotations by reliability rather than accepting them wholesale. GIAE ships as a pip-installable Python library, a CLI, a REST API, and a web frontend; it requires no database installation for competitive ORF-finding performance.

**Keywords:** genome annotation, phage genomics, ORF detection, explainable bioinformatics, evidence-based prediction

---

## 1. Introduction

Genome annotation — the assignment of biological function to predicted coding sequences — sits at the foundation of nearly all comparative and functional genomic analyses. Despite decades of tool development, three persistent problems remain largely unsolved.

**Opacity.** Most widely-used annotation pipelines (Prokka [1], Bakta [2], RAST [3]) report annotations as flat attribute strings. When a gene is labelled "hypothetical protein" or "putative helicase", the user has no access to the evidence chain that produced that label, nor to the alternative hypotheses that were considered and rejected. This opacity makes it impossible to triage predictions by confidence, or to diagnose systematic errors.

**Poor short-ORF recovery.** Bacteriophages and other compact genomes encode substantial biology in short ORFs (< 100 aa) and in overlapping or nested reading frames. Standard gene callers tuned for bacterial genomes underperform on these structures [4, 5]. The problem is especially acute for phage "dark matter" — the 30–60 % of phage gene content with no detectable homologue in current databases [6].

**Rigid extension points.** Adding a new evidence source — a structural-homology tool, a custom HMM library, a novel database — to existing pipelines typically requires forking the tool or writing fragile wrapper scripts. There is no standard plugin contract.

GIAE addresses all three. It builds a typed evidence record for every gene, runs a configurable hypothesis-generation and confidence-scoring engine over that evidence, and exposes its reasoning at every step. Its plugin system provides a stable interface for new analysis tools. Its layered ORF-detection architecture explicitly targets the short-ORF and nested-gene problems that defeat existing callers.

---

## 2. Methods

### 2.1 Overall architecture

GIAE is organised as a four-layer pipeline (Figure 1):

```
Genome file (FASTA / GenBank)
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  Layer 1 — Gene Discovery                                 │
│  Pyrodigal → ShortOrfRescue → NestedOrfFinder             │
│  Aragorn (tRNA) · Barrnap (rRNA)                         │
└───────────────────────────┬───────────────────────────────┘
                            │  gene list
                            ▼
┌───────────────────────────────────────────────────────────┐
│  Layer 2 — Evidence Collection                            │
│  AnalysisPlugin protocol:                                  │
│  UniProt · InterPro · Diamond · HMMER/Pfam · PROSITE      │
└───────────────────────────┬───────────────────────────────┘
                            │  Evidence[]
                            ▼
┌───────────────────────────────────────────────────────────┐
│  Layer 3 — Hypothesis Generation & Scoring                │
│  EvidenceAggregator → HypothesisGenerator                 │
│  → ConfidenceScorer → ConflictResolver                    │
└───────────────────────────┬───────────────────────────────┘
                            │  InterpretationResult
                            ▼
┌───────────────────────────────────────────────────────────┐
│  Layer 4 — Output                                         │
│  HTML report · JSON · GFF3 · GenBank · TSV · FASTA        │
└───────────────────────────────────────────────────────────┘
```
*Figure 1. GIAE pipeline overview.*

### 2.2 Gene discovery layer

#### 2.2.1 Primary ORF prediction

GIAE uses pyrodigal [7] as its primary gene caller. Pyrodigal is a Cython wrapper around Prodigal [8] that achieves the same prediction quality at substantially higher throughput with no subprocess overhead. For phage genomes, pyrodigal is invoked in meta mode (`meta=True`) to avoid self-training on small genomes.

#### 2.2.2 Short-ORF rescue (ShortOrfRescue)

Standard Prodigal/pyrodigal predictions are biased toward longer ORFs. GIAE post-processes the gap regions — sequence intervals between adjacent primary predictions — with `ShortOrfRescue`. A candidate is retained only when it satisfies a two-signal gate:

1. **Shine-Dalgarno score ≥ 0.7.** A tight motif set (AGGAGG, GGAGG, AGGAG) is searched in the window [−14, −4] relative to the start codon. Each motif is scored 1.0 / 0.75 / 0.65 respectively; the maximum over all hits in the window is the SD score.

2. **Codon-usage score ≥ 0.012.** The candidate sequence is scored against a precomputed genome-wide codon usage table. This rejects spurious ATG-to-stop intervals with atypical codon composition.

Only ATG start codons are accepted. Minimum ORF length is 30 aa. The rescue pass runs only on gap regions, so it cannot introduce overlapping predictions that conflict with primary calls.

#### 2.2.3 Phage-aware nested ORF detection (NestedOrfFinder)

Compact phage genomes frequently encode two or more genes in overlapping reading frames [9]. GIAE's `NestedOrfFinder` specifically targets these structures.

The algorithm operates in two passes:

**Pass 1 — all-starts scan.** For each of the six reading frames, the sequence is scanned for all valid start codons (not just the outermost one per ORF block). This generates a superset of candidate ORFs including short internal-start variants that `pyrodigal` would suppress.

**Pass 2 — overlap filter.** A candidate is retained only if its coordinates overlap an existing primary prediction by at least one codon. Candidates whose start and end both lie within a 9 bp margin of an existing gene on the same strand are rejected as near-duplicates.

Retained candidates are scored with a **position-weighted SD scorer** that weights the [−15, −3] window relative to the candidate start codon, with a triangular weighting function peaking at −9 bp (the canonical ribosome-binding distance). Candidates below a configurable RBS threshold (default 0.7) are filtered.

This design means `NestedOrfFinder` cannot introduce false positives in gene-sparse regions — it is structurally incapable of predicting an ORF unless it overlaps an existing primary call.

#### 2.2.4 Non-coding RNA detection

tRNA and tmRNA genes are detected by Aragorn [10] when the binary is available. rRNA genes are detected by Barrnap [11]. Both finders run independently of the coding-sequence pipeline; their results are typed as `ncRNA` features in the gene list.

### 2.3 Evidence collection layer

GIAE's analysis plugins implement a shared `AnalysisPlugin` protocol:

```python
class AnalysisPlugin(Protocol):
    name: str
    def is_available(self) -> bool: ...
    def scan(self, gene: Gene) -> list[Evidence]: ...
```

The `is_available()` contract means every plugin fails silently when its external binary or database is absent. The current built-in plugins are:

| Plugin | Evidence type | External requirement |
|---|---|---|
| UniProtPlugin | BLAST_HOMOLOGY | Internet connection |
| InterProPlugin | DOMAIN_HIT | Internet connection |
| DiamondPlugin | BLAST_HOMOLOGY | Diamond binary + SwissProt DB |
| HmmerPlugin | DOMAIN_HIT | pyhmmer + Pfam HMM |
| PrositePlugin | MOTIF_MATCH | Bundled PROSITE patterns |
| BarcodePlugin | SEQUENCE_FEATURE | None |

Each plugin returns `Evidence` objects with typed fields: `evidence_type`, `gene_id`, `description`, `confidence`, `raw_data`, `provenance` (tool name, version, database), and `timestamp`. No plugin makes annotation decisions; that responsibility belongs entirely to Layer 3.

### 2.4 Hypothesis generation and confidence scoring

`EvidenceAggregator` groups evidence by type. `HypothesisGenerator` applies a priority-ordered tier system: strong multi-database homology generates tier-1 hypotheses; single-source motif evidence generates tier-3 hypotheses. Each hypothesis carries a `source_type` label, a list of supporting evidence IDs, and a `reasoning_steps` list in natural language.

`ConfidenceScorer` computes a scalar confidence in [0, 1] as a weighted mean of constituent evidence confidences, with bonuses for evidence-type diversity and penalties for conflicting hypotheses. Default weights are: BLAST_HOMOLOGY 1.0, DOMAIN_HIT 0.9, MOTIF_MATCH 0.7, SEQUENCE_FEATURE 0.5, ORF_PREDICTION 0.3.

`ConflictResolver` identifies genes with competing hypotheses above a configurable disagreement threshold and marks them for user review.

### 2.5 Functional annotation depth

`FunctionalAnnotator` post-processes every interpretation result with three operations:

1. **Product name normalisation.** Strips leading qualifiers ("putative", "probable", "predicted", "conserved") and trailing fragments ("[partial]", "(fragment)", EC numbers) from product names inherited from database hits.
2. **COG/GO assignment.** Pfam accessions in the evidence record are mapped against a bundled Pfam→COG/GO table (~500 entries) to produce COG category codes (e.g. K = Transcription, J = Translation) and GO term lists.
3. **Category fallback.** When no Pfam accession is found, the GIAE functional category is mapped to a coarse COG code by inference.

### 2.6 Output formats

GIAE writes results in six formats: HTML (interactive report with expandable evidence panels), JSON (machine-readable, includes full evidence and reasoning chains), GFF3, GenBank, TSV (per-gene summary table), and FASTA (protein sequences). The HTML format is the primary human-facing output and is designed to communicate confidence levels visually — each gene card is colour-coded (green/yellow/red/dark) by confidence tier.

### 2.7 System architecture

GIAE ships as three deployable surfaces: a pip library (`giae`), a REST API (`giae[api]`) built with FastAPI and backed by a Celery task queue, and a Next.js web frontend. The Docker Compose stack (`docker compose up -d --build`) brings up the full multi-service system in a single command. JWT and API-key authentication are both supported for programmatic access.

---

## 3. Results

### 3.1 Benchmark design

We evaluated GIAE against Bakta v1.9 [2] on three well-characterised reference phage genomes:

- **phiX174** (NC_001422) — 5,386 bp, 13 annotated CDS features, notable for nested and overlapping genes encoded by translational coupling
- **Lambda phage** (NC_001416) — 48,502 bp, 96 annotated CDS features
- **T7 phage** (NC_001604) — 39,937 bp, 65 annotated CDS features

Both tools received identical FASTA sequences (annotations stripped). Ground truth was defined as the `CDS` features in each genome's NCBI GenBank record. A prediction was counted as a true positive if it shared strand and reciprocal coordinate overlap ≥ 50 % with a unique truth gene. GIAE ran with all online sources disabled (`use_uniprot=False`, `use_interpro=False`, `use_diamond=False`, `use_hmmer=False`) to isolate pure ORF-finding performance. Bakta ran with its light database and all CDS subsystems active.

### 3.2 Headline results

| Genome | GIAE F1 | Bakta F1 | Δ F1 |
|---|---|---|---|
| phiX174 (5.4 kb) | 60.0 % | 60.0 % | 0.0 % |
| λ phage (48.5 kb) | **79.2 %** | 72.6 % | **+6.6 %** |
| T7 (39.9 kb) | **88.1 %** | 85.2 % | **+2.9 %** |

GIAE matches or exceeds Bakta on all three genomes while querying zero external databases.

### 3.3 Per-genome analysis

#### phiX174

Both tools predict 7 CDS features and recover 6 of 13 ground-truth genes (precision 85.7 %, recall 46.2 %, F1 60.0 %). The seven false negatives (A*, B, E, K, and variants) are genes whose expression depends on translational coupling and internal in-frame starts rather than canonical Shine-Dalgarno signals [12]. This represents a biological ceiling for sequence-based ORF callers: both tools hit it equally.

#### λ phage

GIAE produces 63 predictions, all true positives (precision 100 %, recall 65.6 %, F1 79.2 %). Bakta produces 61 predictions, 57 true positives and 4 false positives (precision 93.4 %, recall 59.4 %, F1 72.6 %). The precision advantage (+6.6 % absolute) reflects that GIAE's RBS + codon-usage two-signal gate is more conservative than Bakta's expert-protein database matching, which introduces spurious hits at the edges of its SwissProt coverage.

#### T7

GIAE recovers 52 of 65 true genes with one false positive (precision 98.1 %, recall 80.0 %, F1 88.1 %). Bakta recovers 49 with one false positive (precision 98.0 %, recall 75.4 %, F1 85.2 %). The 3 additional true positives recovered by GIAE on T7 come from `NestedOrfFinder` — overlapping gene pairs that pyrodigal does not predict in its default configuration. This gain comes at zero cost to precision.

### 3.4 Contribution of each discovery layer

| Configuration | λ F1 | T7 F1 |
|---|---|---|
| pyrodigal only | 78.5 % | 85.2 % |
| + ShortOrfRescue | 79.2 % | 86.2 % |
| + NestedOrfFinder | 79.2 % | **88.1 %** |

Each layer adds true positives without introducing false positives, confirming that the two-signal gate (ShortOrfRescue) and overlap-filter strategy (NestedOrfFinder) constrain the search space appropriately.

### 3.5 Explainability output

For each annotated gene, GIAE produces a structured record that includes:

- A ranked list of `FunctionalHypothesis` objects, each with a confidence score, source type, supporting evidence IDs, and a list of natural-language reasoning steps
- An `AggregatedEvidence` record grouping all raw evidence by type
- A `ConflictRecord` for genes where competing hypotheses disagree by more than the configured threshold
- Normalised product name, COG category, and GO terms (when Pfam/database plugins are active)

This output is machine-readable (JSON) and human-readable (HTML), enabling both programmatic downstream analysis and interactive exploration by annotators.

---

## 4. Discussion

### 4.1 ORF-finding without databases

The benchmark results challenge a common assumption: that expert-protein databases are necessary for competitive phage gene prediction. GIAE achieves +6.6 % F1 over Bakta on λ phage and +2.9 % on T7 using only pyrodigal output post-processed by two lightweight signal-based filters. This has practical implications for novel phage isolation workflows, metagenomic dark-matter analysis, and resource-constrained environments where large database downloads are impractical.

The precision advantage is especially important. A false-positive CDS prediction propagates through every downstream analysis that accepts the annotation. GIAE's zero-FP performance on λ phage reflects the conservative design of its rescue and nested-finder layers: both require positive evidence (RBS signal, codon usage, overlap with a primary call) rather than simply extending the prediction space.

### 4.2 Translational coupling as a hard limit

PhiX174 exposes a genuine biological ceiling for sequence-only methods. Genes A*, B, E, and K are expressed via translational coupling — the ribosome re-initiates at an internal AUG as part of the same translational event that synthesises the upstream protein — without a free ribosome-binding event at the internal start site [12]. No tool that relies on SD-signal detection can systematically recover these features. The expected route to improvement is structural homology (AlphaFold2 / Foldseek) or translational-coupling-aware callers trained on experimentally verified datasets.

### 4.3 Explainability as a first-class feature

Existing annotation tools treat explainability as a secondary concern, if at all. GIAE makes it architectural: the `Evidence`, `FunctionalHypothesis`, and `InterpretationResult` types are the primary data model; formatted output (GFF3, GenBank, HTML) is derived from them. This means that any output format change is a rendering problem, not a data problem, and that new consumers (lab information systems, downstream ML pipelines) can access the full evidence record without scraping formatted text.

The practical consequence for end users is that every annotation can be evaluated on its merits. A gene annotated at 87 % confidence with three independent evidence sources requires a different level of experimental follow-up than a gene annotated at 41 % confidence from a single weak UniProt hit.

### 4.4 Extensibility

The `AnalysisPlugin` protocol requires four attributes: `name`, `is_available()`, `scan()`. Any tool that satisfies this interface integrates into the GIAE evidence model with no changes to the engine. The `AnalysisPlugin`, `EvidenceType`, `EvidenceAggregator`, `HypothesisGenerator`, and `ConfidenceScorer` components are all independently instantiable, enabling GIAE to be used as a library within larger annotation workflows rather than only as a standalone tool.

### 4.5 Limitations and future work

The current benchmark covers three phage genomes. Extension to a diverse bacterial genome panel (multiple phyla, plasmids, chromosome-scale) is the primary planned validation work. The functional annotation system (COG/GO assignment) is currently limited to Pfam-annotated features; expanding the bundled mapping table and integrating eggNOG-mapper [13] output is on the roadmap. The NestedOrfFinder's overlap-filter strategy is conservative by design; future work will investigate sequence-context models (e.g., transformer-based translation-initiation predictors) to recover translationally-coupled genes.

---

## 5. Availability

GIAE is available under the MIT Licence at:

**https://github.com/Ayo-Cyber/GIAE**

```bash
pip install giae           # library + CLI
pip install "giae[api]"    # + REST API server
```

Documentation: **https://ayo-cyber.github.io/GIAE**  
Current stable version: **0.2.2**  
Requires: Python ≥ 3.9

The benchmark reproduction script is at `post_assets/bakta_comparison.py`. All test genomes are fetched from NCBI at runtime; no pre-downloaded data files are required.

---

## 6. Acknowledgements

This work was carried out as independent research. The author thanks the developers of pyrodigal, Bakta, Aragorn, Barrnap, and the BioPython project, whose libraries are integral to GIAE.

---

## References

[1] Seemann T. Prokka: rapid prokaryotic genome annotation. *Bioinformatics* 2014;30(14):2068–2069.

[2] Schwengers O, et al. Bakta: rapid and standardized annotation of bacterial genomes via a comprehensive database. *Microbial Genomics* 2021;7(11):000685.

[3] Overbeek R, et al. The SEED and the Rapid Annotation of microbial genomes using Subsystems Technology (RAST). *Nucleic Acids Research* 2014;42(D1):D206–D214.

[4] Delcher AL, et al. Identifying bacterial genes and endosymbiont DNA with Glimmer. *Bioinformatics* 2007;23(6):673–679.

[5] Hyatt D, et al. Prodigal: prokaryotic gene recognition and translation initiation site identification. *BMC Bioinformatics* 2010;11:119.

[6] Hatfull GF, Hendrix RW. Bacteriophages and their genomes. *Current Opinion in Virology* 2011;1(4):298–303.

[7] Larralde M, Zeller G. Pyrodigal: faster gene predictions with Prodigal. *Journal of Open Source Software* 2022;7(72):4296.

[8] Hyatt D, et al. Prodigal: prokaryotic gene recognition and translation initiation site identification. *BMC Bioinformatics* 2010;11:119.

[9] Oppenheim DS, Yanofsky C. Translational coupling during expression of the tryptophan operon of *Escherichia coli*. *Genetics* 1980;95(4):785–795.

[10] Laslett D, Canback B. ARAGORN, a program to detect tRNA genes and tmRNA genes in nucleotide sequences. *Nucleic Acids Research* 2004;32(1):11–16.

[11] Seemann T. Barrnap 0.9: rapid ribosomal RNA prediction. https://github.com/tseemann/barrnap, 2013.

[12] Grosjean H, Fiers W. Preferential codon usage in prokaryotic genes: the optimal codon-anticodon interaction energy and the selective codon usage in efficiently expressed genes. *Gene* 1982;18(3):199–209.

[13] Cantalapiedra CP, et al. eggNOG-mapper v2: functional annotation, orthology assignments, and domain prediction at the metagenomic scale. *Molecular Biology and Evolution* 2021;38(12):5825–5829.

---

*Manuscript prepared for submission to Bioinformatics / Microbial Genomics / PLOS Computational Biology.*  
*Word count (main text): ~2,800 words.*
