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

    def test_parse_interpro_rest_single_entry(self):
        """Test InterPro REST API response parsing."""
        data = {
            "results": [
                {
                    "metadata": {
                        "accession": "PF00069",
                        "name": "Pkinase",
                        "source_database": "pfam",
                    }
                }
            ]
        }
        hits = self.client._parse_interpro_rest(data)
        assert len(hits) == 1
        assert hits[0].name == "Pkinase"
        assert hits[0].accession == "PF00069"
        assert hits[0].database == "pfam"

    def test_parse_interpro_rest_multiple_entries(self):
        """Test parsing multiple domain entries."""
        data = {
            "results": [
                {
                    "metadata": {
                        "accession": "PF00069",
                        "name": "Pkinase",
                        "source_database": "pfam",
                    }
                },
                {
                    "metadata": {
                        "accession": "PF07714",
                        "name": "Pkinase_Tyr",
                        "source_database": "pfam",
                    }
                },
            ]
        }
        hits = self.client._parse_interpro_rest(data)
        assert len(hits) == 2
        assert hits[0].name == "Pkinase"
        assert hits[1].name == "Pkinase_Tyr"

    def test_parse_interpro_rest_empty(self):
        hits = self.client._parse_interpro_rest({"results": []})
        assert hits == []

    def test_parse_interpro_rest_malformed(self):
        hits = self.client._parse_interpro_rest({})
        assert hits == []

    def test_parse_interpro_rest_respects_max_hits(self):
        client = InterProClient(max_hits=2)
        entries = [
            {
                "metadata": {
                    "accession": f"PF0000{i}",
                    "name": f"Dom{i}",
                    "source_database": "pfam",
                }
            }
            for i in range(5)
        ]
        data = {"results": entries}
        hits = client._parse_interpro_rest(data)
        assert len(hits) <= 2

    def test_parse_interpro_rest_assigns_significant_evalue(self):
        """InterPro REST hits should be marked as significant (evalue=1e-10)."""
        data = {
            "results": [
                {
                    "metadata": {
                        "accession": "PF00069",
                        "name": "Pkinase",
                        "source_database": "pfam",
                    }
                }
            ]
        }
        hits = self.client._parse_interpro_rest(data)
        assert hits[0].evalue == 1e-10
        assert hits[0].is_significant is True

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
