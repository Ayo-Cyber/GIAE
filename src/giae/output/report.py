"""Human-readable report generation for GIAE.

Produces Markdown reports explaining interpretation results.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from giae.engine.interpreter import GenomeInterpretationSummary
    from giae.models.genome import Genome

from giae.output.reasoning import ReasoningEngine


class ReportGenerator:
    """
    Generates human-readable interpretation reports.

    Reports are designed for non-technical researchers to understand
    genomic interpretations without needing to read code or raw data.
    """

    def __init__(self, include_evidence_details: bool = True) -> None:
        self.include_evidence_details = include_evidence_details
        self.reasoning_engine = ReasoningEngine()

    def generate(
        self,
        genome: Genome,
        summary: GenomeInterpretationSummary,
    ) -> str:
        """
        Generate a complete interpretation report.

        Args:
            genome: The interpreted genome.
            summary: Interpretation results.

        Returns:
            Markdown-formatted report string.
        """
        sections = [
            self._header(genome),
            self._summary_section(summary),
            self._interpretation_section(summary),
            self._conflict_summary_section(summary),
            self._novel_genes_section(summary),
            self._methodology_section(),
            self._footer(),
        ]

        return "\n\n".join(sections)

    def _header(self, genome: Genome) -> str:
        """Generate report header."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        return f"""# Genome Interpretation Report

**Genome:** {genome.name}
**Generated:** {timestamp}
**Tool:** GIAE (Genome Interpretation & Annotation Engine)

---

## Genome Overview

| Property | Value |
|----------|-------|
| Name | {genome.name} |
| Length | {genome.length:,} bp |
| GC Content | {genome.gc_content}% |
| Total Genes | {genome.gene_count} |
| Source File | {genome.source_file.name} |
| Format | {genome.file_format.upper()} |
| Organism | {genome.metadata.organism or "Unknown"} |"""

    def _summary_section(self, summary: GenomeInterpretationSummary) -> str:
        """Generate summary statistics section."""
        return f"""## Interpretation Summary

GIAE analyzed **{summary.total_genes} genes** and generated interpretations for **{summary.interpreted_genes}** ({summary.success_rate:.1f}%).

### Confidence Distribution

| Confidence Level | Count | Description |
|-----------------|-------|-------------|
| High | {summary.high_confidence_count} | Strong, consistent evidence supporting the interpretation |
| Moderate | {summary.moderate_confidence_count} | Good evidence with some uncertainty |
| Low | {summary.low_confidence_count} | Limited evidence, hypothesis only |
| Failed | {summary.failed_genes} | Unable to generate interpretation |

**Processing Time:** {summary.processing_time_seconds:.2f} seconds"""

    def _interpretation_section(self, summary: GenomeInterpretationSummary) -> str:
        """Generate detailed interpretations section."""
        lines = ["## Gene Interpretations", ""]

        # Group by confidence
        high_conf = [
            r
            for r in summary.results
            if r.interpretation and r.interpretation.confidence_level.value == "high"
        ]
        mod_conf = [
            r
            for r in summary.results
            if r.interpretation and r.interpretation.confidence_level.value == "moderate"
        ]
        low_conf = [
            r
            for r in summary.results
            if r.interpretation
            and r.interpretation.confidence_level.value in ("low", "speculative")
        ]

        if high_conf:
            lines.append("### High Confidence Interpretations")
            lines.append("")
            for result in high_conf[:10]:  # Limit to 10
                lines.append(self._format_interpretation(result))

        if mod_conf:
            lines.append("### Moderate Confidence Interpretations")
            lines.append("")
            for result in mod_conf[:10]:
                lines.append(self._format_interpretation(result))

        if low_conf:
            lines.append("### Low Confidence Interpretations")
            lines.append("")
            lines.append("*These interpretations have limited evidence support.*")
            lines.append("")
            for result in low_conf[:5]:
                lines.append(self._format_interpretation(result, brief=True))

        # Note if there are more
        total_shown = min(len(high_conf), 10) + min(len(mod_conf), 10) + min(len(low_conf), 5)
        total_interpreted = summary.interpreted_genes
        if total_shown < total_interpreted:
            lines.append(f"\n*Showing {total_shown} of {total_interpreted} interpreted genes.*")

        return "\n".join(lines)

    def _format_interpretation(self, result: Any, brief: bool = False) -> str:
        """Format a single gene interpretation."""
        interp = result.interpretation
        gene_name = result.gene_name or result.gene_id

        if brief:
            return f"- **{gene_name}**: {interp.hypothesis} ({interp.confidence_score:.0%})"

        lines = [
            f"#### {gene_name}",
            "",
            f"**Predicted Function:** {interp.hypothesis}",
            f"**Confidence:** {interp.confidence_score:.0%} ({interp.confidence_level.value})",
            "",
            "**Narrative Explanation:**",
            f"{self.reasoning_engine.generate_narrative(interp)}",
            "",
            "**Specific Evidence:**",
        ]

        for i, step in enumerate(interp.reasoning_chain[:3], 1):
            lines.append(f"{i}. {step}")

        if interp.competing_hypotheses:
            lines.append("")
            lines.append("**Alternative Hypotheses:**")
            for alt in interp.competing_hypotheses[:2]:
                lines.append(f"- {alt.hypothesis} ({alt.confidence:.0%})")

        if interp.uncertainty_sources:
            lines.append("")
            lines.append("**Uncertainty Notes:**")
            for source in interp.uncertainty_sources[:2]:
                lines.append(f"- {source.replace('_', ' ').title()}")

        lines.append("")
        return "\n".join(lines)

    def _conflict_summary_section(self, summary: GenomeInterpretationSummary) -> str:
        """Generate a section highlighting genes with conflicting evidence."""
        conflicted = [
            r
            for r in summary.results
            if r.interpretation
            and r.interpretation.metadata.get("conflict_severity") in ("HIGH", "MODERATE")
        ]

        if not conflicted:
            return ""

        lines = [
            "## Evidence Conflicts",
            "",
            f"GIAE detected **{len(conflicted)} gene(s)** where evidence sources disagree. "
            "These warrant careful manual review before drawing biological conclusions.",
            "",
            "| Gene | Primary Hypothesis | Conflict Severity | Confidence |",
            "|------|--------------------|-------------------|-----------|",
        ]

        for result in conflicted[:10]:
            interp = result.interpretation
            name = result.gene_name or result.gene_id
            severity = interp.metadata.get("conflict_severity", "UNKNOWN")  # type: ignore[union-attr]
            lines.append(
                f"| {name} | {interp.hypothesis[:50]} | {severity} | {interp.confidence_score:.0%} |"  # type: ignore[union-attr]
            )

        return "\n".join(lines)

    def _novel_genes_section(self, summary: GenomeInterpretationSummary) -> str:
        """Generate a novel gene discovery section."""
        report = summary.novel_gene_report
        if not report or not report.has_novel_genes:
            return ""

        lines = [
            "## Novel Gene Discovery",
            "",
            f"GIAE identified **{report.total_novel} gene(s)** that lack sufficient "
            "functional characterisation. Rather than treating these as failures, "
            "GIAE surfaces them as structured research opportunities.",
            "",
            "| Category | Count |",
            "|----------|-------|",
            f"| Dark matter (zero evidence) | {report.dark_matter_count} |",
            f"| Poorly characterised (weak signal) | {report.weak_evidence_count} |",
            f"| Ambiguous function (conflicting) | {report.conflict_count} |",
            "",
            "### Top Research Priorities",
            "",
        ]

        for candidate in report.top_priorities:
            lines.append(f"#### {candidate.display_name} — {candidate.priority_label}")
            lines.append("")
            lines.append(f"**Category:** {candidate.category_label}")
            lines.append(f"**Protein length:** {candidate.protein_length} aa")
            lines.append(f"**Novelty score:** {candidate.novelty_score:.0%}")
            lines.append(f"**Reason flagged:** {candidate.reason}")
            if candidate.suggested_experiments:
                lines.append("")
                lines.append("**Suggested experiments:**")
                for exp in candidate.suggested_experiments[:3]:
                    lines.append(f"- {exp}")
            lines.append("")

        return "\n".join(lines)

    def _methodology_section(self) -> str:
        """Generate methodology description."""
        return """## Methodology

This report was generated by GIAE using a multi-layer evidence pipeline:

1. **Parsing:** Genome file parsed and validated
2. **ORF Detection:** Open reading frames identified (if needed)
3. **Evidence Extraction (4 independent layers):**
   - Sequence motif scanning (PROSITE + 8 built-in patterns)
   - Profile HMM domain search via EBI HMMER web API (Pfam database)
   - Sequence homology search via UniProt REST API
   - Local BLAST+ search (if installed and database available)
4. **Hypothesis Generation:** Up to 3 independent hypotheses per gene from each evidence layer
5. **Conflict Detection:** Contradictory evidence flagged explicitly
6. **Confidence Scoring:** Evidence-weighted scoring with explicit uncertainty tracking
7. **Novel Gene Discovery:** Uncharacterised genes ranked as research priorities

### Evidence Reliability Hierarchy

| Source | Weight | Notes |
|--------|--------|-------|
| Sequence homology (BLAST/UniProt) | 1.00 | Most specific |
| Profile HMM domain (Pfam) | 0.90 | High specificity, database-backed |
| Motif pattern (PROSITE) | 0.80 | Pattern-based |
| ORF prediction | 0.60 | Structural only |

### Confidence Levels Explained

- **High (≥80%):** Strong, multi-source evidence with consistent predictions
- **Moderate (50-79%):** Good evidence but some uncertainty remains
- **Low (30-49%):** Limited evidence, treat as preliminary hypothesis
- **Speculative (<30%):** Minimal evidence, requires validation"""

    def _footer(self) -> str:
        """Generate report footer."""
        return """---

## Disclaimer

This interpretation is computationally generated and has not been experimentally validated.
All predictions should be treated as hypotheses requiring laboratory confirmation.

Generated by **GIAE** - Genome Interpretation & Annotation Engine
https://github.com/Ayo-Cyber/GIAE"""
