# CLI reference

Every command, every flag.

```text
giae [OPTIONS] COMMAND [ARGS]...
```

## Global options

| Option | Description |
|---|---|
| `--version` | Print version and exit |
| `-v`, `--verbose` | Show pipeline details (motif counts, active plugins, per-gene status) |
| `--debug` | Full debug logging (timestamps, logger names, every API call) |
| `--help` | Print command-specific help |

---

## Commands

### `giae interpret`

The main command. Runs the full interpretation pipeline on a genome.

```bash
giae interpret INPUT_FILE [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `INPUT_FILE` | `Path` | required | `.gb`, `.gbk`, `.fa`, or `.fasta` |
| `-o`, `--output` | `Path` | stdout | Write report to file |
| `-f`, `--format` | `report` \| `json` \| `html` | `report` | Output format |
| `-w`, `--workers` | `int` (1–16) | `1` | Parallel workers |
| `--mode` | `online` \| `local` \| `offline` | `online` | Evidence pipeline mode |
| `--phage` | flag | off | Enable phage-aware nested ORF detection |
| `--no-cache` | flag | off | Disable disk caching of API responses |

#### `--mode` presets

| Mode | What's enabled | When to use |
|---|---|---|
| `offline` | PROSITE + bundled functional annotation only | Air-gapped runs, fastest, no network |
| `local` | offline + local BLAST / HMMER plugins (if installed) | Production, no API rate limits |
| `online` | local + UniProt + InterPro / EBI HMMER (cached) | Best quality, requires internet |

#### Examples

```bash
# Quick offline annotation
giae interpret lambda_phage.gb --mode offline

# Phage-aware mode for compact viral genomes
giae interpret phiX174.gb --phage --mode offline

# Full pipeline, parallel, HTML output
giae interpret bacterial.gb --mode online --workers 8 \
    --format html -o report.html

# JSON for downstream processing
giae interpret genome.gb --format json -o results.json
```

---

### `giae parse`

Parse a genome file and show basic stats — no interpretation.

```bash
giae parse INPUT_FILE [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `INPUT_FILE` | `Path` | required | `.gb`, `.gbk`, `.fa`, or `.fasta` |
| `-f`, `--format` | `summary` \| `detailed` | `summary` | Output verbosity |

```bash
giae parse lambda_phage.gb
# Genome: NC_001416 (Enterobacteria phage lambda)
# Length: 48,502 bp · GC: 49.9% · Genes: 92
```

---

### `giae analyze`

Run only the evidence-extraction layer. Useful for inspecting motif /
domain hits without committing to a hypothesis.

```bash
giae analyze INPUT_FILE
```

Output is a per-gene list of raw evidence with confidence weights. No
hypotheses, no aggregation, no scoring.

---

### `giae quick`

Quickly interpret a single raw sequence. No genome file needed.

```bash
giae quick SEQUENCE [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `SEQUENCE` | `str` | required | Nucleotide or protein sequence |
| `-t`, `--seq-type` | `nucleotide` \| `protein` | auto-detected | Sequence type |

```bash
giae quick MKVLIAGAGKSTFAM -t protein
giae quick ATGAAAGTACTGATCGCTGGTGCAGGTAAGTCTACCTTCGCTATG -t nucleotide
```

---

### `giae info`

Print GIAE's capabilities — version, bundled databases, optional
features detected.

```bash
giae info
```

```text
GIAE 0.2.2
  Bundled: PROSITE 1,298 patterns
  Optional capabilities:
    pyrodigal: ✅ available
    pyhmmer:   ❌ not installed
    diamond:   ✅ found at /opt/homebrew/bin/diamond
    aragorn:   ❌ not installed
    barrnap:   ❌ not installed
```

---

### `giae db`

Manage optional local databases for the plugin layer. The base
pipeline (PROSITE) needs no setup — `giae db` is only needed if you
want local BLAST, HMMER, or Diamond plugins.

#### `giae db status`

Show what's installed.

```bash
giae db status
```

#### `giae db download`

Download and prepare a database.

```bash
giae db download {prosite|swissprot|swissprot-diamond|pfam|esm} [--force]
```

| Database | Tool needed | Purpose |
|---|---|---|
| `prosite` | none | Updates the bundled PROSITE motif file from ExPASy |
| `swissprot` | `makeblastdb` (NCBI BLAST+) | Builds an NCBI BLAST DB from UniProt |
| `swissprot-diamond` | `diamond` | Builds a Diamond DB (~3× smaller than BLAST+) |
| `pfam` | `hmmpress` (HMMER3) | Sets up Pfam-A HMM database |
| `esm` | `fair-esm` Python package | Pre-warms the ESM-2 model cache |

```bash
# Examples
giae db download prosite
giae db download swissprot-diamond  # preferred over swissprot if Diamond is installed
giae db download pfam
giae db download swissprot --force  # re-install
```

---

### `giae serve`

Run the FastAPI HTTP server. Wraps `uvicorn`.

```bash
giae serve [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--host` | `str` | `127.0.0.1` | Bind host |
| `-p`, `--port` | `int` | `8000` | Bind port |
| `--reload` | flag | off | Auto-reload on code change (dev only) |
| `--workers` | `int` | `1` | Number of uvicorn worker processes (ignored when `--reload`) |

Requires the `[api]` extras: `pip install "giae[api]"`.

```bash
# Local development
giae serve --reload

# Production-style binding
giae serve --host 0.0.0.0 --port 8000 --workers 4
```

Set `JWT_SECRET` and `DATABASE_URL` via environment. See the
[deployment guide](deployment.md) for the full env-var list.

---

### `giae worker`

Run a Celery worker that processes interpretation jobs. Wraps
`celery worker`.

```bash
giae worker [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `-c`, `--concurrency` | `int` | `4` | Concurrent worker threads |
| `--pool` | `threads` \| `prefork` \| `solo` | `threads` | Celery executor pool |
| `--loglevel` | `debug` \| `info` \| `warning` \| `error` | `info` | Log level |

!!! warning "Use `threads`, not `prefork`, when HMMER or ESM-2 are enabled"
    `pyhmmer` and `torch` are C extensions that aren't fork-safe.
    The default `threads` pool is correct for the GIAE worker.

Requires Redis for the broker (`REDIS_URL` env var, default
`redis://localhost:6379/0`).

```bash
# Local development
giae worker --concurrency 2 --loglevel debug

# Production
giae worker --concurrency 8
```

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Generic error (parse failure, invalid input, etc.) |
| `2` | Click usage error (bad flag, missing argument) |
| `130` | Interrupted (Ctrl-C) |

---

## Environment variables

Most configuration is via flags. A few global env vars exist:

| Variable | Default | Used by |
|---|---|---|
| `GIAE_CACHE_DIR` | `~/.giae/cache` | `--no-cache` overrides per-invocation |
| `GIAE_DATA_DIR` | `~/.giae` | Local databases (BLAST, HMMER, Diamond) |
| `JWT_SECRET` | dev fallback | `giae serve` (refuses to boot in production without one) |
| `DATABASE_URL` | `postgresql+psycopg2://giae:giae@localhost:5432/giae` | `giae serve`, `giae worker` |
| `REDIS_URL` | `redis://localhost:6379/0` | `giae worker` (broker), `giae serve` (status check) |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | `60` | Token lifetime for `/api/v1/auth/login` |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,...` | `giae serve` CORS |
| `ENV` | `dev` | `giae serve` (`production` requires `JWT_SECRET`) |
| `BAKTA_DB` | — | Used by the Bakta comparison script (`post_assets/bakta_comparison.py`) |

[Full deployment guide →](deployment.md)
