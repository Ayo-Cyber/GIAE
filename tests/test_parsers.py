"""Tests for GIAE parsers."""

from pathlib import Path

import pytest

from giae.parsers import detect_format, parse_genome
from giae.parsers.fasta import FastaParser
from giae.parsers.genbank import GenBankParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestFormatDetection:
    """Tests for file format detection."""

    def test_detect_fasta_by_extension(self) -> None:
        """Test FASTA detection by extension."""
        assert detect_format(FIXTURES_DIR / "sample.fasta") == "fasta"

    def test_detect_genbank_by_extension(self) -> None:
        """Test GenBank detection by extension."""
        assert detect_format(FIXTURES_DIR / "sample.gb") == "genbank"


class TestFastaParser:
    """Tests for the FASTA parser."""

    def test_parse_fasta(self) -> None:
        """Test parsing a FASTA file."""
        parser = FastaParser()
        genome = parser.parse(FIXTURES_DIR / "sample.fasta")

        assert genome.name == "sample_sequence"
        assert genome.file_format == "fasta"
        assert genome.length > 0
        assert set(genome.sequence) <= {"A", "T", "G", "C", "N"}

    def test_fasta_extensions(self) -> None:
        """Test supported extensions."""
        parser = FastaParser()
        assert ".fasta" in parser.supported_extensions
        assert ".fa" in parser.supported_extensions


class TestGenBankParser:
    """Tests for the GenBank parser."""

    def test_parse_genbank(self) -> None:
        """Test parsing a GenBank file."""
        parser = GenBankParser()
        genome = parser.parse(FIXTURES_DIR / "sample.gb")

        assert genome.file_format == "genbank"
        assert genome.length > 0
        assert genome.gene_count >= 0  # May have genes

    def test_extract_metadata(self) -> None:
        """Test metadata extraction from GenBank."""
        parser = GenBankParser()
        genome = parser.parse(FIXTURES_DIR / "sample.gb")

        # Should have organism from source feature
        assert genome.metadata.organism is not None or genome.description

    def test_genbank_extensions(self) -> None:
        """Test supported extensions."""
        parser = GenBankParser()
        assert ".gb" in parser.supported_extensions
        assert ".gbk" in parser.supported_extensions


class TestUnifiedParser:
    """Tests for the unified parse_genome function."""

    def test_parse_genome_fasta(self) -> None:
        """Test parsing FASTA via unified interface."""
        genome = parse_genome(FIXTURES_DIR / "sample.fasta")
        assert genome.file_format == "fasta"

    def test_parse_genome_genbank(self) -> None:
        """Test parsing GenBank via unified interface."""
        genome = parse_genome(FIXTURES_DIR / "sample.gb")
        assert genome.file_format == "genbank"

    def test_file_not_found(self) -> None:
        """Test error handling for missing files."""
        with pytest.raises(FileNotFoundError):
            parse_genome("nonexistent.fasta")

    def test_parse_genome_string_path(self) -> None:
        """Test parsing with string path."""
        genome = parse_genome(str(FIXTURES_DIR / "sample.fasta"))
        assert genome.file_format == "fasta"
