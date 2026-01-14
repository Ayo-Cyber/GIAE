"""Gene data model for GIAE.

Genes represent coding sequences within a genome, along with
their translated products, evidence, and interpretations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from giae.models.evidence import Evidence
    from giae.models.interpretation import Interpretation
    from giae.models.protein import Protein


class Strand(Enum):
    """DNA strand orientation."""

    FORWARD = 1
    REVERSE = -1

    @classmethod
    def from_int(cls, value: int) -> Strand:
        """Convert integer to Strand."""
        if value >= 0:
            return cls.FORWARD
        return cls.REVERSE


@dataclass
class GeneLocation:
    """Precise genomic location of a gene."""

    start: int  # 0-based, inclusive
    end: int    # 0-based, exclusive
    strand: Strand

    def __post_init__(self) -> None:
        """Validate location data."""
        if self.start < 0:
            raise ValueError(f"Start position must be >= 0, got {self.start}")
        if self.end <= self.start:
            raise ValueError(f"End must be > start, got start={self.start}, end={self.end}")

    @property
    def length(self) -> int:
        """Length of the gene in base pairs."""
        return self.end - self.start

    def to_dict(self) -> dict[str, Any]:
        """Serialize location to a dictionary."""
        return {
            "start": self.start,
            "end": self.end,
            "strand": self.strand.value,
        }


@dataclass
class Gene:
    """
    A gene within a genome.

    Genes are the primary unit of analysis in GIAE. Each gene
    can have associated evidence and interpretations that explain
    its predicted function.

    Attributes:
        id: Unique identifier for this gene.
        name: Gene name/symbol if known (e.g., "dnaE").
        locus_tag: Systematic locus identifier if available.
        location: Genomic coordinates and strand.
        sequence: Nucleotide sequence of the gene.
        protein: Translated protein product if applicable.
        evidence: Evidence objects linked to this gene.
        interpretations: Functional interpretations for this gene.
        is_pseudo: Whether this is a pseudogene.
        source: How this gene was identified ("annotation" or "orf_prediction").

    Example:
        >>> gene = Gene(
        ...     name="dnaE",
        ...     location=GeneLocation(start=1000, end=4000, strand=Strand.FORWARD),
        ...     sequence="ATGAAACGT..."
        ... )
    """

    location: GeneLocation
    sequence: str
    id: str = field(default_factory=lambda: f"gene_{uuid4().hex[:12]}")
    name: str | None = None
    locus_tag: str | None = None
    protein: Protein | None = None
    evidence: list[Evidence] = field(default_factory=list)
    interpretations: list[Interpretation] = field(default_factory=list)
    is_pseudo: bool = False
    source: str = "annotation"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate gene data after initialization."""
        self.sequence = self.sequence.upper()

        valid_bases = {"A", "T", "G", "C", "N"}
        invalid = set(self.sequence) - valid_bases
        if invalid:
            raise ValueError(f"Invalid nucleotides in sequence: {invalid}")

    @property
    def display_name(self) -> str:
        """Best available name for display."""
        return self.name or self.locus_tag or self.id

    @property
    def length(self) -> int:
        """Length of the gene in base pairs."""
        return len(self.sequence)

    @property
    def strand(self) -> Strand:
        """Strand orientation (shortcut to location.strand)."""
        return self.location.strand

    @property
    def has_interpretation(self) -> bool:
        """Check if this gene has been interpreted."""
        return len(self.interpretations) > 0

    @property
    def best_interpretation(self) -> Interpretation | None:
        """Get the highest-confidence interpretation if available."""
        if not self.interpretations:
            return None
        return max(self.interpretations, key=lambda i: i.confidence_score)

    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence to this gene."""
        self.evidence.append(evidence)

    def add_interpretation(self, interpretation: Interpretation) -> None:
        """Add an interpretation to this gene."""
        self.interpretations.append(interpretation)

    def to_dict(self) -> dict[str, Any]:
        """Serialize gene to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "locus_tag": self.locus_tag,
            "location": self.location.to_dict(),
            "sequence": self.sequence,
            "length": self.length,
            "protein": self.protein.to_dict() if self.protein else None,
            "evidence_ids": [e.id for e in self.evidence],
            "interpretation_ids": [i.id for i in self.interpretations],
            "is_pseudo": self.is_pseudo,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Gene:
        """Deserialize gene from a dictionary (without linked objects)."""
        location = GeneLocation(
            start=data["location"]["start"],
            end=data["location"]["end"],
            strand=Strand(data["location"]["strand"]),
        )
        return cls(
            id=data["id"],
            name=data.get("name"),
            locus_tag=data.get("locus_tag"),
            location=location,
            sequence=data["sequence"],
            is_pseudo=data.get("is_pseudo", False),
            source=data.get("source", "annotation"),
            metadata=data.get("metadata", {}),
        )
