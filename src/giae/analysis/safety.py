"""Phage safety screening for therapeutic / biosecurity use.

Therapeutic phage selection has hard safety gates that ordinary annotation does
not surface: a candidate phage should be *strictly lytic* (no lysogeny
machinery), and must not carry antibiotic-resistance, toxin, or virulence
genes. This module reads the products GIAE already assigned and flags those
signals into a single, auditable safety report.

Honesty by design (matches GIAE's trust posture): this is a **screen**, not a
validated assay. It flags candidates for expert review with the exact matched
signal and its provenance, and it states its own limits — a signature-based
screen is a lower bound (novel/renamed genes can be missed). It never returns a
bare "safe/unsafe" verdict without the evidence behind it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

# ── Signature library ────────────────────────────────────────────────────────
# (compiled regex, human label). Word-boundaried, case-insensitive. Curated for
# precision over recall — a signature-based screen is explicitly a lower bound.

_LYSOGENY = [
    (r"\bintegrase\b", "integrase"),
    (r"\b(tyrosine|serine)[- ]recombinase\b", "site-specific recombinase"),
    (r"\bexcisionase\b", "excisionase"),
    (r"\bxis\b", "excisionase (xis)"),
    (r"\bci\b repressor|\brepressor ci\b|\bci-like repressor\b", "CI repressor"),
    (r"\bcro\b", "Cro repressor"),
    (r"\bantirepressor\b", "antirepressor"),
    (r"\bprophage\b|\blysogen", "prophage/lysogeny"),
    (r"\battachment site\b|\battp\b", "attachment site"),
    (r"\bsuperinfection (exclusion|immunity)\b", "superinfection immunity"),
]

_AMR = [
    (r"beta-lactamase|β-lactamase|\bbla[A-Z]?\b", "beta-lactamase"),
    (r"aminoglycoside|\baac\(|\baph\(|\baad[A-Z]?\b", "aminoglycoside resistance"),
    (r"tetracycline resistance|\btet\([A-Z]\)|\btet[A-Z]\b", "tetracycline resistance"),
    (r"chloramphenicol acetyltransferase|\bcat[A-Z]?\b", "chloramphenicol resistance"),
    (r"macrolide|\berm[A-Z]?\b|\bmef[A-Z]\b", "macrolide resistance"),
    (r"vancomycin|\bvan[A-Z]\b", "vancomycin resistance"),
    (r"\bmec[A-C]\b|methicillin resist", "methicillin resistance"),
    (r"\bsul[123]\b|sulfonamide resist", "sulfonamide resistance"),
    (r"\bqnr[A-Z]?\b|quinolone resist", "quinolone resistance"),
    (r"dihydrofolate reductase.*trimethoprim|\bdfr[A-Z]?\b", "trimethoprim resistance"),
    (r"multidrug efflux|\bmdr\b|efflux pump.*resist", "multidrug efflux"),
    (r"antibiotic resistance|drug resistance", "generic AMR term"),
]

_VIRULENCE = [
    (r"shiga(-| )?(like )?toxin|\bstx[0-9]?\b", "Shiga toxin"),
    (r"cholera toxin|\bctx[AB]?\b", "cholera toxin"),
    (r"diphtheria toxin", "diphtheria toxin"),
    (r"\bhemolysin\b|\bhly[A-Z]?\b|haemolysin", "hemolysin"),
    (r"leukocidin|panton-valentine|\bluk[A-Z]{1,2}\b", "leukocidin"),
    (r"enterotoxin", "enterotoxin"),
    (r"superantigen|exotoxin", "superantigen/exotoxin"),
    (r"\btoxin\b", "toxin (generic)"),
    (r"virulence factor|virulence-associated", "virulence factor"),
    (r"\badhesin\b|\binvasin\b|intimin", "adhesin/invasin"),
]

_CATEGORIES = {
    "lysogeny": (_LYSOGENY, "warning"),   # temperate lifestyle → caution for therapy
    "amr": (_AMR, "critical"),
    "virulence": (_VIRULENCE, "critical"),
}
_COMPILED = {
    cat: ([(re.compile(pat, re.I), label) for pat, label in sigs], sev)
    for cat, (sigs, sev) in _CATEGORIES.items()
}
# Uninformative products never trigger a flag (avoids "toxin" matching noise).
_UNINFORMATIVE = re.compile(r"^(hypothetical|uncharacteri[sz]ed|unknown|putative protein)\b", re.I)


@dataclass
class SafetyFlag:
    category: str          # lysogeny | amr | virulence
    severity: str          # warning | critical
    gene_id: str
    gene_name: str
    product: str
    signal: str            # human label of what matched
    source: str            # provenance (tool/hit that produced the product)


@dataclass
class SafetyReport:
    flags: list[SafetyFlag] = field(default_factory=list)
    lysogenic: bool = False          # temperate-lifestyle markers present
    verdict: str = ""                # short machine-ish verdict
    recommendation: str = ""         # human sentence
    screened_genes: int = 0

    @property
    def critical_flags(self) -> list[SafetyFlag]:
        return [f for f in self.flags if f.severity == "critical"]

    def counts(self) -> dict:
        c = {"lysogeny": 0, "amr": 0, "virulence": 0}
        for f in self.flags:
            c[f.category] = c.get(f.category, 0) + 1
        return c


def _informative(product: Optional[str]) -> bool:
    return bool(product and product.strip() and not _UNINFORMATIVE.match(product.strip()))


class SafetyScreener:
    """Signature-based phage-safety screen over annotated products."""

    def screen(self, items: Iterable[tuple]) -> SafetyReport:
        """items: iterable of (gene_id, gene_name, product, source)."""
        report = SafetyReport()
        seen: set[tuple] = set()
        n = 0
        for gene_id, gene_name, product, source in items:
            n += 1
            if not _informative(product):
                continue
            text = product
            for cat, (sigs, sev) in _COMPILED.items():
                for rx, label in sigs:
                    if rx.search(text):
                        key = (gene_id, cat, label)
                        if key in seen:
                            continue
                        seen.add(key)
                        report.flags.append(SafetyFlag(
                            category=cat, severity=sev, gene_id=gene_id,
                            gene_name=gene_name or gene_id, product=product,
                            signal=label, source=source or "annotation",
                        ))
                        break  # one flag per category per gene is enough
        report.screened_genes = n
        self._verdict(report)
        return report

    def screen_genome(self, genome) -> SafetyReport:
        items = []
        for g in genome.genes:
            product = (g.protein.product_name if getattr(g, "protein", None) else None) or g.name
            items.append((g.id, g.name or g.locus_tag or g.id, product, "genbank/annotation"))
        return self.screen(items)

    def screen_summary(self, summary, genome) -> SafetyReport:
        """Screen from interpretation results — prefers the normalized product /
        hypothesis GIAE assigned, with the strongest evidence source as provenance."""
        gmap = {g.id: g for g in genome.genes}
        items = []
        for r in summary.results:
            interp = getattr(r, "interpretation", None)
            gene = gmap.get(r.gene_id)
            product = None
            source = "annotation"
            if interp:
                product = (interp.metadata or {}).get("normalized_product") or interp.hypothesis
            if not product and gene and getattr(gene, "protein", None):
                product = gene.protein.product_name
            agg = getattr(r, "aggregated_evidence", None)
            if agg:
                try:
                    top = agg.get_top_evidence(1)
                    if top and top[0].provenance:
                        source = top[0].provenance.tool_name
                except Exception:
                    pass
            name = (gene.name if gene else None) or r.gene_id
            items.append((r.gene_id, name, product, source))
        return self.screen(items)

    # ── verdict logic ────────────────────────────────────────────────────────
    @staticmethod
    def _verdict(report: SafetyReport) -> None:
        counts = report.counts()
        report.lysogenic = counts["lysogeny"] > 0
        crit = report.critical_flags
        if any(f.category == "amr" for f in crit) or any(f.category == "virulence" for f in crit):
            cats = sorted({f.category for f in crit})
            report.verdict = "not_recommended"
            report.recommendation = (
                "Not recommended for therapeutic use — candidate carries "
                + " and ".join(cats)
                + " gene signals. Confirm by expert review before any use."
            )
        elif report.lysogenic:
            report.verdict = "caution"
            report.recommendation = (
                "Caution — lysogeny machinery detected (temperate lifestyle). "
                "Therapeutic phages are generally strictly lytic; verify lifestyle "
                "experimentally."
            )
        else:
            report.verdict = "no_flags"
            report.recommendation = (
                "No AMR, toxin/virulence, or lysogeny signatures detected. This is "
                "a signature screen, not a validated assay — absence of a flag is "
                "not proof of safety."
            )
