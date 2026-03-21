"""Main Interpreter orchestrator for GIAE.

Coordinates evidence extraction, aggregation, hypothesis generation,
and confidence scoring to produce complete interpretations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from giae.analysis.ai import EsmPlugin
from giae.analysis.blast_local import BlastLocalPlugin
from giae.analysis.cache import DiskCache
from giae.analysis.hmmer import HmmerPlugin
from giae.analysis.motif import MotifScanner
from giae.analysis.orf_finder import ORFFinder
from giae.analysis.throttle import configure_throttle
from giae.engine.aggregator import AggregatedEvidence, EvidenceAggregator
from giae.engine.confidence import ConfidenceReport, ConfidenceScorer
from giae.engine.conflict import ConflictResolver, ConflictSeverity
from giae.engine.hypothesis import FunctionalHypothesis, HypothesisGenerator
from giae.engine.novelty import NovelGeneReport, NoveltyScorer
from giae.engine.plugin import PluginManager
from giae.models.evidence import Evidence
from giae.models.gene import Gene
from giae.models.genome import Genome
from giae.models.interpretation import (
    CompetingHypothesis,
    ConfidenceLevel,
    Interpretation,
)

logger = logging.getLogger(__name__)


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
    skipped_layers: list[str] = field(default_factory=list)

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
    novel_gene_report: NovelGeneReport | None = None

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
    conflict_threshold: float = 0.15
    use_interpro: bool = True
    use_cache: bool = True  # Enable disk caching of API responses
    max_api_concurrent: int = 3  # Max simultaneous API calls
    conflict_resolver: ConflictResolver = field(init=False)
    plugin_manager: PluginManager = field(init=False)
    novelty_scorer: NoveltyScorer = field(init=False)
    cache: DiskCache = field(init=False)

    def __post_init__(self) -> None:
        """Initialize components."""
        self.conflict_resolver = ConflictResolver(self.conflict_threshold)
        self.novelty_scorer = NoveltyScorer()

        # Initialize API cache
        self.cache = DiskCache(enabled=self.use_cache)

        # Configure API rate limiting
        configure_throttle(self.max_api_concurrent)

        # Auto-load PROSITE patterns if available
        self._load_prosite_data()

        # Initialize plugins
        self.plugin_manager = PluginManager()

        # Register HMMER plugin
        # Default path: ~/.giae/hmmer/pfam.hmm
        hmmer_db = Path.home() / ".giae" / "hmmer" / "pfam.hmm"
        self.plugin_manager.register(HmmerPlugin(hmmer_db))

        # Register ESM-2 plugin
        self.plugin_manager.register(EsmPlugin())

        # Register Local BLAST plugin
        # Default path: ~/.giae/blast/swissprot
        blast_db = Path.home() / ".giae" / "blast" / "swissprot"
        self.plugin_manager.register(BlastLocalPlugin(blast_db))

    def _load_prosite_data(self) -> None:
        """Auto-load PROSITE patterns from bundled data or user directory."""
        import importlib.resources
        import logging

        logger = logging.getLogger(__name__)

        # 1. Try bundled package data using importlib.resources
        try:
            # This works when installed via pip (wheel or sdist)
            # The data is logically packaged under 'giae.data.prosite'
            bundled_res = importlib.resources.files("giae").joinpath(
                "data", "prosite", "prosite.dat"
            )
            # importlib.resources gives a Traversable, which might be in a zip.
            # MotifScanner requires a string/Path to a real file.
            import importlib.resources.abc

            # Using as_file ensures it's extracted to a temp file if in a zip,
            # or just returns the path if it's on disk.
            with importlib.resources.as_file(bundled_res) as bundled_path:
                if bundled_path.exists():
                    try:
                        count = self.motif_scanner.load_prosite(str(bundled_path))
                        logger.info(
                            f"Loaded {count} PROSITE patterns from bundled data ({bundled_path})"
                        )
                        return
                    except Exception as e:
                        logger.debug(f"Failed to load bundled PROSITE data: {e}")
        except Exception as e:
            logger.debug(f"importlib.resources failed to find PROSITE: {e}")

        # 2. Try user-downloaded data (~/.giae/prosite/prosite.dat)
        user_path = Path.home() / ".giae" / "prosite" / "prosite.dat"
        if user_path.exists():
            try:
                count = self.motif_scanner.load_prosite(str(user_path))
                logger.info(f"Loaded {count} PROSITE patterns from {user_path}")
                return
            except Exception as e:
                logger.debug(f"Failed to load user PROSITE data: {e}")

        # 3. Try project data directory (development mode fallback)
        # __file__ is src/giae/engine/interpreter.py
        # root is src/giae/engine/../../.. -> repository root
        project_path = (
            Path(__file__).parent.parent.parent.parent / "data" / "prosite" / "prosite.dat"
        )
        if project_path.exists():
            try:
                count = self.motif_scanner.load_prosite(str(project_path))
                logger.info(f"Loaded {count} PROSITE patterns from project data")
                return
            except Exception as e:
                logger.debug(f"Failed to load project PROSITE data: {e}")

        # Fall back to builtin motifs (already loaded by default)
        logger.warning(
            "No PROSITE database found! Falling back to 8 builtin motifs. Interpretation quality will be low."
        )

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
            1
            for r in results
            if r.interpretation and r.interpretation.confidence_level == ConfidenceLevel.HIGH
        )
        mod_conf = sum(
            1
            for r in results
            if r.interpretation and r.interpretation.confidence_level == ConfidenceLevel.MODERATE
        )
        low_conf = sum(
            1
            for r in results
            if r.interpretation
            and r.interpretation.confidence_level
            in (ConfidenceLevel.LOW, ConfidenceLevel.SPECULATIVE)
        )
        failed = sum(1 for r in results if not r.success)

        summary = GenomeInterpretationSummary(
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

        # Identify novel/uncharacterised genes as research opportunities
        summary.novel_gene_report = self.novelty_scorer.analyze(genome, summary)

        return summary

    def interpret_gene(self, gene: Gene) -> InterpretationResult:
        """
        Interpret a single gene.

        Args:
            gene: Gene object to interpret.

        Returns:
            InterpretationResult with interpretation or error.
        """
        try:
            # Step 1: Extract evidence (motifs and plugins)
            evidence, skipped_layers = self._extract_evidence(gene)

            # Run plugins
            plugin_evidence = self.plugin_manager.scan_gene(gene)
            evidence.extend(plugin_evidence)

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
                    skipped_layers=skipped_layers,
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
                    skipped_layers=skipped_layers,
                )

            # Step 4: Score confidence
            confidence_reports = self.confidence_scorer.score_batch(hypotheses, aggregated)

            # Step 5: Build interpretation from best hypothesis
            best_hypothesis = hypotheses[0]
            best_report = confidence_reports[0]

            # Create competing hypotheses from alternatives
            competing = []
            for _i, h in enumerate(hypotheses[1:], 1):
                competing.append(
                    CompetingHypothesis(
                        hypothesis=h.function,
                        confidence=h.confidence,
                        reason_not_preferred=(
                            f"Lower confidence ({h.confidence:.0%}) than primary hypothesis"
                        ),
                    )
                )

            # Step 6: Check for conflicts
            conflict = self.conflict_resolver.check_conflicts(hypotheses)

            final_hypothesis = best_hypothesis.function
            final_confidence = best_report.adjusted_score
            final_level = best_report.confidence_level.value
            uncertainty_sources = [s.value for s in best_report.uncertainty_sources]
            reasoning = best_hypothesis.reasoning_steps.copy()

            if conflict.severity in (ConflictSeverity.MODERATE, ConflictSeverity.HIGH):
                # Downgrade confidence on conflict
                final_confidence *= 0.8  # Penalty
                uncertainty_sources.append("conflicting_evidence")
                reasoning.append(f"Output flagged: {conflict.description}")

                # If severe, explicitly mark hypothesis as Ambiguous
                if conflict.severity == ConflictSeverity.HIGH:
                    final_hypothesis = f"{conflict.description}"
                    final_level = "low"

            interpretation = Interpretation(
                gene_id=gene.id,
                hypothesis=final_hypothesis,
                confidence_score=final_confidence,
                confidence_level=ConfidenceLevel(final_level),
                supporting_evidence_ids=best_hypothesis.supporting_evidence_ids,
                reasoning_chain=reasoning,
                competing_hypotheses=competing,
                uncertainty_sources=uncertainty_sources,
                metadata={
                    "category": best_hypothesis.category,
                    "keyword": best_hypothesis.keywords,
                    "conflict_severity": conflict.severity.name,
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
                skipped_layers=skipped_layers,
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

    def _extract_evidence(self, gene: Gene) -> tuple[list[Evidence], list[str]]:
        """Extract evidence from a gene using available analyzers.

        Returns:
            Tuple of (evidence_list, skipped_layers).
        """
        evidence: list[Evidence] = []
        skipped: list[str] = []

        # Motif scanning (always available)
        motif_evidence = self.motif_scanner.analyze_gene(gene)
        evidence.extend(motif_evidence)

        # UniProt API search (if enabled)
        if self.use_uniprot and gene.protein:
            try:
                from giae.analysis.uniprot import UniProtClient

                client = UniProtClient(max_results=3, timeout=15, cache=self.cache)
                uniprot_evidence = client.analyze_gene(gene)
                evidence.extend(uniprot_evidence)
            except Exception as exc:
                logger.warning("UniProt search failed for %s: %s", gene.display_name, exc)
                skipped.append("UniProt")

        # InterPro/HMMER web API domain search (if enabled)
        if self.use_interpro and gene.protein:
            try:
                from giae.analysis.interpro import InterProClient

                interpro_client = InterProClient(timeout=45, max_hits=5, cache=self.cache)
                domain_evidence = interpro_client.analyze_gene(gene)
                evidence.extend(domain_evidence)
            except Exception as exc:
                logger.warning("InterPro search failed for %s: %s", gene.display_name, exc)
                skipped.append("InterPro")

        return evidence, skipped

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
