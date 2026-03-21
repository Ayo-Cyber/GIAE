"""Tests for GIAE interpretation engine."""

from giae.engine.aggregator import (
    AggregatedEvidence,
    EvidenceAggregator,
    EvidenceWeights,
)
from giae.engine.confidence import ConfidenceReport, ConfidenceScorer, UncertaintySource
from giae.engine.hypothesis import FunctionalHypothesis, HypothesisGenerator
from giae.engine.interpreter import InterpretationResult, Interpreter
from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.gene import Gene, GeneLocation, Strand
from giae.models.interpretation import ConfidenceLevel
from giae.models.protein import Protein


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
        gene.add_evidence(create_test_evidence(gene.id, EvidenceType.BLAST_HOMOLOGY, 0.8))
        gene.add_evidence(create_test_evidence(gene.id, EvidenceType.MOTIF_MATCH, 0.6))

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
        gene1.add_evidence(create_test_evidence(gene1.id, EvidenceType.BLAST_HOMOLOGY, 0.9))

        gene2 = create_test_gene()
        gene2.add_evidence(create_test_evidence(gene2.id, EvidenceType.MOTIF_MATCH, 0.3))

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

    def test_merge_similar(self) -> None:
        """Test merging of similar hypotheses."""
        generator = HypothesisGenerator()
        h1 = FunctionalHypothesis("Kinase", "metabolism", 0.5, ["ev1"], ["r1"])
        h2 = FunctionalHypothesis("Kinase XYZ", "metabolism", 0.4, ["ev2"], ["r2"])
        h3 = FunctionalHypothesis("Transporter", "transport", 0.8, ["ev3"], ["r3"])

        merged = generator._merge_similar([h1, h2, h3])
        assert len(merged) == 2

    def test_combined_evidence(self) -> None:
        """Test generating from multiple evidence types."""
        generator = HypothesisGenerator()
        ev1 = create_test_evidence("g1", EvidenceType.BLAST_HOMOLOGY, 0.9)
        ev1.description = "DNA polymerase III"
        ev2 = create_test_evidence("g1", EvidenceType.MOTIF_MATCH, 0.8)
        ev2.description = "polymerase domain"

        aggregated = AggregatedEvidence(
            "g1",
            {EvidenceType.BLAST_HOMOLOGY: [ev1], EvidenceType.MOTIF_MATCH: [ev2]},
            {},
            1.7,
            2,
            2,
        )

        hyps = generator._hypotheses_from_combined(aggregated)
        assert len(hyps) > 0
        assert hyps[0].source_type == "COMBINED"


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

    def test_score_batch_and_explain(self) -> None:
        """Test batch scoring and explaining differences."""
        h1 = FunctionalHypothesis("Kinase", "metabolism", 0.9, ["ev1"], ["r1"])
        h2 = FunctionalHypothesis("Phosphatase", "metabolism", 0.4, ["ev2"], ["r2"])

        aggregated = AggregatedEvidence("g1", {}, {}, 1.0, 1, 1)
        scorer = ConfidenceScorer()

        reports = scorer.score_batch([h1, h2], aggregated)
        assert len(reports) == 2

        explanation = scorer.explain_differences(reports)
        assert "Comparison" in explanation
        assert "Hypothesis 1" in explanation


class TestInterpreter:
    """Tests for the main Interpreter."""

    def test_interpret_gene(self) -> None:
        """Test interpreting a single gene."""
        interpreter = Interpreter(use_uniprot=False)
        gene = create_test_gene()

        result = interpreter.interpret_gene(gene)

        assert isinstance(result, InterpretationResult)
        assert result.gene_id == gene.id
        assert result.success

    def test_quick_interpret(self) -> None:
        """Test quick interpretation of a sequence."""
        interpreter = Interpreter(use_uniprot=False)

        # Sequence with P-loop motif
        sequence = "MKVLIGXXXXGKSFAMKKKKKKKKKK"
        result = interpreter.quick_interpret(sequence, sequence_type="protein")

        assert isinstance(result, str)
        assert len(result) > 0


class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_full_pipeline(self) -> None:
        """Test the complete interpretation pipeline."""
        from pathlib import Path

        from giae.parsers import parse_genome

        # Use test fixture
        fixtures_dir = Path(__file__).parent / "fixtures"
        genome = parse_genome(fixtures_dir / "sample.gb")

        interpreter = Interpreter(use_uniprot=False)
        summary = interpreter.interpret_genome(genome)

        assert summary.genome_id == genome.id
        assert summary.total_genes == genome.gene_count
        assert summary.processing_time_seconds >= 0
