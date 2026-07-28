"""Tests for the phage safety screener."""

from __future__ import annotations

from giae.analysis.safety import SafetyScreener


def _items(products):
    # (gene_id, gene_name, product, source)
    return [(f"g{i}", f"g{i}", p, "test") for i, p in enumerate(products)]


def test_lysogeny_flags_temperate():
    r = SafetyScreener().screen(_items([
        "integrase", "CI repressor", "major capsid protein",
    ]))
    assert r.lysogenic is True
    assert r.verdict == "caution"
    cats = {f.category for f in r.flags}
    assert "lysogeny" in cats


def test_amr_is_not_recommended():
    r = SafetyScreener().screen(_items([
        "class A beta-lactamase", "major tail protein",
    ]))
    assert r.verdict == "not_recommended"
    assert any(f.category == "amr" and f.severity == "critical" for f in r.flags)


def test_toxin_is_not_recommended():
    r = SafetyScreener().screen(_items([
        "Shiga toxin subunit A", "portal protein",
    ]))
    assert r.verdict == "not_recommended"
    assert any(f.category == "virulence" for f in r.flags)


def test_amr_outranks_lysogeny_in_verdict():
    r = SafetyScreener().screen(_items(["integrase", "aminoglycoside phosphotransferase"]))
    # carrying AMR is the harder gate than temperate lifestyle
    assert r.verdict == "not_recommended"
    assert r.lysogenic is True  # still reported


def test_clean_lytic_has_no_flags():
    r = SafetyScreener().screen(_items([
        "major capsid protein", "portal protein", "DNA polymerase", "tail fiber protein",
    ]))
    assert r.verdict == "no_flags"
    assert r.flags == []


def test_hypothetical_never_flags():
    # uninformative products must not trigger (e.g. bare "toxin" noise)
    r = SafetyScreener().screen(_items(["hypothetical protein", "uncharacterized protein"]))
    assert r.flags == []


def test_lambda_is_temperate_t7_is_lytic():
    """Real biology: lambda is the model temperate phage; T7 is strictly lytic."""
    from pathlib import Path
    from giae.parsers.genbank import GenBankParser
    root = Path(__file__).resolve().parent.parent
    lam = root / "case_studies" / "lambda_phage.gb"
    t7 = root / "case_studies" / "T7.gb"
    if not lam.exists() or not t7.exists():
        import pytest
        pytest.skip("case-study genomes not present")
    p, s = GenBankParser(), SafetyScreener()
    assert s.screen_genome(p.parse(lam)).lysogenic is True
    assert s.screen_genome(p.parse(t7)).lysogenic is False
