# GIAE — Genome Interpretation & Annotation Engine

**Explainability-first genome annotation. Every prediction shows its reasoning.**

Most genome annotation tools are overconfident. PROKKA, Bakta, and RAST assign a label, hide the evidence, and give you no way to know how certain the prediction is. 

**GIAE** takes the opposite approach: every gene interpretation includes the full evidence stack, confidence score, uncertainty sources, and a ranked list of competing hypotheses.

---

## 🚀 Key Features

*   **Multi-layer Evidence**: PROSITE motifs, EBI HMMER domains, and UniProt reviews.
*   **Confidence Levels**: Calibrated scores (`HIGH`, `MODERATE`, `LOW`, `SPECULATIVE`).
*   **Explainable Reporting**: Narrative reasoning for every prediction.
*   **Novel Gene Discovery**: Identifying and ranking "Dark Matter" genes.
*   **Parallel Execution**: Scalable to large genomes.
*   **Flexible Output**: Terminal tables, Markdown, and machine-readable JSON.

---

## 🛠️ Installation

```bash
pip install giae
```

---

## 📖 How it Works

GIAE uses a **convergence model**. When multiple independent evidence sources (motifs, domains, homology) agree on a function, the confidence is high. When they disagree, GIAE flags the conflict rather than silently resolving it.

```text
Genome (.gb / .fasta)
       │
       ▼
┌──────────────────────────────────────────────┐
│  1. PROSITE Motif Scan         weight: 0.80  │
│  2. EBI HMMER / Pfam Domains   weight: 0.90  │
│  3. UniProt API Lookup         weight: 1.00  │
│  4. Conflict Detection                        │
└──────────────────────────────────────────────┘
       │
       ▼
Interpretation + Confidence Score + Novelty Report
```
