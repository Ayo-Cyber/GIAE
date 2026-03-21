"""
Conflict resolution module for identifying contradictory interpretations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from giae.engine.hypothesis import FunctionalHypothesis


class ConflictSeverity(Enum):
    """
    Severity of conflict between top hypotheses.

    NONE: No conflict or clear winner.
    LOW: Minor terminological differences (e.g. "kinase" vs "serine kinase").
    MODERATE: Functional differences within same broad category.
    HIGH: Fundamental disagreement (e.g. "Stuctural protein" vs "Enzyme").
    """

    NONE = auto()
    LOW = auto()
    MODERATE = auto()
    HIGH = auto()


@dataclass
class ConflictReport:
    """Report detailing conflicts found between hypotheses."""

    severity: ConflictSeverity
    description: str
    conflicting_sources: list[str]
    recommended_action: str


class ConflictResolver:
    """
    Engine for detecting and resolving conflicts in interpretation.

    Compares the top ranked hypotheses to ensure the leading interpretation
    isn't contested by another strong candidate with a different function.
    """

    def __init__(self, confidence_threshold: float = 0.15):
        """
        Args:
            confidence_threshold: Max confidence difference to consider hypotheses 'comparable'.
        """
        self.confidence_threshold = confidence_threshold

    def check_conflicts(self, hypotheses: list[FunctionalHypothesis]) -> ConflictReport:
        """
        Analyze hypotheses for conflicts.

        Args:
            hypotheses: List of hypotheses, sorted by confidence (highest first).

        Returns:
            ConflictReport with severity and details.
        """
        if not hypotheses or len(hypotheses) < 2:
            return ConflictReport(
                severity=ConflictSeverity.NONE,
                description="No conflict (single or no hypothesis)",
                conflicting_sources=[],
                recommended_action="none",
            )

        top1 = hypotheses[0]
        top2 = hypotheses[1]

        # 1. Check if the primary hypothesis is clearly dominant
        score_diff = top1.confidence - top2.confidence
        if score_diff > self.confidence_threshold:
            # Primary is much stronger -> No conflict
            return ConflictReport(
                severity=ConflictSeverity.NONE,
                description="Primary hypothesis dominant",
                conflicting_sources=[],
                recommended_action="none",
            )

        # 2. Check if functions are effectively the same
        # Ideally this would use an ontology, but keyword matching works for MVP
        func1 = top1.function.lower()
        func2 = top2.function.lower()

        # Remove common fluff words
        stop_words = {"putative", "potential", "probable", "protein", "domain", "containing"}
        tokens1 = {w for w in func1.split() if w not in stop_words and len(w) > 3}
        tokens2 = {w for w in func2.split() if w not in stop_words and len(w) > 3}

        # Start simplistic comparison
        if tokens1 & tokens2:
            # They share significant words (e.g. "kinase") -> Low conflict
            return ConflictReport(
                severity=ConflictSeverity.LOW,
                description=f"Similar functions: '{top1.function}' vs '{top2.function}'",
                conflicting_sources=[],
                recommended_action="merge",
            )

        # 3. If here, scores are close AND descriptions are different -> High Conflict
        return ConflictReport(
            severity=ConflictSeverity.HIGH,
            description=f"Ambiguous interpretation: '{top1.function}' vs '{top2.function}'",
            conflicting_sources=[
                f"{top1.source_type} ({top1.confidence:.2f}): {top1.function}",
                f"{top2.source_type} ({top2.confidence:.2f}): {top2.function}",
            ],
            recommended_action="flag_ambiguous",
        )
