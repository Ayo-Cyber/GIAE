"""InterPro/HMMER web API integration for GIAE.

Provides multi-database domain detection using EBI's HMMER web service.
No local installation required. Searches Pfam and other domain databases,
giving GIAE access to 20,000+ protein family profiles.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from giae.analysis.cache import DiskCache
from giae.analysis.throttle import throttled_urlopen
from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.gene import Gene

logger = logging.getLogger(__name__)

EBI_HMMER_URL = "https://www.ebi.ac.uk/Tools/hmmer/search/hmmscan"


@dataclass
class DomainHit:
    """A protein domain hit from a profile HMM database."""

    name: str  # Domain name (e.g. "Pkinase")
    accession: str  # Database accession (e.g. "PF00069.24")
    description: str  # Domain description
    evalue: float  # E-value (lower = more significant)
    score: float  # Bit score (higher = more significant)
    database: str  # Source database (e.g. "pfam")

    @property
    def is_significant(self) -> bool:
        """Check if hit is statistically significant (e-value < 0.01)."""
        return self.evalue < 0.01

    @property
    def confidence(self) -> float:
        """Convert e-value to a 0–1 confidence score."""
        if self.evalue < 1e-20:
            return 0.95
        elif self.evalue < 1e-10:
            return 0.90
        elif self.evalue < 1e-5:
            return 0.80
        elif self.evalue < 1e-3:
            return 0.70
        elif self.evalue < 0.01:
            return 0.60
        else:
            return 0.45

    @property
    def summary(self) -> str:
        """One-line summary of the hit."""
        return f"{self.name} ({self.accession}): {self.description} [E={self.evalue:.1e}]"


@dataclass
class InterProClient:
    """
    Client for EBI's HMMER web service.

    Searches protein sequences against Pfam (and optionally TIGRfam)
    using the European Bioinformatics Institute's HMMER web API.
    Equivalent to running a local hmmscan without any installation.

    Attributes:
        timeout: HTTP timeout in seconds.
        max_hits: Maximum domain hits to return.
        database: HMM database to search ("pfam" or "tigrfam").

    Example:
        >>> client = InterProClient()
        >>> hits = client.search_sequence("MKVLIAGKS...")
        >>> for hit in hits:
        ...     print(hit.summary)
    """

    timeout: int = 60
    max_hits: int = 5
    database: str = "pfam"
    cache: DiskCache | None = None

    def search_sequence(self, sequence: str) -> list[DomainHit]:
        """
        Search a protein sequence against the Pfam domain database.

        Args:
            sequence: Protein amino acid sequence.

        Returns:
            List of DomainHit objects sorted by e-value (best first).
        """
        sequence = sequence.upper().replace("*", "").replace("-", "").strip()
        if len(sequence) < 20:
            return []

        # Check cache first
        if self.cache:
            cached = self.cache.get("interpro", sequence)
            if cached is not None:
                logger.debug("InterPro cache hit for sequence %s...", sequence[:20])
                return self._parse_response(cached)

        fasta = f">query\n{sequence}"
        post_data = urllib.parse.urlencode(
            {
                "seqdb": self.database,
                "seq": fasta,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            EBI_HMMER_URL,
            data=post_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

        with throttled_urlopen(request, timeout=self.timeout) as response:
            raw = response.read().decode("utf-8")

        result = json.loads(raw)

        # Cache the raw API response
        if self.cache:
            self.cache.put("interpro", sequence, result)

        return self._parse_response(result)

    def _parse_response(self, data: dict[str, Any]) -> list[DomainHit]:
        """
        Parse EBI HMMER API JSON response.

        Handles two known response formats from the EBI HMMER API.
        """
        hits: list[DomainHit] = []

        results = data.get("results", {})

        # Format 1: {"results": {"hits": [...]}} (current EBI API)
        hit_list: list[Any] = []
        if isinstance(results, dict):
            hit_list = results.get("hits", [])

        # Format 2: {"results": [{"hits": [...]}]} (legacy format)
        if not hit_list and isinstance(results, list):
            for item in results:
                if isinstance(item, dict) and "hits" in item:
                    hit_list = item["hits"]
                    break

        for raw_hit in hit_list[: self.max_hits]:
            try:
                evalue = float(raw_hit.get("evalue", 1.0))
                score = float(raw_hit.get("score", 0.0))

                if evalue >= 0.01:
                    continue

                hits.append(
                    DomainHit(
                        name=str(raw_hit.get("name", "unknown")),
                        accession=str(raw_hit.get("acc", raw_hit.get("accession", ""))),
                        description=str(raw_hit.get("desc", raw_hit.get("description", ""))),
                        evalue=evalue,
                        score=score,
                        database=self.database,
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue

        return sorted(hits, key=lambda h: h.evalue)

    def hits_to_evidence(self, hits: list[DomainHit], gene_id: str) -> list[Evidence]:
        """
        Convert DomainHit objects to GIAE Evidence objects.

        Args:
            hits: Domain hits from search_sequence().
            gene_id: ID of the gene that was searched.

        Returns:
            List of Evidence objects with DOMAIN_HIT type.
        """
        evidence_list: list[Evidence] = []

        for hit in hits:
            if not hit.is_significant:
                continue

            evidence_list.append(
                Evidence(
                    evidence_type=EvidenceType.DOMAIN_HIT,
                    gene_id=gene_id,
                    description=f"Pfam domain: {hit.name} — {hit.description}",
                    confidence=hit.confidence,
                    raw_data={
                        "domain_name": hit.name,
                        "accession": hit.accession,
                        "description": hit.description,
                        "evalue": hit.evalue,
                        "score": hit.score,
                        "database": hit.database,
                    },
                    provenance=EvidenceProvenance(
                        tool_name="hmmer_web",
                        tool_version="3.x",
                        database=f"EBI {hit.database.upper()}",
                    ),
                )
            )

        return evidence_list

    def analyze_gene(self, gene: Gene) -> list[Evidence]:
        """
        Analyze a gene by searching its protein against Pfam.

        Args:
            gene: Gene with an associated protein sequence.

        Returns:
            List of Evidence objects from domain search.
        """
        if not gene.protein or not gene.protein.sequence:
            return []

        hits = self.search_sequence(gene.protein.sequence)
        return self.hits_to_evidence(hits, gene.id)
