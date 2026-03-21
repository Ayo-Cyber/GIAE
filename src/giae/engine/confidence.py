"""Confidence scoring module for GIAE.

Calculates final confidence scores and explains uncertainty
sources for interpretations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from giae.engine.aggregator import AggregatedEvidence
from giae.engine.hypothesis import FunctionalHypothesis
from giae.models.evidence import EvidenceType
from giae.models.interpretation import ConfidenceLevel


class UncertaintySource(Enum):
    """Sources of uncertainty in interpretations."""

    LOW_SEQUENCE_IDENTITY = "low_sequence_identity"
    LIMITED_EVIDENCE = "limited_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    SINGLE_EVIDENCE_TYPE = "single_evidence_type"
    NO_EXPERIMENTAL_VALIDATION = "no_experimental_validation"
    HYPOTHETICAL_HOMOLOG = "hypothetical_homolog"
    WEAK_MOTIF_MATCH = "weak_motif_match"


@dataclass
class ConfidenceReport:
    """Detailed breakdown of confidence scoring."""

    raw_score: float
    adjusted_score: float
    confidence_level: ConfidenceLevel
    positive_factors: list[str]
    negative_factors: list[str]
    uncertainty_sources: list[UncertaintySource]

    @property
    def explanation(self) -> str:
        """Generate human-readable explanation."""
        lines = [
            f"Confidence: {self.adjusted_score:.0%} ({self.confidence_level.value})",
            "",
        ]

        if self.positive_factors:
            lines.append("Supporting factors:")
            for factor in self.positive_factors:
                lines.append(f"  + {factor}")

        if self.negative_factors:
            lines.append("")
            lines.append("Limiting factors:")
            for factor in self.negative_factors:
                lines.append(f"  - {factor}")

        if self.uncertainty_sources:
            lines.append("")
            lines.append("Sources of uncertainty:")
            for source in self.uncertainty_sources:
                lines.append(f"  ? {source.value.replace('_', ' ').title()}")

        return "\n".join(lines)


@dataclass
class ConfidenceScorer:
    """
    Calculate and explain confidence scores.

    Takes a hypothesis and its supporting evidence to produce
    a calibrated confidence score with explicit uncertainty
    documentation.

    Attributes:
        evidence_diversity_bonus: Bonus for multiple evidence types.
        strong_hit_threshold: Identity threshold for "strong" hits.

    Example:
        >>> scorer = ConfidenceScorer()
        >>> report = scorer.score(hypothesis, aggregated_evidence)
        >>> print(report.explanation)
    """

    evidence_diversity_bonus: float = 0.1
    strong_hit_threshold: float = 0.8

    def score(
        self,
        hypothesis: FunctionalHypothesis,
        aggregated: AggregatedEvidence,
    ) -> ConfidenceReport:
        """
        Calculate confidence score for a hypothesis.

        Args:
            hypothesis: The hypothesis to score.
            aggregated: Evidence aggregation for the gene.

        Returns:
            ConfidenceReport with score and explanation.
        """
        raw_score = hypothesis.confidence
        positive_factors: list[str] = []
        negative_factors: list[str] = []
        uncertainty_sources: list[UncertaintySource] = []

        # Adjust based on evidence diversity
        if aggregated.type_diversity >= 2:
            raw_score += self.evidence_diversity_bonus
            positive_factors.append(
                f"Multiple evidence types ({aggregated.type_diversity}) support this hypothesis"
            )
        elif aggregated.type_diversity == 1:
            uncertainty_sources.append(UncertaintySource.SINGLE_EVIDENCE_TYPE)
            negative_factors.append("Only one type of evidence available")

        # Adjust based on evidence count
        if aggregated.evidence_count >= 5:
            raw_score += 0.05
            positive_factors.append(f"Strong evidence support ({aggregated.evidence_count} items)")
        elif aggregated.evidence_count <= 2:
            raw_score -= 0.1
            uncertainty_sources.append(UncertaintySource.LIMITED_EVIDENCE)
            negative_factors.append("Limited evidence available")

        # Check for strong homology hits
        if aggregated.has_homology:
            homology = aggregated.groups_by_type[EvidenceType.BLAST_HOMOLOGY]
            max_identity = max(e.confidence for e in homology)
            if max_identity >= self.strong_hit_threshold:
                raw_score += 0.05
                positive_factors.append(f"Strong sequence homology ({max_identity:.0%} identity)")
            else:
                uncertainty_sources.append(UncertaintySource.LOW_SEQUENCE_IDENTITY)
                negative_factors.append("Moderate sequence identity to known proteins")

        # Check for domain hits (Pfam/HMM — high specificity profiles)
        if EvidenceType.DOMAIN_HIT in aggregated.groups_by_type:
            domain_hits = aggregated.groups_by_type[EvidenceType.DOMAIN_HIT]
            best_domain = max(domain_hits, key=lambda e: e.confidence)
            if best_domain.confidence >= 0.85:
                raw_score += 0.08
                domain_name = best_domain.raw_data.get("domain_name", "domain")
                positive_factors.append(
                    f"High-confidence Pfam domain hit: {domain_name} ({best_domain.confidence:.0%})"
                )
            elif best_domain.confidence >= 0.70:
                raw_score += 0.04
                domain_name = best_domain.raw_data.get("domain_name", "domain")
                positive_factors.append(f"Pfam domain hit: {domain_name}")
            else:
                positive_factors.append("Weak Pfam domain signal detected")

        # Check for hypothetical protein hits (lower confidence)
        if "hypothetical" in hypothesis.function.lower():
            raw_score -= 0.15
            uncertainty_sources.append(UncertaintySource.HYPOTHETICAL_HOMOLOG)
            negative_factors.append("Homolog is itself hypothetical/uncharacterized")

        # Cap the score
        adjusted_score = max(0.0, min(1.0, raw_score))

        # Enforce strict cap for nonspecific motifs (e.g. phosphorylation)
        if hypothesis.category == "modification" and adjusted_score > 0.45:
            adjusted_score = 0.45
            negative_factors.append("Likely nonspecific motif pattern")
            uncertainty_sources.append(UncertaintySource.WEAK_MOTIF_MATCH)

        # Cap confidence if evidence is ONLY based on motifs
        if aggregated.type_diversity == 1 and aggregated.has_motifs and adjusted_score > 0.85:
            adjusted_score = 0.85
            negative_factors.append(
                "Prediction based entirely on sequence motifs without homology"
            )
            uncertainty_sources.append(UncertaintySource.WEAK_MOTIF_MATCH)

        # Always add the experimental validation uncertainty
        uncertainty_sources.append(UncertaintySource.NO_EXPERIMENTAL_VALIDATION)

        # Determine confidence level
        confidence_level = self._score_to_level(adjusted_score)

        return ConfidenceReport(
            raw_score=hypothesis.confidence,
            adjusted_score=adjusted_score,
            confidence_level=confidence_level,
            positive_factors=positive_factors,
            negative_factors=negative_factors,
            uncertainty_sources=uncertainty_sources,
        )

    def _score_to_level(self, score: float) -> ConfidenceLevel:
        """Convert numeric score to confidence level."""
        if score >= 0.8:
            return ConfidenceLevel.HIGH
        elif score >= 0.5:
            return ConfidenceLevel.MODERATE
        elif score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.SPECULATIVE

    def score_batch(
        self,
        hypotheses: list[FunctionalHypothesis],
        aggregated: AggregatedEvidence,
    ) -> list[ConfidenceReport]:
        """Score multiple hypotheses."""
        return [self.score(h, aggregated) for h in hypotheses]

    def explain_differences(
        self,
        reports: list[ConfidenceReport],
    ) -> str:
        """Explain why hypotheses have different confidence levels."""
        if len(reports) <= 1:
            return "Single hypothesis - no comparison available."

        lines = ["Hypothesis Comparison:", ""]

        for _i, report in enumerate(reports, 1):
            lines.append(f"Hypothesis {_i}: {report.confidence_level.value}")

            if report.positive_factors:
                lines.append(f"  Strengths: {', '.join(report.positive_factors[:2])}")
            if report.negative_factors:
                lines.append(f"  Weaknesses: {', '.join(report.negative_factors[:2])}")
            lines.append("")

        return "\n".join(lines)
