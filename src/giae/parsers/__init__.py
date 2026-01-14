"""Input parsers for GIAE."""

from giae.parsers.base import parse_genome, detect_format, ParserError
from giae.parsers.fasta import FastaParser
from giae.parsers.genbank import GenBankParser

__all__ = [
    "parse_genome",
    "detect_format",
    "ParserError",
    "FastaParser",
    "GenBankParser",
]
