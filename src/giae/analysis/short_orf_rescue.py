"""Short ORF rescue scanner for GIAE.

A second-pass ORF finder that recovers genes missed by pyrodigal:
  - Short ORFs (< 90 bp / 30 aa) that fall below pyrodigal's min-length threshold
  - Nested / overlapping genes (e.g. phiX174 gene B inside gene A)

Rescued ORFs pass through an evidence gate combining two biological signals:
  - Ribosome binding site (Shine-Dalgarno) detected upstream of the start codon
  - Codon usage similarity to the rest of the genome

Both signals must pass for a gap-region ORF to be kept. Nested ORFs only
require the RBS signal (codon usage is skewed by the host gene's sequence).
"""

from __future__ import annotations

import re
from collections import Counter
from uuid import uuid4

from giae.models.gene import Gene, GeneLocation, Strand

# Only strong Shine-Dalgarno motifs (≥5 bp) — shorter ones appear by
# chance too often in a random 15 bp window.
_SD_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in ["AGGAGG", "GGAGG", "AGGAG"]
]

# Rescue uses ATG-only starts: GTG/TTG are valid in pyrodigal's model but
# produce too many spurious hits when scanning with a relaxed gate.
_START_CODONS = frozenset({"ATG"})
_STOP_CODONS = frozenset({"TAA", "TAG", "TGA"})

_COMPLEMENT = str.maketrans("ACGTN", "TGCAN")


def _revcomp(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def _rbs_score(sequence: str, start: int) -> int:
    """Count distinct SD motif hits in the -14 to -4 window upstream of start.

    The tighter window (-14 to -4 vs the classic -20 to -5) reduces random
    hits while covering the biologically active spacing range.
    """
    lo = max(0, start - 14)
    hi = max(0, start - 4)
    if hi <= lo:
        return 0
    window = sequence[lo:hi]
    return sum(1 for pat in _SD_PATTERNS if pat.search(window))


def _build_codon_table(genes: list[Gene]) -> dict[str, float]:
    """Return normalised codon frequencies from all existing gene sequences."""
    counts: Counter[str] = Counter()
    for gene in genes:
        seq = (gene.sequence or "").upper()
        if gene.location.strand == Strand.REVERSE:
            seq = _revcomp(seq)
        for i in range(0, len(seq) - 2, 3):
            codon = seq[i : i + 3]
            if len(codon) == 3 and set(codon) <= set("ACGT"):
                counts[codon] += 1
    total = sum(counts.values()) or 1
    return {c: n / total for c, n in counts.items()}


def _codon_score(nuc_seq: str, table: dict[str, float]) -> float:
    """Average codon frequency for nuc_seq under the genome's codon table."""
    if not table or len(nuc_seq) < 3:
        return 0.0
    scores = []
    for i in range(0, len(nuc_seq) - 2, 3):
        codon = nuc_seq[i : i + 3].upper()
        if len(codon) == 3:
            scores.append(table.get(codon, 0.0))
    return sum(scores) / len(scores) if scores else 0.0


def _scan_frame(seq: str, frame: int, min_aa: int) -> list[tuple[int, int]]:
    """
    Scan one reading frame and return (start, end) of ORFs ≥ min_aa.

    Coordinates are 0-based, exclusive-end, relative to `seq`.
    Takes the most upstream (longest) start for each stop codon window.
    """
    results: list[tuple[int, int]] = []
    seq_len = len(seq)
    last_stop = frame

    i = frame
    while i + 2 < seq_len:
        codon = seq[i : i + 3].upper()
        if codon in _STOP_CODONS:
            # Scan back for the earliest start codon in this window
            for j in range(last_stop, i, 3):
                if seq[j : j + 3].upper() in _START_CODONS:
                    if (i - j) // 3 >= min_aa:
                        results.append((j, i + 3))
                    break
            last_stop = i + 3
        i += 3

    return results


class ShortOrfRescue:
    """
    Two-mode ORF rescue layer that runs after pyrodigal.

    Gap-region sweep: finds short ORFs in regions between annotated genes,
    gated by RBS + codon usage signals.

    Nested scan: finds ORFs fully inside an existing gene's span (different
    frame or sub-interval), gated by RBS only.  This recovers phiX174-style
    overlapping genes.

    Args:
        min_aa: Minimum rescue ORF length in amino acids (default 20 / 60 bp).
        codon_usage_threshold: Minimum average codon frequency required for
            gap-region ORFs.  Approx genome average is ~0.016; 0.004 keeps
            only ORFs whose codons appear in the genome at all.
        scan_nested: Whether to scan inside existing gene bodies for sub-ORFs
            (catches phiX174-style overlapping / nested genes).
    """

    def __init__(
        self,
        min_aa: int = 20,
        codon_usage_threshold: float = 0.010,
        scan_nested: bool = False,
    ) -> None:
        self.min_aa = min_aa
        self.codon_usage_threshold = codon_usage_threshold
        self.scan_nested = scan_nested

    # ── Public API ────────────────────────────────────────────────────────────

    def rescue(self, genome_sequence: str, existing_genes: list[Gene]) -> list[Gene]:
        """
        Return rescued Gene objects not already represented in existing_genes.

        Args:
            genome_sequence: Full nucleotide genome sequence (forward strand).
            existing_genes: Genes already found by pyrodigal (used for overlap
                filtering and codon usage table construction).

        Returns:
            List of Gene objects with source='orf_rescue'.
        """
        seq = genome_sequence.upper()
        rc_seq = _revcomp(seq)
        seq_len = len(seq)

        codon_table = _build_codon_table(existing_genes)
        existing_spans = [(g.location.start, g.location.end) for g in existing_genes]

        rescued: list[Gene] = []
        seen_spans: set[tuple[int, int, Strand]] = set()

        def _add(start: int, end: int, strand: Strand, nuc: str) -> None:
            key = (start, end, strand)
            if key not in seen_spans:
                seen_spans.add(key)
                rescued.append(self._make_gene(start, end, strand, nuc))

        # ── Gap-region sweep (forward) ─────────────────────────────────────
        for frame in range(3):
            for start, end in _scan_frame(seq, frame, self.min_aa):
                if self._overlaps_any(start, end, existing_spans):
                    continue
                nuc = seq[start:end]
                if self._gap_gate(seq, start, nuc, codon_table):
                    _add(start, end, Strand.FORWARD, nuc)

        # ── Gap-region sweep (reverse) ─────────────────────────────────────
        for frame in range(3):
            for rc_start, rc_end in _scan_frame(rc_seq, frame, self.min_aa):
                fwd_start = seq_len - rc_end
                fwd_end = seq_len - rc_start
                if self._overlaps_any(fwd_start, fwd_end, existing_spans):
                    continue
                nuc = rc_seq[rc_start:rc_end]
                if self._gap_gate(rc_seq, rc_start, nuc, codon_table):
                    _add(fwd_start, fwd_end, Strand.REVERSE, nuc)

        # ── Nested scan ───────────────────────────────────────────────────
        if self.scan_nested:
            for host in existing_genes:
                h_start, h_end = host.location.start, host.location.end
                region_len = h_end - h_start
                if region_len < self.min_aa * 3 + 6:
                    continue

                # Forward sub-ORFs inside the host span
                region_fwd = seq[h_start:h_end]
                for frame in range(3):
                    for r_start, r_end in _scan_frame(region_fwd, frame, self.min_aa):
                        abs_start = h_start + r_start
                        abs_end = h_start + r_end
                        # Skip if identical to the host gene itself
                        if abs_start == h_start and abs_end == h_end:
                            continue
                        key = (abs_start, abs_end, Strand.FORWARD)
                        if key in seen_spans:
                            continue
                        nuc = region_fwd[r_start:r_end]
                        if _rbs_score(region_fwd, r_start) > 0:
                            _add(abs_start, abs_end, Strand.FORWARD, nuc)

                # Reverse sub-ORFs inside the host span
                region_rc = _revcomp(region_fwd)
                region_len = len(region_fwd)
                for frame in range(3):
                    for r_start, r_end in _scan_frame(region_rc, frame, self.min_aa):
                        abs_fwd_start = h_end - r_end
                        abs_fwd_end = h_end - r_start
                        if abs_fwd_start == h_start and abs_fwd_end == h_end:
                            continue
                        key = (abs_fwd_start, abs_fwd_end, Strand.REVERSE)
                        if key in seen_spans:
                            continue
                        nuc = region_rc[r_start:r_end]
                        if _rbs_score(region_rc, r_start) > 0:
                            _add(abs_fwd_start, abs_fwd_end, Strand.REVERSE, nuc)

        return rescued

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _overlaps_any(
        self, start: int, end: int, existing: list[tuple[int, int]]
    ) -> bool:
        """True if this span overlaps any existing gene by > 50% of its own length."""
        span_len = end - start
        for e_start, e_end in existing:
            inter = max(0, min(end, e_end) - max(start, e_start))
            if inter / span_len > 0.5:
                return True
        return False

    def _gap_gate(
        self,
        sequence: str,
        start: int,
        nuc_seq: str,
        codon_table: dict[str, float],
    ) -> bool:
        """Both RBS and codon usage must pass for a gap-region ORF."""
        rbs_ok = _rbs_score(sequence, start) > 0
        cu_ok = _codon_score(nuc_seq, codon_table) >= self.codon_usage_threshold
        return rbs_ok and cu_ok

    @staticmethod
    def _make_gene(start: int, end: int, strand: Strand, nuc_seq: str) -> Gene:
        gene_id = f"gene_{uuid4().hex[:12]}"
        return Gene(
            id=gene_id,
            location=GeneLocation(start=start, end=end, strand=strand),
            sequence=nuc_seq,
            source="orf_rescue",
            metadata={"feature_type": "CDS", "rescue": True},
        )
