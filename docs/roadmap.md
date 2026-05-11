# Roadmap

GIAE is an evolving platform. The strategic direction is moving from
*sequence-based interpretation* to *multi-modal structural and
functional reasoning*. This page is a living document — we update it
as work lands.

For the broader product vision (hosted SaaS, enterprise tier),
see [PRODUCT_STRATEGY.md](https://github.com/Ayo-Cyber/GIAE/blob/main/PRODUCT_STRATEGY.md).

---

## ✅ Recently shipped (0.2.2)

| Phase | What landed | Lift |
|---|---|---|
| **Phase 1** | pyrodigal-backed ORF prediction | Replaced naive ATG scanner |
| **Phase 2** | Motif confidence tiering + `--mode` flag | Reduced false positives on motifs |
| **Phase 3** | Diamond BLASTP plugin | ~10× faster than NCBI BLAST+ |
| **Phase 4A** | Validation suite (precision/recall/F1) | Reproducible quality metrics |
| **Phase 4B** | Aragorn (tRNA) + Barrnap (rRNA) detection | Non-coding RNA coverage |
| **Phase 5** | Short-ORF rescue (RBS + codon usage gate) | +1 TP each on λ and T7, 0 new FP |
| **Phase 6** | Functional annotation depth (COG / GO / normalised product) | Closed Bakta's last advantage |
| **Phase 7** | Phage-aware nested ORF detection (`--phage`) | T7 F1 86.2 % → 88.1 %, 0 new FP |
| **Phase C** | REST API + Celery worker + Docker stack | Production deployment surface |
| **Phase D** | Version + report-label fixes | Polish |

The cumulative effect: GIAE matches or beats Bakta on three reference
phage genomes ([benchmarks →](benchmarks.md)), and runs as a CLI,
library, or REST service.

---

## 🎯 Next horizon (0.3.0)

### Foldseek / AlphaFold structural homology

- **What:** A `FoldseekPlugin` that emits `STRUCTURAL_HOMOLOGY`
  evidence by searching the AlphaFold Database (AFDB) for structural
  homologs.
- **Why:** PhiX174 and other compact phages have proteins with no
  detectable sequence-based signal but conserved 3D folds. Sequence
  search is at its biological floor here; structural search isn't.
- **Status:** Design ready. The `STRUCTURAL_HOMOLOGY` evidence type
  already exists. Plugin scaffold sketched in [extending.md](extending.md#1-adding-a-new-analysis-plugin).
- **Hard part:** AFDB is large (~250 GB downloaded, several TB
  uncompressed). Need a hosted index option for users without the
  storage.

### Translational coupling detection

- **What:** Detect ORFs whose start codon sits within a small window
  downstream of a stop codon in the *same* frame — the canonical
  signature of translationally coupled overlapping genes (PhiX174 A\*,
  B, E, K all use this).
- **Why:** Closes the PhiX174 60 % F1 ceiling that even Bakta can't
  beat with sequence-based methods.
- **Status:** Diagnostic evidence collected (the missing genes
  consistently have RBS=0 at canonical positions). Algorithm sketched.

### Bacterial-genome scaling

- **What:** Validation suite on 4–6 Mb bacterial genomes (E. coli K-12,
  B. subtilis, M. tuberculosis). Memory profiling, parallel-worker
  benchmarks, possibly a streaming gene-iterator.
- **Why:** Currently validated on phages only. Bacterial-scale is the
  real-world target.
- **Hard part:** Per-gene API calls in online mode become a throughput
  bottleneck. Need batch UniProt requests or a local embedding-based
  pre-filter.

---

## 🌅 Mid-horizon (0.4.0)

### Comparative-genomics mode

- **What:** `giae diff genome_a.gb genome_b.gb` — show functional
  divergence between two interpretations side by side.
- **Why:** Strain comparison, phage variant analysis, host adaptation
  studies all want this.
- **Status:** Concept; data model already supports it.

### Evidence-network visualisation

- **What:** Web UI panel showing evidence flow per gene as a graph —
  each evidence type a node, conflicts highlighted, reasoning chain as
  edges.
- **Why:** The reasoning chain is GIAE's central differentiator;
  visualising it makes it immediately obvious to non-bioinformatician
  consumers.
- **Status:** Prototyping in the Next.js frontend.

### Streaming output

- **What:** Server-sent events on `/api/v1/jobs/{id}/stream` — emit
  `Interpretation` records as they complete, instead of waiting for
  the whole genome.
- **Why:** Bacterial genomes are slow; streaming makes progress
  visible to the user.

---

## 🌌 Long-horizon (1.0.0)

### Hosted SaaS

- Frontend dashboard (already scaffolded in `frontend/`).
- API key tier with rate limiting and metering.
- "Dark matter" cross-genome database — index every unannotated protein
  across all uploaded genomes, continuously re-annotated by structural
  AI as new methods land.

See [PRODUCT_STRATEGY.md](https://github.com/Ayo-Cyber/GIAE/blob/main/PRODUCT_STRATEGY.md)
for the full product vision.

### Self-correcting annotations

- **What:** When new structural data, UniProt entries, or HMM models
  appear, re-interpret old GIAE predictions and surface what changed.
- **Why:** Annotations rot. Our reasoning chains make it possible to
  ask *"would this prediction still hold today?"* — that's a useful
  capability nobody else has.

---

## How to influence the roadmap

- **Open a feature request** with a clear use case →
  [issue tracker](https://github.com/Ayo-Cyber/GIAE/issues)
- **Send a PR** — extension points are documented in
  [extending.md](extending.md)
- **Bring a benchmark** — a real genome we don't currently handle well
  is the most actionable signal we can get
- **Discuss it first** for anything that would touch the engine core
  ([discussions](https://github.com/Ayo-Cyber/GIAE/discussions))

---

*Last updated: 2026-05-09 (v0.2.2 release)*
