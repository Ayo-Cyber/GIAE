<h1 align="center">
  <img src="https://raw.githubusercontent.com/Ayo-Cyber/GIAE/main/docs/assets/mark.svg" alt="GIAE" width="64" align="middle"/>
  <br/>
  GIAE — Genome Interpretation &amp; Annotation Engine
</h1>

<p align="center">
  <strong>Explainable, evidence-first genome annotation. Every prediction shows its reasoning.</strong>
</p>

<p align="center">
  <a href="https://github.com/Ayo-Cyber/GIAE/actions"><img src="https://img.shields.io/github/actions/workflow/status/Ayo-Cyber/GIAE/ci.yml?branch=main&label=CI&logo=github" alt="CI"/></a>
  <a href="https://github.com/Ayo-Cyber/GIAE/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/version-0.2.3-2ea44f" alt="Version"/></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white" alt="Python"/></a>
  <a href="https://github.com/Ayo-Cyber/GIAE/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow" alt="License"/></a>
  <a href="https://Ayo-Cyber.github.io/GIAE/"><img src="https://img.shields.io/badge/docs-mkdocs--material-526CFE" alt="Docs"/></a>
  <img src="https://img.shields.io/badge/tests-166%20passing-success" alt="Tests"/>
</p>

---

GIAE is a genome annotation engine that **shows its work**. Where Bakta and Prokka return labels, GIAE returns labels with the full evidence stack, a **calibrated** confidence score, the reasoning chain that produced it, and the alternatives it considered.

On **gene finding**, GIAE is on par with Bakta — as it should be: both call genes with **pyrodigal (Prodigal)**. Parity there is table stakes. GIAE's edge is the layer on top: calibrated confidence you can threshold on, auditable provenance, honest abstention, and zero-config robustness (it auto-detects genetic code 4, where a default Bakta run does not).

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  35-genome benchmark (29 phage + 6 bacteria) — same FASTA, RefSeq truth,  │
│  reciprocal-overlap ≥ 0.5. Both tools call genes with pyrodigal.          │
├────────────────────────────┬───────────────┬───────────────┬─────────────┤
│  Metric                    │     GIAE      │     Bakta     │   Verdict   │
├────────────────────────────┼───────────────┼───────────────┼─────────────┤
│  Gene-finding F1 (mean)    │    0.850      │    0.827      │  tied *     │
│  Phages (n=29)             │    0.832      │    0.838      │  tied       │
│  Bacteria (n=6)            │    0.935      │    0.777      │  GIAE **    │
│  Speed / phage (offline)   │   ~0.25 s     │   ~7.5 s      │  30× faster │
└────────────────────────────┴───────────────┴───────────────┴─────────────┘
 * Wilcoxon signed-rank p = 0.11 → statistically indistinguishable.
** Bacteria gap is a genetic-code artifact: GIAE's pyrodigal meta-mode
   auto-selects table 4 for Mycoplasma; the default Bakta run used table 11.
   A configuration win, not an algorithmic one — see the methodology doc.
```

Confidence is genuinely calibrated: after isotonic recalibration (5-fold CV,
out-of-sample), **ECE 0.30 → 0.004** — a reported probability means what it says.

[Full methodology, caveats & "say this, not that" claims →](BENCHMARK_METHODOLOGY.md) · [Reproduce →](post_assets/benchmark_figure.py)

---

## Why GIAE

| | Prokka / Bakta / RAST | **GIAE** |
|---|---|---|
| Output per gene | Label only | Label **+ evidence chain + confidence score + alternatives** |
| Uncertainty | Hidden | Explicit, numeric, **calibrated** (out-of-sample ECE 0.004) |
| Conflicting evidence | Silently resolved | **Surfaced and reported** |
| "hypothetical protein" | End of the line | Ranked as **research priority** with suggested experiments |
| Reasoning audit | None | Full reasoning chain in every record |
| Gene finding | Prodigal | **Prodigal too** — on par by construction (35-genome F1 tie) |
| Functional IDs | Product name | Product name **+ GO/EC IDs** (synonym-invariant) |
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

[Full architecture doc →](https://Ayo-Cyber.github.io/GIAE/architecture/)

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

[Full REST API reference →](https://Ayo-Cyber.github.io/GIAE/rest_api/)

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
[architecture.md → Confidence model](https://Ayo-Cyber.github.io/GIAE/architecture/#confidence-model)

For **homology-backed** calls, GIAE also reports a **calibrated probability of
correctness** — the raw score mapped through an isotonic calibrator fit
out-of-sample (5-fold CV) on the 35-genome benchmark. Raw scores are
over-confident; the calibrated value is not (out-of-sample ECE 0.004), so
"0.66" means the call is right about two-thirds of the time. See
[BENCHMARK_METHODOLOGY.md](BENCHMARK_METHODOLOGY.md).

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
| COG / GO / EC functional annotation | `analysis/functional_annotator.py` | Always on (~100 Pfam IDs bundled) |
| Confidence recalibration (isotonic) | `analysis/confidence_calibration.py` | On for homology-backed calls |
| Product-name normaliser | `analysis/product_normalizer.py` | Always on |
| HTML report generator | `output/html_report.py` | `--format html` |
| REST API + worker queue | `giae_api/` | `giae serve` / `giae worker` |

---

## Documentation

| Topic | Link |
|---|---|
| **Quickstart** (5 minutes) | [docs/quickstart](https://Ayo-Cyber.github.io/GIAE/quickstart/) |
| **CLI reference** | [docs/cli](https://Ayo-Cyber.github.io/GIAE/cli/) |
| **Python library API** | [docs/python_api](https://Ayo-Cyber.github.io/GIAE/python_api/) |
| **REST API reference** | [docs/rest_api](https://Ayo-Cyber.github.io/GIAE/rest_api/) |
| **Architecture & confidence model** | [docs/architecture](https://Ayo-Cyber.github.io/GIAE/architecture/) |
| **Benchmark methodology & caveats** (authoritative) | [BENCHMARK_METHODOLOGY.md](BENCHMARK_METHODOLOGY.md) |
| **Deployment plan & runbook** | [DEPLOYMENT.md](DEPLOYMENT.md) |
| **Roadmap** (product · paper · tool) | [ROADMAP.md](ROADMAP.md) |
| **Extending GIAE** (plugins) | [docs/extending](https://Ayo-Cyber.github.io/GIAE/extending/) |
| **Contributing** | [CONTRIBUTING.md](https://github.com/Ayo-Cyber/GIAE/blob/main/CONTRIBUTING.md) |
| **Hosted docs** | [Ayo-Cyber.github.io/GIAE/](https://Ayo-Cyber.github.io/GIAE/) |

---

## Roadmap

GIAE is an evolving platform. The next horizon:

- **Foldseek / AlphaFold structural homology** — `STRUCTURAL_HOMOLOGY` evidence to put calibrated, hedged function on the dark genes no homology tool annotates
- **Full prediction-side GO/EC** — UniProt id-mapping enrichment so homology hits carry ontology IDs, not just names
- **Larger, multi-tool benchmark** — 50+ genomes across phyla vs Bakta + Prokka + DFAST, with per-tool significance
- **Hosted SaaS + phage safety screening** — see [PRODUCT_STRATEGY.md](https://github.com/Ayo-Cyber/GIAE/blob/main/PRODUCT_STRATEGY.md)

Validated on 29 phage + 6 bacterial genomes (see the benchmark box above).
[Full phased roadmap →](ROADMAP.md)

---

## Contributing

Contributions are welcome — issues, PRs, benchmark genomes, plugin ideas. Read [CONTRIBUTING.md](https://github.com/Ayo-Cyber/GIAE/blob/main/CONTRIBUTING.md) before opening a PR.

```bash
# Quickly run the test suite
pytest tests/ -q

# Run the Bakta head-to-head (requires Bakta installed)
.venv/bin/python post_assets/bakta_comparison.py
```

By participating you agree to the [Code of Conduct](https://github.com/Ayo-Cyber/GIAE/blob/main/CODE_OF_CONDUCT.md). Security issues should follow [SECURITY.md](https://github.com/Ayo-Cyber/GIAE/blob/main/SECURITY.md).

---

## Citation

If GIAE contributes to your published work, please cite:

```bibtex
@software{giae_2026,
  author  = {{GIAE Contributors}},
  title   = {GIAE: Genome Interpretation and Annotation Engine},
  year    = {2026},
  version = {0.2.3},
  url     = {https://github.com/Ayo-Cyber/GIAE},
}
```

A formal application-note manuscript is in preparation (Phase 8).

---

## License

[MIT](https://github.com/Ayo-Cyber/GIAE/blob/main/LICENSE) — use it, fork it, build on it. We only ask that you cite GIAE when it contributes to a publication.

---

<p align="center">
  <sub>Built by people who think genome annotation should be auditable.</sub>
  <br/>
  <sub><strong>Lambda 79.2% · T7 88.1% · 166 tests · 0 dark patterns</strong></sub>
</p>
