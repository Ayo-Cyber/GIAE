"""Homology analysis module for GIAE.

Wraps local BLAST+ tools to find sequence similarities
and generate evidence for gene function prediction.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.gene import Gene


class BlastNotFoundError(Exception):
    """Raised when BLAST+ is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "BLAST+ not found. Please install BLAST+:\n"
            "  macOS: brew install blast\n"
            "  Ubuntu: sudo apt install ncbi-blast+\n"
            "  Or download from: https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/"
        )


@dataclass
class BlastHit:
    """A single BLAST hit result."""

    hit_id: str
    hit_description: str
    hit_accession: str
    e_value: float
    bit_score: float
    identity_percent: float
    query_coverage: float
    alignment_length: int
    mismatches: int
    gap_opens: int
    query_start: int
    query_end: int
    hit_start: int
    hit_end: int

    @property
    def is_significant(self) -> bool:
        """Check if this hit is statistically significant."""
        return self.e_value < 1e-5

    @property
    def is_high_identity(self) -> bool:
        """Check if this hit has high sequence identity."""
        return self.identity_percent >= 70.0


@dataclass
class HomologyAnalyzer:
    """
    Analyze sequence homology using local BLAST+.

    This class wraps the BLAST+ command-line tools to perform
    sequence similarity searches against local databases.

    Attributes:
        database: Path to BLAST database or name of NCBI database.
        blast_type: Type of BLAST to run ("blastp", "blastn", "blastx").
        evalue_threshold: E-value cutoff for significant hits.
        max_hits: Maximum number of hits to return per query.
        num_threads: Number of CPU threads to use.

    Example:
        >>> analyzer = HomologyAnalyzer(database="/path/to/nr")
        >>> hits = analyzer.search(protein_sequence)
        >>> for hit in hits:
        ...     print(f"{hit.hit_id}: {hit.identity_percent}%")
    """

    database: str
    blast_type: str = "blastp"
    evalue_threshold: float = 1e-5
    max_hits: int = 10
    num_threads: int = 4
    _blast_path: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate configuration and find BLAST executable."""
        if self.blast_type not in ("blastp", "blastn", "blastx", "tblastn", "tblastx"):
            raise ValueError(f"Unknown BLAST type: {self.blast_type}")

        self._blast_path = self._find_blast()

    def _find_blast(self) -> str | None:
        """Find the BLAST executable path."""
        try:
            result = subprocess.run(
                ["which", self.blast_type],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return None

    @property
    def is_available(self) -> bool:
        """Check if BLAST+ is available on this system."""
        return self._blast_path is not None

    def search(self, sequence: str, _gene_id: str | None = None) -> list[BlastHit]:
        """
        Search for homologous sequences.

        Args:
            sequence: Query sequence (protein or nucleotide).
            gene_id: Optional gene ID for tracking.

        Returns:
            List of BlastHit objects.

        Raises:
            BlastNotFoundError: If BLAST+ is not installed.
            RuntimeError: If BLAST execution fails.
        """
        if not self.is_available:
            raise BlastNotFoundError()

        query_path: Path | None = None
        output_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".fasta", delete=False) as query_file:
                query_file.write(f">query\n{sequence}\n")
                query_path = Path(query_file.name)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as out_file:
                output_path = Path(out_file.name)

            # Run BLAST
            if not self._blast_path:
                raise BlastNotFoundError()

            cmd = [
                str(self._blast_path),
                "-query",
                str(query_path),
                "-db",
                self.database,
                "-outfmt",
                "5",  # XML output
                "-evalue",
                str(self.evalue_threshold),
                "-max_target_seqs",
                str(self.max_hits),
                "-num_threads",
                str(self.num_threads),
                "-out",
                str(output_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                raise RuntimeError(f"BLAST failed: {result.stderr}")

            # Parse results
            return self._parse_blast_xml(output_path)

        finally:
            # Cleanup temp files
            if query_path:
                query_path.unlink(missing_ok=True)
            if output_path:
                output_path.unlink(missing_ok=True)

    def _parse_blast_xml(self, xml_path: Path) -> list[BlastHit]:
        """Parse BLAST XML output format 5."""
        hits: list[BlastHit] = []

        try:
            tree = ElementTree.parse(xml_path)
            root = tree.getroot()

            # Find all hits
            for hit in root.findall(".//Hit"):
                hit_id = hit.findtext("Hit_id", "")
                hit_def = hit.findtext("Hit_def", "")
                hit_accession = hit.findtext("Hit_accession", "")

                # Get best HSP for this hit
                hsp = hit.find(".//Hsp")
                if hsp is None:
                    continue

                # Extract HSP values
                bit_score = float(hsp.findtext("Hsp_bit-score", "0"))
                evalue = float(hsp.findtext("Hsp_evalue", "1"))
                identity = int(hsp.findtext("Hsp_identity", "0"))
                align_len = int(hsp.findtext("Hsp_align-len", "1"))
                mismatches = int(hsp.findtext("Hsp_gaps", "0"))
                gap_opens = int(hsp.findtext("Hsp_gaps", "0"))
                query_from = int(hsp.findtext("Hsp_query-from", "0"))
                query_to = int(hsp.findtext("Hsp_query-to", "0"))
                hit_from = int(hsp.findtext("Hsp_hit-from", "0"))
                hit_to = int(hsp.findtext("Hsp_hit-to", "0"))

                identity_percent = (identity / align_len * 100) if align_len > 0 else 0
                query_len = query_to - query_from + 1
                query_coverage = (query_len / align_len * 100) if align_len > 0 else 0

                hits.append(
                    BlastHit(
                        hit_id=hit_id,
                        hit_description=hit_def,
                        hit_accession=hit_accession,
                        e_value=evalue,
                        bit_score=bit_score,
                        identity_percent=round(float(identity_percent), 1),
                        query_coverage=round(float(query_coverage), 1),
                        alignment_length=align_len,
                        mismatches=mismatches,
                        gap_opens=gap_opens,
                        query_start=query_from,
                        query_end=query_to,
                        hit_start=hit_from,
                        hit_end=hit_to,
                    )
                )

        except ElementTree.ParseError as e:
            raise RuntimeError(f"Failed to parse BLAST XML: {e}") from e

        return hits

    def hits_to_evidence(self, hits: list[BlastHit], gene_id: str) -> list[Evidence]:
        """
        Convert BLAST hits to Evidence objects.

        Args:
            hits: List of BlastHit from search().
            gene_id: ID of the gene that was searched.

        Returns:
            List of Evidence objects for significant hits.
        """
        evidence_list: list[Evidence] = []

        for hit in hits:
            if not hit.is_significant:
                continue

            # Calculate confidence based on e-value and identity
            # Higher identity and lower e-value = higher confidence
            confidence = min(hit.identity_percent / 100, 0.99)

            provenance = EvidenceProvenance(
                tool_name=self.blast_type,
                tool_version="2.x",  # Could be detected dynamically
                parameters={
                    "evalue_threshold": self.evalue_threshold,
                    "max_hits": self.max_hits,
                },
                database=self.database,
            )

            evidence = Evidence(
                evidence_type=EvidenceType.BLAST_HOMOLOGY,
                gene_id=gene_id,
                description=(f"{hit.identity_percent:.0f}% identity to {hit.hit_description[:80]}"),
                confidence=confidence,
                raw_data={
                    "hit_id": hit.hit_id,
                    "hit_accession": hit.hit_accession,
                    "hit_description": hit.hit_description,
                    "e_value": hit.e_value,
                    "bit_score": hit.bit_score,
                    "identity_percent": hit.identity_percent,
                    "query_coverage": hit.query_coverage,
                    "alignment_length": hit.alignment_length,
                },
                provenance=provenance,
            )
            evidence_list.append(evidence)

        return evidence_list

    def analyze_gene(self, gene: Gene) -> list[Evidence]:
        """
        Analyze a gene for homology and return evidence.

        Uses the protein sequence if available, otherwise
        uses the nucleotide sequence with appropriate BLAST.

        Args:
            gene: Gene object to analyze.

        Returns:
            List of Evidence objects from homology search.
        """
        if gene.protein and self.blast_type == "blastp":
            sequence = gene.protein.sequence
        else:
            sequence = gene.sequence

        hits = self.search(sequence, gene.id)
        return self.hits_to_evidence(hits, gene.id)
