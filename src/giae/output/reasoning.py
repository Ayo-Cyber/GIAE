"""
Natural Language Reasoning Engine for GIAE.

Transforms structured evidence into narrative explanations, making
interpretations feel more human and "intelligent".
"""

from __future__ import annotations

from giae.models.evidence import EvidenceType
from giae.models.interpretation import Interpretation, ConfidenceLevel


class ReasoningEngine:
    """
    Generates human-readable narratives from Interpretation objects.
    
    Uses templated logic to construct paragraphs that explain the "Why"
    behind a prediction, highlighting key evidence and handling uncertainty.
    """

    def generate_narrative(self, interpretation: Interpretation) -> str:
        """
        Generate a narrative explanation for an interpretation.
        
        Args:
            interpretation: The interpretation to explain.
            
        Returns:
            A string paragraph explaining the conclusion.
        """
        # 1. Opening statement (Hypothesis & Confidence)
        opening = self._generate_opening(interpretation)
        
        # 2. Evidence summary (The "Because")
        evidence_text = self._generate_evidence_text(interpretation)
        
        # 3. Uncertainty/Conflict handling (The "However")
        caveats = self._generate_caveats(interpretation)
        
        # Assemble
        narrative = f"{opening} {evidence_text}"
        if caveats:
            narrative += f" {caveats}"
            
        return narrative

    def _generate_opening(self, interp: Interpretation) -> str:
        """Generate the opening sentence."""
        func = interp.hypothesis
        conf = interp.confidence_score
        
        if "Ambiguous" in func:
            return f"The function of this gene is ambiguous due to conflicting evidence."
            
        if interp.confidence_level == ConfidenceLevel.HIGH:
            if conf > 0.9:
                return f"GIAE identifies this gene as a **{func}** with very high confidence."
            return f"Primary evidence strongly suggests this gene encodes a **{func}**."
        elif interp.confidence_level == ConfidenceLevel.MODERATE:
            return f"This gene is likely a **{func}**, though some uncertainty remains."
        elif interp.confidence_level == ConfidenceLevel.LOW:
            return f"Preliminary analysis suggests a possible role as a **{func}**."
        else:
            return f"The function is speculative, potentially resembling a **{func}**."

    def _generate_evidence_text(self, interp: Interpretation) -> str:
        """Generate the evidence supporting the claim."""
        # This is a simplified version - in a real system we'd parse the reasoning_chain
        # or look up the specific Evidence objects if we had access to them here.
        # For MVP, we use the pre-generated reasoning chain strings.
        
        chain = interp.reasoning_chain
        if not chain:
            return "No specific evidence details were provided."
            
        # Try to identify evidence types from the strings
        has_blast = any("BLAST" in s or "homology" in s.lower() for s in chain)
        has_motif = any("motif" in s.lower() or "domain" in s.lower() for s in chain)
        
        if has_blast and has_motif:
            return (
                "This conclusion is supported by both sequence homology and specific structural motifs, "
                "providing a robust consensus."
            )
        elif has_blast:
             return "This is based primarily on sequence homology to known proteins in the database."
        elif has_motif:
            return (
                "The identification is driven by the presence of conserved functional motifs, "
                "characteristic of this protein family."
            )
        else:
            return "This based on available structural and sequence features."

    def _generate_caveats(self, interp: Interpretation) -> str:
        """Generate sentences about uncertainty or conflicts."""
        caveats = []
        
        # Check for conflicts
        if "conflicting_evidence" in interp.uncertainty_sources:
            caveats.append(
                "However, there are conflicting signal from different evidence sources that warrant manual review."
            )
        elif interp.has_competing_hypotheses:
            top_alt = interp.competing_hypotheses[0]
            caveats.append(
                f"An alternative hypothesis ({top_alt.hypothesis}) was also considered but had lower support."
            )
            
        # Check for single evidence
        if "Single Evidence Type" in interp.uncertainty_sources:
             caveats.append(
                 "Note that this relies on a single type of evidence, which increases the risk of false positives."
             )
             
        if not caveats:
            return ""
            
        return " ".join(caveats)
