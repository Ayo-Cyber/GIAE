"""Phase 1 smoke test — compare gene counts across three modes.

Modes per genome:
  1. GenBank  — parser extracts annotated genes; ORF trigger fires only if sparse
  2. FASTA/pyrodigal — sequence only, pyrodigal predicts genes
  3. FASTA/naive     — sequence only, old six-frame ATG scanner (use_pyrodigal=False)

Run: .venv/bin/python post_assets/phase1_smoke_test.py
"""

from __future__ import annotations

from pathlib import Path

from Bio import SeqIO

from giae.analysis.orf_finder import ORFFinder
from giae.engine.interpreter import Interpreter
from giae.parsers.genbank import GenBankParser

CASE_DIR = Path(__file__).parent.parent / "case_studies"
GENOMES = ["phiX174.gb", "lambda_phage.gb", "T7.gb"]

parser = GenBankParser()

print(f"{'Genome':<18} {'Mode':<20} {'Genes':>6}  notes")
print("-" * 58)

for filename in GENOMES:
    gb_path = CASE_DIR / filename
    name = filename.replace(".gb", "")

    # --- Mode 1: GenBank (annotated) ---
    genome_gb = parser.parse(gb_path)
    annotated_count = len(genome_gb.genes)
    genome_length_kb = len(genome_gb.sequence) / 1000.0
    density = annotated_count / genome_length_kb if genome_length_kb else 0
    print(
        f"{name:<18} {'GenBank (annotated)':<20} {annotated_count:>6}"
        f"  ({genome_length_kb:.0f} kb, {density:.1f} g/kb)"
    )

    # --- Mode 2: FASTA / pyrodigal ---
    genome_fasta = parser.parse(gb_path)
    genome_fasta.genes.clear()
    genome_fasta.file_format = "fasta"

    orf_finder_pyrodigal = ORFFinder(use_pyrodigal=True)
    orfs = orf_finder_pyrodigal.find_orfs(genome_fasta.sequence)
    genes_pyrodigal = orf_finder_pyrodigal.orfs_to_genes(orfs)
    print(
        f"{name:<18} {'FASTA / pyrodigal':<20} {len(genes_pyrodigal):>6}"
    )

    # --- Mode 3: FASTA / naive scanner ---
    orf_finder_naive = ORFFinder(use_pyrodigal=False)
    orfs_naive = orf_finder_naive.find_orfs(genome_fasta.sequence)
    genes_naive = orf_finder_naive.orfs_to_genes(orfs_naive)
    print(
        f"{name:<18} {'FASTA / naive':<20} {len(genes_naive):>6}"
    )

    print()
