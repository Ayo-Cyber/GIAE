"""Tests for product normaliser + functional annotator."""

from __future__ import annotations

from datetime import datetime, timezone

from giae.analysis.functional_annotator import FunctionalAnnotator
from giae.analysis.product_normalizer import ProductNormalizer
from giae.engine.hypothesis import FunctionalHypothesis
from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.interpretation import ConfidenceLevel, Interpretation


# ── ProductNormalizer ─────────────────────────────────────────────────────────


def test_normalizer_strips_putative():
    n = ProductNormalizer()
    assert n.normalize("putative DNA polymerase") == "DNA polymerase"


def test_normalizer_strips_stacked_modifiers():
    n = ProductNormalizer()
    assert n.normalize("probable putative helicase") == "helicase"


def test_normalizer_drops_partial_fragment():
    n = ProductNormalizer()
    assert n.normalize("DNA gyrase subunit B [partial]") == "DNA gyrase subunit B"
    assert n.normalize("RNA polymerase (fragment)") == "RNA polymerase"


def test_normalizer_strips_ec_suffix():
    n = ProductNormalizer()
    assert n.normalize("alkaline phosphatase EC 3.1.3.1") == "alkaline phosphatase"


def test_normalizer_preserves_placeholders():
    n = ProductNormalizer()
    for ph in ("hypothetical protein", "uncharacterized protein", "Hypothetical Protein"):
        assert n.normalize(ph) == ph


def test_normalizer_collapses_whitespace():
    n = ProductNormalizer()
    assert n.normalize("DNA   polymerase   III") == "DNA polymerase III"


def test_normalizer_handles_empty():
    n = ProductNormalizer()
    assert n.normalize("") == ""
    assert n.normalize("   ") == ""


# ── FunctionalAnnotator ───────────────────────────────────────────────────────


def _make_evidence(description: str, raw_data: dict | None = None) -> Evidence:
    return Evidence(
        evidence_type=EvidenceType.DOMAIN_HIT,
        gene_id="g1",
        description=description,
        confidence=0.9,
        raw_data=raw_data or {},
        provenance=EvidenceProvenance(tool_name="test", tool_version="1.0"),
        timestamp=datetime.now(timezone.utc),
    )


def _make_interpretation(hypothesis: str = "DNA polymerase") -> Interpretation:
    return Interpretation(
        gene_id="g1",
        hypothesis=hypothesis,
        confidence_score=0.8,
        confidence_level=ConfidenceLevel.HIGH,
        supporting_evidence_ids=["ev1"],
        reasoning_chain=["test"],
        metadata={"category": "replication", "keyword": []},
    )


def test_annotator_pfam_lookup_assigns_cog():
    """A Pfam ID in evidence raw_data → direct COG/GO assignment."""
    a = FunctionalAnnotator()
    interp = _make_interpretation()
    ev = _make_evidence("DNA polymerase III", raw_data={"pfam_id": "PF00136"})
    hyps = [
        FunctionalHypothesis(
            function="DNA polymerase III",
            category="replication",
            confidence=0.9,
            supporting_evidence_ids=["ev1"],
            reasoning_steps=["test"],
            source_type="DOMAIN",
            keywords=["polymerase"],
        )
    ]
    a.annotate(interp, hyps, [ev])
    assert interp.metadata["pfam_id"] == "PF00136"
    assert interp.metadata["cog_category"] == "L"
    assert "Replication" in interp.metadata["cog_name"]
    assert interp.metadata["cog_source"] == "pfam"
    assert "GO:0003887" in interp.metadata["go_terms"]


def test_annotator_pfam_in_description():
    """Pfam ID embedded in evidence description also gets picked up."""
    a = FunctionalAnnotator()
    interp = _make_interpretation()
    ev = _make_evidence("Pfam hit: PF00009 GTP_EFTU translation factor")
    a.annotate(interp, [], [ev])
    assert interp.metadata.get("pfam_id") == "PF00009"
    assert interp.metadata.get("cog_category") == "J"


def test_annotator_falls_back_to_inferred_cog():
    """No Pfam evidence → COG inferred from GIAE category."""
    a = FunctionalAnnotator()
    interp = _make_interpretation()
    hyps = [
        FunctionalHypothesis(
            function="DNA polymerase",
            category="replication",
            confidence=0.7,
            supporting_evidence_ids=[],
            reasoning_steps=["test"],
            source_type="MOTIF",
            keywords=["polymerase"],
        )
    ]
    a.annotate(interp, hyps, [])
    assert interp.metadata["cog_category"] == "L"
    assert interp.metadata["cog_source"] == "inferred"


def test_annotator_normalizes_product():
    a = FunctionalAnnotator()
    interp = _make_interpretation("putative DNA polymerase III")
    a.annotate(interp, [], [])
    assert interp.metadata["normalized_product"] == "DNA polymerase III"


def test_annotator_handles_unknown_pfam():
    """A Pfam ID not in the bundled table falls through to inferred COG."""
    a = FunctionalAnnotator()
    interp = _make_interpretation()
    ev = _make_evidence("Pfam hit: PF99999 (unknown)")
    hyps = [
        FunctionalHypothesis(
            function="x",
            category="transcription",
            confidence=0.6,
            supporting_evidence_ids=[],
            reasoning_steps=["t"],
            source_type="MOTIF",
            keywords=[],
        )
    ]
    a.annotate(interp, hyps, [ev])
    # PF99999 not in table → inferred from category
    assert interp.metadata["cog_category"] == "K"
    assert interp.metadata["cog_source"] == "inferred"


def test_annotator_idempotent():
    """Running annotate twice gives the same metadata."""
    a = FunctionalAnnotator()
    interp = _make_interpretation()
    ev = _make_evidence("PF00136 DNA_pol_B")
    a.annotate(interp, [], [ev])
    first = dict(interp.metadata)
    a.annotate(interp, [], [ev])
    assert interp.metadata == first


def test_annotator_loaded_table_nonempty():
    """The bundled Pfam table actually loaded."""
    a = FunctionalAnnotator()
    assert len(a.pfam_table) > 50
    assert "PF00136" in a.pfam_table
