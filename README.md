<h1 align="center">
  <img src="docs/assets/mark.svg" alt="GIAE" width="64" align="middle"/>
  <br/>
  GIAE — Genome Interpretation &amp; Annotation Engine
</h1>

<p align="center">
  <strong>Explainable, evidence-first genome annotation. Every prediction shows its reasoning.</strong>
</p>

<p align="center">
  <a href="https://github.com/Ayo-Cyber/GIAE/actions"><img src="https://img.shields.io/github/actions/workflow/status/Ayo-Cyber/GIAE/ci.yml?branch=main&label=CI&logo=github" alt="CI"/></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/version-0.2.2-2ea44f" alt="Version"/></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white" alt="Python"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow" alt="License"/></a>
  <a href="https://Ayo-Cyber.github.io/GIAE/"><img src="https://img.shields.io/badge/docs-mkdocs--material-526CFE" alt="Docs"/></a>
  <img src="https://img.shields.io/badge/tests-166%20passing-success" alt="Tests"/>
</p>

---

GIAE is a genome annotation engine that **shows its work**. Where Bakta and Prokka return labels, GIAE returns labels with the full evidence stack, a numerical confidence score, the reasoning chain that produced it, and the alternatives it considered.

It's also faster and more accurate than Bakta on the genomes we've benchmarked.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  Phage benchmark — same FASTA, same scoring, same overlap criterion    │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────┤
│   Genome     │   GIAE F1    │   Bakta F1   │     Δ        │   Verdict   │
├──────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│   phiX174    │   60.0 %     │   60.0 %     │     —        │   tied      │
│   λ phage    │   79.2 %     │   72.6 %     │   +6.6 %     │   GIAE wins │
│   T7         │   88.1 %     │   85.2 %     │   +2.9 %     │   GIAE wins │
└──────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
GIAE config: pyrodigal + rescue + phage_mode (no UniProt/BLAST/InterPro).
Bakta config: light db, --skip-* for missing tools, CDS pipeline active.
```

[Reproduce these numbers →](post_assets/bakta_comparison.py)

---

## Why GIAE

| | Prokka / Bakta / RAST | **GIAE** |
|---|---|---|
| Output per gene | Label only | Label **+ evidence chain + confidence score + alternatives** |
| Uncertainty | Hidden | Explicit, numeric, calibrated |
| Conflicting evidence | Silently resolved | **Surfaced and reported** |
| "hypothetical protein" | End of the line | Ranked as **research priority** with suggested experiments |
| Reasoning audit | None | Full reasoning chain in every record |
| Accuracy on phages | Baseline | **Matches or beats Bakta on all 3 reference genomes** |
| Deployment | CLI only | CLI + **Python library + REST API + Docker stack** |

---

## Architecture at a glance

```
              ┌─────────────────────────────────────────────────────────┐
  Genome ───▶ │ pyrodigal ORF prediction                                │
  (.gb/.fa)   │  + ShortOrfRescue (RBS + codon-usage gate)              │
              │  + NestedOrfFinder (phage_mode, position-weighted SD)   │
              │  + Aragorn (tRNA) + Barrnap (rRNA)                      │
              └────────────────────────────┬────────────────────────────┘
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │ Evidence extraction (typed, weighted, with provenance)  │
              │  • PROSITE motifs (1,298 patterns, bundled)             │
              │  • Pfam / HMMER domains (local pyhmmer)                 │
              │  • Diamond / BLAST+ homology (local DB)                 │
              │  • UniProt + InterPro (online, cached)                  │
              │  • ESM-2 protein language model (optional)              │
              │  • GenBank curator annotations                          │
              └────────────────────────────┬────────────────────────────┘
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │ Aggregation → Hypothesis generation → Confidence score  │
              │ Tiered: GenBank ▶ Homology ▶ Domain ▶ Motif ▶ Combined  │
              │ Conflict detection, novelty scoring, dark-matter rank   │
              └────────────────────────────┬────────────────────────────┘
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │ FunctionalAnnotator (COG category, GO terms, normalised │
              │ product) → Interpretation object with reasoning chain   │
              └────────────────────────────┬────────────────────────────┘
                                           ▼
                Markdown · JSON · Interactive HTML report · REST API
```

[Full architecture doc →](docs/architecture.md)

---

## Install

### From PyPI

```bash
pip install giae
```

### From source (recommended for dev)

```bash
git clone https://github.com/Ayo-Cyber/GIAE.git
cd GIAE
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Optional capabilities

```bash
pip install "giae[annotation]"     # pyrodigal — required for ORF prediction on FASTA
pip install "giae[hmmer]"          # pyhmmer — local Pfam domain search
pip install "giae[ai]"             # ESM-2 + torch — protein LM embeddings
pip install "giae[api]"            # FastAPI + Celery + Postgres — REST API server
```

**Requirements:** Python 3.9+, BioPython, Click, Rich. PROSITE patterns are bundled — no database setup needed for the base pipeline.

---

## Quickstart

### CLI — interpret a genome

```bash
# Offline pipeline (PROSITE only, ~seconds)
giae interpret lambda_phage.gb

# Phage genome with nested-ORF detection
giae interpret phiX174.gb --phage

# Full online pipeline (UniProt + InterPro)
giae interpret lambda_phage.gb --mode online

# Interactive HTML report
giae interpret lambda_phage.gb --format html -o report.html

# Parallel workers for large genomes
giae interpret big_genome.gb --workers 8 --mode local
```

### Python library

```python
from giae.engine.interpreter import Interpreter
from giae.parsers.genbank import GenBankParser

genome = GenBankParser().parse("lambda_phage.gb")

interpreter = Interpreter(
    use_uniprot=False,         # offline mode
    use_interpro=False,
    phage_mode=True,           # phage-aware nested ORF detection
)
summary = interpreter.interpret_genome(genome)

for result in summary.results:
    interp = result.interpretation
    if not interp:
        continue
    print(f"{result.gene_id}: {interp.hypothesis}")
    print(f"  confidence: {interp.confidence_level.value} ({interp.confidence_score:.2f})")
    print(f"  COG:        {interp.metadata.get('cog_category')} — {interp.metadata.get('cog_name')}")
    print(f"  reasoning:  {' → '.join(interp.reasoning_chain)}")
```

### REST API — full stack via Docker

```bash
cp .env.example .env  # then fill in JWT_SECRET, NEXTAUTH_SECRET
docker compose up -d postgres redis api worker
curl http://localhost:8000/api/v1/health
```

```bash
# Sign up, get a token, submit a genome
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"you@lab.org","password":"correct-horse-battery"}' \
  | jq -r .access_token)

curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@lambda_phage.gb" \
  -F "phage_mode=true"
```

[Full REST API reference →](docs/rest_api.md)

---

## Example output

A well-characterised gene with converging evidence:

```text
─────────────────────────────────────────────────────────────────
Gene: J  ·  Locus: lambda_J  ·  Length: 1,131 aa
Hypothesis:   Tail fiber / host-receptor binding protein
Confidence:   HIGH   (0.87)
COG:          X — Mobilome: prophages, transposons   (source: pfam)
Pfam:         PF09255 (Phage_tail_fib)
GO:           GO:0019028, GO:0019068

Evidence:
  [0.94] HMMER         Pfam_PF09255  e-value 2.1e-14
  [0.90] UniProt       P03722 — Tail fiber protein J, λ phage
  [0.82] PROSITE       PS51123 — Phage tail fiber repeat

Reasoning:
  1. Pfam domain hit Phage_tail_fib (e-value 2.1e-14) is diagnostic
  2. UniProt homolog P03722 is a Swiss-Prot reviewed entry from same organism
  3. PROSITE motif corroborates structural prediction

Uncertainty sources: none
Competing hypotheses: none above 0.50 threshold
─────────────────────────────────────────────────────────────────
```

A dark-matter gene flagged for research:

```text
─────────────────────────────────────────────────────────────────
Gene: orf_b72b1  ·  147 aa
Interpretation:  NONE
Novelty class:   DARK MATTER  (no signal from any source)
Priority:        HIGH
Suggested experiments:
  • Recombinant expression and biochemical activity screening
  • Deletion mutant phenotyping for essentiality
  • Comparative genomics across related strains
  • Structural characterization (cryo-EM or AlphaFold + Foldseek)
─────────────────────────────────────────────────────────────────
```

---

## Confidence model

Every prediction carries a numeric score `[0.0, 1.0]` mapped to a named level:

| Level | Score | Meaning |
|---|---|---|
| **HIGH** | ≥ 0.80 | Multiple independent evidence types converge |
| **MODERATE** | 0.50 – 0.79 | Some convergence, or one strong source |
| **LOW** | 0.30 – 0.49 | Weak / single signal — treat as a lead |
| **SPECULATIVE** | < 0.30 | Minimal signal, flagged for review |
| **NONE** | — | No evidence at all (dark matter) |

Scoring penalties and bonuses are explicit and documented:
[architecture.md → Confidence model](docs/architecture.md#confidence-model)

---

## What's in the box

| Capability | Module | Status |
|---|---|---|
| ORF prediction (pyrodigal) | `analysis/orf_finder.py` | Always on |
| Short-ORF rescue (RBS + codon usage gate) | `analysis/short_orf_rescue.py` | Default on |
| Nested-ORF detection (phage mode) | `analysis/nested_orf_finder.py` | `--phage` |
| tRNA / tmRNA detection | `analysis/aragorn.py` | If `aragorn` on PATH |
| rRNA detection | `analysis/barrnap.py` | If `barrnap` on PATH |
| PROSITE motif scan | `analysis/motif.py` | Always on (1,298 patterns bundled) |
| Local Diamond BLASTP | `analysis/diamond.py` | If `diamond` on PATH + DB |
| Local NCBI BLAST+ | `analysis/blast_local.py` | Fallback if Diamond absent |
| Local Pfam HMMER | `analysis/hmmer.py` | If `pfam.hmm` present |
| UniProt API client | `analysis/uniprot.py` | `--mode online` |
| InterPro / EBI HMMER client | `analysis/interpro.py` | `--mode online` |
| ESM-2 protein language model | `analysis/ai.py` | If `[ai]` extras installed |
| COG / GO functional annotation | `analysis/functional_annotator.py` | Always on (~100 Pfam IDs bundled) |
| Product-name normaliser | `analysis/product_normalizer.py` | Always on |
| HTML report generator | `output/html_report.py` | `--format html` |
| REST API + worker queue | `giae_api/` | `giae serve` / `giae worker` |

---

## Documentation

| Topic | Link |
|---|---|
| **Quickstart** (5 minutes) | [docs/quickstart.md](docs/quickstart.md) |
| **CLI reference** | [docs/cli.md](docs/cli.md) |
| **Python library API** | [docs/python_api.md](docs/python_api.md) |
| **REST API reference** | [docs/rest_api.md](docs/rest_api.md) |
| **Architecture & confidence model** | [docs/architecture.md](docs/architecture.md) |
| **Benchmarks** (vs Bakta) | [docs/benchmarks.md](docs/benchmarks.md) |
| **Deployment** (Docker, scaling) | [docs/deployment.md](docs/deployment.md) |
| **Extending GIAE** (plugins) | [docs/extending.md](docs/extending.md) |
| **Roadmap** | [docs/roadmap.md](docs/roadmap.md) |
| **Contributing** | [CONTRIBUTING.md](CONTRIBUTING.md) |
| **Hosted docs** | [Ayo-Cyber.github.io/GIAE/](https://Ayo-Cyber.github.io/GIAE/) |

---

## Roadmap

GIAE is an evolving platform. The next horizon:

- **Foldseek / AlphaFold structural homology** — `STRUCTURAL_HOMOLOGY` evidence to crack PhiX174-class cases where sequence-based methods plateau
- **Bacterial genome scaling** — currently validated on phages; next target is 4–6 Mb bacterial genomes
- **Translational coupling detection** — recover compact-phage overlapping genes that lack canonical SD signals
- **Comparative-genomics mode** — diff two interpretations side-by-side
- **Hosted SaaS** — see [PRODUCT_STRATEGY.md](PRODUCT_STRATEGY.md) for the broader vision

[Detailed roadmap →](docs/roadmap.md)

---

## Contributing

Contributions are welcome — issues, PRs, benchmark genomes, plugin ideas. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

```bash
# Quickly run the test suite
pytest tests/ -q

# Run the Bakta head-to-head (requires Bakta installed)
.venv/bin/python post_assets/bakta_comparison.py
```

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Security issues should follow [SECURITY.md](SECURITY.md).

---

## Citation

If GIAE contributes to your published work, please cite:

```bibtex
@software{giae_2026,
  author  = {{GIAE Contributors}},
  title   = {GIAE: Genome Interpretation and Annotation Engine},
  year    = {2026},
  version = {0.2.2},
  url     = {https://github.com/Ayo-Cyber/GIAE},
}
```

A formal application-note manuscript is in preparation (Phase 8).

---

## License

[MIT](LICENSE) — use it, fork it, build on it. We only ask that you cite GIAE when it contributes to a publication.

---

<p align="center">
  <sub>Built by people who think genome annotation should be auditable.</sub>
  <br/>
  <sub><strong>Lambda 79.2% · T7 88.1% · 166 tests · 0 dark patterns</strong></sub>
</p>
