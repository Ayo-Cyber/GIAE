"""Protein data model for GIAE.

Proteins are translated gene products with associated
biochemical properties.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


# Standard amino acid molecular weights in Daltons
AMINO_ACID_WEIGHTS: dict[str, float] = {
    "A": 89.1,   "R": 174.2,  "N": 132.1,  "D": 133.1,  "C": 121.2,
    "E": 147.1,  "Q": 146.2,  "G": 75.1,   "H": 155.2,  "I": 131.2,
    "L": 131.2,  "K": 146.2,  "M": 149.2,  "F": 165.2,  "P": 115.1,
    "S": 105.1,  "T": 119.1,  "W": 204.2,  "Y": 181.2,  "V": 117.1,
}


@dataclass
class Protein:
    """
    A protein translated from a gene.

    Proteins store the amino acid sequence and computed
    biochemical properties derived from the sequence.

    Attributes:
        id: Unique identifier for this protein.
        gene_id: ID of the gene this protein was translated from.
        sequence: Amino acid sequence (single-letter codes).
        product_name: Name/description of the protein if known.
        molecular_weight: Calculated molecular weight in Daltons.
        isoelectric_point: Calculated pI if available.

    Example:
        >>> protein = Protein(
        ...     gene_id="gene_001",
        ...     sequence="MKFLILLFNILCLFPVLAADNHGVGPQGAS",
        ...     product_name="Hypothetical protein"
        ... )
        >>> protein.length
        30
    """

    gene_id: str
    sequence: str
    id: str = field(default_factory=lambda: f"prot_{uuid4().hex[:12]}")
    product_name: str | None = None
    isoelectric_point: float | None = None
    _molecular_weight: float | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate protein data after initialization."""
        # Normalize sequence to uppercase
        self.sequence = self.sequence.upper()

        # Validate sequence contains only valid amino acids
        valid_aa = set(AMINO_ACID_WEIGHTS.keys()) | {"X", "*"}  # X=unknown, *=stop
        invalid = set(self.sequence) - valid_aa
        if invalid:
            raise ValueError(f"Invalid amino acids in sequence: {invalid}")

    @property
    def length(self) -> int:
        """Length of the protein in amino acids."""
        return len(self.sequence.rstrip("*"))

    @property
    def molecular_weight(self) -> float:
        """
        Calculate molecular weight in Daltons.

        Uses average isotopic masses. Water is released during
        peptide bond formation (subtract 18.015 per bond).
        """
        if self._molecular_weight is not None:
            return self._molecular_weight

        sequence = self.sequence.rstrip("*")  # Remove stop codon
        weight = sum(AMINO_ACID_WEIGHTS.get(aa, 110.0) for aa in sequence)

        # Subtract water for peptide bonds (n-1 bonds for n amino acids)
        if len(sequence) > 1:
            weight -= (len(sequence) - 1) * 18.015

        self._molecular_weight = round(weight, 2)
        return self._molecular_weight

    @property
    def molecular_weight_kda(self) -> float:
        """Molecular weight in kiloDaltons."""
        return round(self.molecular_weight / 1000, 2)

    def get_amino_acid_composition(self) -> dict[str, int]:
        """Count occurrences of each amino acid."""
        composition: dict[str, int] = {}
        for aa in self.sequence.rstrip("*"):
            composition[aa] = composition.get(aa, 0) + 1
        return dict(sorted(composition.items()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize protein to a dictionary."""
        return {
            "id": self.id,
            "gene_id": self.gene_id,
            "sequence": self.sequence,
            "length": self.length,
            "product_name": self.product_name,
            "molecular_weight": self.molecular_weight,
            "molecular_weight_kda": self.molecular_weight_kda,
            "isoelectric_point": self.isoelectric_point,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Protein:
        """Deserialize protein from a dictionary."""
        return cls(
            id=data["id"],
            gene_id=data["gene_id"],
            sequence=data["sequence"],
            product_name=data.get("product_name"),
            isoelectric_point=data.get("isoelectric_point"),
        )
