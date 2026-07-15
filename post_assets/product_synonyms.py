"""Rule-based product-name synonym normaliser for functional-accuracy grading.

The homology calibration grades a predicted product name against the curated
RefSeq product by token overlap. That under-counts correct calls whenever the
two databases use different *conventions* for the same protein. Those
differences are systematic, not random, so they can be normalised by rule
rather than by a hand-picked lookup that could be accused of cherry-picking:

  1. Aminoacyl-tRNA synthetases  — UniProt 'serine--tRNA ligase' vs
     RefSeq 'seryl-tRNA synthetase'  → canonical 'aars:serine'
  2. Ribosomal proteins          — UniProt 'small ribosomal subunit protein
     bS6' vs RefSeq '30S ribosomal protein S6'  → canonical 'rp:s6'
  3. synthase / synthetase spelling
  4. A small curated set of documented equivalences (capsid=head, portal=
     connector, enolase=phosphopyruvate hydratase, …)

`synonym_agree(pred, truth)` returns True iff the raw token-overlap grader
already agrees OR both names canonicalise to the same protein. Genuine
mismatches (e.g. 'replication-related protein' vs 'transketolase') are left
wrong. Every rule that fires is attributable, so the adjusted number is
defensible rather than inflated.
"""

from __future__ import annotations

import re

from benchmark_figure import func_agree, tokens

# ── amino-acid adjective (‑yl) ↔ noun forms, for aminoacyl-tRNA synthetases ──
_AA = {
    "alanyl": "alanine", "arginyl": "arginine", "asparaginyl": "asparagine",
    "aspartyl": "aspartate", "cysteinyl": "cysteine", "glutaminyl": "glutamine",
    "glutamyl": "glutamate", "glycyl": "glycine", "histidyl": "histidine",
    "isoleucyl": "isoleucine", "leucyl": "leucine", "lysyl": "lysine",
    "methionyl": "methionine", "phenylalanyl": "phenylalanine", "prolyl": "proline",
    "seryl": "serine", "threonyl": "threonine", "tryptophanyl": "tryptophan",
    "tyrosyl": "tyrosine", "valyl": "valine",
}
_AA_NOUNS = set(_AA.values())

_RIBO_UNIPROT = re.compile(r"(?:small|large) ribosomal subunit protein\s+[a-z]*([sl])(\d+)", re.I)
_RIBO_REFSEQ = re.compile(r"(?:30s|50s)?\s*ribosomal protein\s+([sl])(\d+)", re.I)

# curated documented equivalences — each frozenset is one protein under aliases
_EQUIV_CLASSES = [
    {"major capsid protein", "major head protein"},
    {"capsid assembly scaffolding protein", "head scaffolding protein",
     "scaffolding protein", "capsid scaffolding protein"},
    {"portal protein", "upper collar connector", "connector protein", "head-tail connector"},
    {"enolase", "phosphopyruvate hydratase"},
    {"terminase large subunit", "terminase", "large terminase subunit", "dna packaging protein"},
    {"terminase small subunit", "small terminase subunit"},
    {"tail terminator", "tail tube terminator protein", "tail terminator protein"},
    {"single-stranded dna-binding protein", "single strand dna binding protein",
     "ssdna-binding protein", "ssdna binding protein"},
    {"dna terminal protein", "primer terminal protein", "terminal protein"},
]
# term -> canonical representative
_EQUIV = {}
for _cls in _EQUIV_CLASSES:
    rep = sorted(_cls)[0]
    for _t in _cls:
        _EQUIV[_t] = rep


def canonical(product: str | None) -> str | None:
    """Map a product name to a convention-invariant canonical key, or None if
    no rule applies (caller then falls back to token overlap)."""
    if not product:
        return None
    p = product.strip().lower()
    p = p.replace("synthetase", "synthase")

    # 1. aminoacyl-tRNA synthetase (both 'X--tRNA ligase' and 'Xyl-tRNA synthase')
    if "trna" in p and ("ligase" in p or "synthas" in p):
        for adj, noun in _AA.items():
            if adj in p:
                return f"aars:{noun}"
        for noun in _AA_NOUNS:
            if noun in p:
                return f"aars:{noun}"

    # 2. ribosomal proteins (bS6 / 30S S6 → rp:s6)
    m = _RIBO_UNIPROT.search(p) or _RIBO_REFSEQ.search(p)
    if m:
        return f"rp:{m.group(1).lower()}{m.group(2)}"

    # 4. curated equivalence classes
    if p in _EQUIV:
        return _EQUIV[p]

    return None


def synonym_agree(pred: str | None, truth: str | None) -> tuple[bool, str]:
    """Return (agree, reason). reason ∈ {token, aars, ribosomal, curated, ''}."""
    if func_agree(pred, truth):
        return True, "token"
    cp, ct = canonical(pred), canonical(truth)
    if cp and ct and cp == ct:
        if cp.startswith("aars:"):
            return True, "aars"
        if cp.startswith("rp:"):
            return True, "ribosomal"
        return True, "curated"
    return False, ""
