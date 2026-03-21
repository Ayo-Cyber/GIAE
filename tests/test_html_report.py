import pytest
from pathlib import Path
from giae.models.genome import Genome
from giae.engine.interpreter import GenomeInterpretationSummary, InterpretationResult
from giae.output.html_report import HTMLReportGenerator

def test_html_generator_smoke():
    genome = Genome(
        id="test",
        name="Test Genome",
        sequence="ATGC",
        source_file=Path("test.fasta"),
        file_format="fasta"
    )
    summary = GenomeInterpretationSummary(
        genome_id="test",
        genome_name="Test Genome",
        total_genes=1,
        interpreted_genes=1,
        high_confidence_count=1,
        moderate_confidence_count=0,
        low_confidence_count=0,
        failed_genes=0,
        processing_time_seconds=1.0,
        results=[]
    )
    
    generator = HTMLReportGenerator()
    html = generator.generate(genome, summary)
    
    assert "Test Genome" in html
    assert "GIAE Genome Interpretation Report" in html
    assert "Gene Explorer" in html
    assert "<style>" in html
    assert "<script>" in html

def test_html_generator_no_results():
    genome = Genome(
        id="empty",
        name="Empty",
        sequence="",
        source_file=Path("empty.fasta"),
        file_format="fasta"
    )
    summary = GenomeInterpretationSummary(
        genome_id="empty",
        genome_name="Empty",
        total_genes=0,
        interpreted_genes=0,
        high_confidence_count=0,
        moderate_confidence_count=0,
        low_confidence_count=0,
        failed_genes=0,
        processing_time_seconds=0.1,
        results=[]
    )
    
    generator = HTMLReportGenerator()
    html = generator.generate(genome, summary)
    assert "Empty" in html
