"""Tests for GIAE data models."""

from pathlib import Path

import pytest

from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.gene import Gene, GeneLocation, Strand
from giae.models.genome import Genome
from giae.models.interpretation import (
    ConfidenceLevel,
    Interpretation,
)
from giae.models.protein import Protein


class TestEvidence:
    """Tests for the Evidence model."""

    def test_create_evidence(self) -> None:
        """Test creating a valid Evidence object."""
        provenance = EvidenceProvenance(
            tool_name="blastp",
            tool_version="2.15.0",
            database="nr",
        )
        evidence = Evidence(
            evidence_type=EvidenceType.BLAST_HOMOLOGY,
            gene_id="gene_001",
            description="85% identity to E. coli DnaE",
            confidence=0.85,
            raw_data={"e_value": 1e-50},
            provenance=provenance,
        )

        assert evidence.evidence_type == EvidenceType.BLAST_HOMOLOGY
        assert evidence.confidence == 0.85
        assert evidence.id.startswith("ev_")

    def test_confidence_validation(self) -> None:
        """Test that confidence must be between 0 and 1."""
        provenance = EvidenceProvenance(tool_name="test", tool_version="1.0")

        with pytest.raises(ValueError):
            Evidence(
                evidence_type=EvidenceType.MOTIF_MATCH,
                gene_id="gene_001",
                description="Test",
                confidence=1.5,  # Invalid
                raw_data={},
                provenance=provenance,
            )

    def test_serialization(self) -> None:
        """Test Evidence serialization round-trip."""
        provenance = EvidenceProvenance(
            tool_name="test",
            tool_version="1.0",
        )
        original = Evidence(
            evidence_type=EvidenceType.ORF_PREDICTION,
            gene_id="gene_001",
            description="Predicted ORF",
            confidence=0.9,
            raw_data={"length": 300},
            provenance=provenance,
        )

        data = original.to_dict()
        restored = Evidence.from_dict(data)

        assert restored.id == original.id
        assert restored.evidence_type == original.evidence_type
        assert restored.confidence == original.confidence


class TestInterpretation:
    """Tests for the Interpretation model."""

    def test_create_interpretation(self) -> None:
        """Test creating a valid Interpretation object."""
        interpretation = Interpretation(
            gene_id="gene_001",
            hypothesis="DNA polymerase III alpha subunit",
            confidence_score=0.82,
            confidence_level=ConfidenceLevel.HIGH,
            supporting_evidence_ids=["ev_abc", "ev_def"],
            reasoning_chain=["BLAST hit to E. coli dnaE", "Contains polymerase domain"],
        )

        assert interpretation.hypothesis == "DNA polymerase III alpha subunit"
        assert interpretation.is_high_confidence
        assert interpretation.id.startswith("int_")

    def test_must_have_reasoning(self) -> None:
        """Test that interpretation must have reasoning."""
        with pytest.raises(ValueError):
            Interpretation(
                gene_id="gene_001",
                hypothesis="Test",
                confidence_score=0.5,
                confidence_level=ConfidenceLevel.MODERATE,
                supporting_evidence_ids=[],
                reasoning_chain=[],  # Empty - invalid
            )

    def test_get_explanation(self) -> None:
        """Test human-readable explanation generation."""
        interpretation = Interpretation(
            gene_id="gene_001",
            hypothesis="Helicase",
            confidence_score=0.7,
            confidence_level=ConfidenceLevel.MODERATE,
            supporting_evidence_ids=["ev_1"],
            reasoning_chain=["Domain match found"],
            uncertainty_sources=["Low sequence coverage"],
        )

        explanation = interpretation.get_explanation()
        assert "Helicase" in explanation
        assert "70%" in explanation
        assert "Low sequence coverage" in explanation

    def test_serialization(self) -> None:
        """Test Interpretation serialization round-trip."""
        original = Interpretation(
            gene_id="gene_001",
            hypothesis="Helicase",
            confidence_score=0.7,
            confidence_level=ConfidenceLevel.MODERATE,
            supporting_evidence_ids=["ev_1"],
            reasoning_chain=["Domain match found"],
        )
        data = original.to_dict()
        restored = Interpretation.from_dict(data)

        assert restored.id == original.id
        assert restored.hypothesis == original.hypothesis
        assert restored.confidence_score == original.confidence_score

    def test_get_summary(self) -> None:
        """Test getting interpretation summary."""
        interpretation = Interpretation(
            gene_id="g_1",
            hypothesis="XYZ",
            confidence_score=0.5,
            confidence_level=ConfidenceLevel.MODERATE,
            supporting_evidence_ids=[],
            reasoning_chain=["1"],
        )
        assert "XYZ" in interpretation.get_summary()
        assert "50%" in interpretation.get_summary()


class TestProtein:
    """Tests for the Protein model."""

    def test_create_protein(self) -> None:
        """Test creating a valid Protein object."""
        protein = Protein(
            gene_id="gene_001",
            sequence="MKFLILLFNILCLFPVLAADNHGVGPQGAS",
        )

        assert protein.length == 30
        assert protein.molecular_weight > 0

    def test_molecular_weight(self) -> None:
        """Test molecular weight calculation."""
        protein = Protein(gene_id="gene_001", sequence="MAAAA")
        # Should be sum of weights minus water for peptide bonds
        assert protein.molecular_weight > 400

    def test_invalid_sequence(self) -> None:
        """Test that invalid amino acids raise error."""
        with pytest.raises(ValueError):
            Protein(gene_id="gene_001", sequence="MXZJB123")


class TestGene:
    """Tests for the Gene model."""

    def test_create_gene(self) -> None:
        """Test creating a valid Gene object."""
        location = GeneLocation(start=100, end=400, strand=Strand.FORWARD)
        gene = Gene(
            name="testA",
            location=location,
            sequence="ATGCGTACG" * 33 + "A",  # 300 bp
        )

        assert gene.display_name == "testA"
        assert gene.length == 298
        assert gene.strand == Strand.FORWARD

    def test_gene_location_validation(self) -> None:
        """Test that invalid locations raise errors."""
        with pytest.raises(ValueError):
            GeneLocation(start=400, end=100, strand=Strand.FORWARD)

    def test_add_evidence_and_interpretation(self) -> None:
        gene = Gene(
            name="test",
            location=GeneLocation(start=1, end=10, strand=Strand.FORWARD),
            sequence="A" * 10,
        )

        ev = Evidence(
            evidence_type=EvidenceType.MOTIF_MATCH,
            gene_id=gene.id,
            description="test",
            confidence=0.5,
            raw_data={},
            provenance=EvidenceProvenance(tool_name="test", tool_version="1.0"),
        )
        gene.add_evidence(ev)
        assert len(gene.evidence) == 1

        interp = Interpretation(
            gene_id=gene.id,
            hypothesis="test",
            confidence_score=0.5,
            confidence_level=ConfidenceLevel.MODERATE,
            supporting_evidence_ids=[],
            reasoning_chain=["1"],
        )
        gene.add_interpretation(interp)
        assert len(gene.interpretations) == 1


class TestGenome:
    """Tests for the Genome model."""

    def test_create_genome(self) -> None:
        """Test creating a valid Genome object."""
        genome = Genome(
            name="TestGenome",
            sequence="ATGCATGCATGC" * 100,
            source_file=Path("test.fasta"),
            file_format="fasta",
        )

        assert genome.length == 1200
        assert genome.gc_content == 50.0
        assert genome.gene_count == 0

    def test_gc_content(self) -> None:
        """Test GC content calculation."""
        genome = Genome(
            name="Test",
            sequence="GGCCGGCC",  # 100% GC
            source_file=Path("test.fasta"),
            file_format="fasta",
        )
        assert genome.gc_content == 100.0

    def test_invalid_format(self) -> None:
        """Test that invalid format raises error."""
        with pytest.raises(ValueError):
            Genome(
                name="Test",
                sequence="ATGC",
                source_file=Path("test.xyz"),
                file_format="xyz",  # Invalid
            )

    def test_add_gene(self) -> None:
        genome = Genome(
            name="Test", sequence="A" * 100, source_file=Path("test.gb"), file_format="genbank"
        )
        gene = Gene(name="g1", location=GeneLocation(1, 10, Strand.FORWARD), sequence="A" * 10)
        genome.add_gene(gene)
        assert genome.gene_count == 1
        assert len(genome.genes) == 1
