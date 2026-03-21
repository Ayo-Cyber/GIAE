"""Base parser interface and utilities for GIAE."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from giae.models.genome import Genome


class ParserError(Exception):
    """Raised when parsing fails."""

    def __init__(self, message: str, file_path: Path | None = None) -> None:
        self.file_path = file_path
        super().__init__(message)


class BaseParser(ABC):
    """Abstract base class for genome file parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """File extensions this parser supports."""
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Name of the format this parser handles."""
        ...

    @abstractmethod
    def parse(self, file_path: Path) -> Genome:
        """
        Parse a genome file and return a Genome object.

        Args:
            file_path: Path to the input file.

        Returns:
            A fully populated Genome object.

        Raises:
            ParserError: If parsing fails.
        """
        ...

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file."""
        return file_path.suffix.lower() in self.supported_extensions


def detect_format(file_path: Path) -> str:
    """
    Detect the format of a genome file.

    Args:
        file_path: Path to the input file.

    Returns:
        Format name: "fasta" or "genbank".

    Raises:
        ParserError: If format cannot be detected.
    """
    suffix = file_path.suffix.lower()

    fasta_extensions = {".fasta", ".fa", ".fna", ".ffn", ".faa"}
    genbank_extensions = {".gb", ".gbk", ".genbank", ".gbff"}

    if suffix in fasta_extensions:
        return "fasta"
    elif suffix in genbank_extensions:
        return "genbank"

    # Try to detect by content
    try:
        with open(file_path) as f:
            first_line = f.readline().strip()

        if first_line.startswith(">"):
            return "fasta"
        elif first_line.startswith("LOCUS"):
            return "genbank"

    except Exception as e:
        raise ParserError(f"Could not read file to detect format: {e}", file_path) from e

    raise ParserError(f"Could not detect format for file: {file_path}", file_path)


def parse_genome(file_path: Path | str) -> Genome:
    """
    Parse a genome file, auto-detecting the format.

    This is the main entry point for parsing genome files.
    It automatically detects the file format and uses the
    appropriate parser.

    Args:
        file_path: Path to the input file.

    Returns:
        A fully populated Genome object.

    Raises:
        ParserError: If parsing fails.
        FileNotFoundError: If the file does not exist.

    Example:
        >>> from giae.parsers import parse_genome
        >>> genome = parse_genome("my_genome.fasta")
        >>> print(genome.name, genome.length)
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    file_format = detect_format(path)

    # Import here to avoid circular imports
    from giae.parsers.fasta import FastaParser
    from giae.parsers.genbank import GenBankParser

    parser: BaseParser
    if file_format == "fasta":
        parser = FastaParser()
    elif file_format == "genbank":
        parser = GenBankParser()
    else:
        raise ParserError(f"Unsupported format: {file_format}", path)

    return parser.parse(path)
