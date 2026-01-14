"""Evidence aggregation module for GIAE.

Collects and organizes evidence from multiple sources
to prepare for interpretation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from giae.models.evidence import Evidence, EvidenceType
from giae.models.gene import Gene


@dataclass
class EvidenceGroup:
    """A group of related evidence for a gene."""

    gene_id: str
    evidence: list[Evidence]

    @property
    def count(self) -> int:
        """Number of evidence items."""
        return len(self.evidence)

    @property
    def types(self) -> set[EvidenceType]:
        """Unique evidence types in this group."""
        return {e.evidence_type for e in self.evidence}

    @property
    def average_confidence(self) -> float:
        """Average confidence across all evidence."""
        if not self.evidence:
            return 0.0
        return sum(e.confidence for e in self.evidence) / len(self.evidence)

    @property
    def max_confidence(self) -> float:
        """Maximum confidence in this group."""
        if not self.evidence:
            return 0.0
        return max(e.confidence for e in self.evidence)

    def by_type(self, evidence_type: EvidenceType) -> list[Evidence]:
        """Get evidence of a specific type."""
        return [e for e in self.evidence if e.evidence_type == evidence_type]

    def sorted_by_confidence(self) -> list[Evidence]:
        """Get evidence sorted by confidence (highest first)."""
        return sorted(self.evidence, key=lambda e: e.confidence, reverse=True)


@dataclass
class EvidenceWeights:
    """Weights for different evidence types in aggregation."""

    blast_homology: float = 1.0
    motif_match: float = 0.8
    orf_prediction: float = 0.6
    domain_hit: float = 0.9
    sequence_feature: float = 0.5

    def get_weight(self, evidence_type: EvidenceType) -> float:
        """Get weight for an evidence type."""
        weight_map = {
            EvidenceType.BLAST_HOMOLOGY: self.blast_homology,
            EvidenceType.MOTIF_MATCH: self.motif_match,
            EvidenceType.ORF_PREDICTION: self.orf_prediction,
            EvidenceType.DOMAIN_HIT: self.domain_hit,
            EvidenceType.SEQUENCE_FEATURE: self.sequence_feature,
        }
        return weight_map.get(evidence_type, 0.5)


@dataclass
class AggregatedEvidence:
    """Result of evidence aggregation for a gene."""

    gene_id: str
    groups_by_type: dict[EvidenceType, list[Evidence]]
    weighted_scores: dict[EvidenceType, float]
    total_weighted_score: float
    evidence_count: int
    type_diversity: int  # Number of different evidence types

    @property
    def has_homology(self) -> bool:
        """Check if homology evidence exists."""
        return EvidenceType.BLAST_HOMOLOGY in self.groups_by_type

    @property
    def has_motifs(self) -> bool:
        """Check if motif evidence exists."""
        return EvidenceType.MOTIF_MATCH in self.groups_by_type

    @property
    def strongest_type(self) -> EvidenceType | None:
        """Get the type with highest weighted score."""
        if not self.weighted_scores:
            return None
        return max(self.weighted_scores, key=lambda t: self.weighted_scores[t])

    def get_top_evidence(self, n: int = 3) -> list[Evidence]:
        """Get the top N evidence items by confidence."""
        all_evidence = []
        for evidence_list in self.groups_by_type.values():
            all_evidence.extend(evidence_list)
        return sorted(all_evidence, key=lambda e: e.confidence, reverse=True)[:n]


@dataclass
class EvidenceAggregator:
    """
    Aggregates evidence from multiple sources for interpretation.

    This class collects evidence for each gene, weights it by
    source type, and prepares structured summaries for the
    hypothesis generator.

    Attributes:
        weights: Weights for different evidence types.
        min_evidence_count: Minimum evidence items required.

    Example:
        >>> aggregator = EvidenceAggregator()
        >>> for gene in genome.genes:
        ...     aggregated = aggregator.aggregate(gene)
        ...     print(f"{gene.id}: {aggregated.total_weighted_score}")
    """

    weights: EvidenceWeights = field(default_factory=EvidenceWeights)
    min_evidence_count: int = 1

    def aggregate(self, gene: Gene) -> AggregatedEvidence:
        """
        Aggregate all evidence for a gene.

        Args:
            gene: Gene with evidence attached.

        Returns:
            AggregatedEvidence with organized and scored evidence.
        """
        # Group evidence by type
        groups: dict[EvidenceType, list[Evidence]] = defaultdict(list)
        for evidence in gene.evidence:
            groups[evidence.evidence_type].append(evidence)

        # Calculate weighted scores per type
        weighted_scores: dict[EvidenceType, float] = {}
        for etype, evidence_list in groups.items():
            weight = self.weights.get_weight(etype)
            avg_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)
            weighted_scores[etype] = weight * avg_confidence * len(evidence_list)

        # Total weighted score
        total_score = sum(weighted_scores.values())

        return AggregatedEvidence(
            gene_id=gene.id,
            groups_by_type=dict(groups),
            weighted_scores=weighted_scores,
            total_weighted_score=total_score,
            evidence_count=len(gene.evidence),
            type_diversity=len(groups),
        )

    def aggregate_batch(self, genes: list[Gene]) -> list[AggregatedEvidence]:
        """Aggregate evidence for multiple genes."""
        return [self.aggregate(gene) for gene in genes if gene.evidence]

    def summarize(self, aggregated: AggregatedEvidence) -> dict[str, Any]:
        """Create a summary dict of aggregated evidence."""
        return {
            "gene_id": aggregated.gene_id,
            "evidence_count": aggregated.evidence_count,
            "type_diversity": aggregated.type_diversity,
            "weighted_score": round(aggregated.total_weighted_score, 3),
            "has_homology": aggregated.has_homology,
            "has_motifs": aggregated.has_motifs,
            "strongest_type": (
                aggregated.strongest_type.value if aggregated.strongest_type else None
            ),
        }

    def rank_genes_by_evidence(
        self,
        genes: list[Gene],
    ) -> list[tuple[Gene, AggregatedEvidence]]:
        """
        Rank genes by strength of their aggregated evidence.

        Returns:
            List of (gene, aggregated) tuples, sorted by score.
        """
        gene_scores = []
        for gene in genes:
            if gene.evidence:
                agg = self.aggregate(gene)
                gene_scores.append((gene, agg))

        return sorted(gene_scores, key=lambda x: x[1].total_weighted_score, reverse=True)
