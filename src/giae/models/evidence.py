"""Evidence data model for GIAE.

Evidence objects represent atomic pieces of biological information
extracted from analysis modules. They do not contain conclusions,
only observations with provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class EvidenceType(Enum):
    """Types of evidence that can be extracted from genomic analysis."""

    BLAST_HOMOLOGY = "blast_homology"
    MOTIF_MATCH = "motif_match"
    ORF_PREDICTION = "orf_prediction"
    DOMAIN_HIT = "domain_hit"
    SEQUENCE_FEATURE = "sequence_feature"


@dataclass
class EvidenceProvenance:
    """Tracks how evidence was generated for reproducibility."""

    tool_name: str
    tool_version: str
    parameters: dict[str, Any] = field(default_factory=dict)
    database: str | None = None
    database_version: str | None = None
    execution_time_ms: float | None = None


@dataclass
class Evidence:
    """
    An atomic piece of biological evidence extracted from analysis.

    Evidence objects are designed to:
    - Preserve raw observations without interpretation
    - Track provenance for reproducibility
    - Express confidence in the observation itself
    - Link back to the gene they describe

    Attributes:
        id: Unique identifier for this evidence.
        evidence_type: Category of evidence (homology, motif, etc.).
        gene_id: ID of the gene this evidence relates to.
        description: Human-readable summary of the evidence.
        confidence: Confidence in the observation (0.0 to 1.0).
        raw_data: Original tool output preserved for inspection.
        provenance: How this evidence was generated.
        timestamp: When this evidence was created.
        notes: Optional additional context or caveats.

    Example:
        >>> evidence = Evidence(
        ...     evidence_type=EvidenceType.BLAST_HOMOLOGY,
        ...     gene_id="gene_001",
        ...     description="85% identity to E. coli DNA polymerase III",
        ...     confidence=0.85,
        ...     raw_data={"e_value": 1e-50, "identity": 85.0},
        ...     provenance=EvidenceProvenance(
        ...         tool_name="blastp",
        ...         tool_version="2.15.0",
        ...         database="nr"
        ...     )
        ... )
    """

    evidence_type: EvidenceType
    gene_id: str
    description: str
    confidence: float
    raw_data: dict[str, Any]
    provenance: EvidenceProvenance
    id: str = field(default_factory=lambda: f"ev_{uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate evidence data after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize evidence to a dictionary."""
        return {
            "id": self.id,
            "evidence_type": self.evidence_type.value,
            "gene_id": self.gene_id,
            "description": self.description,
            "confidence": self.confidence,
            "raw_data": self.raw_data,
            "provenance": {
                "tool_name": self.provenance.tool_name,
                "tool_version": self.provenance.tool_version,
                "parameters": self.provenance.parameters,
                "database": self.provenance.database,
                "database_version": self.provenance.database_version,
                "execution_time_ms": self.provenance.execution_time_ms,
            },
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        """Deserialize evidence from a dictionary."""
        provenance = EvidenceProvenance(
            tool_name=data["provenance"]["tool_name"],
            tool_version=data["provenance"]["tool_version"],
            parameters=data["provenance"].get("parameters", {}),
            database=data["provenance"].get("database"),
            database_version=data["provenance"].get("database_version"),
            execution_time_ms=data["provenance"].get("execution_time_ms"),
        )
        return cls(
            id=data["id"],
            evidence_type=EvidenceType(data["evidence_type"]),
            gene_id=data["gene_id"],
            description=data["description"],
            confidence=data["confidence"],
            raw_data=data["raw_data"],
            provenance=provenance,
            timestamp=datetime.fromisoformat(data["timestamp"]),
            notes=data.get("notes", []),
        )
