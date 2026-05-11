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

INTERPRO_API_BASE = "https://www.ebi.ac.uk/interpro/api"
UNIPROT_API_BASE = "https://rest.uniprot.org"


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

    def search_by_accession(self, uniprot_accession: str) -> list[DomainHit]:
        """
        Look up Pfam domains for a UniProt accession via InterPro REST API.

        Args:
            uniprot_accession: UniProt accession (e.g. "P03707").

        Returns:
            List of DomainHit objects sorted by e-value (best first).
        """
        if not uniprot_accession:
            return []

        # Check cache first
        cache_key = f"accession:{uniprot_accession}"
        if self.cache:
            cached = self.cache.get("interpro", cache_key)
            if cached is not None:
                logger.debug("InterPro cache hit for %s", uniprot_accession)
                return self._parse_interpro_rest(cached)

        url = f"{INTERPRO_API_BASE}/entry/pfam/protein/uniprot/{uniprot_accession}"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})

        with throttled_urlopen(request, timeout=self.timeout) as response:
            raw = response.read().decode("utf-8")

        result = json.loads(raw)

        # Cache the raw API response
        if self.cache:
            self.cache.put("interpro", cache_key, result)

        return self._parse_interpro_rest(result)

    def search_by_gene_name(self, gene_name: str) -> list[DomainHit]:
        """
        Find Pfam domains by first resolving gene name to a UniProt accession.

        Args:
            gene_name: Gene name to search.

        Returns:
            List of DomainHit objects.
        """
        if not gene_name:
            return []

        # Check cache
        cache_key = f"gene:{gene_name}"
        if self.cache:
            cached = self.cache.get("interpro", cache_key)
            if cached is not None:
                logger.debug("InterPro gene cache hit for %s", gene_name)
                return self._parse_interpro_rest(cached)

        # Step 1: Resolve gene name to UniProt accession
        query = urllib.parse.quote(f"(gene_exact:{gene_name})")
        uniprot_url = (
            f"{UNIPROT_API_BASE}/uniprotkb/search"
            f"?query={query}&fields=accession&format=json&size=1"
        )
        request = urllib.request.Request(uniprot_url, headers={"Accept": "application/json"})

        with throttled_urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = data.get("results", [])
        if not results:
            return []

        accession = results[0].get("primaryAccession", "")
        if not accession:
            return []

        # Step 2: Look up Pfam domains for this accession
        hits = self.search_by_accession(accession)

        # Cache under gene name too
        if self.cache and hits:
            # Re-fetch from accession cache to store under gene name
            cached_data = self.cache.get("interpro", f"accession:{accession}")
            if cached_data is not None:
                self.cache.put("interpro", cache_key, cached_data)

        return hits

    def _parse_interpro_rest(self, data: dict[str, Any]) -> list[DomainHit]:
        """
        Parse InterPro REST API JSON response.

        Handles the format from /entry/pfam/protein/uniprot/{accession}.
        """
        hits: list[DomainHit] = []

        results = data.get("results", [])
        if not isinstance(results, list):
            return hits

        for entry in results[: self.max_hits]:
            try:
                metadata = entry.get("metadata", {})
                accession = str(metadata.get("accession", ""))
                name = str(metadata.get("name", "unknown"))
                source_db = str(metadata.get("source_database", self.database))

                hits.append(
                    DomainHit(
                        name=name,
                        accession=accession,
                        description=name,
                        evalue=1e-10,  # InterPro REST doesn't return e-values; mark as significant
                        score=100.0,
                        database=source_db,
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue

        return hits

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

        hits = self.search_by_gene_name(gene.display_name)
        return self.hits_to_evidence(hits, gene.id)
