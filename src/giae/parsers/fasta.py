"""FASTA file parser for GIAE."""

from __future__ import annotations

from pathlib import Path

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

from giae.models.genome import Genome, GenomeMetadata
from giae.parsers.base import BaseParser, ParserError


class FastaParser(BaseParser):
    """
    Parser for FASTA format genome files.

    FASTA files contain raw sequences without annotation.
    For these files, genes must be predicted (e.g., via ORF finding)
    rather than extracted from existing annotations.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """File extensions this parser supports."""
        return (".fasta", ".fa", ".fna", ".ffn", ".faa")

    @property
    def format_name(self) -> str:
        """Name of the format this parser handles."""
        return "fasta"

    def parse(self, file_path: Path) -> Genome:
        """
        Parse a FASTA file and return a Genome object.

        For multi-record FASTA files, only the first record is used
        as the primary genome sequence. Use parse_multi for handling
        multiple sequences.

        Args:
            file_path: Path to the FASTA file.

        Returns:
            A Genome object with the sequence loaded.

        Raises:
            ParserError: If parsing fails.
        """
        try:
            records = list(SeqIO.parse(file_path, "fasta"))
        except Exception as e:
            raise ParserError(f"Failed to parse FASTA file: {e}", file_path) from e

        if not records:
            raise ParserError("FASTA file contains no sequences", file_path)

        # Use first record as primary genome
        primary_record = records[0]

        return self._record_to_genome(primary_record, file_path)

    def parse_multi(self, file_path: Path) -> list[Genome]:
        """
        Parse a multi-record FASTA file.

        Args:
            file_path: Path to the FASTA file.

        Returns:
            List of Genome objects, one per record.

        Raises:
            ParserError: If parsing fails.
        """
        try:
            records = list(SeqIO.parse(file_path, "fasta"))
        except Exception as e:
            raise ParserError(f"Failed to parse FASTA file: {e}", file_path) from e

        if not records:
            raise ParserError("FASTA file contains no sequences", file_path)

        return [self._record_to_genome(record, file_path) for record in records]

    def _record_to_genome(self, record: SeqRecord, file_path: Path) -> Genome:
        """Convert a BioPython SeqRecord to a Genome object."""
        # Extract name from record ID
        name = record.id

        # Description is everything after the ID in the header
        description = record.description
        if record.id and description.startswith(record.id):
            description = description[len(record.id) :].strip()

        # Parse organism from description if present (common format: [Organism name])
        organism = None
        if "[" in description and "]" in description:
            start = description.rfind("[")
            end = description.rfind("]")
            if start < end:
                organism = description[start + 1 : end]

        sequence = str(record.seq).upper()

        # Validate sequence
        valid_bases = {"A", "T", "G", "C", "N", "R", "Y", "S", "W", "K", "M", "B", "D", "H", "V"}
        sequence_bases = set(sequence)
        invalid = sequence_bases - valid_bases

        if invalid:
            raise ParserError(
                f"Invalid characters in sequence: {invalid}. "
                f"FASTA should contain nucleotides only.",
                file_path,
            )

        metadata = GenomeMetadata(
            organism=organism,
            definition=record.description,
        )

        return Genome(
            name=str(name),
            description=description,
            sequence=sequence,
            source_file=file_path,
            file_format="fasta",
            metadata=metadata,
        )
