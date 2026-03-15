"""Unit tests for the Conflict Resolution Engine."""

from giae.engine.conflict import ConflictResolver, ConflictReport, ConflictSeverity
from giae.engine.hypothesis import FunctionalHypothesis

def make_hypothesis(function: str, confidence: float, source_type: str) -> FunctionalHypothesis:
    return FunctionalHypothesis(
        function=function,
        confidence=confidence,
        source_type=source_type,
        category="unknown",
        supporting_evidence_ids=[],
        reasoning_steps=[]
    )

def test_no_conflict_single_hypothesis():
    resolver = ConflictResolver()
    hypotheses = [
        make_hypothesis("Kinase", 0.9, "combined")
    ]
    report = resolver.check_conflicts(hypotheses)
    assert report.severity == ConflictSeverity.NONE
    assert report.recommended_action == "none"

def test_no_conflict_dominant_hypothesis():
    resolver = ConflictResolver(confidence_threshold=0.1)
    hypotheses = [
        make_hypothesis("Kinase", 0.9, "BLAST"),
        make_hypothesis("Phosphatase", 0.5, "Motif"),
    ]
    report = resolver.check_conflicts(hypotheses)
    assert report.severity == ConflictSeverity.NONE
    assert "dominant" in report.description

def test_low_conflict_similar_functions():
    resolver = ConflictResolver(confidence_threshold=0.1)
    hypotheses = [
        make_hypothesis("Serine/Threonine Kinase", 0.85, "BLAST"),
        make_hypothesis("Protein Kinase Domain", 0.82, "Motif"),
    ]
    report = resolver.check_conflicts(hypotheses)
    assert report.severity == ConflictSeverity.LOW
    assert report.recommended_action == "merge"

def test_high_conflict_different_functions():
    resolver = ConflictResolver(confidence_threshold=0.1)
    hypotheses = [
        make_hypothesis("DNA Polymerase", 0.85, "BLAST"),
        make_hypothesis("ATP Synthase", 0.84, "Motif"),
    ]
    report = resolver.check_conflicts(hypotheses)
    assert report.severity == ConflictSeverity.HIGH
    assert report.recommended_action == "flag_ambiguous"
    assert "Ambiguous" in report.description
