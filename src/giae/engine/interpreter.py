"""Main Interpreter orchestrator for GIAE.

Coordinates evidence extraction, aggregation, hypothesis generation,
and confidence scoring to produce complete interpretations.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from giae.analysis.ai import EsmPlugin
from giae.analysis.aragorn import AragornFinder
from giae.analysis.barrnap import BarrnapFinder
from giae.analysis.functional_annotator import FunctionalAnnotator
from giae.analysis.nested_orf_finder import NestedOrfFinder
from giae.analysis.short_orf_rescue import ShortOrfRescue
from giae.analysis.blast_local import BlastLocalPlugin
from giae.analysis.cache import DiskCache
from giae.analysis.diamond import DiamondPlugin
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
from giae.models.evidence import Evidence, EvidenceType
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
    use_diamond: bool = True  # Enable Diamond BLASTP (preferred over BLAST+ when available)
    use_local_blast: bool = True  # Enable local BLAST+ plugin (fallback when Diamond absent)
    use_hmmer: bool = True  # Enable HMMER/pyhmmer plugin (C extension — not fork-safe)
    use_esm: bool = True  # Enable ESM-2/torch plugin (C extension — not fork-safe)
    use_cache: bool = True  # Enable disk caching of API responses
    use_aragorn: bool = True  # Enable Aragorn tRNA/tmRNA detection
    use_barrnap: bool = True  # Enable Barrnap rRNA detection
    use_rescue: bool = True   # Enable short ORF / nested ORF rescue pass
    phage_mode: bool = False  # Enable phage-aware nested ORF detection
    max_api_concurrent: int = 3  # Max simultaneous API calls
    conflict_resolver: ConflictResolver = field(init=False)
    plugin_manager: PluginManager = field(init=False)
    novelty_scorer: NoveltyScorer = field(init=False)
    cache: DiskCache = field(init=False)
    aragorn_finder: AragornFinder = field(init=False)
    barrnap_finder: BarrnapFinder = field(init=False)
    rescue_scanner: ShortOrfRescue = field(init=False)
    nested_finder: NestedOrfFinder = field(init=False)
    functional_annotator: FunctionalAnnotator = field(init=False)

    def __post_init__(self) -> None:
        """Initialize components."""
        self.conflict_resolver = ConflictResolver(self.conflict_threshold)
        self.novelty_scorer = NoveltyScorer()
        self.aragorn_finder = AragornFinder()
        self.barrnap_finder = BarrnapFinder()
        self.rescue_scanner = ShortOrfRescue()
        self.nested_finder = NestedOrfFinder()
        self.functional_annotator = FunctionalAnnotator()

        # Initialize API cache
        self.cache = DiskCache(enabled=self.use_cache)

        # Configure API rate limiting
        configure_throttle(self.max_api_concurrent)

        # Auto-load PROSITE patterns if available
        self._load_prosite_data()

        # Initialize plugins
        self.plugin_manager = PluginManager()

        # Register HMMER plugin (skip in worker/offline mode — pyhmmer is not fork-safe)
        if self.use_hmmer:
            hmmer_db = Path.home() / ".giae" / "hmmer" / "pfam.hmm"
            self.plugin_manager.register(HmmerPlugin(hmmer_db))

        # Register ESM-2 plugin (skip in worker/offline mode — torch is not fork-safe)
        if self.use_esm:
            self.plugin_manager.register(EsmPlugin())

        # Register local homology search: Diamond preferred, BLAST+ as fallback.
        # Both flags must be True and the respective binary+DB must be present
        # for the plugin to actually register (PluginManager calls is_available()).
        if self.use_diamond:
            diamond_db = Path.home() / ".giae" / "diamond" / "swissprot"
            diamond_plugin = DiamondPlugin(diamond_db)
            self.plugin_manager.register(diamond_plugin)
            _diamond_active = diamond_plugin.is_available()
        else:
            _diamond_active = False

        if self.use_local_blast and not _diamond_active:
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
            bundled_res = importlib.resources.files("giae") / "data" / "prosite" / "prosite.dat"
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

        # Run ORF prediction when annotations are absent or suspiciously sparse.
        # The FASTA-only guard was too narrow — GenBank files can also arrive
        # with very few CDS features relative to genome length (e.g. draft
        # assemblies, RefSeq entries that only annotate a subset of ORFs).
        # Threshold: < 0.3 genes / kb on genomes ≥ 5 kb signals under-annotation.
        if self.find_orfs:
            genome_length_kb = len(genome.sequence) / 1000.0
            gene_density = len(genome.genes) / genome_length_kb if genome_length_kb > 0 else 0
            needs_orfs = not genome.genes or (
                genome_length_kb >= 5.0 and gene_density < 0.3
            )
            if needs_orfs:
                orfs = self.orf_finder.find_orfs(genome.sequence)
                orf_genes = self.orf_finder.orfs_to_genes(orfs)
                if genome.genes:
                    # Only add predictions that don't overlap an existing annotated gene.
                    existing_spans = [
                        (g.location.start, g.location.end) for g in genome.genes
                    ]
                    orf_genes = [
                        g for g in orf_genes
                        if not any(
                            g.location.start < e_end and g.location.end > e_start
                            for e_start, e_end in existing_spans
                        )
                    ]
                for gene in orf_genes:
                    genome.add_gene(gene)

        # Short ORF / nested ORF rescue pass — runs after pyrodigal so the
        # codon usage table is built from full-length high-confidence genes.
        if self.use_rescue and genome.sequence:
            rescued = self.rescue_scanner.rescue(genome.sequence, list(genome.genes))
            for gene in rescued:
                genome.add_gene(gene)

        # Phage-aware nested ORF detection — recovers overlapping genes
        # (gene B inside gene A, gene E inside gene D) that pyrodigal drops.
        if self.phage_mode and genome.sequence:
            nested = self.nested_finder.find_nested(genome.sequence, list(genome.genes))
            for gene in nested:
                genome.add_gene(gene)

        # Detect non-coding RNAs (tRNA via Aragorn, rRNA via Barrnap).
        # Both finders skip silently when the binary is absent.
        # We apply the same overlap-filter so ncRNA predictions never
        # displace existing annotated features.
        for ncrna_genes, enabled in (
            (
                self.aragorn_finder.find_trnas(genome.sequence, genome.name)
                if self.use_aragorn
                else [],
                self.use_aragorn,
            ),
            (
                self.barrnap_finder.find_rrnas(genome.sequence, genome.name)
                if self.use_barrnap
                else [],
                self.use_barrnap,
            ),
        ):
            if not enabled or not ncrna_genes:
                continue
            existing_spans = [(g.location.start, g.location.end) for g in genome.genes]
            for gene in ncrna_genes:
                if not any(
                    gene.location.start < e_end and gene.location.end > e_start
                    for e_start, e_end in existing_spans
                ):
                    genome.add_gene(gene)

        # Interpret genes in parallel — each gene is independent at this stage.
        # Cap workers at 8 to avoid thrashing; online mode is I/O-bound so
        # threads help even more there.
        n_workers = min(8, max(1, len(genome.genes)))
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            future_to_gene = {
                pool.submit(self.interpret_gene, gene): gene
                for gene in genome.genes
            }
            for future in as_completed(future_to_gene):
                gene = future_to_gene[future]
                result = future.result()
                results.append(result)
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
            # Non-coding RNA genes (tRNA/rRNA) don't have protein sequences;
            # their identity is already established by Aragorn/Barrnap.
            feature_type = gene.metadata.get("feature_type", "")
            if feature_type in ("tRNA", "rRNA"):
                product = gene.metadata.get("product", gene.name or feature_type)
                interp = Interpretation(
                    gene_id=gene.id,
                    hypothesis=product,
                    confidence_score=0.95,
                    confidence_level=ConfidenceLevel.HIGH,
                    supporting_evidence_ids=[],
                    reasoning_chain=[f"Predicted by structural RNA finder ({gene.source})"],
                    competing_hypotheses=[],
                    uncertainty_sources=[],
                    metadata={"category": "ncRNA", "keyword": [feature_type]},
                )
                self.functional_annotator.annotate(interp, [], [])
                return InterpretationResult(
                    gene_id=gene.id,
                    gene_name=gene.display_name,
                    interpretation=interp,
                    hypotheses=[],
                    confidence_reports=[],
                    aggregated_evidence=None,
                    success=True,
                    skipped_layers=[],
                )

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

            # Step 5: Re-rank by adjusted score so the primary is truly the
            # best after all penalties/caps are applied, then build interpretation.
            ranked = sorted(
                zip(hypotheses, confidence_reports),
                key=lambda pair: pair[1].adjusted_score,
                reverse=True,
            )
            hypotheses = [h for h, _ in ranked]
            confidence_reports = [r for _, r in ranked]

            best_hypothesis = hypotheses[0]
            best_report = confidence_reports[0]

            # Create competing hypotheses from alternatives.
            # Use adjusted_score on both sides so the displayed numbers are
            # on the same scale and an alternative can never show a higher
            # figure than the primary.
            competing = []
            for h, report in zip(hypotheses[1:], confidence_reports[1:]):
                delta = best_report.adjusted_score - report.adjusted_score
                reason = (
                    f"Lower adjusted confidence ({report.adjusted_score:.0%} vs "
                    f"{best_report.adjusted_score:.0%}; Δ={delta:.0%})"
                )
                competing.append(
                    CompetingHypothesis(
                        hypothesis=h.function,
                        confidence=report.adjusted_score,
                        reason_not_preferred=reason,
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
            self.functional_annotator.annotate(interpretation, hypotheses, evidence)

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

    _UNINFORMATIVE_ANNOTATIONS = frozenset(
        {
            "hypothetical protein",
            "predicted protein",
            "unknown protein",
            "uncharacterized protein",
            "putative protein",
            "conserved hypothetical protein",
            "probable protein",
        }
    )

    # Regex that matches bare ORF placeholder names: orf00001, orf_001, gp001 etc.
    import re as _re
    _ORF_PLACEHOLDER = _re.compile(
        r"^(orf|gp|cds|gene|protein|hypothetical|putative\s+orf)\s*[\d_\-]+$",
        _re.IGNORECASE,
    )

    @classmethod
    def _is_uninformative(cls, text: str) -> bool:
        """Return True if the annotation text carries no functional information."""
        t = text.strip().lower()
        if t in cls._UNINFORMATIVE_ANNOTATIONS:
            return True
        if cls._ORF_PLACEHOLDER.match(t):
            return True
        return False

    def _evidence_from_genbank_annotation(self, gene: Gene) -> list[Evidence]:
        """Create Evidence objects from existing GenBank CDS qualifiers.

        phiX174 and other well-characterised genomes already carry product/
        function/note annotations that the motif scanner cannot rediscover.
        This surfaces that pre-existing knowledge as first-class evidence so
        the hypothesis generator can produce meaningful interpretations even
        in fully offline mode.

        Placeholder names like 'orf00001' or 'gp07' are explicitly rejected —
        they indicate the submitter had no functional knowledge either, so
        genes carrying only these labels are correctly classified as dark matter.
        """
        from giae.models.evidence import EvidenceProvenance as EP

        out: list[Evidence] = []
        provenance = EP(
            tool_name="genbank_parser",
            tool_version="1.0.0",
            database="NCBI GenBank",
        )

        # product qualifier → SEQUENCE_FEATURE (GenBank curator annotation)
        if gene.protein and gene.protein.product_name:
            product = gene.protein.product_name.strip()
            if not self._is_uninformative(product) and len(product) > 3:
                out.append(
                    Evidence(
                        evidence_type=EvidenceType.SEQUENCE_FEATURE,
                        gene_id=gene.id,
                        description=product,
                        confidence=0.85,
                        raw_data={"product": product, "source": "genbank_product"},
                        provenance=provenance,
                    )
                )

        # function qualifier → SEQUENCE_FEATURE
        gb_function = gene.metadata.get("gb_function", "")
        if gb_function and not self._is_uninformative(gb_function):
            out.append(
                Evidence(
                    evidence_type=EvidenceType.SEQUENCE_FEATURE,
                    gene_id=gene.id,
                    description=gb_function.strip(),
                    confidence=0.80,
                    raw_data={"function": gb_function, "source": "genbank_function"},
                    provenance=provenance,
                )
            )

        # note qualifier → SEQUENCE_FEATURE (lower confidence)
        gb_note = gene.metadata.get("gb_note", "")
        if gb_note and len(gb_note) > 5:
            out.append(
                Evidence(
                    evidence_type=EvidenceType.SEQUENCE_FEATURE,
                    gene_id=gene.id,
                    description=gb_note.strip(),
                    confidence=0.60,
                    raw_data={"note": gb_note, "source": "genbank_note"},
                    provenance=provenance,
                )
            )

        return out

    def _extract_evidence(self, gene: Gene) -> tuple[list[Evidence], list[str]]:
        """Extract evidence from a gene using available analyzers.

        Returns:
            Tuple of (evidence_list, skipped_layers).
        """
        evidence: list[Evidence] = []
        skipped: list[str] = []

        # GenBank annotation evidence — always checked first (highest priority)
        annotation_evidence = self._evidence_from_genbank_annotation(gene)
        evidence.extend(annotation_evidence)

        # Motif scanning — skip if we already have high-confidence annotation
        # evidence (avoids running thousands of PROSITE patterns needlessly)
        high_conf_annotation = any(e.confidence >= 0.8 for e in annotation_evidence)
        if not high_conf_annotation:
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
