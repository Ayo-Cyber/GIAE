"""Tests for the InterPro/HMMER web API client."""

from __future__ import annotations

import pytest

from giae.analysis.interpro import DomainHit, InterProClient
from giae.models.evidence import EvidenceType

# ── DomainHit unit tests ────────────────────────────────────────────────────


class TestDomainHit:
    def test_confidence_very_significant(self):
        hit = DomainHit("PF00069", "PF00069.24", "Protein kinase", 1e-25, 300.0, "pfam")
        assert hit.confidence == 0.95

    def test_confidence_significant(self):
        hit = DomainHit("PF00069", "PF00069.24", "Protein kinase", 1e-12, 150.0, "pfam")
        assert hit.confidence == 0.90

    def test_confidence_moderate(self):
        hit = DomainHit("PF00069", "PF00069.24", "Protein kinase", 1e-7, 80.0, "pfam")
        assert hit.confidence == 0.80

    def test_confidence_weak(self):
        hit = DomainHit("PF00069", "PF00069.24", "Protein kinase", 5e-4, 30.0, "pfam")
        assert hit.confidence == 0.70

    def test_confidence_marginal(self):
        hit = DomainHit("PF00069", "PF00069.24", "Protein kinase", 0.005, 15.0, "pfam")
        assert hit.confidence == 0.60

    def test_confidence_insignificant(self):
        hit = DomainHit("PF00069", "PF00069.24", "Protein kinase", 0.5, 5.0, "pfam")
        assert hit.confidence == 0.45

    def test_is_significant_true(self):
        hit = DomainHit("PF00069", "PF00069.24", "Protein kinase", 1e-10, 200.0, "pfam")
        assert hit.is_significant is True

    def test_is_significant_false(self):
        hit = DomainHit("PF00069", "PF00069.24", "Protein kinase", 0.05, 10.0, "pfam")
        assert hit.is_significant is False

    def test_summary_format(self):
        hit = DomainHit("Pkinase", "PF00069.24", "Protein kinase domain", 1e-10, 200.0, "pfam")
        assert "Pkinase" in hit.summary
        assert "PF00069.24" in hit.summary
        assert "Protein kinase domain" in hit.summary


# ── InterProClient parsing tests ────────────────────────────────────────────


class TestInterProClientParsing:
    def setup_method(self):
        self.client = InterProClient(timeout=10, max_hits=5)

    def test_parse_response_format1(self):
        """Test current EBI HMMER API response format."""
        data = {
            "results": {
                "hits": [
                    {
                        "name": "Pkinase",
                        "acc": "PF00069.24",
                        "desc": "Protein kinase domain",
                        "score": 250.3,
                        "evalue": 1.5e-74,
                    }
                ]
            }
        }
        hits = self.client._parse_response(data)
        assert len(hits) == 1
        assert hits[0].name == "Pkinase"
        assert hits[0].accession == "PF00069.24"
        assert hits[0].description == "Protein kinase domain"
        assert hits[0].evalue == pytest.approx(1.5e-74)

    def test_parse_response_format2(self):
        """Test legacy EBI HMMER API response format."""
        data = {
            "results": [
                {
                    "hits": [
                        {
                            "name": "Pkinase",
                            "acc": "PF00069.24",
                            "desc": "Protein kinase domain",
                            "score": 250.3,
                            "evalue": 1.5e-74,
                        }
                    ]
                }
            ]
        }
        hits = self.client._parse_response(data)
        assert len(hits) == 1
        assert hits[0].name == "Pkinase"

    def test_parse_response_filters_weak_hits(self):
        """Hits with evalue >= 0.01 should be filtered out."""
        data = {
            "results": {
                "hits": [
                    {
                        "name": "Strong",
                        "acc": "PF00001",
                        "desc": "Strong hit",
                        "score": 200.0,
                        "evalue": 1e-10,
                    },
                    {
                        "name": "Weak",
                        "acc": "PF00002",
                        "desc": "Weak hit",
                        "score": 5.0,
                        "evalue": 0.05,
                    },
                ]
            }
        }
        hits = self.client._parse_response(data)
        assert len(hits) == 1
        assert hits[0].name == "Strong"

    def test_parse_response_sorted_by_evalue(self):
        """Hits should be returned sorted best (lowest evalue) first."""
        data = {
            "results": {
                "hits": [
                    {
                        "name": "Second",
                        "acc": "PF00002",
                        "desc": "B",
                        "score": 100.0,
                        "evalue": 1e-8,
                    },
                    {
                        "name": "First",
                        "acc": "PF00001",
                        "desc": "A",
                        "score": 200.0,
                        "evalue": 1e-20,
                    },
                ]
            }
        }
        hits = self.client._parse_response(data)
        assert hits[0].name == "First"
        assert hits[1].name == "Second"

    def test_parse_response_empty(self):
        hits = self.client._parse_response({"results": {"hits": []}})
        assert hits == []

    def test_parse_response_malformed(self):
        hits = self.client._parse_response({})
        assert hits == []

    def test_parse_response_respects_max_hits(self):
        client = InterProClient(max_hits=2)
        hits_data = [
            {
                "name": f"Dom{i}",
                "acc": f"PF0000{i}",
                "desc": f"Domain {i}",
                "score": 100.0,
                "evalue": 10 ** -(i + 5),
            }
            for i in range(5)
        ]
        data = {"results": {"hits": hits_data}}
        hits = client._parse_response(data)
        assert len(hits) <= 2

    def test_hits_to_evidence(self):
        hits = [
            DomainHit("Pkinase", "PF00069.24", "Protein kinase domain", 1e-30, 300.0, "pfam"),
        ]
        evidence_list = self.client.hits_to_evidence(hits, "gene_001")
        assert len(evidence_list) == 1
        ev = evidence_list[0]
        assert ev.evidence_type == EvidenceType.DOMAIN_HIT
        assert ev.gene_id == "gene_001"
        assert ev.confidence > 0.9
        assert ev.raw_data["domain_name"] == "Pkinase"
        assert ev.raw_data["accession"] == "PF00069.24"
        assert ev.provenance.tool_name == "hmmer_web"

    def test_hits_to_evidence_skips_insignificant(self):
        hits = [
            DomainHit("Weak", "PF00001", "Weak domain", 0.5, 3.0, "pfam"),
        ]
        evidence_list = self.client.hits_to_evidence(hits, "gene_001")
        assert len(evidence_list) == 0

    def test_search_sequence_too_short(self):
        """Sequences shorter than 20 aa should return empty without API call."""
        result = self.client.search_sequence("MKVLIAS")
        assert result == []
