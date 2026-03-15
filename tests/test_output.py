"""Tests for GIAE output generation and formatting."""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from giae.models.genome import Genome, GenomeMetadata
from giae.models.gene import Gene, GeneLocation, Strand
from giae.models.evidence import Evidence, EvidenceType, EvidenceProvenance
from giae.models.interpretation import Interpretation, ConfidenceLevel
from giae.engine.interpreter import GenomeInterpretationSummary, InterpretationResult
from giae.engine.aggregator import AggregatedEvidence
from giae.output.report import ReportGenerator
from giae.output.reasoning import ReasoningEngine
from giae.output.json_export import (
    export_genome_json,
    export_interpretation_json,
    export_evidence_json,
)

def _create_sample_genome() -> Genome:
    genome = Genome(
        name="Test Organism",
        sequence="ATGCATGC",
        source_file=Path("test.fasta"),
        file_format="fasta",
        metadata=GenomeMetadata(organism="Escherichia coli", taxonomy_id="562")
    )
    
    gene = Gene(
        name="dnaE",
        location=GeneLocation(start=0, end=9, strand=Strand.FORWARD),
        sequence="ATG"
    )
    
    ev = Evidence(
        evidence_type=EvidenceType.BLAST_HOMOLOGY,
        gene_id=gene.id,
        description="DNA polymerase III alpha subunit",
        confidence=0.9,
        raw_data={},
        provenance=EvidenceProvenance(tool_name="test", tool_version="1.0")
    )
    gene.add_evidence(ev)
    
    interp = Interpretation(
        gene_id=gene.id,
        hypothesis="DNA polymerase III",
        confidence_score=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        supporting_evidence_ids=[ev.id],
        reasoning_chain=["Reason 1", "Reason 2"]
    )
    gene.add_interpretation(interp)
    genome.add_gene(gene)
    
    return genome

def _create_sample_summary(genome: Genome) -> GenomeInterpretationSummary:
    gene = genome.genes[0]
    result = InterpretationResult(
        gene_id=gene.id,
        gene_name=gene.display_name,
        interpretation=gene.interpretations[0],
        hypotheses=[],
        confidence_reports=[],
        aggregated_evidence=None,
        success=True
    )
    return GenomeInterpretationSummary(
        genome_id=genome.id,
        genome_name=genome.name,
        total_genes=1,
        interpreted_genes=1,
        high_confidence_count=1,
        moderate_confidence_count=0,
        low_confidence_count=0,
        failed_genes=0,
        processing_time_seconds=1.5,
        results=[result]
    )


class TestJSONExport:
    def test_export_genome_json(self):
        genome = _create_sample_genome()
        json_str = export_genome_json(genome, include_sequence=True)
        data = json.loads(json_str)
        
        assert data["name"] == "Test Organism"
        assert data["metadata"]["organism"] == "Escherichia coli"
        assert "sequence" in data
        assert len(data["genes"]) == 1
        
    def test_export_interpretation_json(self):
        genome = _create_sample_genome()
        summary = _create_sample_summary(genome)
        json_str = export_interpretation_json(summary)
        data = json.loads(json_str)
        
        assert data["statistics"]["total_genes"] == 1
        assert data["statistics"]["high_confidence"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["interpretation"]["hypothesis"] == "DNA polymerase III"

    def test_export_evidence_json(self):
        genome = _create_sample_genome()
        json_str = export_evidence_json(genome.genes[0].evidence)
        data = json.loads(json_str)
        
        assert len(data) == 1
        assert data[0]["evidence_type"] == EvidenceType.BLAST_HOMOLOGY.value


class TestReportGenerator:
    def test_generate_report(self):
        generator = ReportGenerator()
        genome = _create_sample_genome()
        summary = _create_sample_summary(genome)
        
        report = generator.generate(genome, summary)
        
        assert "# Genome Interpretation Report" in report
        assert "Test Organism" in report
        assert "DNA polymerase III" in report
        assert "High Confidence Interpretations" in report
        assert "Escherichia coli" in report
        assert "Methodology" in report


class TestReasoningEngine:
    def test_generate_narrative_high_confidence(self):
        engine = ReasoningEngine()
        genome = _create_sample_genome()
        interp = genome.genes[0].interpretations[0]
        
        narrative = engine.generate_narrative(interp)
        assert "very high confidence" in narrative.lower() or "strongly suggests" in narrative.lower()

    def test_generate_narrative_with_conflict(self):
        engine = ReasoningEngine()
        genome = _create_sample_genome()
        interp = genome.genes[0].interpretations[0]
        interp.hypothesis = "Ambiguous: Kinase vs Phosphatase"
        
        narrative = engine.generate_narrative(interp)
        assert "ambiguous" in narrative.lower()

    def test_generate_narrative_with_caveats(self):
        engine = ReasoningEngine()
        genome = _create_sample_genome()
        interp = genome.genes[0].interpretations[0]
        interp.uncertainty_sources = ["conflicting_evidence"]
        
        narrative = engine.generate_narrative(interp)
        assert "conflicting signal" in narrative.lower()
