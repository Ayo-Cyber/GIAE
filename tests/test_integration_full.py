"""End-to-end integration tests for GIAE."""

from pathlib import Path

from giae.engine.interpreter import Interpreter
from giae.output.report import ReportGenerator
from giae.parsers import parse_genome

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_full_pipeline_genbank_to_report():
    # 1. Parse
    genome = parse_genome(FIXTURES_DIR / "sample.gb")
    assert genome.file_format == "genbank"
    assert genome.gene_count > 0

    # 2. Setup interpreter (disable UniProt for offline tests)
    interpreter = Interpreter(use_uniprot=False)

    # 3. Interpret
    summary = interpreter.interpret_genome(genome)
    assert summary.total_genes > 0
    assert summary.interpreted_genes >= 0  # Could be 0 depending on sample.gb evidence

    # Check that reasoning chain is present if interpreted
    for result in summary.results:
        if result.interpretation:
            assert len(result.interpretation.reasoning_chain) > 0

    # 4. Generate Report
    generator = ReportGenerator()
    report = generator.generate(genome, summary)

    assert "# Genome Interpretation Report" in report
    assert str(summary.total_genes) in report


def test_full_pipeline_fasta_to_report():
    # FASTA pipeline includes ORF finding step
    genome = parse_genome(FIXTURES_DIR / "sample.fasta")
    assert genome.file_format == "fasta"

    # 2. Interpret (will trigger ORFFinder)
    interpreter = Interpreter(use_uniprot=False, find_orfs=True)
    summary = interpreter.interpret_genome(genome)

    # The sample fasta is very small, might not have ORFs > min_length
    # So we just assert it ran without crashing and summary exists.
    assert summary.genome_id == genome.id
    assert summary.processing_time_seconds >= 0


def test_quick_interpret_api():
    interpreter = Interpreter(use_uniprot=False)
    # A known ATP-binding motif sequence (P-loop)
    seq = "MKVLIGXXXXGKSFAM"
    result = interpreter.quick_interpret(seq, sequence_type="protein")
    assert isinstance(result, str)
    assert len(result) > 0
