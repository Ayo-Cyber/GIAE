"""Tests for GIAE interpretation engine."""

import pytest

from giae.engine.aggregator import (
    EvidenceAggregator,
    EvidenceWeights,
    AggregatedEvidence,
)
from giae.engine.hypothesis import HypothesisGenerator, FunctionalHypothesis
from giae.engine.confidence import ConfidenceScorer, ConfidenceReport, UncertaintySource
from giae.engine.interpreter import Interpreter, InterpretationResult
from giae.models.gene import Gene, GeneLocation, Strand
from giae.models.protein import Protein
from giae.models.evidence import Evidence, EvidenceType, EvidenceProvenance
from giae.models.interpretation import ConfidenceLevel


def create_test_gene() -> Gene:
    """Create a test gene with some evidence."""
    gene = Gene(
        name="testGene",
        location=GeneLocation(start=0, end=300, strand=Strand.FORWARD),
        sequence="ATG" + "AAA" * 99,  # 300 bp
    )
    gene.protein = Protein(
        gene_id=gene.id,
        sequence="M" + "K" * 99,
    )
    return gene


def create_test_evidence(gene_id: str, etype: EvidenceType, confidence: float) -> Evidence:
    """Create test evidence."""
    provenance = EvidenceProvenance(tool_name="test", tool_version="1.0")
    return Evidence(
        evidence_type=etype,
        gene_id=gene_id,
        description=f"Test {etype.value} evidence",
        confidence=confidence,
        raw_data={"test": True},
        provenance=provenance,
    )


class TestEvidenceAggregator:
    """Tests for EvidenceAggregator."""

    def test_aggregate_empty_gene(self) -> None:
        """Test aggregating a gene with no evidence."""
        gene = create_test_gene()
        aggregator = EvidenceAggregator()
        result = aggregator.aggregate(gene)

        assert result.gene_id == gene.id
        assert result.evidence_count == 0
        assert result.total_weighted_score == 0

    def test_aggregate_with_evidence(self) -> None:
        """Test aggregating a gene with evidence."""
        gene = create_test_gene()
        gene.add_evidence(
            create_test_evidence(gene.id, EvidenceType.BLAST_HOMOLOGY, 0.8)
        )
        gene.add_evidence(
            create_test_evidence(gene.id, EvidenceType.MOTIF_MATCH, 0.6)
        )

        aggregator = EvidenceAggregator()
        result = aggregator.aggregate(gene)

        assert result.evidence_count == 2
        assert result.type_diversity == 2
        assert result.has_homology
        assert result.has_motifs

    def test_weighted_scores(self) -> None:
        """Test that evidence types are weighted correctly."""
        weights = EvidenceWeights()
        assert weights.get_weight(EvidenceType.BLAST_HOMOLOGY) == 1.0
        assert weights.get_weight(EvidenceType.MOTIF_MATCH) == 0.8

    def test_rank_genes(self) -> None:
        """Test ranking genes by evidence strength."""
        gene1 = create_test_gene()
        gene1.add_evidence(
            create_test_evidence(gene1.id, EvidenceType.BLAST_HOMOLOGY, 0.9)
        )

        gene2 = create_test_gene()
        gene2.add_evidence(
            create_test_evidence(gene2.id, EvidenceType.MOTIF_MATCH, 0.3)
        )

        aggregator = EvidenceAggregator()
        ranked = aggregator.rank_genes_by_evidence([gene1, gene2])

        assert len(ranked) == 2
        assert ranked[0][0].id == gene1.id  # Gene1 should be first


class TestHypothesisGenerator:
    """Tests for HypothesisGenerator."""

    def test_generate_no_evidence(self) -> None:
        """Test generating from empty evidence."""
        aggregated = AggregatedEvidence(
            gene_id="test",
            groups_by_type={},
            weighted_scores={},
            total_weighted_score=0,
            evidence_count=0,
            type_diversity=0,
        )

        generator = HypothesisGenerator()
        hypotheses = generator.generate(aggregated)

        assert len(hypotheses) == 0

    def test_categorize_function(self) -> None:
        """Test function categorization."""
        generator = HypothesisGenerator()

        assert generator._categorize_function("DNA polymerase") == "replication"
        assert generator._categorize_function("ATP synthase") == "metabolism"
        assert generator._categorize_function("membrane transporter") == "transport"
        assert generator._categorize_function("xyz protein") == "unknown"

    def test_motif_to_function(self) -> None:
        """Test motif to function mapping."""
        generator = HypothesisGenerator()

        assert "ATP" in generator._motif_to_function("atp_binding_p_loop")
        assert "DNA" in generator._motif_to_function("helix_turn_helix")


class TestConfidenceScorer:
    """Tests for ConfidenceScorer."""

    def test_score_hypothesis(self) -> None:
        """Test scoring a hypothesis."""
        hypothesis = FunctionalHypothesis(
            function="Test protein",
            category="unknown",
            confidence=0.7,
            supporting_evidence_ids=["ev1"],
            reasoning_steps=["Test reason"],
        )

        aggregated = AggregatedEvidence(
            gene_id="test",
            groups_by_type={},
            weighted_scores={},
            total_weighted_score=0.7,
            evidence_count=1,
            type_diversity=1,
        )

        scorer = ConfidenceScorer()
        report = scorer.score(hypothesis, aggregated)

        assert isinstance(report, ConfidenceReport)
        assert 0 <= report.adjusted_score <= 1
        assert report.confidence_level is not None

    def test_score_to_level(self) -> None:
        """Test numeric to level conversion."""
        scorer = ConfidenceScorer()

        assert scorer._score_to_level(0.85) == ConfidenceLevel.HIGH
        assert scorer._score_to_level(0.6) == ConfidenceLevel.MODERATE
        assert scorer._score_to_level(0.35) == ConfidenceLevel.LOW
        assert scorer._score_to_level(0.1) == ConfidenceLevel.SPECULATIVE

    def test_uncertainty_sources(self) -> None:
        """Test that uncertainty sources are tracked."""
        hypothesis = FunctionalHypothesis(
            function="Hypothetical protein",  # Should trigger uncertainty
            category="unknown",
            confidence=0.5,
            supporting_evidence_ids=["ev1"],
            reasoning_steps=["Test"],
        )

        aggregated = AggregatedEvidence(
            gene_id="test",
            groups_by_type={},
            weighted_scores={},
            total_weighted_score=0.5,
            evidence_count=1,
            type_diversity=1,
        )

        scorer = ConfidenceScorer()
        report = scorer.score(hypothesis, aggregated)

        assert UncertaintySource.HYPOTHETICAL_HOMOLOG in report.uncertainty_sources


class TestInterpreter:
    """Tests for the main Interpreter."""

    def test_interpret_gene(self) -> None:
        """Test interpreting a single gene."""
        interpreter = Interpreter()
        gene = create_test_gene()

        result = interpreter.interpret_gene(gene)

        assert isinstance(result, InterpretationResult)
        assert result.gene_id == gene.id
        assert result.success

    def test_quick_interpret(self) -> None:
        """Test quick interpretation of a sequence."""
        interpreter = Interpreter()

        # Sequence with P-loop motif
        sequence = "MKVLIGXXXXGKSFAMKKKKKKKKKK"
        result = interpreter.quick_interpret(sequence, sequence_type="protein")

        assert isinstance(result, str)
        assert len(result) > 0


class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_full_pipeline(self) -> None:
        """Test the complete interpretation pipeline."""
        from giae.parsers import parse_genome
        from pathlib import Path

        # Use test fixture
        fixtures_dir = Path(__file__).parent / "fixtures"
        genome = parse_genome(fixtures_dir / "sample.gb")

        interpreter = Interpreter()
        summary = interpreter.interpret_genome(genome)

        assert summary.genome_id == genome.id
        assert summary.total_genes == genome.gene_count
        assert summary.processing_time_seconds >= 0
