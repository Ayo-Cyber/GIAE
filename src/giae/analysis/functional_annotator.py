"""Functional annotation depth: COG categories + GO terms + product names.

This module enriches a finished ``Interpretation`` with three pieces of
metadata that consumers (HTML report, downstream tools, papers) expect:

  * ``cog_category`` — single COG letter (J, K, L, M, ...)
  * ``cog_name``     — human-readable name of the category
  * ``go_terms``     — list of GO accessions (e.g. ["GO:0003677"])
  * ``normalized_product`` — cleaned-up product string

Two lookup paths are tried in order:

  1. **Pfam-based lookup**: if the supporting evidence carries a Pfam
     accession (PFxxxxx), the bundled Pfam→COG/GO table provides a direct
     answer. This is the strong, citable assignment.
  2. **Category-inferred lookup**: if no Pfam accession is available, the
     hypothesis's existing GIAE category ("replication", "translation"…)
     is mapped to its closest COG letter. Marked ``cog_source='inferred'``
     so consumers know the difference.

The bundled table covers ~100 common phage + bacterial Pfam IDs. Users
with full Pfam coverage can point ``FunctionalAnnotator`` at a custom
TSV file with the same schema.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from giae.analysis.product_normalizer import ProductNormalizer
from giae.models.evidence import Evidence
from giae.models.interpretation import Interpretation

if TYPE_CHECKING:
    from giae.engine.hypothesis import FunctionalHypothesis

logger = logging.getLogger(__name__)


# Canonical COG categories — letters and full names.
COG_CATEGORIES: dict[str, str] = {
    "J": "Translation, ribosomal structure and biogenesis",
    "A": "RNA processing and modification",
    "K": "Transcription",
    "L": "Replication, recombination and repair",
    "B": "Chromatin structure and dynamics",
    "D": "Cell cycle control, cell division, chromosome partitioning",
    "Y": "Nuclear structure",
    "V": "Defense mechanisms",
    "T": "Signal transduction mechanisms",
    "M": "Cell wall/membrane/envelope biogenesis",
    "N": "Cell motility",
    "Z": "Cytoskeleton",
    "W": "Extracellular structures",
    "U": "Intracellular trafficking, secretion, and vesicular transport",
    "O": "Posttranslational modification, protein turnover, chaperones",
    "X": "Mobilome: prophages, transposons",
    "C": "Energy production and conversion",
    "G": "Carbohydrate transport and metabolism",
    "E": "Amino acid transport and metabolism",
    "F": "Nucleotide transport and metabolism",
    "H": "Coenzyme transport and metabolism",
    "I": "Lipid transport and metabolism",
    "P": "Inorganic ion transport and metabolism",
    "Q": "Secondary metabolites biosynthesis, transport and catabolism",
    "R": "General function prediction only",
    "S": "Function unknown",
}

# GIAE's keyword-based categories → closest COG letter.
# Used as a fallback when no Pfam evidence is available.
_GIAE_CATEGORY_TO_COG: dict[str, str] = {
    "replication": "L",
    "transcription": "K",
    "translation": "J",
    "metabolism": "G",
    "transport": "P",
    "regulation": "T",
    "cell_structure": "M",
    "stress_response": "O",
    "phage": "X",
    "unknown": "S",
}

# Default location of the bundled Pfam→COG/GO table.
_DEFAULT_TABLE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data" / "functional" / "pfam_categories.tsv"
)

# Match Pfam accessions in evidence text or raw_data.
_PFAM_RE = re.compile(r"\b(PF\d{5})\b")


class FunctionalAnnotator:
    """Enriches Interpretation objects with COG/GO/normalised product."""

    def __init__(self, pfam_table_path: Path | None = None) -> None:
        self.normalizer = ProductNormalizer()
        path = pfam_table_path or _DEFAULT_TABLE_PATH
        self.pfam_table = self._load_pfam_table(path)

    # ── Public API ───────────────────────────────────────────────────────────

    def annotate(
        self,
        interpretation: Interpretation,
        hypotheses: "list[FunctionalHypothesis]",
        evidence: list[Evidence],
    ) -> None:
        """Mutate ``interpretation.metadata`` in place with functional fields.

        Idempotent: running twice produces the same metadata.
        """
        # 1. Normalised product name
        normalized = self.normalizer.normalize(interpretation.hypothesis)
        if normalized:
            interpretation.metadata["normalized_product"] = normalized

        # 2. Pfam-based COG / GO lookup
        pfam_id = self._extract_pfam_id(evidence)
        if pfam_id and pfam_id in self.pfam_table:
            row = self.pfam_table[pfam_id]
            interpretation.metadata["pfam_id"] = pfam_id
            interpretation.metadata["pfam_name"] = row.get("pfam_name", "")
            cog = row.get("cog", "")
            if cog:
                interpretation.metadata["cog_category"] = cog
                interpretation.metadata["cog_name"] = COG_CATEGORIES.get(cog, "Unknown")
                interpretation.metadata["cog_source"] = "pfam"
            go_terms = row.get("go_terms", [])
            if go_terms:
                interpretation.metadata["go_terms"] = go_terms
            return

        # 3. Fallback: GIAE category → COG letter
        primary = hypotheses[0] if hypotheses else None
        if primary and primary.category in _GIAE_CATEGORY_TO_COG:
            cog = _GIAE_CATEGORY_TO_COG[primary.category]
            interpretation.metadata["cog_category"] = cog
            interpretation.metadata["cog_name"] = COG_CATEGORIES.get(cog, "Unknown")
            interpretation.metadata["cog_source"] = "inferred"

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_pfam_table(self, path: Path) -> dict[str, dict[str, object]]:
        table: dict[str, dict[str, object]] = {}
        if not path.exists():
            logger.warning("Pfam categories table not found at %s", path)
            return table

        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                pfam_id = parts[0].strip()
                pfam_name = parts[1].strip()
                cog = parts[2].strip()
                go_terms: list[str] = []
                if len(parts) >= 4 and parts[3].strip():
                    go_terms = [g.strip() for g in parts[3].split("|") if g.strip()]
                table[pfam_id] = {
                    "pfam_name": pfam_name,
                    "cog": cog,
                    "go_terms": go_terms,
                }
        logger.info("Loaded %d Pfam categories from %s", len(table), path)
        return table

    @staticmethod
    def _extract_pfam_id(evidence: list[Evidence]) -> str | None:
        """Find the first Pfam accession in evidence descriptions or raw_data."""
        for ev in evidence:
            # Check raw_data for explicit accession key
            for key in ("pfam_id", "pfam_acc", "accession"):
                v = ev.raw_data.get(key) if ev.raw_data else None
                if isinstance(v, str):
                    m = _PFAM_RE.search(v)
                    if m:
                        return m.group(1)
            # Fall back to scanning the description
            if ev.description:
                m = _PFAM_RE.search(ev.description)
                if m:
                    return m.group(1)
        return None
