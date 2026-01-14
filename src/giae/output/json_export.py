"""JSON export utilities for GIAE.

Provides serialization of all GIAE data structures to JSON format.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from giae.models.genome import Genome
    from giae.engine.interpreter import GenomeInterpretationSummary


class GIAEJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for GIAE objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "value"):  # For enums
            return obj.value
        return super().default(obj)


def export_genome_json(
    genome: Genome,
    include_sequence: bool = False,
    include_evidence: bool = True,
    indent: int = 2,
) -> str:
    """
    Export a Genome to JSON format.

    Args:
        genome: Genome object to export.
        include_sequence: Whether to include full sequences.
        include_evidence: Whether to include evidence details.
        indent: JSON indentation level.

    Returns:
        JSON string representation.
    """
    data = {
        "id": genome.id,
        "name": genome.name,
        "description": genome.description,
        "length": genome.length,
        "gc_content": genome.gc_content,
        "gene_count": genome.gene_count,
        "source_file": str(genome.source_file),
        "file_format": genome.file_format,
        "created_at": genome.created_at.isoformat(),
        "metadata": {
            "organism": genome.metadata.organism,
            "strain": genome.metadata.strain,
            "taxonomy_id": genome.metadata.taxonomy_id,
            "assembly_accession": genome.metadata.assembly_accession,
        },
    }

    if include_sequence:
        data["sequence"] = genome.sequence

    # Export genes
    genes_data = []
    for gene in genome.genes:
        gene_data = {
            "id": gene.id,
            "name": gene.name,
            "locus_tag": gene.locus_tag,
            "location": {
                "start": gene.location.start,
                "end": gene.location.end,
                "strand": gene.location.strand.value,
            },
            "length": gene.length,
            "is_pseudo": gene.is_pseudo,
            "source": gene.source,
        }

        if include_sequence:
            gene_data["sequence"] = gene.sequence

        if gene.protein:
            gene_data["protein"] = {
                "id": gene.protein.id,
                "length": gene.protein.length,
                "molecular_weight": gene.protein.molecular_weight,
                "product_name": gene.protein.product_name,
            }
            if include_sequence:
                gene_data["protein"]["sequence"] = gene.protein.sequence

        if include_evidence and gene.evidence:
            gene_data["evidence"] = [e.to_dict() for e in gene.evidence]

        if gene.interpretations:
            gene_data["interpretations"] = [i.to_dict() for i in gene.interpretations]

        genes_data.append(gene_data)

    data["genes"] = genes_data

    return json.dumps(data, indent=indent, cls=GIAEJSONEncoder)


def export_interpretation_json(
    summary: GenomeInterpretationSummary,
    indent: int = 2,
) -> str:
    """
    Export interpretation results to JSON format.

    Args:
        summary: GenomeInterpretationSummary from interpreter.
        indent: JSON indentation level.

    Returns:
        JSON string representation.
    """
    data = {
        "genome_id": summary.genome_id,
        "genome_name": summary.genome_name,
        "statistics": {
            "total_genes": summary.total_genes,
            "interpreted_genes": summary.interpreted_genes,
            "success_rate": round(summary.success_rate, 2),
            "high_confidence": summary.high_confidence_count,
            "moderate_confidence": summary.moderate_confidence_count,
            "low_confidence": summary.low_confidence_count,
            "failed": summary.failed_genes,
        },
        "processing_time_seconds": summary.processing_time_seconds,
        "results": [],
    }

    for result in summary.results:
        result_data = {
            "gene_id": result.gene_id,
            "gene_name": result.gene_name,
            "success": result.success,
        }

        if result.error_message:
            result_data["error"] = result.error_message

        if result.interpretation:
            result_data["interpretation"] = result.interpretation.to_dict()

        if result.hypotheses:
            result_data["hypotheses"] = [
                {
                    "function": h.function,
                    "category": h.category,
                    "confidence": h.confidence,
                    "reasoning": h.reasoning_steps,
                }
                for h in result.hypotheses
            ]

        if result.aggregated_evidence:
            result_data["evidence_summary"] = {
                "count": result.aggregated_evidence.evidence_count,
                "types": result.aggregated_evidence.type_diversity,
                "weighted_score": result.aggregated_evidence.total_weighted_score,
            }

        data["results"].append(result_data)

    return json.dumps(data, indent=indent, cls=GIAEJSONEncoder)


def export_evidence_json(evidence_list: list, indent: int = 2) -> str:
    """Export a list of Evidence objects to JSON."""
    return json.dumps(
        [e.to_dict() for e in evidence_list],
        indent=indent,
        cls=GIAEJSONEncoder,
    )
