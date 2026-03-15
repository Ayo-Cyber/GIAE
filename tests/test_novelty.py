"""Tests for the novel gene discovery engine."""

from __future__ import annotations

import pytest

from giae.engine.novelty import NoveltyScorer, NovelGeneReport, NovelGeneCandidate


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_result(
    gene_id: str,
    gene_name: str | None = None,
    success: bool = True,
    evidence_count: int = 0,
    confidence: float | None = None,
    conflict_severity: str | None = None,
    aggregated_evidence=None,
    interpretation=None,
):
    """Build a minimal mock InterpretationResult."""
    from types import SimpleNamespace

    agg = SimpleNamespace(evidence_count=evidence_count) if aggregated_evidence is None else aggregated_evidence

    if interpretation is None and confidence is not None:
        interp = SimpleNamespace(
            confidence_score=confidence,
            hypothesis="Some function",
            metadata={"conflict_severity": conflict_severity} if conflict_severity else {},
        )
    elif interpretation is None:
        interp = None
    else:
        interp = interpretation

    return SimpleNamespace(
        gene_id=gene_id,
        gene_name=gene_name,
        success=success,
        aggregated_evidence=agg if evidence_count > 0 else SimpleNamespace(evidence_count=0),
        interpretation=interp,
    )


def _make_genome(genes: list):
    from types import SimpleNamespace
    return SimpleNamespace(genes=genes)


def _make_gene(gene_id: str, protein_length: int = 100):
    from types import SimpleNamespace
    protein = SimpleNamespace(sequence="M" * protein_length)
    location = SimpleNamespace(start=0, end=protein_length * 3)
    return SimpleNamespace(id=gene_id, protein=protein, location=location)


def _make_summary(results: list):
    from types import SimpleNamespace
    return SimpleNamespace(results=results)


# ── NoveltyScorer tests ─────────────────────────────────────────────────────

class TestNoveltyScorer:
    def setup_method(self):
        self.scorer = NoveltyScorer()

    def test_dark_matter_gene_flagged(self):
        gene = _make_gene("g1", 200)
        result = _make_result("g1", "gp1", evidence_count=0)
        genome = _make_genome([gene])
        summary = _make_summary([result])

        report = self.scorer.analyze(genome, summary)

        assert report.dark_matter_count == 1
        assert report.total_novel == 1
        assert report.candidates[0].category == "dark_matter"
        assert report.candidates[0].gene_id == "g1"

    def test_well_interpreted_gene_not_flagged(self):
        gene = _make_gene("g1", 200)
        result = _make_result("g1", evidence_count=3, confidence=0.85)
        genome = _make_genome([gene])
        summary = _make_summary([result])

        report = self.scorer.analyze(genome, summary)

        assert report.total_novel == 0
        assert not report.has_novel_genes

    def test_weak_evidence_gene_flagged(self):
        gene = _make_gene("g1", 250)
        result = _make_result("g1", evidence_count=1, confidence=0.20)
        genome = _make_genome([gene])
        summary = _make_summary([result])

        report = self.scorer.analyze(genome, summary)

        assert report.weak_evidence_count == 1
        assert report.candidates[0].category == "weak_evidence"

    def test_conflict_gene_flagged(self):
        gene = _make_gene("g1", 150)
        result = _make_result("g1", evidence_count=4, confidence=0.35,
                              conflict_severity="HIGH")
        genome = _make_genome([gene])
        summary = _make_summary([result])

        report = self.scorer.analyze(genome, summary)

        assert report.conflict_count == 1
        assert report.candidates[0].category == "conflict"

    def test_failed_result_not_flagged(self):
        gene = _make_gene("g1", 100)
        result = _make_result("g1", success=False, evidence_count=0)
        genome = _make_genome([gene])
        summary = _make_summary([result])

        report = self.scorer.analyze(genome, summary)

        assert report.total_novel == 0

    def test_dark_matter_score_longer_protein_higher_priority(self):
        score_long = NoveltyScorer._dark_matter_score(400)
        score_short = NoveltyScorer._dark_matter_score(30)
        assert score_long > score_short

    def test_dark_matter_score_long(self):
        assert NoveltyScorer._dark_matter_score(400) == 0.95

    def test_dark_matter_score_medium(self):
        assert NoveltyScorer._dark_matter_score(200) == 0.85

    def test_dark_matter_score_short(self):
        assert NoveltyScorer._dark_matter_score(80) == 0.75

    def test_dark_matter_score_tiny(self):
        assert NoveltyScorer._dark_matter_score(20) == 0.55

    def test_candidates_sorted_by_novelty(self):
        genes = [_make_gene(f"g{i}", 50 + i * 100) for i in range(3)]
        results = [_make_result(f"g{i}", evidence_count=0) for i in range(3)]
        genome = _make_genome(genes)
        summary = _make_summary(results)

        report = self.scorer.analyze(genome, summary)

        scores = [c.novelty_score for c in report.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_top_priorities_returns_max_5(self):
        genes = [_make_gene(f"g{i}", 200) for i in range(10)]
        results = [_make_result(f"g{i}", evidence_count=0) for i in range(10)]
        genome = _make_genome(genes)
        summary = _make_summary(results)

        report = self.scorer.analyze(genome, summary)

        assert len(report.top_priorities) <= 5

    def test_suggested_experiments_present_for_dark_matter(self):
        gene = _make_gene("g1", 300)
        result = _make_result("g1", evidence_count=0)
        genome = _make_genome([gene])
        summary = _make_summary([result])

        report = self.scorer.analyze(genome, summary)

        assert len(report.candidates[0].suggested_experiments) > 0

    def test_report_has_novel_genes_false_when_empty(self):
        genome = _make_genome([])
        summary = _make_summary([])
        report = self.scorer.analyze(genome, summary)
        assert not report.has_novel_genes

    def test_novel_gene_candidate_display_name_uses_name(self):
        c = NovelGeneCandidate(
            gene_id="g1", gene_name="cI", protein_length=100,
            novelty_score=0.9, category="dark_matter",
            reason="test", evidence_count=0,
        )
        assert c.display_name == "cI"

    def test_novel_gene_candidate_display_name_falls_back_to_id(self):
        c = NovelGeneCandidate(
            gene_id="g1", gene_name=None, protein_length=100,
            novelty_score=0.9, category="dark_matter",
            reason="test", evidence_count=0,
        )
        assert c.display_name == "g1"

    def test_priority_label_high(self):
        c = NovelGeneCandidate(
            gene_id="g1", gene_name=None, protein_length=100,
            novelty_score=0.85, category="dark_matter",
            reason="test", evidence_count=0,
        )
        assert c.priority_label == "HIGH PRIORITY"

    def test_priority_label_medium(self):
        c = NovelGeneCandidate(
            gene_id="g1", gene_name=None, protein_length=100,
            novelty_score=0.60, category="weak_evidence",
            reason="test", evidence_count=1,
        )
        assert c.priority_label == "MEDIUM PRIORITY"

    def test_dark_matter_fraction(self):
        report = NovelGeneReport(
            total_novel=10,
            dark_matter_count=4,
            weak_evidence_count=4,
            conflict_count=2,
            candidates=[],
        )
        assert report.dark_matter_fraction == pytest.approx(0.4)

    def test_dark_matter_fraction_zero_total(self):
        report = NovelGeneReport(
            total_novel=0, dark_matter_count=0,
            weak_evidence_count=0, conflict_count=0,
            candidates=[],
        )
        assert report.dark_matter_fraction == 0.0
