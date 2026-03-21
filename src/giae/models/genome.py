"""Genome data model for GIAE.

The Genome class is the top-level container representing
a complete genomic sequence with its annotations.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from giae.models.evidence import Evidence
from giae.models.gene import Gene
from giae.models.interpretation import Interpretation


@dataclass
class GenomeMetadata:
    """Metadata about a genome's origin and properties."""

    organism: str | None = None
    strain: str | None = None
    taxonomy_id: int | None = None
    assembly_accession: str | None = None
    definition: str | None = None
    keywords: list[str] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    dbxrefs: list[str] = field(default_factory=list)


@dataclass
class Genome:
    """
    A complete genome with its sequence, genes, and annotations.

    The Genome class is the primary data structure in GIAE. It holds
    the raw sequence, all identified genes, and provides methods
    for querying and analyzing the genomic content.

    Attributes:
        id: Unique identifier for this genome.
        name: Short name for the genome.
        description: Longer description/title.
        sequence: Complete nucleotide sequence.
        genes: List of genes identified in this genome.
        source_file: Path to the original input file.
        file_format: Format of the source file ("fasta" or "genbank").
        metadata: Additional metadata about the genome.
        created_at: When this genome object was created.

    Example:
        >>> genome = Genome(
        ...     name="E. coli K-12",
        ...     description="Escherichia coli str. K-12 substr. MG1655",
        ...     sequence="ATGCATGC...",
        ...     source_file=Path("ecoli.gb"),
        ...     file_format="genbank"
        ... )
    """

    name: str
    sequence: str
    source_file: Path
    file_format: str
    id: str = field(default_factory=lambda: f"genome_{uuid4().hex[:12]}")
    description: str = ""
    genes: list[Gene] = field(default_factory=list)
    metadata: GenomeMetadata = field(default_factory=GenomeMetadata)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate genome data after initialization."""
        self.sequence = self.sequence.upper()

        if self.file_format not in ("fasta", "genbank"):
            raise ValueError(f"Unsupported file format: {self.file_format}")

        valid_bases = {"A", "T", "G", "C", "N", "R", "Y", "S", "W", "K", "M", "B", "D", "H", "V"}
        invalid = set(self.sequence) - valid_bases
        if invalid:
            raise ValueError(f"Invalid characters in sequence: {invalid}")

    @property
    def length(self) -> int:
        """Length of the genome in base pairs."""
        return len(self.sequence)

    @property
    def gc_content(self) -> float:
        """Calculate GC content as a percentage."""
        if not self.sequence:
            return 0.0
        gc_count = self.sequence.count("G") + self.sequence.count("C")
        return round((gc_count / len(self.sequence)) * 100, 2)

    @property
    def gene_count(self) -> int:
        """Number of genes in this genome."""
        return len(self.genes)

    @property
    def interpreted_gene_count(self) -> int:
        """Number of genes that have interpretations."""
        return sum(1 for g in self.genes if g.has_interpretation)

    def get_gene_by_id(self, gene_id: str) -> Gene | None:
        """Find a gene by its ID."""
        for gene in self.genes:
            if gene.id == gene_id:
                return gene
        return None

    def get_gene_by_name(self, name: str) -> Gene | None:
        """Find a gene by its name or locus tag."""
        for gene in self.genes:
            if gene.name == name or gene.locus_tag == name:
                return gene
        return None

    def get_genes_in_region(self, start: int, end: int) -> list[Gene]:
        """Get all genes overlapping a genomic region."""
        return [g for g in self.genes if g.location.start < end and g.location.end > start]

    def iter_genes(self) -> Iterator[Gene]:
        """Iterate over genes in order of genomic position."""
        yield from sorted(self.genes, key=lambda g: g.location.start)

    def add_gene(self, gene: Gene) -> None:
        """Add a gene to this genome."""
        self.genes.append(gene)

    def get_all_evidence(self) -> list[Evidence]:
        """Collect all evidence from all genes."""
        evidence: list[Evidence] = []
        for gene in self.genes:
            evidence.extend(gene.evidence)
        return evidence

    def get_all_interpretations(self) -> list[Interpretation]:
        """Collect all interpretations from all genes."""
        interpretations: list[Interpretation] = []
        for gene in self.genes:
            interpretations.extend(gene.interpretations)
        return interpretations

    def get_summary(self) -> dict[str, Any]:
        """Generate a summary of the genome."""
        interpreted = self.interpreted_gene_count
        total_genes = self.gene_count

        return {
            "id": self.id,
            "name": self.name,
            "length_bp": self.length,
            "gc_content": self.gc_content,
            "total_genes": total_genes,
            "interpreted_genes": interpreted,
            "interpretation_coverage": (
                round(interpreted / total_genes * 100, 1) if total_genes > 0 else 0
            ),
            "source_file": str(self.source_file),
            "file_format": self.file_format,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize genome to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sequence_length": self.length,
            "gc_content": self.gc_content,
            "genes": [g.to_dict() for g in self.genes],
            "source_file": str(self.source_file),
            "file_format": self.file_format,
            "metadata": {
                "organism": self.metadata.organism,
                "strain": self.metadata.strain,
                "taxonomy_id": self.metadata.taxonomy_id,
                "assembly_accession": self.metadata.assembly_accession,
                "definition": self.metadata.definition,
                "keywords": self.metadata.keywords,
                "references": self.metadata.references,
                "dbxrefs": self.metadata.dbxrefs,
            },
            "created_at": self.created_at.isoformat(),
            "summary": self.get_summary(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], sequence: str) -> Genome:
        """Deserialize genome from a dictionary."""
        metadata = GenomeMetadata(
            organism=data["metadata"].get("organism"),
            strain=data["metadata"].get("strain"),
            taxonomy_id=data["metadata"].get("taxonomy_id"),
            assembly_accession=data["metadata"].get("assembly_accession"),
            definition=data["metadata"].get("definition"),
            keywords=data["metadata"].get("keywords", []),
            references=data["metadata"].get("references", []),
            dbxrefs=data["metadata"].get("dbxrefs", []),
        )

        genome = cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            sequence=sequence,
            source_file=Path(data["source_file"]),
            file_format=data["file_format"],
            metadata=metadata,
            created_at=datetime.fromisoformat(data["created_at"]),
        )

        # Genes would need to be deserialized separately with full objects
        return genome
