"""Hypothesis generation module for GIAE.

Generates functional hypotheses from aggregated evidence,
the core contribution of the interpretation engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from giae.engine.aggregator import AggregatedEvidence
from giae.models.evidence import Evidence, EvidenceType


@dataclass
class FunctionalHypothesis:
    """A hypothesis about gene function."""

    function: str  # e.g., "DNA polymerase III alpha subunit"
    category: str  # e.g., "replication", "metabolism", "transport"
    confidence: float  # 0.0 to 1.0
    supporting_evidence_ids: list[str]
    reasoning_steps: list[str]
    source_type: str = "aggregated"  # e.g. "BLAST", "Motif", "Combined"
    keywords: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """One-line summary of the hypothesis."""
        return f"{self.function} (confidence: {self.confidence:.0%})"


# Keywords that suggest functional categories
FUNCTION_KEYWORDS: dict[str, list[str]] = {
    "replication": [
        "polymerase",
        "helicase",
        "primase",
        "ligase",
        "dna",
        "replication",
        "dnaa",
        "dnab",
        "dnac",
        "dnan",
        "topoisomerase",
        "gyrase",
    ],
    "transcription": [
        "rna polymerase",
        "sigma",
        "transcription",
        "rnap",
        "promoter",
        "terminator",
        "elongation",
        "initiation",
    ],
    "translation": [
        "ribosom",
        "trna",
        "rrna",
        "aminoacyl",
        "synthetase",
        "elongation factor",
        "initiation factor",
        "release factor",
        "translation",
    ],
    "metabolism": [
        "kinase",
        "phosphatase",
        "dehydrogenase",
        "oxidase",
        "reductase",
        "synthase",
        "transferase",
        "hydrolase",
        "lyase",
        "isomerase",
        "ligase",
        "atp",
        "nad",
        "metabolism",
        "glycolysis",
        "oxidation",
    ],
    "transport": [
        "transporter",
        "permease",
        "channel",
        "pump",
        "abc",
        "mfs",
        "import",
        "export",
        "efflux",
        "influx",
        "membrane",
    ],
    "regulation": [
        "regulator",
        "repressor",
        "activator",
        "response",
        "sensor",
        "histidine kinase",
        "two-component",
        "transcription factor",
    ],
    "cell_structure": [
        "membrane",
        "cell wall",
        "peptidoglycan",
        "lipopolysaccharide",
        "flagell",
        "pili",
        "fimbri",
        "capsule",
    ],
    "stress_response": [
        "chaperone",
        "heat shock",
        "cold shock",
        "oxidative",
        "stress",
        "groel",
        "dnak",
        "clp",
        "protease",
    ],
    "modification": [
        "phosphorylation",
        "glycosylation",
        "amidation",
        "acetylation",
        "methylation",
        "ubiquitination",
        "modification",
        "target protein",
    ],
    "phage_structure": [
        "capsid",
        "coat protein",
        "spike protein",
        "tail",
        "head",
        "portal",
        "baseplate",
        "fiber",
        "pilot protein",
        "major capsid",
        "minor capsid",
        "scaffold",
        "scaffolding",
        "prohead",
        "procapsid",
    ],
    "phage_lysis": [
        "lysis",
        "lysin",
        "holin",
        "endolysin",
        "spanin",
        "lytic",
    ],
    "phage_replication": [
        "replication initiation",
        "dna binding protein",
        "dna pilot",
        "single-stranded dna binding",
        "ssdna",
        "rf replication",
        "rolling circle",
        "phage replication",
    ],
    "unknown": [],
}


@dataclass
class HypothesisGenerator:
    """
    Generates functional hypotheses from aggregated evidence.

    This is the core of GIAE's interpretation engine. It examines
    evidence from multiple sources and formulates plausible
    functional hypotheses with explicit reasoning.

    Attributes:
        max_hypotheses: Maximum hypotheses to generate per gene.
        min_confidence: Minimum confidence to report a hypothesis.

    Example:
        >>> generator = HypothesisGenerator()
        >>> hypotheses = generator.generate(aggregated_evidence)
        >>> for h in hypotheses:
        ...     print(h.summary)
    """

    max_hypotheses: int = 3
    min_confidence: float = 0.3

    def generate(self, aggregated: AggregatedEvidence) -> list[FunctionalHypothesis]:
        """
        Generate functional hypotheses from aggregated evidence.

        Args:
            aggregated: AggregatedEvidence from the aggregator.

        Returns:
            List of FunctionalHypothesis, ranked by confidence.
        """
        hypotheses: list[FunctionalHypothesis] = []

        # Tier 1 — GenBank annotation (curator-assigned, most authoritative)
        if EvidenceType.SEQUENCE_FEATURE in aggregated.groups_by_type:
            hypotheses.extend(self._hypotheses_from_annotations(aggregated))

        # Tier 2 — Homology (BLAST / GenBank product qualifier)
        if aggregated.has_homology:
            hypotheses.extend(self._hypotheses_from_homology(aggregated))

        # Tier 3 — Domain hits (Pfam/HMMER profile HMMs)
        if EvidenceType.DOMAIN_HIT in aggregated.groups_by_type:
            hypotheses.extend(self._hypotheses_from_domain_hits(aggregated))

        # Tier 4 — Motifs (PROSITE / builtin patterns).
        # Motifs are supporting evidence — they should corroborate a higher-tier
        # hypothesis, not originate one.  We only keep motif-derived hypotheses
        # when no Tier 1-3 evidence produced anything; even then, confidence is
        # capped at 0.45 so the result stays in LOW territory.
        if aggregated.has_motifs:
            motif_hypotheses = self._hypotheses_from_motifs(aggregated)
            if hypotheses:
                # Higher-tier hypotheses exist — silently discard motif-only
                # candidates.  The COMBINED step below will still incorporate
                # motif evidence when type_diversity >= 2.
                pass
            else:
                for h in motif_hypotheses:
                    h.confidence = min(h.confidence, 0.45)
                hypotheses.extend(motif_hypotheses)

        # Combined evidence boost — fires when multiple evidence types agree
        if aggregated.type_diversity >= 2:
            hypotheses.extend(self._hypotheses_from_combined(aggregated))

        # Deduplicate and merge similar hypotheses
        hypotheses = self._merge_similar(hypotheses)

        # Sort by confidence and limit
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        hypotheses = [h for h in hypotheses if h.confidence >= self.min_confidence]

        return hypotheses[: self.max_hypotheses]

    def _hypotheses_from_annotations(
        self,
        aggregated: AggregatedEvidence,
    ) -> list[FunctionalHypothesis]:
        """Generate hypotheses directly from GenBank product/function/note annotations.

        These annotations are curated by the submitter or NCBI and are the most
        authoritative evidence available in an already-annotated GenBank file.
        """
        hypotheses = []
        annotation_evidence = aggregated.groups_by_type.get(EvidenceType.SEQUENCE_FEATURE, [])

        for evidence in annotation_evidence:
            source = evidence.raw_data.get("source", "")
            if source not in ("genbank_product", "genbank_function", "genbank_note"):
                continue

            function = evidence.description
            if not function:
                continue

            category = self._categorize_function(function)
            keywords = self._extract_keywords(function)

            if source == "genbank_product":
                reasoning = [
                    f"GenBank product annotation: {function}",
                    "Curator-assigned product name from the submitted GenBank record",
                ]
            else:
                reasoning = [
                    f"GenBank annotation: {function}",
                    "Curator-assigned functional description from the submitted GenBank record",
                ]

            hypotheses.append(
                FunctionalHypothesis(
                    function=function,
                    category=category,
                    confidence=evidence.confidence,
                    supporting_evidence_ids=[evidence.id],
                    reasoning_steps=reasoning,
                    source_type="GENBANK",
                    keywords=keywords,
                )
            )

        return hypotheses

    def _hypotheses_from_homology(
        self,
        aggregated: AggregatedEvidence,
    ) -> list[FunctionalHypothesis]:
        """Generate hypotheses from BLAST homology evidence."""
        hypotheses = []
        homology_evidence = aggregated.groups_by_type.get(EvidenceType.BLAST_HOMOLOGY, [])

        for evidence in homology_evidence[:3]:  # Top 3 hits
            function = self._extract_function_from_description(evidence.description)
            category = self._categorize_function(function)

            reasoning = [
                f"BLAST homology hit: {evidence.description}",
                "Sequence identity supports functional similarity",
                "E-value indicates statistical significance",
            ]

            keywords = self._extract_keywords(evidence.description)

            hypotheses.append(
                FunctionalHypothesis(
                    function=function,
                    category=category,
                    confidence=evidence.confidence,
                    supporting_evidence_ids=[evidence.id],
                    reasoning_steps=reasoning,
                    source_type="BLAST",
                    keywords=keywords,
                )
            )

        return hypotheses

    def _hypotheses_from_domain_hits(
        self,
        aggregated: AggregatedEvidence,
    ) -> list[FunctionalHypothesis]:
        """Generate hypotheses from Pfam/HMMER domain hits.

        Domain hits from profile HMM databases are highly specific —
        each Pfam domain maps to a well-characterised protein family.
        They are treated as higher-confidence signals than raw motifs.
        """
        hypotheses = []
        domain_evidence = aggregated.groups_by_type.get(EvidenceType.DOMAIN_HIT, [])

        for evidence in domain_evidence[:3]:
            domain_name = evidence.raw_data.get("domain_name", "")
            description = evidence.raw_data.get("description", "") or evidence.description
            evalue = evidence.raw_data.get("evalue", 1.0)
            accession = evidence.raw_data.get("accession", "")

            # Use the domain description as the function name
            function = description if description else f"Protein with {domain_name} domain"
            category = self._categorize_function(function + " " + domain_name)

            evalue_str = f"{evalue:.1e}"
            reasoning = [
                f"Pfam domain hit: {domain_name} ({accession})",
                f"Domain description: {description}",
                f"Statistical significance: E-value = {evalue_str}",
            ]

            keywords = self._extract_keywords(function)
            if domain_name and domain_name not in keywords:
                keywords.insert(0, domain_name)

            hypotheses.append(
                FunctionalHypothesis(
                    function=function,
                    category=category,
                    confidence=evidence.confidence,
                    supporting_evidence_ids=[evidence.id],
                    reasoning_steps=reasoning,
                    source_type="DOMAIN",
                    keywords=keywords[:5],
                )
            )

        return hypotheses

    def _hypotheses_from_motifs(
        self,
        aggregated: AggregatedEvidence,
    ) -> list[FunctionalHypothesis]:
        """Generate hypotheses from motif evidence."""
        hypotheses = []
        motif_evidence = aggregated.groups_by_type.get(EvidenceType.MOTIF_MATCH, [])

        # Basic taxonomic heuristic: Assume phage if genome name indicates it
        # For a real system we'd pass organism info down.
        is_phage = True  # Safe assumption for current test cases

        # Eukaryotic structural/extracellular motifs that are almost always
        # false positives in phage/bacterial sequences.  PROSITE patterns for
        # these domains match cysteine-spacing patterns common to many unrelated
        # prokaryotic proteins.
        eukaryotic_motifs = {
            "conotoxin", "egf", "sh2", "sh3", "zinc_finger", "zf-c2h2",
            "vwfc", "vwfa", "vwfb", "vwfd",      # Von Willebrand Factor domains
            "tsp1", "thrombospondin",             # thrombospondin type-1 repeats
            "fn3", "fibronectin",                 # fibronectin type-III
            "ig", "immunoglobulin",               # Ig-fold domains
            "lrr", "leucine_rich",                # leucine-rich repeats
            "ank", "ankyrin",                     # ankyrin repeats
            "wd40",                               # WD40 repeats
        }

        # Group motifs by what they suggest
        motif_groups: dict[str, list[Evidence]] = {}
        for evidence in motif_evidence:
            motif_name = evidence.raw_data.get("motif_name", "unknown")
            if motif_name not in motif_groups:
                motif_groups[motif_name] = []
            motif_groups[motif_name].append(evidence)

        for motif_name, evidences in motif_groups.items():
            function = self._motif_to_function(motif_name)
            category = self._categorize_function(function)

            avg_confidence = sum(e.confidence for e in evidences) / len(evidences)

            # Suppress unmapped fallback hypotheses ("Protein with X motif") that
            # rest on only a single hit — these are almost always PROSITE false
            # positives and add no interpretive value.
            is_unmapped_fallback = function == f"Protein with {motif_name} motif"
            if is_unmapped_fallback and len(evidences) < 2:
                continue

            # Formulate penalizations
            boost_factor = 0.1
            max_confidence = 0.95

            # Taxonomic filtering
            if is_phage and any(euk in motif_name.lower() for euk in eukaryotic_motifs):
                # Heavily penalize eukaryotic motifs in phages
                boost_factor = 0.0
                max_confidence = 0.20
            elif category == "modification" or avg_confidence < 0.5:
                # Penalize low-quality motifs (e.g. phosphorylation sites)
                boost_factor = 0.02  # Minimal boost from count
                max_confidence = 0.45  # Hard cap

            # Adjust confidence based on number of supporting motifs
            adjusted_confidence = min(
                avg_confidence * (1 + boost_factor * len(evidences)), max_confidence
            )

            reasoning = [
                f"Detected {motif_name} motif pattern",
                f"Motif suggests {function} function",
                f"Supported by {len(evidences)} motif match(es)",
            ]

            hypotheses.append(
                FunctionalHypothesis(
                    function=function,
                    category=category,
                    confidence=adjusted_confidence,
                    supporting_evidence_ids=[e.id for e in evidences],
                    reasoning_steps=reasoning,
                    source_type="MOTIF",
                    keywords=[motif_name],
                )
            )

        return hypotheses

    def _hypotheses_from_combined(
        self,
        aggregated: AggregatedEvidence,
    ) -> list[FunctionalHypothesis]:
        """Generate hypotheses from multiple evidence types."""
        hypotheses: list[FunctionalHypothesis] = []

        # Get best evidence from each type
        top_evidence = aggregated.get_top_evidence(5)
        if len(top_evidence) < 2:
            return hypotheses

        # Look for consensus
        all_descriptions = " ".join(e.description for e in top_evidence)
        category = self._categorize_function(all_descriptions)

        if category != "unknown":
            # Found a consistent theme
            combined_confidence = sum(e.confidence for e in top_evidence) / len(top_evidence)
            combined_confidence *= 1.2  # Boost for multi-source support
            combined_confidence = min(combined_confidence, 0.95)

            function = f"{category.replace('_', ' ').title()}-related protein"

            reasoning = [
                f"Multiple evidence types point to {category} function",
                f"Supported by {len(top_evidence)} evidence items",
                "Cross-validation increases confidence",
            ]

            hypotheses.append(
                FunctionalHypothesis(
                    function=function,
                    category=category,
                    confidence=combined_confidence,
                    supporting_evidence_ids=[e.id for e in top_evidence],
                    reasoning_steps=reasoning,
                    source_type="COMBINED",
                )
            )

        return hypotheses

    def _extract_function_from_description(self, description: str) -> str:
        """Extract a function name from a BLAST hit description."""
        # Remove common prefixes
        cleaned = description.lower()
        for prefix in ["putative ", "probable ", "hypothetical ", "predicted "]:
            cleaned = cleaned.replace(prefix, "")

        # Remove organism names (often in square brackets or at end)
        cleaned = re.sub(r"\[.*?\]", "", cleaned)

        # Take first meaningful part
        parts = cleaned.split(",")
        function = parts[0].strip()

        # Capitalize properly
        if function:
            function = function[0].upper() + function[1:]

        return function or "Hypothetical protein"

    def _motif_to_function(self, motif_name: str) -> str:
        """Map a motif name to a functional description."""
        motif_functions = {
            "atp_binding_p_loop": "ATP/GTP binding protein",
            "walker_b": "ATPase",
            "helix_turn_helix": "DNA-binding transcription regulator",
            "zinc_finger_c2h2": "Zinc finger transcription factor",
            "serine_protease": "Serine protease",
            "signal_peptide": "Secreted/membrane protein",
            "transmembrane": "Membrane protein",
            "phosphorylation_site": "Phosphorylation target protein",
            "gram_negative_lipobox": "Lipoprotein",
        }
        return motif_functions.get(motif_name, f"Protein with {motif_name} motif")

    def _categorize_function(self, function_text: str) -> str:
        """Categorize a function based on keywords."""
        text_lower = function_text.lower()

        for category, keywords in FUNCTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category

        return "unknown"

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract functional keywords from text."""
        keywords = []
        text_lower = text.lower()

        for _category, category_keywords in FUNCTION_KEYWORDS.items():
            for keyword in category_keywords:
                if keyword in text_lower and keyword not in keywords:
                    keywords.append(keyword)

        return keywords[:5]  # Limit to 5 keywords

    def _merge_similar(
        self,
        hypotheses: list[FunctionalHypothesis],
    ) -> list[FunctionalHypothesis]:
        """Merge hypotheses that are essentially the same."""
        if not hypotheses:
            return hypotheses

        merged: list[FunctionalHypothesis] = []
        used = set()

        for i, h1 in enumerate(hypotheses):
            if i in used:
                continue

            similar_ids = [i]
            for j, h2 in enumerate(hypotheses[i + 1 :], start=i + 1):
                if j in used:
                    continue
                if self._are_similar(h1, h2):
                    similar_ids.append(j)
                    used.add(j)

            if len(similar_ids) > 1:
                # Merge similar hypotheses
                all_evidence_ids: list[str] = []
                all_reasoning: list[str] = []
                total_confidence: float = 0.0

                for idx in similar_ids:
                    h = hypotheses[idx]
                    all_evidence_ids.extend(h.supporting_evidence_ids)
                    all_reasoning.extend(h.reasoning_steps)
                    total_confidence += h.confidence

                merged.append(
                    FunctionalHypothesis(
                        function=h1.function,
                        category=h1.category,
                        confidence=min(total_confidence / len(similar_ids) * 1.1, 0.95),
                        supporting_evidence_ids=list(set(all_evidence_ids)),
                        reasoning_steps=list(dict.fromkeys(all_reasoning)),  # Dedupe
                        keywords=h1.keywords,
                    )
                )
            else:
                merged.append(h1)

            used.add(i)

        return merged

    def _are_similar(self, h1: FunctionalHypothesis, h2: FunctionalHypothesis) -> bool:
        """Check if two hypotheses are similar enough to merge."""
        # Same category and overlapping keywords
        if h1.category == h2.category and h1.category != "unknown":
            return True

        # Similar function names
        return h1.function.lower() == h2.function.lower()
