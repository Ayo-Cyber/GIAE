"""UniProt API integration for GIAE.

Provides lightweight homology search and functional annotation
using UniProt's REST API - no local database required.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass

from giae.analysis.cache import DiskCache
from giae.analysis.throttle import throttled_urlopen
from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.gene import Gene

logger = logging.getLogger(__name__)

UNIPROT_API_BASE = "https://rest.uniprot.org"


@dataclass
class UniProtHit:
    """A UniProt database hit."""

    accession: str
    entry_name: str
    protein_name: str
    organism: str
    gene_names: list[str]
    function: str
    keywords: list[str]
    go_terms: list[str]
    identity: float  # Estimated from BLAST-like search
    length: int

    @property
    def summary(self) -> str:
        """One-line summary."""
        return f"{self.accession}: {self.protein_name} ({self.organism})"


@dataclass
class UniProtClient:
    """
    Client for UniProt REST API.

    Provides sequence-based search and lookup without requiring
    local BLAST installation or database downloads.

    Example:
        >>> client = UniProtClient()
        >>> hits = client.search_sequence("MKVLIFFVIA...")
        >>> for hit in hits:
        ...     print(hit.protein_name)
    """

    timeout: int = 30
    max_results: int = 5
    cache: DiskCache | None = None

    def search_sequence(self, sequence: str) -> list[UniProtHit]:
        """
        Search UniProt by sequence similarity.

        Uses UniProt's BLAST-like search to find similar proteins.

        Args:
            sequence: Protein sequence to search.

        Returns:
            List of UniProtHit objects.
        """
        # Clean sequence
        sequence = sequence.upper().replace("*", "").replace("-", "")

        if len(sequence) < 10:
            return []

        # Check cache first
        cache_key = sequence
        if self.cache:
            cached = self.cache.get("uniprot", cache_key)
            if cached is not None:
                logger.debug("UniProt cache hit for sequence %s...", sequence[:20])
                return self._parse_results(cached)

        # Use UniProt's sequence search endpoint
        url = f"{UNIPROT_API_BASE}/uniprotkb/search"
        params = {
            "query": f"sequence:{sequence[:100]}",  # Use first 100 aa
            "fields": "accession,id,protein_name,organism_name,gene_names,cc_function,keyword,go,length",
            "format": "json",
            "size": str(self.max_results),
        }

        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"

        request = urllib.request.Request(
            full_url,
            headers={"Accept": "application/json"},
        )

        with throttled_urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Cache the raw API response
        if self.cache:
            self.cache.put("uniprot", cache_key, data)

        return self._parse_results(data)

    def search_by_keyword(self, keyword: str) -> list[UniProtHit]:
        """
        Search UniProt by keyword or function.

        Args:
            keyword: Functional keyword to search.

        Returns:
            List of UniProtHit objects.
        """
        url = f"{UNIPROT_API_BASE}/uniprotkb/search"
        params = {
            "query": f"({keyword}) AND (reviewed:true)",
            "fields": "accession,id,protein_name,organism_name,gene_names,cc_function,keyword,go,length",
            "format": "json",
            "size": str(self.max_results),
        }

        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"

        request = urllib.request.Request(
            full_url,
            headers={"Accept": "application/json"},
        )

        with throttled_urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        return self._parse_results(data)

    def lookup_accession(self, accession: str) -> UniProtHit | None:
        """
        Look up a specific UniProt entry by accession.

        Args:
            accession: UniProt accession (e.g., "P12345").

        Returns:
            UniProtHit object or None if not found.
        """
        url = f"{UNIPROT_API_BASE}/uniprotkb/{accession}"
        params = {
            "fields": "accession,id,protein_name,organism_name,gene_names,cc_function,keyword,go,length",
            "format": "json",
        }

        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"

        request = urllib.request.Request(
            full_url,
            headers={"Accept": "application/json"},
        )

        with throttled_urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        hits = self._parse_single_result(data)
        return hits[0] if hits else None

    def _parse_results(self, data: dict) -> list[UniProtHit]:
        """Parse UniProt API results."""
        hits = []

        results = data.get("results", [])
        for entry in results:
            hit = self._entry_to_hit(entry)
            if hit:
                hits.append(hit)

        return hits

    def _parse_single_result(self, data: dict) -> list[UniProtHit]:
        """Parse a single UniProt entry."""
        hit = self._entry_to_hit(data)
        return [hit] if hit else []

    def _entry_to_hit(self, entry: dict) -> UniProtHit | None:
        """Convert a UniProt entry to UniProtHit."""
        try:
            accession = entry.get("primaryAccession", "")
            entry_name = entry.get("uniProtkbId", "")

            # Protein name
            protein_desc = entry.get("proteinDescription", {})
            rec_name = protein_desc.get("recommendedName", {})
            full_name = rec_name.get("fullName", {}).get("value", "Unknown protein")

            # Organism
            organism_data = entry.get("organism", {})
            organism = organism_data.get("scientificName", "Unknown")

            # Gene names
            gene_data = entry.get("genes", [])
            gene_names = []
            for gene in gene_data:
                if "geneName" in gene:
                    gene_names.append(gene["geneName"].get("value", ""))

            # Function from comments
            function = ""
            comments = entry.get("comments", [])
            for comment in comments:
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        function = texts[0].get("value", "")
                        break

            # Keywords
            keyword_data = entry.get("keywords", [])
            keywords = [kw.get("name", "") for kw in keyword_data]

            # GO terms
            go_terms = []
            xrefs = entry.get("uniProtKBCrossReferences", [])
            for xref in xrefs:
                if xref.get("database") == "GO":
                    go_terms.append(xref.get("id", ""))

            # Length
            length = entry.get("sequence", {}).get("length", 0)

            return UniProtHit(
                accession=accession,
                entry_name=entry_name,
                protein_name=full_name,
                organism=organism,
                gene_names=gene_names,
                function=function,
                keywords=keywords[:10],  # Limit keywords
                go_terms=go_terms[:10],  # Limit GO terms
                identity=0.0,  # Will be set by sequence comparison
                length=length,
            )

        except Exception:
            return None

    def hits_to_evidence(self, hits: list[UniProtHit], gene_id: str) -> list[Evidence]:
        """
        Convert UniProt hits to Evidence objects.

        Args:
            hits: List of UniProtHit from search.
            gene_id: ID of the gene that was searched.

        Returns:
            List of Evidence objects.
        """
        evidence_list = []

        for hit in hits:
            provenance = EvidenceProvenance(
                tool_name="uniprot_api",
                tool_version="1.0",
                database="UniProtKB/Swiss-Prot",
            )

            # Calculate confidence from available data
            confidence = 0.7  # Base confidence for UniProt hit
            if hit.function:
                confidence = 0.85  # Higher if function is known
            if "Reviewed" in str(hit.keywords):
                confidence = 0.9  # Swiss-Prot reviewed

            description = f"UniProt match: {hit.protein_name}"
            if hit.function:
                description += f" - {hit.function[:100]}"

            evidence = Evidence(
                evidence_type=EvidenceType.BLAST_HOMOLOGY,
                gene_id=gene_id,
                description=description,
                confidence=confidence,
                raw_data={
                    "accession": hit.accession,
                    "entry_name": hit.entry_name,
                    "protein_name": hit.protein_name,
                    "organism": hit.organism,
                    "function": hit.function,
                    "keywords": hit.keywords,
                    "go_terms": hit.go_terms,
                },
                provenance=provenance,
            )
            evidence_list.append(evidence)

        return evidence_list

    def analyze_gene(self, gene: Gene) -> list[Evidence]:
        """
        Analyze a gene by searching UniProt.

        Args:
            gene: Gene object with protein sequence.

        Returns:
            List of Evidence objects from UniProt search.
        """
        if not gene.protein:
            return []

        sequence = gene.protein.sequence
        hits = self.search_sequence(sequence)
        return self.hits_to_evidence(hits, gene.id)


def quick_uniprot_search(sequence: str) -> list[UniProtHit]:
    """Convenience function for quick UniProt search."""
    client = UniProtClient()
    return client.search_sequence(sequence)
