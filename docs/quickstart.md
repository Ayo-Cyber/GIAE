# Quickstart

> **Time to first interpretation:** ~5 minutes &nbsp;·&nbsp; **Skill level:** Beginner

This page gets you from zero to a complete genome annotation, with three
paths depending on how you want to use GIAE: as a **CLI tool**, as a
**Python library**, or as a **REST service** in Docker.

---

## 1. Install GIAE

GIAE needs Python 3.9 or newer.

=== "From PyPI"

    ```bash
    pip install giae
    ```

=== "From source"

    ```bash
    git clone https://github.com/Ayo-Cyber/GIAE.git
    cd GIAE
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev,annotation]"
    ```

Verify it worked:

```bash
giae --version
# giae, version 0.2.2
```

!!! tip "Optional capabilities are extras"
    Most pipelines need only the base install. Pull in extras as you
    need them:
    ```bash
    pip install "giae[annotation]"   # pyrodigal — ORF prediction on FASTA
    pip install "giae[hmmer]"        # local Pfam HMMER
    pip install "giae[ai]"           # ESM-2 protein language model
    pip install "giae[api]"          # REST API server
    ```

---

## 2. Get a genome file

GIAE accepts **GenBank** (`.gb`, `.gbk`) or **FASTA** (`.fa`, `.fasta`)
files.

If you don't have one handy, download Lambda phage from NCBI (48 kb,
92 genes — small enough to finish in seconds):

```bash
curl -o lambda_phage.gb \
  "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_001416&rettype=gb&retmode=text"
```

Or, if you cloned the repo, the `case_studies/` directory ships with
seven reference phage genomes ready to use.

---

## 3. Pick your path

=== "🖥️ CLI"

    The fastest way to see GIAE in action.

    ### Offline mode — no network, ~seconds

    ```bash
    giae interpret lambda_phage.gb --mode offline
    ```

    ```text
    ✅ Done in 4.2s — 92 genes interpreted
       45 high confidence · 3 moderate · 0 low · 44 dark matter
       Report: lambda_phage_report.md
    ```

    ### Online mode — UniProt + InterPro, deeper annotations

    ```bash
    giae interpret lambda_phage.gb --mode online
    ```

    ### Phage-aware mode — recovers nested overlapping genes

    ```bash
    giae interpret phiX174.gb --phage
    ```

    ### Interactive HTML report

    ```bash
    giae interpret lambda_phage.gb --format html -o lambda.html
    ```

    Open `lambda.html` in any browser. Every gene is colour-coded by
    confidence with COG / Pfam / GO badges.

    ### Parallel workers for big genomes

    ```bash
    giae interpret bacterial_genome.gb --workers 8 --mode local
    ```

    [Full CLI reference →](cli.md)

=== "🐍 Python library"

    Use GIAE inside your own pipelines.

    ```python
    from giae.engine.interpreter import Interpreter
    from giae.parsers.genbank import GenBankParser

    # 1. Parse the genome
    genome = GenBankParser().parse("lambda_phage.gb")

    # 2. Configure the interpreter
    interpreter = Interpreter(
        use_uniprot=False,        # offline mode
        use_interpro=False,
        phage_mode=True,          # phage-aware nested-ORF detection
    )

    # 3. Run interpretation
    summary = interpreter.interpret_genome(genome)

    print(f"Total: {summary.total_genes} | "
          f"interpreted: {summary.interpreted_genes} | "
          f"dark: {summary.novel_gene_report.dark_matter_count}")

    # 4. Inspect individual results
    for result in summary.results:
        interp = result.interpretation
        if not interp:
            continue
        print(f"\n{result.gene_id}  ·  {interp.hypothesis}")
        print(f"  confidence: {interp.confidence_level.value} "
              f"({interp.confidence_score:.2f})")
        print(f"  COG: {interp.metadata.get('cog_category')} — "
              f"{interp.metadata.get('cog_name')}")
        print(f"  reasoning:")
        for step in interp.reasoning_chain:
            print(f"    • {step}")
    ```

    [Full Python API reference →](python_api.md)

=== "🐳 REST API (Docker)"

    Run GIAE as a service. Same engine, async job queue, multi-user.

    ```bash
    # 1. One-time setup — generate secrets and write .env
    cp .env.example .env
    # then edit .env to fill in JWT_SECRET and NEXTAUTH_SECRET
    # Generate values with:
    #   python -c "import secrets; print(secrets.token_urlsafe(64))"

    # 2. Bring up the stack
    docker compose up -d postgres redis api worker

    # 3. Verify
    curl http://localhost:8000/api/v1/health
    # {"status":"ok","message":"GIAE API Engine is fully operational."}
    ```

    Submit a genome:

    ```bash
    # Sign up
    TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/signup \
      -H "Content-Type: application/json" \
      -d '{"email":"you@lab.org","password":"correct-horse-battery"}' \
      | jq -r .access_token)

    # Submit a job (phage_mode optional)
    curl -X POST http://localhost:8000/api/v1/jobs \
      -H "Authorization: Bearer $TOKEN" \
      -F "file=@lambda_phage.gb" \
      -F "phage_mode=false"

    # → {"job_id": "abc...", "status": "PENDING", ...}

    # Poll status
    curl -H "Authorization: Bearer $TOKEN" \
      http://localhost:8000/api/v1/jobs/abc...

    # When status: "COMPLETED", fetch the report
    open http://localhost:8000/reports/abc....html
    ```

    [Full REST API reference →](rest_api.md) ·
    [Deployment guide →](deployment.md)

---

## 4. Reading the output

A typical interpretation block:

```text
─────────────────────────────────────────────────────────────────
Gene: cI  ·  λ-phage repressor protein
Hypothesis:   Lambda phage repressor CI
Confidence:   HIGH   (0.87)
COG:          K — Transcription   (source: pfam)
Pfam:         PF01381 (HTH_3)
GO:           GO:0003677, GO:0006355

Evidence:
  [0.94] HMMER     PF01381 (HTH_3, e-value 1.2e-9)
  [0.96] UniProt   P03034 — Repressor protein CI, λ phage
  [0.82] PROSITE   PS50943 — Helix-turn-helix DNA-binding domain

Reasoning:
  1. Pfam HTH_3 domain hit (e-value 1.2e-9) is diagnostic for
     transcriptional regulators
  2. UniProt P03034 is a Swiss-Prot reviewed entry for the same gene
     in the same organism (96% identity)
  3. Three independent evidence types converge on the same function

Uncertainty sources: none
Competing hypotheses: Cro-like repressor (0.23) — rejected by HTH variant
─────────────────────────────────────────────────────────────────
```

### Confidence levels

| Score | Level | Interpretation |
|---|---|---|
| ≥ 0.80 | **HIGH** | Multiple independent evidence types converge |
| 0.50 – 0.79 | **MODERATE** | Some convergence or one strong source |
| 0.30 – 0.49 | **LOW** | Weak / single signal — treat as a hypothesis |
| < 0.30 | **SPECULATIVE** | Minimal signal, flagged for review |
| — | **NONE** | No evidence (dark matter — research priority) |

[Full confidence model →](architecture.md#confidence-model)

---

## 5. What's next?

- **[CLI reference](cli.md)** — every command, every flag
- **[Python API](python_api.md)** — programmatic use, plugin protocol
- **[REST API](rest_api.md)** — HTTP surface, auth, jobs
- **[Architecture](architecture.md)** — evidence flow, scoring math
- **[Benchmarks](benchmarks.md)** — head-to-head vs Bakta
- **[Extending GIAE](extending.md)** — write your own plugin
