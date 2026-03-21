# API Reference

GIAE is designed to be used both as a CLI tool and a Python library. This page documents the core data models and interpretation engine.

---

## 🧬 Core Models

### `Genome`
The top-level container for a genomic sequence and its annotations.

**Key Attributes:**
- `id`: Unique identifier (UUID-based).
- `name`: Short name for the genome.
- `sequence`: The raw nucleotide sequence (BioPython compatible).
- `genes`: A list of `Gene` objects.

**Key Methods:**
- `add_gene(gene)`: Add a new gene to the genome.
- `get_summary()`: Returns a dictionary with GC content, gene count, etc.

---

### `Gene`
Represents a single feature (CDS, tRNA, etc.) with its location and translations.

**Key Attributes:**
- `id`: Unique identifier.
- `location`: Start/End position and strand.
- `protein`: A `Protein` object containing the translation.
- `evidence`: A list of `Evidence` objects extracted during interpretation.

---

## 🧠 Interpretation Engine

### `Interpreter`
The primary orchestrator for the GIAE pipeline.

**Initialization:**
```python
from giae.engine.interpreter import Interpreter
interpreter = Interpreter()
```

**Workflow:**
1. **ORF Finding**: If input is FASTA, identifies potential genes.
2. **Evidence Extraction**: Scans motifs and runs plugins (HMMER, BLAST).
3. **Aggregation**: Merges overlapping evidence signals.
4. **Hypothesis Generation**: Proposes functions based on evidence.
5. **Confidence Scoring**: Calibrates the final interpretation.

---

## 🔌 Plugins

GIAE is extensible via the `Plugin` interface.

### `HmmerPlugin`
Integrates local HMMER3 searches against Pfam.

### `BlastLocalPlugin`
Integrates local BLAST+ searches against Swiss-Prot or custom databases.

### `EsmPlugin`
Uses the **ESM-2** deep learning model for sequence feature extraction (requires PyTorch).
