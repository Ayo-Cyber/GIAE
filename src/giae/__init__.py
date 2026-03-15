"""
GIAE - Genome Interpretation & Annotation Engine

An Explainable, Evidence-Centric Framework for Genomic Interpretation.
"""

__version__ = "0.2.0"
__author__ = "GIAE Contributors"

from giae.models.genome import Genome
from giae.models.gene import Gene
from giae.models.protein import Protein
from giae.models.evidence import Evidence
from giae.models.interpretation import Interpretation

__all__ = [
    "__version__",
    "Genome",
    "Gene",
    "Protein",
    "Evidence",
    "Interpretation",
]
