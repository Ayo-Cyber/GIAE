"""Interpretation data model for GIAE.

Interpretations represent functional hypotheses derived from
aggregated evidence. They are the core output of the interpretation
engine and embody the project's novelty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ConfidenceLevel(Enum):
    """Qualitative confidence levels for interpretations."""

    HIGH = "high"  # Strong, consistent evidence
    MODERATE = "moderate"  # Good evidence with some uncertainty
    LOW = "low"  # Limited or conflicting evidence
    SPECULATIVE = "speculative"  # Minimal evidence, hypothesis only


@dataclass
class CompetingHypothesis:
    """An alternative interpretation that was considered but ranked lower."""

    hypothesis: str
    confidence: float
    reason_not_preferred: str


@dataclass
class Interpretation:
    """
    A functional hypothesis derived from aggregated evidence.

    Interpretations are the primary output of GIAE. They represent
    what the system believes a gene's function might be, along with
    explicit reasoning and uncertainty.

    Attributes:
        id: Unique identifier for this interpretation.
        gene_id: ID of the gene being interpreted.
        hypothesis: Primary functional hypothesis (e.g., "DNA polymerase III subunit").
        confidence_score: Numerical confidence (0.0 to 1.0).
        confidence_level: Qualitative confidence category.
        supporting_evidence_ids: IDs of evidence objects supporting this hypothesis.
        reasoning_chain: Step-by-step explanation of how the hypothesis was formed.
        competing_hypotheses: Alternative interpretations that were considered.
        uncertainty_sources: Explicit notes about what creates uncertainty.
        timestamp: When this interpretation was generated.

    Example:
        >>> interpretation = Interpretation(
        ...     gene_id="gene_001",
        ...     hypothesis="DNA polymerase III alpha subunit",
        ...     confidence_score=0.82,
        ...     confidence_level=ConfidenceLevel.HIGH,
        ...     supporting_evidence_ids=["ev_abc123", "ev_def456"],
        ...     reasoning_chain=[
        ...         "BLAST hit to E. coli dnaE with 85% identity",
        ...         "Contains polymerase domain motif",
        ...         "Gene location consistent with replication machinery"
        ...     ],
        ...     uncertainty_sources=["No experimental validation available"]
        ... )
    """

    gene_id: str
    hypothesis: str
    confidence_score: float
    confidence_level: ConfidenceLevel
    supporting_evidence_ids: list[str]
    reasoning_chain: list[str]
    id: str = field(default_factory=lambda: f"int_{uuid4().hex[:12]}")
    competing_hypotheses: list[CompetingHypothesis] = field(default_factory=list)
    uncertainty_sources: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate interpretation data after initialization."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"Confidence score must be between 0.0 and 1.0, got {self.confidence_score}"
            )
        if not self.reasoning_chain:
            raise ValueError("Interpretation must have at least one reasoning step")

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence interpretation."""
        return self.confidence_level == ConfidenceLevel.HIGH

    @property
    def has_competing_hypotheses(self) -> bool:
        """Check if alternative interpretations were considered."""
        return len(self.competing_hypotheses) > 0

    def get_summary(self) -> str:
        """Generate a one-line summary of the interpretation."""
        return (
            f"{self.hypothesis} "
            f"(confidence: {self.confidence_score:.0%}, {self.confidence_level.value})"
        )

    def get_explanation(self) -> str:
        """Generate a human-readable explanation of the interpretation."""
        lines = [
            f"Hypothesis: {self.hypothesis}",
            f"Confidence: {self.confidence_score:.0%} ({self.confidence_level.value})",
            "",
            "Reasoning:",
        ]
        for i, step in enumerate(self.reasoning_chain, 1):
            lines.append(f"  {i}. {step}")

        if self.competing_hypotheses:
            lines.append("")
            lines.append("Alternative hypotheses considered:")
            for alt in self.competing_hypotheses:
                lines.append(f"  - {alt.hypothesis} ({alt.confidence:.0%})")
                lines.append(f"    Not preferred because: {alt.reason_not_preferred}")

        if self.uncertainty_sources:
            lines.append("")
            lines.append("Sources of uncertainty:")
            for source in self.uncertainty_sources:
                lines.append(f"  - {source}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize interpretation to a dictionary."""
        return {
            "id": self.id,
            "gene_id": self.gene_id,
            "hypothesis": self.hypothesis,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level.value,
            "supporting_evidence_ids": self.supporting_evidence_ids,
            "reasoning_chain": self.reasoning_chain,
            "competing_hypotheses": [
                {
                    "hypothesis": ch.hypothesis,
                    "confidence": ch.confidence,
                    "reason_not_preferred": ch.reason_not_preferred,
                }
                for ch in self.competing_hypotheses
            ],
            "uncertainty_sources": self.uncertainty_sources,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Interpretation:
        """Deserialize interpretation from a dictionary."""
        competing = [
            CompetingHypothesis(
                hypothesis=ch["hypothesis"],
                confidence=ch["confidence"],
                reason_not_preferred=ch["reason_not_preferred"],
            )
            for ch in data.get("competing_hypotheses", [])
        ]
        return cls(
            id=data["id"],
            gene_id=data["gene_id"],
            hypothesis=data["hypothesis"],
            confidence_score=data["confidence_score"],
            confidence_level=ConfidenceLevel(data["confidence_level"]),
            supporting_evidence_ids=data["supporting_evidence_ids"],
            reasoning_chain=data["reasoning_chain"],
            competing_hypotheses=competing,
            uncertainty_sources=data.get("uncertainty_sources", []),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )
