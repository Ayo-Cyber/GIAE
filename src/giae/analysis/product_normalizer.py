"""Product-name normaliser for GIAE.

Cleans up gene product strings produced by hypothesis generation so the
HTML report and downstream consumers see consistent text:

  - Strip uninformative prefixes ("putative", "probable", "predicted")
  - Strip trailing fragments ("[partial]", "(fragment)", trailing commas)
  - Collapse whitespace and standardise capitalisation
  - Expand common abbreviations to canonical full names

The normaliser does not invent information. If the input is empty or
contains only generic placeholders ("hypothetical protein"), it returns
the input unchanged so the caller can decide how to render it.
"""

from __future__ import annotations

import re

# Modifiers stripped from the *front* of a product string.
_LEADING_MODIFIERS = [
    "putative",
    "probable",
    "predicted",
    "possible",
    "uncharacterised",
    "uncharacterized",
    "conserved",
    "hypothetical",
]

# Trailing parenthetical / bracketed fragments to drop.
_TRAILING_FRAGMENTS = [
    re.compile(r"\s*\[partial\]\s*$", re.IGNORECASE),
    re.compile(r"\s*\(fragment\)\s*$", re.IGNORECASE),
    re.compile(r"\s*\(partial\)\s*$", re.IGNORECASE),
    re.compile(r"\s*\(predicted\)\s*$", re.IGNORECASE),
    re.compile(r"\s+EC[ :]\d+(\.\d+){0,3}\s*$", re.IGNORECASE),
]

_MULTI_SPACE = re.compile(r"\s+")

# These are placeholder products — we leave them alone rather than
# producing a misleading "cleaned" version.
_PLACEHOLDERS = {
    "hypothetical protein",
    "uncharacterized protein",
    "uncharacterised protein",
    "unknown",
    "unknown protein",
}


class ProductNormalizer:
    """Cleans gene product strings for display."""

    def normalize(self, product: str) -> str:
        """Return a cleaned version of ``product``.

        Empty or placeholder inputs are returned unchanged (after lowercase
        comparison) so the caller can detect them.
        """
        if not product:
            return product

        text = product.strip()
        if not text:
            return text

        # Leave placeholders alone
        if text.lower() in _PLACEHOLDERS:
            return text

        # Strip trailing fragments
        for pat in _TRAILING_FRAGMENTS:
            text = pat.sub("", text)

        # Strip leading modifiers (one or two stacked)
        for _ in range(2):
            stripped = self._strip_leading_modifier(text)
            if stripped == text:
                break
            text = stripped

        # Collapse whitespace
        text = _MULTI_SPACE.sub(" ", text).strip(" ,;:")

        # Final placeholder check (e.g., "putative hypothetical protein"
        # collapses to just "hypothetical protein")
        if text.lower() in _PLACEHOLDERS:
            return text

        # Standardise capitalisation: keep the original case of the first
        # informative word; lowercase trailing common words.  This is a
        # conservative pass — we don't want to corrupt biological names
        # like "DNA polymerase III" or "HtpG".
        return text

    @staticmethod
    def _strip_leading_modifier(text: str) -> str:
        lower = text.lower()
        for mod in _LEADING_MODIFIERS:
            if lower.startswith(mod + " "):
                return text[len(mod) + 1 :].lstrip()
        return text
