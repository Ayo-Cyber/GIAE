# Changelog

All notable changes to GIAE are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.2] — 2026-05-09

The "publishable" release. Same evidence-first core, dramatically better
prediction quality, real production surface, and full functional depth.

### Added

#### Phase 1 — Pyrodigal-backed ORF prediction
- Replaced the naive ATG scanner with **pyrodigal**, the Python port of
  Prodigal. Same prediction quality as Bakta's ORF backbone.
- Auto-trigger heuristic: when annotations are absent or sparser than
  0.3 genes/kb on a ≥5 kb genome, ORF prediction runs automatically.

#### Phase 2 — Motif confidence tiering and `--mode` flag
- Three-tier motif scoring (high/medium/low) replacing the flat-rate
  PROSITE weight. Reduces false positives on noisy motif hits.
- `--mode` flag with three presets:
  `online` (UniProt + InterPro), `local` (BLAST + HMMER, no network),
  `offline` (PROSITE bundled, fully offline).

#### Phase 3 — Diamond BLASTP
- New [`DiamondPlugin`](src/giae/analysis/diamond.py) using `diamond blastp`,
  ~10× faster than NCBI BLAST+ with ~3× smaller databases.
- `BlastLocalPlugin` now registers only as a fallback when Diamond is absent.
- `giae db download swissprot-diamond` builds a Diamond database from the
  UniProt E. coli reference proteome.

#### Phase 4A — Validation suite
- [`post_assets/phase4_validation.py`](post_assets/phase4_validation.py) —
  precision/recall/F1 against GenBank ground truth on three reference
  phage genomes (phiX174, λ, T7), reproducible from any clone.

#### Phase 4B — Non-coding RNA detection
- [`AragornFinder`](src/giae/analysis/aragorn.py) — tRNA / tmRNA detection
  via the `aragorn` binary.
- [`BarrnapFinder`](src/giae/analysis/barrnap.py) — rRNA detection via the
  `barrnap` binary.
- ncRNA fast-path in `interpret_gene` returns a pre-built
  HIGH-confidence `Interpretation` (skipping the protein evidence pipeline).
- Both finders fail silently when the binary is absent — no opt-in flag
  required, no errors when tools aren't installed.

#### Phase 5 — Short-ORF rescue
- [`ShortOrfRescue`](src/giae/analysis/short_orf_rescue.py) — recovers
  short genes pyrodigal drops (below the 30 aa minimum) via a two-signal
  evidence gate: tight Shine-Dalgarno detection (window −14 to −4, motifs
  AGGAGG / GGAGG / AGGAG only) **and** codon-usage similarity to the rest
  of the genome.
- Default-on. Adds **+1 TP on lambda, +1 TP on T7, zero new false
  positives** at the tightened gate.

#### Phase 6 — Functional annotation depth
- [`ProductNormalizer`](src/giae/analysis/product_normalizer.py) — strips
  "putative", "[partial]", EC suffixes; collapses whitespace; preserves
  placeholders untouched.
- [`FunctionalAnnotator`](src/giae/analysis/functional_annotator.py) —
  Pfam → COG / GO lookup with category-based fallback. 26 canonical COG
  letters, ~100 curated Pfam IDs bundled in
  [`data/functional/pfam_categories.tsv`](data/functional/pfam_categories.tsv).
- Every `Interpretation` now carries `cog_category`, `cog_name`,
  `cog_source` (`pfam` for direct hits, `inferred` for keyword fallback),
  `go_terms`, `pfam_id`, and `normalized_product` in its metadata.
- HTML report renders COG / Pfam / GO badges per gene.

#### Phase 7 — Phage-aware nested-ORF detection
- [`NestedOrfFinder`](src/giae/analysis/nested_orf_finder.py) — recovers
  overlapping / nested genes (e.g. λ gene rIIB inside rIIA) that
  pyrodigal drops by design. Frame-aware scan in 6 reading frames with a
  position-weighted Shine-Dalgarno score (peak at −9 bp), strict consensus
  motifs, codon-usage gate, and boundary-margin near-duplicate filter.
- Opt-in via `--phage` flag or `Interpreter(phage_mode=True)`.
- **T7 F1: 86.2% → 88.1% (+2 TP, zero new FP).** PhiX174 holds at 60%
  (translational coupling — a documented biological limit, not a bug).

#### Phase C — REST API server
- Full FastAPI surface in [`src/giae_api/`](src/giae_api/) wrapping the
  Interpreter as an async job queue.
- JWT bearer auth + sha256-hashed API keys (two-credential model).
- Postgres-backed job state, Redis-backed Celery worker queue.
- Endpoints: `/api/v1/{health, auth/{signup,login,me}, keys, jobs,
  jobs/{id}, jobs/{id}/cancel, jobs/{id}/rerun, dark-genes,
  worker/status, waitlist}`.
- Per-job `phage_mode` form field passes through to the worker.
- New CLI commands: `giae serve` (uvicorn) and `giae worker` (Celery).
- Multi-stage `Dockerfile` and `docker-compose.yml` for the full stack
  (postgres, redis, api, worker, optional Next.js frontend).
- 18 API tests using FastAPI's `TestClient` + in-memory SQLite.

#### Documentation
- Full mkdocs site rewrite — [docs/](docs/) is now a real reference, not
  marketing copy.
- New: [`docs/architecture.md`](docs/architecture.md),
  [`docs/cli.md`](docs/cli.md),
  [`docs/rest_api.md`](docs/rest_api.md),
  [`docs/benchmarks.md`](docs/benchmarks.md),
  [`docs/deployment.md`](docs/deployment.md),
  [`docs/extending.md`](docs/extending.md).
- Repository now ships [`CONTRIBUTING.md`](CONTRIBUTING.md),
  [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and
  [`SECURITY.md`](SECURITY.md).

### Changed

- **GenBank product evidence retyped.** Curator-assigned product names
  used to be tagged `EvidenceType.BLAST_HOMOLOGY`, which routed them
  through the homology hypothesis path and produced misleading reasoning
  text like *"BLAST homology hit: …"* for genes that came from a GenBank
  curator. Product evidence is now `EvidenceType.SEQUENCE_FEATURE` with
  `source="genbank_product"` and renders as *"GenBank product
  annotation: …"*.
- `Interpreter.use_local_blast` now activates only when Diamond is
  unavailable, so the two homology plugins never duplicate work.
- Worker `_serialize_genes` exposes the full Phase 6 metadata
  (`cog_category`, `cog_name`, `cog_source`, `go_terms`, `pfam_id`,
  `normalized_product`, `category`) on every gene in the API response.
- Dockerfile runtime stage installs `giae[api]` by package name (looked
  up from `/wheels`) instead of `.[api]`, which used to make pip try to
  build from source and fail without `hatchling`.

### Fixed

- **Version mismatch** between `pyproject.toml` (0.2.2) and
  `__init__.py` (0.2.0). Both now read 0.2.2.
- **HTML report label.** GenBank-sourced gene products are no longer
  labeled "BLAST homology hit" in the reasoning chain. See **Changed**
  above for the underlying retype.

### Tests

166 passing (122 → 134 → 148 → 166 across phases). Coverage spans
analysis modules, engine, novelty, parsers, CLI, full-pipeline
integration, nested-ORF detection, functional annotation, and the
REST API surface.

### Benchmarks

| Genome | GIAE F1 | Bakta F1 | Δ |
|---|---|---|---|
| phiX174 | 60.0 % | 60.0 % | tied |
| λ phage | **79.2 %** | 72.6 % | **+6.6 %** |
| T7 | **88.1 %** | 85.2 % | **+2.9 %** |

GIAE config: pyrodigal + rescue + phage_mode, no UniProt/BLAST/InterPro.
Bakta config: light db, all available CDS subsystems active.
[Reproduce →](post_assets/bakta_comparison.py)

---

## [0.2.0] — 2026-03-19

### Added
- **Explainability engine.** Every prediction includes a reasoning chain
  and aggregated evidence.
- **Multi-layer evidence pipeline:** PROSITE motif scanning (~1,800
  bundled patterns), EBI HMMER / InterPro web API, UniProt REST API.
- **Novel gene discovery.** Ranks "dark matter" genes (zero evidence)
  for research priority.
- **CLI:** `giae interpret`, `giae parse`, `giae db`, `giae quick`,
  `giae analyze`, `giae info`.
- **Parallel processing.** `--workers` flag for multi-threaded
  per-gene interpretation.
- **Plugin system.** Local BLAST+ and HMMER plugins.
- **Reporting.** Markdown and JSON output with stylised terminal
  tables.

### Changed
- Genome parsing logic for large GenBank and FASTA files.
- Confidence scoring calibrated on evidence convergence.
- Source tree moved to `src/` layout.
- Build backend switched to `hatchling`.

---

## [0.1.0] — 2026-02-15

- Initial internal release.
- Basic motif scanning and GenBank parsing.
