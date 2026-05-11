"""Phage-aware nested ORF detection for GIAE.

Recovers phiX174-style overlapping genes (gene B inside gene A, gene E
inside gene D) that pyrodigal misses by design — its probabilistic model
penalises overlaps so it picks one gene per region.

This finder *requires* overlap with an existing gene (the "nested" criterion)
and applies a much stricter gate than gap-region rescue, because scanning
inside coding sequence produces many spurious frame-shifted ORFs.

Three signals make a real nested gene detectable:

  1. Position-weighted Shine-Dalgarno score — peak at -8 to -10 bp upstream
  2. Strict consensus motifs — only 5-6 bp SD cores
  3. Genome-wide codon usage match
  4. Boundary margin — reject ORFs whose start/end coincide with an
     existing gene's boundary (those are same-frame variants of the parent)
"""

from __future__ import annotations

import re
from collections import Counter
from uuid import uuid4

from giae.models.gene import Gene, GeneLocation, Strand

# Strong SD motifs only — anything shorter than 5 bp produces too many
# random hits for nested scanning to discriminate.
_SD_MOTIFS = [
    ("AGGAGG", 1.00),
    ("GGAGG", 0.75),
    ("AGGAG", 0.65),
]
_SD_PATTERNS = [(re.compile(m, re.IGNORECASE), w) for m, w in _SD_MOTIFS]

_START_CODONS = frozenset({"ATG", "GTG", "TTG"})
_STOP_CODONS = frozenset({"TAA", "TAG", "TGA"})

_COMPLEMENT = str.maketrans("ACGTN", "TGCAN")

# Canonical Shine-Dalgarno spacing peaks at 7-10 nt upstream. We weight
# by distance from peak (=9), falling linearly to 0 at the window edges.
_SD_PEAK = 9
_SD_WIDTH = 6


def _revcomp(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def _position_weight(distance_upstream: int) -> float:
    """Triangle weighting peaking at -9 bp, falling to 0 at -3 and -15."""
    return max(0.0, 1.0 - abs(distance_upstream - _SD_PEAK) / _SD_WIDTH)


def _weighted_sd_score(sequence: str, start: int) -> float:
    """Best (motif_weight × position_weight) for any SD hit upstream of start.

    Window scanned is [-15, -3] relative to the start codon. Returns 0 if
    no motif hits, up to 1.0 for AGGAGG at the canonical -9 position.
    """
    if start < 3:
        return 0.0
    lo = max(0, start - 15)
    hi = max(0, start - 3)
    if hi <= lo:
        return 0.0

    window = sequence[lo:hi]
    best = 0.0
    for pat, motif_weight in _SD_PATTERNS:
        for m in pat.finditer(window):
            motif_center = (m.start() + m.end()) / 2
            distance_upstream = start - lo - motif_center
            score = motif_weight * _position_weight(int(round(distance_upstream)))
            if score > best:
                best = score
    return best


def _build_codon_table(genes: list[Gene]) -> dict[str, float]:
    counts: Counter[str] = Counter()
    for g in genes:
        seq = (g.sequence or "").upper()
        if g.location.strand == Strand.REVERSE:
            seq = _revcomp(seq)
        for i in range(0, len(seq) - 2, 3):
            codon = seq[i : i + 3]
            if len(codon) == 3 and set(codon) <= set("ACGT"):
                counts[codon] += 1
    total = sum(counts.values()) or 1
    return {c: n / total for c, n in counts.items()}


def _codon_score(nuc_seq: str, table: dict[str, float]) -> float:
    if not table or len(nuc_seq) < 3:
        return 0.0
    scores = []
    for i in range(0, len(nuc_seq) - 2, 3):
        codon = nuc_seq[i : i + 3].upper()
        if len(codon) == 3:
            scores.append(table.get(codon, 0.0))
    return sum(scores) / len(scores) if scores else 0.0


def _scan_frame_all_starts(
    seq: str, frame: int, min_aa: int
) -> list[tuple[int, int]]:
    """Return ALL valid (start, end) ORFs ≥ min_aa in this frame.

    Unlike a "longest-ORF-per-block" scanner, this returns every internal
    start codon as a separate candidate. This is essential for detecting
    same-stop alternative starts like phiX174's gene A* (internal start
    within gene A, sharing A's stop codon).
    """
    results: list[tuple[int, int]] = []
    seq_len = len(seq)

    # Locate all stop codons in this frame plus a sentinel at end-of-seq
    stops: list[int] = []
    i = frame
    while i + 2 < seq_len:
        if seq[i : i + 3].upper() in _STOP_CODONS:
            stops.append(i)
        i += 3

    # For each ORF block (between stops) emit every internal start
    prev_block_start = frame
    for stop in stops:
        for j in range(prev_block_start, stop, 3):
            if seq[j : j + 3].upper() in _START_CODONS:
                if (stop - j) // 3 >= min_aa:
                    results.append((j, stop + 3))
        prev_block_start = stop + 3

    return results


class NestedOrfFinder:
    """Detects nested / overlapping ORFs missed by pyrodigal.

    Args:
        min_aa: Minimum nested ORF length (default 50). Higher than
            gap-region rescue's 20 because scanning inside coding regions
            produces more spurious candidates per genome.
        rbs_threshold: Minimum position-weighted SD score (default 0.6).
            AGGAGG at peak position scores 1.0, GGAGG at peak scores 0.75,
            anything weaker is rejected.
        codon_threshold: Minimum average codon frequency (default 0.012).
        boundary_margin: ORFs within this many bp of an existing gene's
            start AND end on the same strand are treated as near-duplicates
            and rejected.
    """

    def __init__(
        self,
        min_aa: int = 50,
        rbs_threshold: float = 0.7,
        codon_threshold: float = 0.012,
        boundary_margin: int = 9,
    ) -> None:
        self.min_aa = min_aa
        self.rbs_threshold = rbs_threshold
        self.codon_threshold = codon_threshold
        self.boundary_margin = boundary_margin

    def find_nested(
        self,
        genome_sequence: str,
        parents: list[Gene],
    ) -> list[Gene]:
        """Scan the genome for ORFs that overlap an existing gene.

        Returns Gene objects with source='nested_orf'. ORFs that fall in
        gap regions (no overlap with any parent) are NOT returned — those
        are handled by ShortOrfRescue.
        """
        if not parents:
            return []

        seq = genome_sequence.upper()
        rc_seq = _revcomp(seq)
        seq_len = len(seq)
        codon_table = _build_codon_table(parents)

        parent_spans = [
            (p.location.start, p.location.end, p.location.strand) for p in parents
        ]

        rescued: list[Gene] = []
        seen: set[tuple[int, int, Strand]] = set()
        for s, e, st in parent_spans:
            seen.add((s, e, st))

        # Forward strand
        for frame in range(3):
            for start, end in _scan_frame_all_starts(seq, frame, self.min_aa):
                if not self._overlaps_parent(start, end, parent_spans):
                    continue
                if self._is_near_duplicate(start, end, Strand.FORWARD, parent_spans):
                    continue
                nuc = seq[start:end]
                if not self._gate(seq, start, nuc, codon_table):
                    continue
                key = (start, end, Strand.FORWARD)
                if key in seen:
                    continue
                seen.add(key)
                rescued.append(self._make_gene(start, end, Strand.FORWARD, nuc))

        # Reverse strand — scan revcomp, then convert coords back
        for frame in range(3):
            for rc_start, rc_end in _scan_frame_all_starts(rc_seq, frame, self.min_aa):
                fwd_start = seq_len - rc_end
                fwd_end = seq_len - rc_start
                if not self._overlaps_parent(fwd_start, fwd_end, parent_spans):
                    continue
                if self._is_near_duplicate(
                    fwd_start, fwd_end, Strand.REVERSE, parent_spans
                ):
                    continue
                nuc = rc_seq[rc_start:rc_end]
                if not self._gate(rc_seq, rc_start, nuc, codon_table):
                    continue
                key = (fwd_start, fwd_end, Strand.REVERSE)
                if key in seen:
                    continue
                seen.add(key)
                rescued.append(self._make_gene(fwd_start, fwd_end, Strand.REVERSE, nuc))

        return rescued

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _overlaps_parent(
        start: int, end: int, parents: list[tuple[int, int, Strand]]
    ) -> bool:
        for p_start, p_end, _ in parents:
            if start < p_end and end > p_start:
                return True
        return False

    def _is_near_duplicate(
        self,
        start: int,
        end: int,
        strand: Strand,
        parents: list[tuple[int, int, Strand]],
    ) -> bool:
        m = self.boundary_margin
        for p_start, p_end, p_strand in parents:
            if strand != p_strand:
                continue
            if abs(start - p_start) < m and abs(end - p_end) < m:
                return True
        return False

    def _gate(
        self,
        sequence: str,
        start: int,
        nuc_seq: str,
        codon_table: dict[str, float],
    ) -> bool:
        if _weighted_sd_score(sequence, start) < self.rbs_threshold:
            return False
        if _codon_score(nuc_seq, codon_table) < self.codon_threshold:
            return False
        return True

    @staticmethod
    def _make_gene(start: int, end: int, strand: Strand, nuc_seq: str) -> Gene:
        return Gene(
            id=f"gene_{uuid4().hex[:12]}",
            location=GeneLocation(start=start, end=end, strand=strand),
            sequence=nuc_seq,
            source="nested_orf",
            metadata={"feature_type": "CDS", "nested": True},
        )
