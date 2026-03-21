"""Novel gene discovery engine for GIAE.

Identifies and ranks genes that lack functional characterization,
surfacing them as explicit research priorities rather than silent failures.

The key insight: a gene with no interpretation is not a dead end —
it is a discovery opportunity. This engine transforms those gaps into
a structured, prioritized research agenda.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from giae.engine.interpreter import GenomeInterpretationSummary, InterpretationResult
    from giae.models.genome import Genome


# Suggested experimental approaches keyed by discovery context
_EXPERIMENTS: dict[str, list[str]] = {
    "dark_long": [
        "Recombinant expression and biochemical activity screening",
        "Structural characterization by X-ray crystallography or cryo-EM",
        "Deletion mutant phenotyping to assess essentiality",
        "Comparative genomics: check conservation across related strains",
    ],
    "dark_short": [
        "Gene deletion to assess essentiality",
        "Protein interaction screen (co-immunoprecipitation or Y2H)",
        "RNA-seq profiling across conditions to check expression pattern",
    ],
    "conflict": [
        "Biochemical assay to discriminate between predicted functions",
        "Mutagenesis of key predicted active-site residues",
        "Crystal structure determination for definitive classification",
        "Ortholog functional complementation in model organism",
    ],
    "weak": [
        "Overexpression and in vitro binding/activity assays",
        "Functional complementation in related organism",
        "Protein–protein interaction screen",
    ],
}


@dataclass
class NovelGeneCandidate:
    """
    A gene candidate flagged for novel function discovery.

    Attributes:
        gene_id: Identifier of the gene.
        gene_name: Display name (locus tag or name if available).
        protein_length: Length of the protein in amino acids.
        novelty_score: 0.0–1.0; higher = higher research priority.
        category: "dark_matter" | "conflict" | "weak_evidence".
        reason: Human-readable explanation of why it was flagged.
        evidence_count: How many evidence items were found (0 = true dark matter).
        conflict_severity: Conflict severity if applicable.
        suggested_experiments: Experimental approaches recommended.
    """

    gene_id: str
    gene_name: str | None
    protein_length: int
    novelty_score: float
    category: str
    reason: str
    evidence_count: int
    conflict_severity: str | None = None
    suggested_experiments: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Name to show in reports."""
        return self.gene_name or self.gene_id

    @property
    def priority_label(self) -> str:
        """Human-readable priority tier."""
        if self.novelty_score >= 0.80:
            return "HIGH PRIORITY"
        elif self.novelty_score >= 0.55:
            return "MEDIUM PRIORITY"
        else:
            return "LOW PRIORITY"

    @property
    def category_label(self) -> str:
        """Friendly label for the novelty category."""
        labels = {
            "dark_matter": "Dark Matter Gene",
            "conflict": "Ambiguous Function",
            "weak_evidence": "Poorly Characterised",
        }
        return labels.get(self.category, self.category)


@dataclass
class NovelGeneReport:
    """
    Summary of novel and uncharacterised gene discovery.

    Attributes:
        total_novel: Total genes flagged as needing characterisation.
        dark_matter_count: Genes with absolutely no evidence.
        weak_evidence_count: Genes with some evidence but no clear function.
        conflict_count: Genes with contradictory evidence.
        candidates: Ranked candidates (up to 20), best first.
    """

    total_novel: int
    dark_matter_count: int
    weak_evidence_count: int
    conflict_count: int
    candidates: list[NovelGeneCandidate]

    @property
    def has_novel_genes(self) -> bool:
        """True if any novel genes were found."""
        return self.total_novel > 0

    @property
    def top_priorities(self) -> list[NovelGeneCandidate]:
        """Top 5 highest-priority research candidates."""
        return self.candidates[:5]

    @property
    def dark_matter_fraction(self) -> float:
        """Fraction of novel genes that are complete dark matter."""
        if self.total_novel == 0:
            return 0.0
        return self.dark_matter_count / self.total_novel


class NoveltyScorer:
    """
    Identifies and ranks novel/uncharacterised genes.

    Evaluates every gene in a genome interpretation result and flags those
    that warrant experimental follow-up:

    - **Dark matter**: zero computational evidence of any kind.
    - **Conflict**: contradictory signals from different evidence sources.
    - **Weak evidence**: some hits exist but confidence is too low to call.

    Each candidate receives a novelty score (0–1) reflecting research
    priority, along with concrete suggested experiments.

    Example:
        >>> scorer = NoveltyScorer()
        >>> report = scorer.analyze(genome, summary)
        >>> for c in report.top_priorities:
        ...     print(c.display_name, c.priority_label)
    """

    def analyze(
        self,
        genome: Genome,
        summary: GenomeInterpretationSummary,
    ) -> NovelGeneReport:
        """
        Identify novel gene candidates from genome interpretation results.

        Args:
            genome: The interpreted genome (used for protein length lookup).
            summary: Full interpretation results from the Interpreter.

        Returns:
            NovelGeneReport with ranked candidates.
        """
        # Build a fast lookup: gene_id -> Gene
        gene_map = {g.id: g for g in genome.genes}

        candidates: list[NovelGeneCandidate] = []
        dark_matter_count = 0
        weak_evidence_count = 0
        conflict_count = 0

        for result in summary.results:
            candidate = self._evaluate(result, gene_map)
            if candidate is None:
                continue

            candidates.append(candidate)
            if candidate.category == "dark_matter":
                dark_matter_count += 1
            elif candidate.category == "conflict":
                conflict_count += 1
            else:
                weak_evidence_count += 1

        # Sort by novelty score descending (highest priority first)
        candidates.sort(key=lambda c: c.novelty_score, reverse=True)

        return NovelGeneReport(
            total_novel=len(candidates),
            dark_matter_count=dark_matter_count,
            weak_evidence_count=weak_evidence_count,
            conflict_count=conflict_count,
            candidates=candidates[:20],
        )

    def _evaluate(
        self,
        result: InterpretationResult,
        gene_map: dict,
    ) -> NovelGeneCandidate | None:
        """Evaluate a single interpretation result for novelty."""
        # Skip results that errored — those are bugs, not discoveries
        if not result.success:
            return None

        gene = gene_map.get(result.gene_id)
        protein_length = self._protein_length(gene)

        evidence_count = (
            result.aggregated_evidence.evidence_count if result.aggregated_evidence else 0
        )

        conflict_severity = None
        if result.interpretation and result.interpretation.metadata:
            conflict_severity = result.interpretation.metadata.get("conflict_severity")

        # ── Case 1: No evidence at all → dark matter ──────────────────────
        if evidence_count == 0:
            score = self._dark_matter_score(protein_length)
            experiments = (
                _EXPERIMENTS["dark_long"] if protein_length > 150 else _EXPERIMENTS["dark_short"]
            )
            return NovelGeneCandidate(
                gene_id=result.gene_id,
                gene_name=result.gene_name,
                protein_length=protein_length,
                novelty_score=score,
                category="dark_matter",
                reason="No sequence homology, domains, or motifs detected",
                evidence_count=0,
                conflict_severity=None,
                suggested_experiments=experiments,
            )

        # ── Case 2: High-severity conflict → ambiguous function ───────────
        interp = result.interpretation
        if (
            conflict_severity in ("HIGH", "MODERATE")
            and interp is not None
            and interp.confidence_score < 0.50
        ):
            return NovelGeneCandidate(
                gene_id=result.gene_id,
                gene_name=result.gene_name,
                protein_length=protein_length,
                novelty_score=0.65,
                category="conflict",
                reason=f"Contradictory evidence: {interp.hypothesis[:80]}",
                evidence_count=evidence_count,
                conflict_severity=conflict_severity,
                suggested_experiments=_EXPERIMENTS["conflict"],
            )

        # ── Case 3: No/very weak interpretation ───────────────────────────
        if interp is None or interp.confidence_score < 0.35:
            score = self._weak_evidence_score(protein_length, evidence_count)
            if score < 0.30:
                return None  # Not interesting enough to list
            return NovelGeneCandidate(
                gene_id=result.gene_id,
                gene_name=result.gene_name,
                protein_length=protein_length,
                novelty_score=score,
                category="weak_evidence",
                reason="Functional signal below confidence threshold (< 35%)",
                evidence_count=evidence_count,
                conflict_severity=conflict_severity,
                suggested_experiments=_EXPERIMENTS["weak"],
            )

        # Gene has a credible interpretation — not novel
        return None

    @staticmethod
    def _protein_length(gene: object | None) -> int:
        """Extract protein length from a Gene object safely."""
        if gene is None:
            return 0
        protein = getattr(gene, "protein", None)
        if protein and getattr(protein, "sequence", None):
            return len(protein.sequence)
        loc = getattr(gene, "location", None)
        if loc:
            return max(0, (loc.end - loc.start) // 3)
        return 0

    @staticmethod
    def _dark_matter_score(protein_length: int) -> float:
        """
        Priority score for dark-matter genes.

        Longer proteins are higher priority because they are more likely
        to encode definable enzymatic or structural functions.
        """
        if protein_length > 300:
            return 0.95
        elif protein_length > 150:
            return 0.85
        elif protein_length > 50:
            return 0.75
        else:
            # Very short ORFs may be artefacts
            return 0.55

    @staticmethod
    def _weak_evidence_score(protein_length: int, evidence_count: int) -> float:
        """Priority score for weakly-characterised genes."""
        base = 0.50
        if protein_length > 200:
            base += 0.10
        if evidence_count <= 1:
            base += 0.05  # Almost as unknown as dark matter
        elif evidence_count >= 4:
            base -= 0.10  # Lots of evidence but still unresolved
        return max(0.0, min(base, 0.75))
