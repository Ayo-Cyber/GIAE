"""Main Interpreter orchestrator for GIAE.

Coordinates evidence extraction, aggregation, hypothesis generation,
and confidence scoring to produce complete interpretations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from giae.analysis.orf_finder import ORFFinder
from giae.analysis.motif import MotifScanner
from giae.engine.aggregator import EvidenceAggregator, AggregatedEvidence
from giae.engine.hypothesis import HypothesisGenerator, FunctionalHypothesis
from giae.engine.confidence import ConfidenceScorer, ConfidenceReport
from giae.models.genome import Genome
from giae.models.gene import Gene
from giae.models.evidence import Evidence
from giae.models.interpretation import (
    Interpretation,
    ConfidenceLevel,
    CompetingHypothesis,
)


@dataclass
class InterpretationResult:
    """Result of interpreting a single gene."""

    gene_id: str
    gene_name: str | None
    interpretation: Interpretation | None
    hypotheses: list[FunctionalHypothesis]
    confidence_reports: list[ConfidenceReport]
    aggregated_evidence: AggregatedEvidence | None
    success: bool
    error_message: str | None = None

    @property
    def summary(self) -> str:
        """One-line summary of the result."""
        if not self.success:
            return f"{self.gene_name or self.gene_id}: Failed - {self.error_message}"
        if self.interpretation:
            return self.interpretation.get_summary()
        return f"{self.gene_name or self.gene_id}: No interpretation available"


@dataclass
class GenomeInterpretationSummary:
    """Summary of interpreting an entire genome."""

    genome_id: str
    genome_name: str
    total_genes: int
    interpreted_genes: int
    high_confidence_count: int
    moderate_confidence_count: int
    low_confidence_count: int
    failed_genes: int
    processing_time_seconds: float
    results: list[InterpretationResult]

    @property
    def success_rate(self) -> float:
        """Percentage of genes successfully interpreted."""
        if self.total_genes == 0:
            return 0.0
        return (self.interpreted_genes / self.total_genes) * 100


@dataclass
class Interpreter:
    """
    Main interpretation orchestrator for GIAE.

    Coordinates all components of the interpretation pipeline:
    1. ORF finding (if needed)
    2. Evidence extraction (motifs)
    3. Evidence aggregation
    4. Hypothesis generation
    5. Confidence scoring
    6. Interpretation assembly

    Attributes:
        orf_finder: ORF finder for unannotated sequences.
        motif_scanner: Scanner for sequence motifs.
        aggregator: Evidence aggregation engine.
        hypothesis_generator: Hypothesis generation engine.
        confidence_scorer: Confidence scoring engine.
        find_orfs: Whether to run ORF finding on FASTA inputs.

    Example:
        >>> interpreter = Interpreter()
        >>> results = interpreter.interpret_genome(genome)
        >>> for result in results.results:
        ...     if result.interpretation:
        ...         print(result.interpretation.get_explanation())
    """

    orf_finder: ORFFinder = field(default_factory=ORFFinder)
    motif_scanner: MotifScanner = field(default_factory=MotifScanner)
    aggregator: EvidenceAggregator = field(default_factory=EvidenceAggregator)
    hypothesis_generator: HypothesisGenerator = field(default_factory=HypothesisGenerator)
    confidence_scorer: ConfidenceScorer = field(default_factory=ConfidenceScorer)
    find_orfs: bool = True
    use_uniprot: bool = True  # Enable UniProt API for homology search

    def interpret_genome(self, genome: Genome) -> GenomeInterpretationSummary:
        """
        Interpret all genes in a genome.

        Args:
            genome: Genome object with sequence and genes.

        Returns:
            GenomeInterpretationSummary with all results.
        """
        start_time = datetime.now(timezone.utc)
        results: list[InterpretationResult] = []

        # If no genes and we have FASTA, find ORFs
        if not genome.genes and genome.file_format == "fasta" and self.find_orfs:
            orfs = self.orf_finder.find_orfs(genome.sequence)
            genes = self.orf_finder.orfs_to_genes(orfs)
            for gene in genes:
                genome.add_gene(gene)

        # Interpret each gene
        for gene in genome.genes:
            result = self.interpret_gene(gene)
            results.append(result)

            # Attach interpretation to gene
            if result.interpretation:
                gene.add_interpretation(result.interpretation)

        # Calculate summary statistics
        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()

        high_conf = sum(
            1 for r in results
            if r.interpretation and r.interpretation.confidence_level == ConfidenceLevel.HIGH
        )
        mod_conf = sum(
            1 for r in results
            if r.interpretation and r.interpretation.confidence_level == ConfidenceLevel.MODERATE
        )
        low_conf = sum(
            1 for r in results
            if r.interpretation and r.interpretation.confidence_level in (
                ConfidenceLevel.LOW, ConfidenceLevel.SPECULATIVE
            )
        )
        failed = sum(1 for r in results if not r.success)

        return GenomeInterpretationSummary(
            genome_id=genome.id,
            genome_name=genome.name,
            total_genes=len(genome.genes),
            interpreted_genes=sum(1 for r in results if r.interpretation),
            high_confidence_count=high_conf,
            moderate_confidence_count=mod_conf,
            low_confidence_count=low_conf,
            failed_genes=failed,
            processing_time_seconds=processing_time,
            results=results,
        )

    def interpret_gene(self, gene: Gene) -> InterpretationResult:
        """
        Interpret a single gene.

        Args:
            gene: Gene object to interpret.

        Returns:
            InterpretationResult with interpretation or error.
        """
        try:
            # Step 1: Extract evidence (motifs only without BLAST)
            evidence = self._extract_evidence(gene)
            for e in evidence:
                gene.add_evidence(e)

            # Step 2: Aggregate evidence
            if not gene.evidence:
                return InterpretationResult(
                    gene_id=gene.id,
                    gene_name=gene.display_name,
                    interpretation=None,
                    hypotheses=[],
                    confidence_reports=[],
                    aggregated_evidence=None,
                    success=True,
                )

            aggregated = self.aggregator.aggregate(gene)

            # Step 3: Generate hypotheses
            hypotheses = self.hypothesis_generator.generate(aggregated)

            if not hypotheses:
                return InterpretationResult(
                    gene_id=gene.id,
                    gene_name=gene.display_name,
                    interpretation=None,
                    hypotheses=[],
                    confidence_reports=[],
                    aggregated_evidence=aggregated,
                    success=True,
                )

            # Step 4: Score confidence
            confidence_reports = self.confidence_scorer.score_batch(hypotheses, aggregated)

            # Step 5: Build interpretation from best hypothesis
            best_hypothesis = hypotheses[0]
            best_report = confidence_reports[0]

            # Create competing hypotheses from alternatives
            competing = []
            for i, h in enumerate(hypotheses[1:], 1):
                competing.append(CompetingHypothesis(
                    hypothesis=h.function,
                    confidence=h.confidence,
                    reason_not_preferred=(
                        f"Lower confidence ({h.confidence:.0%}) than primary hypothesis"
                    ),
                ))

            interpretation = Interpretation(
                gene_id=gene.id,
                hypothesis=best_hypothesis.function,
                confidence_score=best_report.adjusted_score,
                confidence_level=best_report.confidence_level,
                supporting_evidence_ids=best_hypothesis.supporting_evidence_ids,
                reasoning_chain=best_hypothesis.reasoning_steps,
                competing_hypotheses=competing,
                uncertainty_sources=[s.value for s in best_report.uncertainty_sources],
                metadata={
                    "category": best_hypothesis.category,
                    "keywords": best_hypothesis.keywords,
                },
            )

            return InterpretationResult(
                gene_id=gene.id,
                gene_name=gene.display_name,
                interpretation=interpretation,
                hypotheses=hypotheses,
                confidence_reports=confidence_reports,
                aggregated_evidence=aggregated,
                success=True,
            )

        except Exception as e:
            return InterpretationResult(
                gene_id=gene.id,
                gene_name=gene.display_name,
                interpretation=None,
                hypotheses=[],
                confidence_reports=[],
                aggregated_evidence=None,
                success=False,
                error_message=str(e),
            )

    def _extract_evidence(self, gene: Gene) -> list[Evidence]:
        """Extract evidence from a gene using available analyzers."""
        evidence: list[Evidence] = []

        # Motif scanning (always available)
        motif_evidence = self.motif_scanner.analyze_gene(gene)
        evidence.extend(motif_evidence)

        # UniProt API search (if enabled)
        if self.use_uniprot and gene.protein:
            try:
                from giae.analysis.uniprot import UniProtClient
                client = UniProtClient(max_results=3, timeout=15)
                uniprot_evidence = client.analyze_gene(gene)
                evidence.extend(uniprot_evidence)
            except Exception:
                pass  # Network error, skip UniProt

        return evidence

    def quick_interpret(self, sequence: str, sequence_type: str = "protein") -> str:
        """
        Quick interpretation of a raw sequence.

        Args:
            sequence: Protein or nucleotide sequence.
            sequence_type: "protein" or "nucleotide".

        Returns:
            Human-readable interpretation string.
        """
        from giae.models.gene import Gene, GeneLocation, Strand

        # Create a temporary gene
        gene = Gene(
            location=GeneLocation(start=0, end=len(sequence) * 3, strand=Strand.FORWARD),
            sequence=sequence if sequence_type == "nucleotide" else "N" * (len(sequence) * 3),
        )

        if sequence_type == "protein":
            from giae.models.protein import Protein
            gene.protein = Protein(gene_id=gene.id, sequence=sequence)

        result = self.interpret_gene(gene)

        if result.interpretation:
            return result.interpretation.get_explanation()
        elif result.hypotheses:
            return f"Possible function: {result.hypotheses[0].summary}"
        else:
            return "No functional prediction available for this sequence."
