<p align="center">
  <img src="docs/assets/logo.png" alt="GIAE Logo" width="300"/>
</p>

# GIAE — Genome Interpretation & Annotation Engine

> **Explainability-first genome annotation. Every prediction shows its reasoning.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-green)](pyproject.toml)

Most genome annotation tools are overconfident. PROKKA, Bakta, and RAST assign a label, hide the evidence, and give you no way to know how certain the prediction is. GIAE takes the opposite approach:
- **Interactive HTML Reports**: Generate premium, searchable reports for biologists (`--format html`).
- **High-Performance Caching**: SQLite-backed local cache for 10x faster re-runs.
- **Explainability**: Every prediction includes a complete narrative reasoning chain and confidence score.
- **Multilayer Evidence**: Integrates Prosite motifs, HMMER domains, protein homology (UniProt), and AI (ESM-2).
- **Novel Gene Discovery**: Dedicated scoring for "Dark Matter" (genes with no homology).
- **Automated CI/CD**: Pre-configured GitHub Actions for testing and PyPI deployment.
- **MkDocs Documentation**: Full documentation site hosted on GitHub Pages.

---

## What Makes GIAE Different

| Feature | PROKKA / Bakta / RAST | GIAE |
|---|---|---|
| Output | Label only | Label + evidence chain + confidence score |
| Uncertainty | Hidden | Explicit, calibrated per gene |
| Conflicting evidence | Silently resolved | Flagged and reported |
| Unknown genes | "hypothetical protein" | Ranked as research priorities |
| Reasoning | Opaque | Full reasoning chain in every report |

---

## 4-Layer Evidence Pipeline

```
Genome (.gb / .fasta)
       │
       ▼
┌──────────────────────────────────────────────┐
│  1. PROSITE Motif Scan         weight: 0.80  │  1,298 curated patterns (bundled)
│  2. EBI HMMER / Pfam Domains   weight: 0.90  │  Pfam via EBI web API (online)
│  3. UniProt API Lookup         weight: 1.00  │  Swiss-Prot reviewed entries (online)
│  4. Conflict Detection                        │  flags when sources disagree
└──────────────────────────────────────────────┘
       │
       ▼
  Interpretation + Confidence Score + Novel Gene Report
```

Confidence is computed from evidence convergence — when PROSITE, Pfam, and UniProt all agree, confidence is HIGH. When they disagree, the conflict is surfaced explicitly rather than silently resolved.

---

## Installation

Install from source (recommended while in active development):

```bash
git clone https://github.com/Ayo-Cyber/GIAE.git
cd GIAE
pip install -e ".[dev]"
```

Or via pip:

```bash
pip install giae
```

**Requirements:** Python 3.10+, BioPython, Click, Rich. No local databases required for the base pipeline — PROSITE (1,298 patterns) is bundled.

---

## Quick Start

```bash
# Offline mode: PROSITE patterns only — no network, instant startup
# Lambda phage (92 genes) completes in ~4 seconds
giae interpret lambda_phage.gb --no-uniprot --no-interpro

# Full pipeline: adds EBI HMMER + UniProt API calls
# Lambda phage takes ~6 minutes (network latency dominates)
giae interpret lambda_phage.gb

# Save Markdown report to file
giae interpret lambda_phage.gb --output lambda_report.md

# JSON output for downstream processing
giae interpret lambda_phage.gb --format json --output results.json

# Large genomes: parallel workers reduce wall time significantly
# T4 phage (288 genes) — use --no-uniprot --no-interpro for offline speed
giae interpret T4.gb --workers 4 --no-uniprot --no-interpro
```

> **Runtime guide:** Offline (PROSITE only) runs in seconds for phage-sized genomes. Online mode (full pipeline) adds ~4–5 seconds per gene for API calls — plan for 5–10 minutes per phage, hours for large bacterial genomes. Use `--workers` to parallelise.

---

## Example Output

A well-characterised gene with converging evidence:

```
Gene: J — Tail fiber protein
Hypothesis:  Tail fiber / host receptor-binding protein
Confidence:  HIGH (0.87)
Category:    structural_protein

Evidence:
  [0.82] PROSITE PS51123 — Phage tail fiber repeat
  [0.94] Pfam PF09255   — Phage_tail_fib (e-value: 2.1e-14)
  [0.90] UniProt P03722 — Tail fiber protein J, Lambda phage (Swiss-Prot reviewed)

Uncertainty sources: none
Competing hypotheses: none above threshold
```

A dark-matter gene with zero detectable signal:

```
Gene: B — hypothetical protein (147 aa)
Interpretation: NONE
Novel Gene Category: DARK MATTER
Priority:  HIGH PRIORITY
Reason:    No sequence homology, domains, or motifs detected

Suggested experiments:
  • Recombinant expression and biochemical activity screening
  • Deletion mutant phenotyping to assess essentiality
  • Comparative genomics across related strains
  • Structural characterization by cryo-EM
```

---

## Confidence Levels

Every prediction carries a numeric score mapped to a named level:

| Level | Score range | Meaning |
|-------|-------------|---------|
| `HIGH` | ≥ 0.80 | Multiple evidence types converge; strong homology or domain hit |
| `MODERATE` | 0.50 – 0.79 | Some convergence; one strong signal or moderate homology |
| `LOW` | 0.30 – 0.49 | Weak or single-type evidence; treat as a lead, not a conclusion |
| `SPECULATIVE` | < 0.30 | Minimal signal; flagged for review |

Scores are adjusted for: evidence diversity (+0.10 for ≥2 types), strong homology (+0.05), high-confidence Pfam domain (+0.08), and penalised for: limited evidence (−0.10), hypothetical homologs (−0.15), single-evidence-type motif-only predictions (capped at 0.85), and conflict (×0.80 penalty).

---

## 7-Phage Benchmark

Benchmarked on seven classic bacteriophage genomes (offline pipeline: PROSITE + Pfam):

| Phage | Genome | Genes | Interpreted | Dark Matter |
|-------|--------|-------|-------------|-------------|
| Lambda (λ) | 48.5 kb | 92 | 45 (48.9%) | 44 (47.8%) |
| T7 | 39.9 kb | 56 | 19 (33.9%) | 36 (64.3%) |
| PhiX174 | 5.4 kb | 11 | 0 (0.0%) | 11 (100%) |
| Phi29 | 19.3 kb | 30 | 13 (43.3%) | 16 (53.3%) |
| Mu | 36.7 kb | 56 | 20 (35.7%) | 35 (62.5%) |
| P22 | 41.7 kb | 69 | 30 (43.5%) | 38 (55.1%) |
| T4 | 168.9 kb | 288 | 75 (26.0%) | 213 (73.9%) |

**Median characterization rate: 34.5%**

> **Lambda with the full 4-layer online pipeline:** 48.9% — identical to offline. The 44 dark-matter genes remain dark not because databases are small, but because these proteins genuinely have no detectable sequence-based signal. That is the correct answer.

> **PhiX174 at 0%** is expected and correct. Its proteins (viral jelly-roll β-barrel capsid, DNA pilot tube) are structurally unique folds with no sequence-recognizable motifs. Structural homology search (Foldseek/AlphaFold) is next on the roadmap.

All 7 GenBank files and benchmark reports are in [`case_studies/`](case_studies/).

---

## Novel Gene Discovery

Every run produces a `Novel Gene Report` — a structured research agenda for genes that couldn't be interpreted:

```
Novel Gene Discovery
  Dark Matter:  44  (zero evidence from any source)
  Weak Signal:  13  (confidence < 35%)
  Conflicting:   0

Top Research Priorities:
  1. B    — 147 aa  HIGH PRIORITY  dark_matter
  2. ea22 — 113 aa  HIGH PRIORITY  dark_matter
  3. orf  — 98  aa  HIGH PRIORITY  dark_matter
```

Three novelty categories:
- **Dark matter** — zero computational evidence from any source
- **Weak evidence** — some hits, but confidence below threshold (< 35%)
- **Conflict** — two or more evidence sources contradict each other

Each candidate includes suggested experiments scaled to protein length and category.

---

## Python API

Use GIAE programmatically for batch processing or integration into pipelines:

```python
from giae.parsers.genbank import parse_genbank
from giae.engine.interpreter import Interpreter

# Load genome
genome = parse_genbank("lambda_phage.gb")

# Run offline pipeline (fast, no network)
interpreter = Interpreter(use_uniprot=False, use_interpro=False)
summary = interpreter.interpret_genome(genome)

print(f"Interpreted {summary.interpreted_genes}/{summary.total_genes} genes")
print(f"Dark matter: {summary.novel_gene_report.dark_matter_count}")

# Inspect individual results
for result in summary.results:
    if result.interpretation:
        print(result.interpretation.get_explanation())

# Quick single-sequence interpretation
interp = interpreter.quick_interpret("MKVLIFFVIALFSSATAAF...", sequence_type="protein")
print(interp)
```

---

## CLI Reference

```
Usage: giae [OPTIONS] COMMAND [ARGS]...

Commands:
  interpret   Interpret a genome file (.gb or .fasta)
  db          Database management (download databases, check status)
```

### `giae interpret`

```
Options:
  --output, -o PATH           Write report to file (default: stdout)
  --format, -f [report|json]  Output format (default: report)
  --workers, -w INT           Parallel workers, 1–16 (default: 1)
  --no-uniprot                Skip UniProt API (offline mode)
  --no-interpro               Skip EBI HMMER domain search (offline mode)
  --verbose, -v               Show pipeline details
```

### `giae db`

Manages optional local databases for the plugin layer. The base pipeline (PROSITE) needs no setup — databases here unlock the local HMMER and BLAST plugins.

```bash
# Check what's installed
giae db status

# Download PROSITE (latest from ExPASy — updates the bundled copy)
giae db download prosite

# Download SwissProt for local BLAST (requires BLAST+ installed)
giae db download swissprot

# Download Pfam for local HMMER (requires HMMER3 installed)
giae db download pfam

# Force re-download
giae db download prosite --force
```

> **Do you need to run `giae db`?** No, for the base pipeline. PROSITE (1,298 patterns) is bundled. `giae db` is only needed if you want local BLAST or HMMER plugins, which bypass the EBI web API with locally-installed tools and larger databases.

---

## Project Structure

```
GIAE/
├── src/giae/
│   ├── analysis/           # Evidence extraction modules
│   │   ├── motif.py        # PROSITE pattern scanning
│   │   ├── prosite.py      # PROSITE database parser
│   │   ├── uniprot.py      # UniProt REST API client
│   │   ├── interpro.py     # EBI HMMER / InterPro client
│   │   ├── hmmer.py        # Local HMMER plugin
│   │   ├── blast_local.py  # Local BLAST plugin
│   │   └── ai.py           # ESM-2 embedding plugin
│   ├── cli/
│   │   ├── main.py         # CLI entrypoint
│   │   └── db.py           # Database management commands
│   ├── engine/
│   │   ├── interpreter.py  # Main orchestrator
│   │   ├── aggregator.py   # Evidence aggregation & weighting
│   │   ├── hypothesis.py   # Hypothesis generation
│   │   ├── confidence.py   # Confidence scoring
│   │   ├── conflict.py     # Conflict detection
│   │   ├── novelty.py      # Novel gene discovery & ranking
│   │   └── plugin.py       # Plugin manager
│   ├── models/             # Core data models
│   │   ├── genome.py
│   │   ├── gene.py
│   │   ├── protein.py
│   │   ├── evidence.py
│   │   └── interpretation.py
│   ├── output/
│   │   ├── report.py       # Markdown report generator
│   │   ├── reasoning.py    # Reasoning chain formatter
│   │   └── json_export.py  # JSON serialization
│   └── parsers/            # FASTA / GenBank parsers
├── tests/                  # pytest test suite
├── case_studies/           # 7 phage GenBank files + benchmark reports
├── data/prosite/           # Bundled PROSITE database (1,298 patterns)
├── pyproject.toml
└── QUICKSTART.md
```

---

## Plugin System

GIAE has a plugin architecture for optional heavy-weight evidence sources. Plugins are auto-detected at startup — if the required binary or database path doesn't exist, the plugin is silently skipped. The base pipeline always runs.

| Plugin | Requirement | Evidence Type | Weight |
|--------|-------------|---------------|--------|
| `HmmerPlugin` | HMMER3 + `~/.giae/hmmer/pfam.hmm` | `DOMAIN_HIT` | 0.90 |
| `BlastLocalPlugin` | BLAST+ + `~/.giae/blast/swissprot` | `BLAST_HOMOLOGY` | 1.00 |
| `EsmPlugin` | PyTorch + ESM-2 model | `SEQUENCE_FEATURE` | 0.50 |

Install plugin dependencies with `giae db download pfam` / `giae db download swissprot`.

---

## 📖 Documentation

Visit the official GIAE documentation site: [Ayo-Cyber.github.io/GIAE/](https://Ayo-Cyber.github.io/GIAE/)

## 🚀 Advanced Features

### Interactive HTML Reports

Generate premium, interactive reports with sortable tables and confidence badges.

```bash
giae interpret genome.gb --format html -o report.html
```

### High-Performance Caching

GIAE uses a local SQLite database to cache API responses. This makes subsequent runs up to 10x faster.

```bash
# Manage the cache
giae db stats
giae db clear
```

---

## Roadmap

- [ ] **Foldseek / AlphaFold structural search** — `STRUCTURAL_HOMOLOGY` evidence (already in codebase); resolves PhiX174-class cases where sequence-based methods fail completely
- [ ] **EBI BLAST async API** — replace text-based UniProt search with real sequence similarity search
- [ ] **Bacterial genome scaling** — currently validated on phages; next target is 4–6 Mb bacterial genomes
- [ ] **Comparison mode** — diff two genome interpretations side by side

---

## Contributing

Issues, PRs, and genome challenges welcome.

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=giae --cov-report=term-missing
```

---

## Citation

If you use GIAE in research, please cite:

```
GIAE — Genome Interpretation & Annotation Engine (v0.2.0)
https://github.com/Ayo-Cyber/GIAE
```

A formal publication is in preparation.

---

## License

MIT — see [LICENSE](LICENSE).

---

*GIAE v0.2.0 — Benchmarked on Lambda, T7, PhiX174, Phi29, Mu, P22, and T4.*
