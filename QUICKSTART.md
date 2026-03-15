# GIAE Quickstart Guide

Get started with the Genome Interpretation & Annotation Engine in under 5 minutes.

---

## Installation

```bash
pip install giae
```

This installs GIAE with all core dependencies (BioPython, NumPy, Click, Rich) and a bundled PROSITE pattern database (~1,800 patterns).

### For Development

```bash
git clone https://github.com/Ayo-Cyber/GIAE.git
cd GIAE
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
pip install -e ".[dev]"
```

---

## Your First Interpretation

### From a GenBank File

```bash
giae interpret genome.gb -o report.md
```

### From a FASTA File

```bash
giae interpret sequence.fasta -o report.md
```

### Quick Sequence Check

```bash
giae quick MKVLIAGAGKSTFAM -t protein
```

---

## Useful Commands

| Command | What It Does |
|---------|-------------|
| `giae parse genome.gb` | Parse and show genome info |
| `giae interpret genome.gb` | Full interpretation pipeline |
| `giae interpret genome.gb -w 4` | Parallel interpretation (4 workers) |
| `giae interpret genome.gb --no-uniprot` | Skip online searches (faster) |
| `giae analyze genome.gb` | Evidence extraction only |
| `giae quick SEQUENCE` | Quick single-sequence check |
| `giae info` | Show GIAE capabilities |
| `giae db status` | Check installed databases |
| `giae -v interpret genome.gb` | Verbose output |
| `giae --debug interpret genome.gb` | Full debug logging |

---

## Output Options

```bash
# Markdown report (default)
giae interpret genome.gb -o report.md

# JSON output
giae interpret genome.gb -f json -o results.json
```

---

## Optional: Install BLAST+ for Better Results

BLAST+ enables homology-based evidence, significantly improving interpretation quality.

```bash
# macOS
brew install blast

# Ubuntu/Debian
sudo apt install ncbi-blast+

# Then download the SwissProt database
giae db download swissprot
```

---

## Check Your Setup

```bash
giae db status
```

This shows which databases and tools are available:
- ✅ PROSITE (bundled with GIAE)
- BLAST+ (optional, install separately)
- HMMER (optional, install separately)

---

## Example: Lambda Phage

GIAE ships with a Lambda phage case study:

```bash
# If running from source
giae interpret case_studies/lambda_phage.gb -o lambda_report.md
```

This analyzes 92 genes and produces a full interpretation report with confidence scores and reasoning chains.
