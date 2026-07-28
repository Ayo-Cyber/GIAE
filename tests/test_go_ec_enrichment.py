"""Tests for Swiss-Prot GO/EC enrichment of homology hits."""

from __future__ import annotations

import giae.engine.interpreter  # noqa: F401  (import first to resolve diamond<->engine cycle)
from giae.analysis.diamond import _accession_from_sseqid
from giae.analysis.functional_annotator import FunctionalAnnotator
from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.interpretation import ConfidenceLevel, Interpretation


def test_accession_parsing():
    assert _accession_from_sseqid("sp|P03709|FI_LAMBD") == "P03709"
    assert _accession_from_sseqid("tr|A0A123|SOMETHING") == "A0A123"
    assert _accession_from_sseqid("P12345") == "P12345"
    assert _accession_from_sseqid("") is None


def _interp():
    return Interpretation(
        gene_id="g1", hypothesis="portal protein", confidence_score=0.9,
        confidence_level=ConfidenceLevel.HIGH, supporting_evidence_ids=[],
        reasoning_chain=["homology hit"],
    )


def _hit(conf, ec=None, gos=None):
    raw = {"identity": conf, "hit_id": "sp|P0|X"}
    if ec:
        raw["ec_number"] = ec
    if gos:
        raw["go_terms"] = gos
    return Evidence(gene_id="g1", evidence_type=EvidenceType.BLAST_HOMOLOGY,
                    description="hit", confidence=conf, raw_data=raw,
                    provenance=EvidenceProvenance(tool_name="diamond", tool_version="test"))


def test_annotator_harvests_go_ec_from_homology():
    interp = _interp()
    ev = [_hit(0.95, ec="2.7.7.7", gos=["GO:0003677", "GO:0003887"])]
    FunctionalAnnotator().annotate(interp, [], ev)
    assert interp.metadata.get("ec_number") == "2.7.7.7"
    assert interp.metadata.get("go_terms") == ["GO:0003677", "GO:0003887"]


def test_annotator_prefers_highest_confidence_hit():
    interp = _interp()
    ev = [
        _hit(0.60, ec="1.1.1.1", gos=["GO:0000001"]),
        _hit(0.98, ec="2.7.7.7", gos=["GO:0003677"]),  # strongest hit wins
    ]
    FunctionalAnnotator().annotate(interp, [], ev)
    assert interp.metadata.get("ec_number") == "2.7.7.7"
    assert interp.metadata.get("go_terms") == ["GO:0003677"]


def test_no_homology_ids_leaves_metadata_clean():
    interp = _interp()
    FunctionalAnnotator().annotate(interp, [], [_hit(0.9)])  # hit with no EC/GO
    assert "go_terms" not in interp.metadata or interp.metadata["go_terms"]
    # ec_number only set if text/evidence carried one; "portal protein" has none
    assert interp.metadata.get("ec_number") is None
