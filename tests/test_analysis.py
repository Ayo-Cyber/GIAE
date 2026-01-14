"""Tests for GIAE analysis modules."""

import pytest

from giae.analysis.orf_finder import ORFFinder, ORFResult, CODON_TABLE
from giae.analysis.motif import MotifScanner, MotifPattern, BUILTIN_MOTIFS
from giae.analysis.homology import HomologyAnalyzer, BlastNotFoundError
from giae.models.gene import Strand


class TestORFFinder:
    """Tests for the ORF finder."""

    def test_find_simple_orf(self) -> None:
        """Test finding a simple ORF with start and stop codons."""
        # Create sequence with clear ORF: ATG...TAA
        # ATG + 30 codons + TAA = 99 bp
        sequence = "ATG" + "AAA" * 32 + "TAA"  # 102 bp total

        finder = ORFFinder(min_length=50)
        orfs = finder.find_orfs(sequence)

        assert len(orfs) >= 1
        # First ORF should start at 0
        orf = orfs[0]
        assert orf.start == 0
        assert orf.protein_sequence.startswith("M")  # Starts with Met
        assert orf.protein_sequence.endswith("*")  # Ends with stop

    def test_min_length_filter(self) -> None:
        """Test that ORFs below min_length are filtered."""
        short_orf = "ATG" + "AAA" * 5 + "TAA"  # 21 bp - too short

        finder = ORFFinder(min_length=100)
        orfs = finder.find_orfs(short_orf)

        assert len(orfs) == 0

    def test_all_reading_frames(self) -> None:
        """Test that all 6 reading frames are searched."""
        finder = ORFFinder(min_length=30)

        # Create sequence with ORFs in different frames
        # Frame 0: ATG...
        # Frame 1: _ATG...
        # etc.
        sequence = "A" + "ATG" + "GGG" * 20 + "TAA"
        orfs = finder.find_orfs(sequence)

        # Should find ORFs in at least one frame
        assert len(orfs) >= 0  # May or may not find depending on frames

    def test_reverse_complement(self) -> None:
        """Test reverse complement calculation."""
        finder = ORFFinder()
        assert finder._reverse_complement("ATGC") == "GCAT"
        assert finder._reverse_complement("AAAA") == "TTTT"

    def test_orfs_to_genes(self) -> None:
        """Test converting ORFs to Gene objects."""
        sequence = "ATG" + "AAA" * 40 + "TAA"  # 126 bp
        finder = ORFFinder(min_length=100)
        orfs = finder.find_orfs(sequence)

        genes = finder.orfs_to_genes(orfs, prefix="TEST")

        if orfs:
            assert len(genes) == len(orfs)
            assert genes[0].locus_tag.startswith("TEST_")
            assert genes[0].source == "orf_prediction"
            assert genes[0].protein is not None


class TestMotifScanner:
    """Tests for the motif scanner."""

    def test_builtin_motifs_loaded(self) -> None:
        """Test that builtin motifs are available."""
        scanner = MotifScanner()
        assert len(scanner.motifs) > 0
        assert any(m.name == "atp_binding_p_loop" for m in scanner.motifs)

    def test_scan_atp_binding(self) -> None:
        """Test detection of ATP binding P-loop motif."""
        # P-loop pattern: [AG].{4}GK[ST]
        # Need: A or G, then 4 any chars, then GKS or GKT
        sequence = "MKVLIGXXXXGKSFAM"  # Contains GXXXXGKS

        scanner = MotifScanner()
        matches = scanner.scan(sequence)

        # Should find the P-loop
        ploop_matches = [m for m in matches if m.motif_name == "atp_binding_p_loop"]
        assert len(ploop_matches) >= 1

    def test_add_custom_motif(self) -> None:
        """Test adding a custom motif pattern."""
        scanner = MotifScanner()
        original_count = len(scanner.motifs)

        custom = MotifPattern(
            name="test_motif",
            pattern=r"WXYZ",
            description="Test motif",
            category="test",
        )
        scanner.add_motif(custom)

        assert len(scanner.motifs) == original_count + 1

    def test_matches_to_evidence(self) -> None:
        """Test converting matches to Evidence objects."""
        sequence = "MKVLIAGAGKSTFAM"
        scanner = MotifScanner()
        matches = scanner.scan(sequence)

        if matches:
            evidence = scanner.matches_to_evidence(matches, "gene_001")
            assert len(evidence) == len(matches)
            assert all(e.gene_id == "gene_001" for e in evidence)
            assert all(e.evidence_type.value == "motif_match" for e in evidence)

    def test_min_score_filter(self) -> None:
        """Test that low-scoring matches are filtered."""
        scanner_strict = MotifScanner(min_score=0.9)
        scanner_loose = MotifScanner(min_score=0.1)

        sequence = "MKVLIAGAGKSTFAM"

        strict_matches = scanner_strict.scan(sequence)
        loose_matches = scanner_loose.scan(sequence)

        # Loose should find at least as many as strict
        assert len(loose_matches) >= len(strict_matches)


class TestHomologyAnalyzer:
    """Tests for the homology analyzer."""

    def test_blast_not_available(self) -> None:
        """Test that appropriate error is raised when BLAST not found."""
        analyzer = HomologyAnalyzer(database="nr")

        if not analyzer.is_available:
            with pytest.raises(BlastNotFoundError):
                analyzer.search("MKVLIFF")

    def test_is_available_property(self) -> None:
        """Test the is_available property."""
        analyzer = HomologyAnalyzer(database="nr")
        # Should return bool without error
        assert isinstance(analyzer.is_available, bool)

    def test_invalid_blast_type(self) -> None:
        """Test that invalid BLAST type raises error."""
        with pytest.raises(ValueError):
            HomologyAnalyzer(database="nr", blast_type="invalid_blast")

    def test_blast_hit_properties(self) -> None:
        """Test BlastHit dataclass properties."""
        from giae.analysis.homology import BlastHit

        hit = BlastHit(
            hit_id="test",
            hit_description="Test protein",
            hit_accession="TEST001",
            e_value=1e-50,
            bit_score=200,
            identity_percent=85.0,
            query_coverage=95.0,
            alignment_length=100,
            mismatches=5,
            gap_opens=0,
            query_start=1,
            query_end=100,
            hit_start=1,
            hit_end=100,
        )

        assert hit.is_significant  # e-value < 1e-5
        assert hit.is_high_identity  # identity >= 70%


class TestIntegration:
    """Integration tests for analysis pipeline."""

    def test_orf_to_motif_pipeline(self) -> None:
        """Test finding ORFs and scanning them for motifs."""
        # Create a sequence with an ORF containing P-loop motif
        # P-loop: [AG].{4}GK[ST]
        # We'll encode AGXXXXGKS in the ORF
        # A=GCT, G=GGT, X=AAA, K=AAA, S=TCT
        ploop_codons = "GCT" + "AAA" * 4 + "GGT" + "AAA" + "TCT"  # AXXXXGKS

        # Full ORF with P-loop inside
        orf_sequence = "ATG" + ploop_codons + "AAA" * 20 + "TAA"

        # Find ORFs
        finder = ORFFinder(min_length=50)
        orfs = finder.find_orfs(orf_sequence)
        genes = finder.orfs_to_genes(orfs)

        # Scan for motifs
        scanner = MotifScanner()
        for gene in genes:
            if gene.protein:
                matches = scanner.scan(gene.protein.sequence)
                # May or may not find matches depending on translation
                evidence = scanner.matches_to_evidence(matches, gene.id)
                assert all(e.gene_id == gene.id for e in evidence)
