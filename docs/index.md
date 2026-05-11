# GIAE

**Genome Interpretation & Annotation Engine — every prediction shows its reasoning.**

GIAE is an explainability-first annotation engine. Where Bakta and
Prokka return labels, GIAE returns labels with the full evidence stack,
a numerical confidence score, the reasoning chain that produced it, and
the alternatives it considered.

It's also faster and more accurate than Bakta on the genomes we've
benchmarked.

| Genome | GIAE F1 | Bakta F1 | Δ |
|---|---|---|---|
| phiX174 | 60.0 % | 60.0 % | tied |
| λ phage | **79.2 %** | 72.6 % | **+6.6 %** |
| T7 | **88.1 %** | 85.2 % | **+2.9 %** |

[Reproduce these numbers →](https://github.com/Ayo-Cyber/GIAE/blob/main/post_assets/bakta_comparison.py)

---

## What's here

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **[Quickstart](quickstart.md)**

    ---

    Five-minute path from `pip install` to your first annotated genome.
    CLI, Python library, and Docker walkthroughs.

-   :material-console:{ .lg .middle } **[CLI reference](cli.md)**

    ---

    Every command, every flag. `interpret`, `parse`, `db`, `serve`,
    `worker`, `analyze`, `quick`, `info`.

-   :material-language-python:{ .lg .middle } **[Python API](python_api.md)**

    ---

    Use GIAE programmatically. `Interpreter`, `Genome`, `Gene`,
    `Evidence`, `Interpretation`, plugin protocol.

-   :material-api:{ .lg .middle } **[REST API](rest_api.md)**

    ---

    Full HTTP surface — auth, jobs, API keys, results. Built on
    FastAPI + Celery + Postgres + Redis.

-   :material-graph:{ .lg .middle } **[Architecture](architecture.md)**

    ---

    How GIAE actually works. Evidence flow, hypothesis generation,
    confidence scoring, conflict detection.

-   :material-chart-bar:{ .lg .middle } **[Benchmarks](benchmarks.md)**

    ---

    Reproducible head-to-head against Bakta. Methodology, raw numbers,
    per-genome breakdowns.

-   :material-server:{ .lg .middle } **[Deployment](deployment.md)**

    ---

    Run the full stack with `docker compose`. Env vars, scaling, ops.

-   :material-puzzle:{ .lg .middle } **[Extending GIAE](extending.md)**

    ---

    Add a plugin — new evidence source, new analysis tool, new database.

</div>

---

## Why explainability matters

Most annotation tools treat the output as the answer: a label, possibly
a score, end of story. That works fine for well-characterised genes
where the consensus is strong. It breaks down at the edges, which is
where the interesting biology lives:

- **Conflicting evidence** — homology says X, motif says Y, domain says Z.
  Most tools silently pick one. GIAE flags the conflict.
- **Weak signals** — a single PROSITE hit isn't a function call. GIAE
  caps single-source-only hypotheses at 0.45 (LOW) so they don't masquerade
  as moderate.
- **Dark matter** — proteins with no sequence-detectable signal aren't
  failures, they're research priorities. GIAE ranks them.
- **Curator vs. computational** — a GenBank product annotation isn't
  the same kind of evidence as a BLAST hit. GIAE keeps them as
  separately typed evidence with different confidence weights.

The core idea: **make uncertainty explicit, make reasoning auditable, let the user decide what to trust**.

---

## Architecture in 30 seconds

```text
Genome ──► ORF prediction (pyrodigal + rescue + nested-finder)
        ──► Evidence extraction (PROSITE, Pfam, Diamond, UniProt, ESM-2)
        ──► Aggregation → Hypothesis generation → Confidence scoring
        ──► Functional annotation (COG / GO / normalised product)
        ──► Markdown · JSON · HTML · REST API
```

Every step keeps full provenance. The output isn't just *"DNA polymerase
III, HIGH"*, it's *"DNA polymerase III, 0.87 HIGH, supported by Pfam
PF00136 (e-value 2.1e-14) + UniProt P03722 + PROSITE PS51123, with no
competing hypothesis above 0.50, COG category L (Replication), GO terms
[GO:0003677, GO:0003887, GO:0006260]"*.

[Read the full architecture doc →](architecture.md)

---

## Latest

GIAE 0.2.2 ships eight major capabilities at once: pyrodigal-backed ORF
prediction, motif confidence tiering, Diamond BLASTP, validation suite,
tRNA/rRNA detection, short-ORF rescue, phage-aware nested ORF detection,
COG/GO functional annotation depth, and a full REST API server. See
the [changelog](changelog.md) for the per-phase breakdown.

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

A formal application-note manuscript is in preparation.
