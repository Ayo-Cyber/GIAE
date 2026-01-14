"""Analysis modules for evidence extraction."""

from giae.analysis.orf_finder import ORFFinder, ORFResult
from giae.analysis.homology import HomologyAnalyzer, BlastHit
from giae.analysis.motif import MotifScanner, MotifMatch
from giae.analysis.prosite import (
    PROSITEDatabase,
    PROSITEEntry,
    load_prosite_patterns,
)
from giae.analysis.uniprot import UniProtClient, UniProtHit

__all__ = [
    "ORFFinder",
    "ORFResult",
    "HomologyAnalyzer",
    "BlastHit",
    "MotifScanner",
    "MotifMatch",
    "PROSITEDatabase",
    "PROSITEEntry",
    "load_prosite_patterns",
    "UniProtClient",
    "UniProtHit",
]
