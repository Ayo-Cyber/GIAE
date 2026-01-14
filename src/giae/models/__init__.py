"""Core data models for GIAE."""

from giae.models.genome import Genome
from giae.models.gene import Gene
from giae.models.protein import Protein
from giae.models.evidence import Evidence, EvidenceType
from giae.models.interpretation import Interpretation

__all__ = [
    "Genome",
    "Gene",
    "Protein",
    "Evidence",
    "EvidenceType",
    "Interpretation",
]
