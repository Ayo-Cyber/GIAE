"""GenBank file parser for GIAE."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import cast

from Bio import SeqIO
from Bio.SeqFeature import SeqFeature
from Bio.SeqRecord import SeqRecord

from giae.models.gene import Gene, GeneLocation, Strand
from giae.models.genome import Genome, GenomeMetadata
from giae.models.protein import Protein
from giae.parsers.base import BaseParser, ParserError


class GenBankParser(BaseParser):
    """
    Parser for GenBank format genome files.

    GenBank files contain rich annotations including gene coordinates,
    protein translations, and metadata. This parser extracts all
    available information into the GIAE data model.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """File extensions this parser supports."""
        return (".gb", ".gbk", ".genbank", ".gbff")

    @property
    def format_name(self) -> str:
        """Name of the format this parser handles."""
        return "genbank"

    def parse(self, file_path: Path) -> Genome:
        """
        Parse a GenBank file and return a Genome object.

        Extracts the genome sequence, gene annotations, and
        translated protein sequences where available.

        Args:
            file_path: Path to the GenBank file.

        Returns:
            A fully populated Genome object with genes.

        Raises:
            ParserError: If parsing fails.
        """
        try:
            records = list(SeqIO.parse(file_path, "genbank"))  # type: ignore[no-untyped-call]
        except Exception as e:
            raise ParserError(f"Failed to parse GenBank file: {e}", file_path) from e

        if not records:
            raise ParserError("GenBank file contains no records", file_path)

        # Use first record as primary genome
        primary_record = records[0]

        return self._record_to_genome(primary_record, file_path)

    def _record_to_genome(self, record: SeqRecord, file_path: Path) -> Genome:
        """Convert a BioPython SeqRecord to a Genome object."""
        # Extract metadata
        metadata = self._extract_metadata(record)

        # Create base genome
        genome = Genome(
            name=str(record.name) if record.name else str(record.id),
            description=record.description,
            sequence=str(record.seq).upper(),
            source_file=file_path,
            file_format="genbank",
            metadata=metadata,
        )

        # Extract genes
        genes = self._extract_genes(record)
        for gene in genes:
            genome.add_gene(gene)

        return genome

    def _extract_metadata(self, record: SeqRecord) -> GenomeMetadata:
        """Extract metadata from a GenBank record."""
        annotations = record.annotations


        # Extract taxonomy id from source features
        taxonomy_id = None
        for feature in record.features:
            if feature.type == "source":
                qualifiers = feature.qualifiers
                db_xref = qualifiers.get("db_xref", [])
                for xref in db_xref:
                    if xref.startswith("taxon:"):
                        with contextlib.suppress(ValueError):
                            taxonomy_id = int(xref.split(":")[1])
                break

        # Extract references
        references = []
        refs: object = annotations.get("references", [])
        if isinstance(refs, list):
            for ref in refs:
                ref_dict = {
                    "title": getattr(ref, "title", None),
                    "authors": getattr(ref, "authors", None),
                    "journal": getattr(ref, "journal", None),
                    "pubmed_id": getattr(ref, "pubmed_id", None),
                }
                if any(ref_dict.values()):
                    references.append(ref_dict)

        # Extract dbxrefs
        dbxrefs = record.dbxrefs if hasattr(record, "dbxrefs") else []

        return GenomeMetadata(
            organism=str(annotations.get("organism")) if annotations.get("organism") else None,
            taxonomy_id=taxonomy_id,
            assembly_accession=str(annotations.get("accessions", [""])[0]) if isinstance(annotations.get("accessions", [""]), list) else "",
            definition=record.description,
            keywords=cast(list[str], annotations.get("keywords", [])),
            references=references,
            dbxrefs=list(dbxrefs),
        )

    def _extract_genes(self, record: SeqRecord) -> list[Gene]:
        """Extract gene features from a GenBank record."""
        genes: list[Gene] = []
        gene_counter: int = 0

        # Create a lookup for CDS features by locus_tag
        cds_by_locus: dict[str, SeqFeature] = {}
        for feature in record.features:
            if feature.type == "CDS":
                locus_tag = feature.qualifiers.get("locus_tag", [None])[0]
                if locus_tag:
                    cds_by_locus[locus_tag] = feature

        # Process gene features
        for feature in record.features:
            if feature.type == "gene":
                gene_counter += 1
                gene = self._feature_to_gene(feature, record, cds_by_locus)
                if gene:
                    genes.append(gene)

        # If no gene features, try CDS features directly
        if not genes:
            for feature in record.features:
                if feature.type == "CDS":
                    gene_counter += 1
                    gene = self._cds_to_gene(feature, record, gene_counter)
                    if gene:
                        genes.append(gene)

        return genes

    def _feature_to_gene(
        self,
        feature: SeqFeature,
        record: SeqRecord,
        cds_lookup: dict[str, SeqFeature],
    ) -> Gene | None:
        """Convert a gene feature to a Gene object."""
        qualifiers = feature.qualifiers

        # Extract location
        try:
            location = feature.location
            if location is None:
                return None
            start = int(location.start)
            end = int(location.end)
            strand = Strand.FORWARD if int(location.strand) >= 0 else Strand.REVERSE
        except (AttributeError, TypeError):
            return None

        # Extract sequence
        try:
            sequence = str(feature.extract(record.seq)).upper()  # type: ignore[no-untyped-call]
        except Exception:
            sequence = str(record.seq[start:end]).upper()  # type: ignore[index]

        # Extract identifiers
        gene_name = qualifiers.get("gene", [None])[0]
        locus_tag = qualifiers.get("locus_tag", [None])[0]
        is_pseudo = "pseudo" in qualifiers or "pseudogene" in qualifiers

        gene_location = GeneLocation(start=start, end=end, strand=strand)

        gene = Gene(
            name=gene_name,
            locus_tag=locus_tag,
            location=gene_location,
            sequence=sequence,
            is_pseudo=is_pseudo,
            source="annotation",
        )

        # Try to get protein from corresponding CDS
        if locus_tag and locus_tag in cds_lookup:
            cds_feature = cds_lookup[locus_tag]
            protein = self._extract_protein(cds_feature, gene.id)
            if protein:
                gene.protein = protein

        return gene

    def _cds_to_gene(
        self,
        feature: SeqFeature,
        record: SeqRecord,
        counter: int,
    ) -> Gene | None:
        """Convert a CDS feature to a Gene object."""
        qualifiers = feature.qualifiers

        # Extract location
        try:
            location = feature.location
            if location is None:
                return None
            start = int(location.start)
            end = int(location.end)
            strand = Strand.FORWARD if int(location.strand) >= 0 else Strand.REVERSE
        except (AttributeError, TypeError):
            return None

        # Extract sequence
        try:
            sequence = str(feature.extract(record.seq)).upper()  # type: ignore[no-untyped-call]
        except Exception:
            sequence = str(record.seq[start:end]).upper()  # type: ignore[index]

        # Extract identifiers
        gene_name = qualifiers.get("gene", [None])[0]
        locus_tag = qualifiers.get("locus_tag", [f"CDS_{counter:04d}"])[0]
        is_pseudo = "pseudo" in qualifiers

        gene_location = GeneLocation(start=start, end=end, strand=strand)

        gene = Gene(
            name=gene_name,
            locus_tag=locus_tag,
            location=gene_location,
            sequence=sequence,
            is_pseudo=is_pseudo,
            source="annotation",
        )

        # Extract protein
        protein = self._extract_protein(feature, gene.id)
        if protein:
            gene.protein = protein

        return gene

    def _extract_protein(self, cds_feature: SeqFeature, gene_id: str) -> Protein | None:
        """Extract protein information from a CDS feature."""
        qualifiers = cds_feature.qualifiers

        translation = qualifiers.get("translation", [None])[0]
        if not translation:
            return None

        product_name = qualifiers.get("product", [None])[0]

        return Protein(
            gene_id=gene_id,
            sequence=translation,
            product_name=product_name,
        )
