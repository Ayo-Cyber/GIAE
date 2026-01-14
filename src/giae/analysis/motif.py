"""Motif and domain detection module for GIAE.

Provides rule-based scanning for sequence motifs and
functional domains using pattern matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from giae.models.evidence import Evidence, EvidenceType, EvidenceProvenance
from giae.models.gene import Gene


@dataclass
class MotifPattern:
    """Definition of a sequence motif to scan for."""

    name: str
    pattern: str  # Regex pattern or PROSITE-like pattern
    description: str
    category: str  # e.g., "domain", "signal", "modification"
    confidence_weight: float = 1.0  # How reliable this motif is


@dataclass
class MotifMatch:
    """A match of a motif in a sequence."""

    motif_name: str
    motif_description: str
    start: int
    end: int
    matched_sequence: str
    score: float

    @property
    def length(self) -> int:
        """Length of the match."""
        return self.end - self.start


# Built-in motif patterns for common functional domains
BUILTIN_MOTIFS: list[MotifPattern] = [
    # DNA/RNA binding motifs
    MotifPattern(
        name="helix_turn_helix",
        pattern=r"[LIVMFYWC][ASGTNQ].{2}[LIVMFYWC].{4,5}[LIVMFYWC].{2}G[LIVMFYWC].{5,6}[LIVMFYWC]{2}",
        description="Helix-turn-helix DNA binding motif",
        category="domain",
        confidence_weight=0.7,
    ),
    MotifPattern(
        name="zinc_finger_c2h2",
        pattern=r"C.{2,4}C.{3}[LIVMFYWC].{8}H.{3,5}H",
        description="C2H2 zinc finger domain",
        category="domain",
        confidence_weight=0.85,
    ),
    # Enzyme active sites
    MotifPattern(
        name="serine_protease",
        pattern=r"[LIVMFYC][LIVMFYWSTAN].{1,2}G[DENSALKR]S[GSC][GSTAPILVMC]",
        description="Serine protease active site",
        category="active_site",
        confidence_weight=0.8,
    ),
    MotifPattern(
        name="atp_binding_p_loop",
        pattern=r"[AG].{4}GK[ST]",
        description="ATP/GTP binding P-loop (Walker A motif)",
        category="domain",
        confidence_weight=0.9,
    ),
    MotifPattern(
        name="walker_b",
        pattern=r"[LIVMFY]{4}D[DEST][LIVMFYAG]{2}[GSTA]",
        description="Walker B motif (ATPase)",
        category="domain",
        confidence_weight=0.8,
    ),
    # Signal sequences
    MotifPattern(
        name="signal_peptide",
        pattern=r"^M[LIVA]{1,3}[^P]{5,15}[AVILM][^P]{0,5}[ASG][^P]{0,3}[ASG]",
        description="N-terminal signal peptide",
        category="signal",
        confidence_weight=0.6,
    ),
    # Membrane proteins
    MotifPattern(
        name="transmembrane",
        pattern=r"[LIVMFYW]{5,}[AGSTC][LIVMFYW]{10,}",
        description="Transmembrane helix",
        category="topology",
        confidence_weight=0.5,
    ),
    # Common bacterial motifs
    MotifPattern(
        name="phosphorylation_site",
        pattern=r"[RK].{0,2}[ST][^P]",
        description="Potential phosphorylation site",
        category="modification",
        confidence_weight=0.4,
    ),
    MotifPattern(
        name="gram_negative_lipobox",
        pattern=r"[LVI][ASTVI][GAS]C",
        description="Gram-negative lipoprotein signal",
        category="signal",
        confidence_weight=0.7,
    ),
]


@dataclass
class MotifScanner:
    """
    Scan sequences for functional motifs and domains.

    This class provides rule-based detection of sequence patterns
    that may indicate biological function. Supports both builtin
    patterns and loading from external databases like PROSITE.

    Attributes:
        motifs: List of MotifPattern to scan for.
        min_score: Minimum score threshold for reporting matches.

    Example:
        >>> scanner = MotifScanner()
        >>> scanner.load_prosite("data/prosite/prosite.dat")
        >>> matches = scanner.scan("MKVLFFVIAAGKSTFAM...")
        >>> for match in matches:
        ...     print(f"{match.motif_name} at {match.start}-{match.end}")
    """

    motifs: list[MotifPattern] = field(default_factory=lambda: BUILTIN_MOTIFS.copy())
    min_score: float = 0.3

    def add_motif(self, motif: MotifPattern) -> None:
        """Add a custom motif pattern."""
        self.motifs.append(motif)

    def load_prosite(
        self,
        filepath: str,
        include_skip: bool = False,
        replace: bool = False,
    ) -> int:
        """
        Load patterns from a PROSITE database file.

        Args:
            filepath: Path to prosite.dat file.
            include_skip: Include high-frequency patterns (default: False).
            replace: If True, replace existing patterns. If False, extend.

        Returns:
            Number of patterns loaded.
        """
        from pathlib import Path
        from giae.analysis.prosite import load_prosite_patterns

        prosite_patterns = load_prosite_patterns(Path(filepath), include_skip)

        if replace:
            self.motifs = prosite_patterns
        else:
            self.motifs.extend(prosite_patterns)

        return len(prosite_patterns)

    def scan(self, sequence: str) -> list[MotifMatch]:
        """
        Scan a sequence for all registered motifs.

        Args:
            sequence: Protein or nucleotide sequence.

        Returns:
            List of MotifMatch objects for all matches found.
        """
        sequence = sequence.upper()
        matches: list[MotifMatch] = []

        for motif in self.motifs:
            motif_matches = self._scan_for_motif(sequence, motif)
            matches.extend(motif_matches)

        # Sort by position
        matches.sort(key=lambda m: m.start)
        return matches

    def _scan_for_motif(
        self,
        sequence: str,
        motif: MotifPattern,
    ) -> list[MotifMatch]:
        """Scan for a specific motif pattern."""
        matches: list[MotifMatch] = []

        try:
            regex = re.compile(motif.pattern)

            for match in regex.finditer(sequence):
                score = motif.confidence_weight
                matched_seq = match.group()

                # Adjust score based on match quality
                # Longer matches in expected size range get higher scores
                expected_len = len(motif.pattern.replace("[", "").replace("]", "")) // 2
                if expected_len > 0:
                    len_ratio = len(matched_seq) / expected_len
                    if 0.8 <= len_ratio <= 1.2:
                        score *= 1.1

                if score >= self.min_score:
                    matches.append(MotifMatch(
                        motif_name=motif.name,
                        motif_description=motif.description,
                        start=match.start(),
                        end=match.end(),
                        matched_sequence=matched_seq,
                        score=min(score, 1.0),
                    ))

        except re.error:
            # Invalid regex pattern, skip this motif
            pass

        return matches

    def scan_categories(
        self,
        sequence: str,
        categories: list[str],
    ) -> list[MotifMatch]:
        """
        Scan for motifs in specific categories only.

        Args:
            sequence: Sequence to scan.
            categories: List of category names to include.

        Returns:
            List of matches in the specified categories.
        """
        # Temporarily filter motifs
        original_motifs = self.motifs
        self.motifs = [m for m in original_motifs if m.category in categories]

        try:
            return self.scan(sequence)
        finally:
            self.motifs = original_motifs

    def matches_to_evidence(
        self,
        matches: list[MotifMatch],
        gene_id: str,
    ) -> list[Evidence]:
        """
        Convert motif matches to Evidence objects.

        Args:
            matches: List of MotifMatch from scan().
            gene_id: ID of the gene that was scanned.

        Returns:
            List of Evidence objects for the matches.
        """
        evidence_list: list[Evidence] = []

        for match in matches:
            provenance = EvidenceProvenance(
                tool_name="giae_motif_scanner",
                tool_version="1.0.0",
                parameters={
                    "min_score": self.min_score,
                    "pattern_count": len(self.motifs),
                },
            )

            evidence = Evidence(
                evidence_type=EvidenceType.MOTIF_MATCH,
                gene_id=gene_id,
                description=(
                    f"Motif match: {match.motif_description} "
                    f"at positions {match.start}-{match.end}"
                ),
                confidence=match.score,
                raw_data={
                    "motif_name": match.motif_name,
                    "motif_description": match.motif_description,
                    "start": match.start,
                    "end": match.end,
                    "matched_sequence": match.matched_sequence,
                    "score": match.score,
                },
                provenance=provenance,
            )
            evidence_list.append(evidence)

        return evidence_list

    def analyze_gene(self, gene: Gene) -> list[Evidence]:
        """
        Analyze a gene for motifs and return evidence.

        Uses protein sequence if available.

        Args:
            gene: Gene object to analyze.

        Returns:
            List of Evidence objects from motif scanning.
        """
        if gene.protein:
            sequence = gene.protein.sequence
        else:
            sequence = gene.sequence

        matches = self.scan(sequence)
        return self.matches_to_evidence(matches, gene.id)


def get_motif_categories() -> list[str]:
    """Get list of available motif categories."""
    return list(set(m.category for m in BUILTIN_MOTIFS))


def describe_motifs() -> dict[str, list[str]]:
    """Get a description of all builtin motifs by category."""
    result: dict[str, list[str]] = {}
    for motif in BUILTIN_MOTIFS:
        if motif.category not in result:
            result[motif.category] = []
        result[motif.category].append(f"{motif.name}: {motif.description}")
    return result
