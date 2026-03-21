# Quickstart Guide

> **Time to complete:** ~5 minutes | **Skill level:** Beginner

This guide will take you from zero to your first genome annotation. By the end, you will have GIAE installed, have run it on a real genome, and know how to read the results.

---

## Step 1 — Install GIAE

You need Python 3.9 or newer. Open your terminal and run:

```bash
pip install giae
```

Verify it worked:

```bash
giae --version
```

You should see something like:

```
giae, version 0.3.0
```

!!! tip "Using a virtual environment?"
    If you are working inside a project, activate your environment first:
    ```bash
    python -m venv .venv && source .venv/bin/activate
    pip install giae
    ```

---

## Step 2 — Get a genome file

GIAE works with **GenBank (`.gb`, `.gbk`)** or **FASTA (`.fa`, `.fasta`)** files.

If you don't have one yet, download a small example — the Lambda phage genome (only 48 kb):

```bash
# Using curl
curl -o lambda_phage.gb "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_001416&rettype=gb&retmode=text"
```

Or grab it directly from [NCBI](https://www.ncbi.nlm.nih.gov/nuccore/NC_001416) → **Send to** → **Complete Record** → **GenBank format**.

---

## Step 3 — Run your first annotation

```bash
giae interpret lambda_phage.gb
```

That's it. GIAE will start processing and print progress to your terminal:

```
🔬 GIAE — Genome Interpretation and Annotation Engine
   Parsing genome: lambda_phage.gb
   Found 92 genes to interpret...

   [■■■■■■■■■■■■■■■          ] 68/92 genes (74%)

✅ Done in 38s — 92 genes interpreted
   Report saved to: lambda_phage_report.md
```

!!! note "First run is slower"
    On first run, GIAE contacts UniProt and InterPro to fetch the latest annotations. Subsequent runs on the same genome are much faster.

---

## Step 4 — Read the output

Open `lambda_phage_report.md` in any text editor or Markdown viewer.

Each gene gets a block like this:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Gene: cI  |  Locus: J02459_1_45516_46325_F
Interpretation: Repressor protein CI
Confidence: HIGH (87%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Evidence:
  ✔ UniProt: 96% identity to P03034 (Lambda repressor CI, E. coli)
  ✔ Motif: HTH_3 (Helix-Turn-Helix domain) detected
  ✔ Domain: cl21500 (lambda-phage repressor, N-terminal)

Reasoning:
  "Primary evidence strongly supports assignment as a lambda phage
   transcriptional repressor. The combination of HTH motif and high
   UniProt identity leaves little ambiguity."

Alternative Hypotheses Considered:
  - Cro-like repressor (23% confidence) — weaker motif match, rejected
```

### What the confidence score means

| Score | Label | What it means |
|-------|-------|---------------|
| 80–100% | **HIGH** | Multiple independent pieces of evidence agree |
| 50–79% | **MEDIUM** | Good signal, but some ambiguity remains |
| 20–49% | **LOW** | Weak or single evidence — treat as hypothesis |
| <20% | **NOVEL** | No known function found — possible discovery! |

---

## Step 5 — Get the rich HTML report (recommended)

The plain text report is good, but the **HTML report** is where GIAE really shines. It gives you an interactive, colour-coded view of your genome:

```bash
giae interpret lambda_phage.gb --format html -o lambda_report.html
```

Open `lambda_report.html` in any browser. You will see:

- 🟢 **Green** genes: HIGH confidence annotations
- 🟡 **Yellow** genes: MEDIUM confidence — worth a second look
- 🔴 **Red** genes: LOW confidence or NOVEL — research targets
- A full reasoning chain for every gene
- Alternative hypotheses you can explore

---

## Common options

| Flag | What it does | Example |
|------|-------------|---------|
| `-o FILE` | Save output to a specific file | `-o my_results.md` |
| `--format` | Choose output format (`md`, `json`, `html`) | `--format json` |
| `--workers N` | Run N genes in parallel (faster on big genomes) | `--workers 4` |
| `--no-uniprot` | Skip UniProt lookup (offline mode) | `--no-uniprot` |
| `--no-interpro` | Skip InterPro lookup (offline mode) | `--no-interpro` |

---

## Next Steps

- 📖 **[Full Tutorial](tutorials/phage.md)**: Walk through a complete phage genome analysis with expert commentary
- 🔌 **[API Reference](api.md)**: Use GIAE as a Python library in your own scripts
- 🗺️ **[Roadmap](roadmap.md)**: See what's coming next
