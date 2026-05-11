"""Unit tests for NestedOrfFinder."""

from __future__ import annotations

from giae.analysis.nested_orf_finder import (
    NestedOrfFinder,
    _position_weight,
    _scan_frame_all_starts,
    _weighted_sd_score,
)
from giae.models.gene import Gene, GeneLocation, Strand


def _make_parent(start: int, end: int, sequence: str, strand: Strand = Strand.FORWARD) -> Gene:
    return Gene(
        id=f"parent_{start}_{end}",
        location=GeneLocation(start=start, end=end, strand=strand),
        sequence=sequence[start:end],
        source="orf_prediction",
    )


# ── Position-weight curve ────────────────────────────────────────────────────

def test_position_weight_peaks_at_minus_nine():
    assert _position_weight(9) == 1.0


def test_position_weight_falls_off_at_edges():
    assert _position_weight(3) == 0.0
    assert _position_weight(15) == 0.0


def test_position_weight_symmetric_around_peak():
    assert _position_weight(7) == _position_weight(11)


# ── SD scoring ────────────────────────────────────────────────────────────────

def test_aggagg_at_peak_position_scores_one():
    # AGGAGG centred at 9 bp upstream of start at index 20
    seq = "N" * 8 + "AGGAGG" + "N" * 6 + "ATG" + "N" * 100
    score = _weighted_sd_score(seq, 20)
    assert score >= 0.99


def test_no_sd_signal_scores_zero():
    seq = "T" * 30 + "ATG" + "N" * 100
    assert _weighted_sd_score(seq, 30) == 0.0


def test_aggag_scores_below_aggagg():
    full_aggagg = "N" * 8 + "AGGAGG" + "N" * 6 + "ATG"
    weak_aggag = "N" * 8 + "AGGAG" + "N" * 7 + "ATG"
    full = _weighted_sd_score(full_aggagg, 20)
    weak = _weighted_sd_score(weak_aggag, 20)
    assert weak < full


# ── Frame scanner emits all internal starts ──────────────────────────────────

def test_scan_frame_emits_internal_starts():
    # Construct a frame-0 ORF block: ATG (pos 0) -- ATG (pos 30) -- TAA (pos 90)
    seq = "ATG" + "AAA" * 9 + "ATG" + "AAA" * 19 + "TAA" + "AAA" * 5
    orfs = _scan_frame_all_starts(seq, 0, min_aa=5)
    starts = sorted(s for s, _ in orfs)
    assert 0 in starts
    assert 30 in starts


def test_scan_frame_respects_min_aa():
    # ATG ... TAA with 5 codons of ORF (incl. start) — min_aa=6 should drop it
    seq = "ATG" + "AAA" * 4 + "TAA" + "AAA" * 5
    assert _scan_frame_all_starts(seq, 0, min_aa=6) == []
    assert _scan_frame_all_starts(seq, 0, min_aa=5) != []


# ── End-to-end integration ───────────────────────────────────────────────────

def test_finder_returns_empty_with_no_parents():
    finder = NestedOrfFinder()
    assert finder.find_nested("ATG" * 100, []) == []


def test_finder_skips_orfs_outside_parent_spans():
    """An ORF in a gap region (no overlap with any parent) is NOT nested."""
    # Parent at 0-90, candidate ATG at 200 with strong RBS would still be
    # rejected because it doesn't overlap any parent.
    parent_seq = "ATG" + "GCT" * 28 + "TAA" + "T" * 100
    rbs_window = "AGGAGG"
    candidate = "AAA" * 3 + rbs_window + "T" * 6 + "ATG" + "GCT" * 60 + "TAA"
    seq = parent_seq + candidate

    parent = _make_parent(0, 90, seq)
    finder = NestedOrfFinder(min_aa=20, rbs_threshold=0.0, codon_threshold=0.0)
    nested = finder.find_nested(seq, [parent])
    # Candidate at offset ~109 doesn't overlap parent (0-90) → must be empty
    assert all(g.location.start < 90 for g in nested) or nested == []


def test_finder_rejects_near_duplicate_of_parent():
    """An ORF within boundary_margin of an existing gene's start AND end is rejected."""
    # Build a parent and a near-duplicate ORF (start+3, end+0 → both within 9 bp)
    coding = "ATG" + "GCT" * 60 + "TAA"  # 186 bp
    seq = "T" * 20 + coding + "T" * 20  # parent at 20-206
    parent = _make_parent(20, 206, seq)
    finder = NestedOrfFinder(
        min_aa=10, rbs_threshold=0.0, codon_threshold=0.0, boundary_margin=9
    )
    nested = finder.find_nested(seq, [parent])
    # The parent ORF itself is found by the scanner but must be filtered as duplicate
    assert all(
        not (abs(g.location.start - 20) < 9 and abs(g.location.end - 206) < 9)
        for g in nested
    )


def test_finder_respects_min_aa():
    """Nested ORFs shorter than min_aa are dropped."""
    # Parent: 600 bp ORF in frame 0
    parent_coding = "ATG" + "GCT" * 198 + "TAA"
    seq = parent_coding
    parent = _make_parent(0, len(parent_coding), seq)
    # min_aa=200 means anything < 200 codons is filtered
    finder = NestedOrfFinder(min_aa=200, rbs_threshold=0.0, codon_threshold=0.0)
    nested = finder.find_nested(seq, [parent])
    for g in nested:
        aa = (g.location.end - g.location.start) // 3
        assert aa >= 200
