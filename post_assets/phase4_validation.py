"""Phase 4 validation — measure GIAE prediction quality against GenBank ground truth.

For each genome we:
  1. Load the GenBank file as ground truth (CDS features only).
  2. Strip annotations → FASTA-only genome, run GIAE ORF prediction offline.
  3. Match predictions to truth by reciprocal coordinate overlap ≥ 50% on the same strand.
  4. Report TP / FP / FN, Precision, Recall, F1.
  5. Compare pyrodigal-only vs pyrodigal + rescue pass.

Run: .venv/bin/python post_assets/phase4_validation.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from giae.engine.interpreter import Interpreter
from giae.parsers.genbank import GenBankParser

CASE_DIR = Path(__file__).parent.parent / "case_studies"
GENOMES = ["phiX174.gb", "lambda_phage.gb", "T7.gb"]

parser = GenBankParser()

_BASE_FLAGS = dict(
    use_uniprot=False,
    use_interpro=False,
    use_local_blast=False,
    use_diamond=False,
    use_hmmer=False,
    use_esm=False,
    use_aragorn=False,
    use_barrnap=False,
    use_cache=False,
)


@dataclass
class MatchResult:
    genome: str
    truth_count: int
    pred_count: int
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def reciprocal_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    """Fraction of the longer span covered by the intersection."""
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    longer = max(a_end - a_start, b_end - b_start)
    return inter / longer if longer else 0.0


def match_genes(
    truth: list[tuple[int, int, int]],
    preds: list[tuple[int, int, int]],
    overlap_threshold: float = 0.5,
) -> tuple[int, int, int]:
    """Return (TP, FP, FN) given truth and prediction spans."""
    matched_truth = set()
    matched_pred = set()

    for pi, (ps, pe, pstrand) in enumerate(preds):
        for ti, (ts, te, tstrand) in enumerate(truth):
            if ti in matched_truth:
                continue
            if pstrand != tstrand:
                continue
            if reciprocal_overlap(ps, pe, ts, te) >= overlap_threshold:
                matched_truth.add(ti)
                matched_pred.add(pi)
                break

    tp = len(matched_pred)
    fp = len(preds) - tp
    fn = len(truth) - len(matched_truth)
    return tp, fp, fn


def run_validation(
    gb_path: Path,
    use_rescue: bool = False,
    phage_mode: bool = False,
) -> MatchResult:
    name = gb_path.stem

    genome_gt = parser.parse(gb_path)
    truth_spans = [
        (g.location.start, g.location.end, g.location.strand.value)
        for g in genome_gt.genes
    ]

    genome_pred = parser.parse(gb_path)
    genome_pred.genes.clear()
    genome_pred.file_format = "fasta"

    interpreter = Interpreter(
        **_BASE_FLAGS,
        use_rescue=use_rescue,
        phage_mode=phage_mode,
    )
    interpreter.interpret_genome(genome_pred)

    pred_spans = [
        (g.location.start, g.location.end, g.location.strand.value)
        for g in genome_pred.genes
    ]

    tp, fp, fn = match_genes(truth_spans, pred_spans)
    return MatchResult(
        genome=name,
        truth_count=len(truth_spans),
        pred_count=len(pred_spans),
        tp=tp,
        fp=fp,
        fn=fn,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

header = (
    f"{'Genome':<18} {'Truth':>6} {'Pred':>6} {'TP':>5} {'FP':>5} {'FN':>5}  "
    f"{'Precision':>9} {'Recall':>7} {'F1':>7}"
)
sep = "-" * 75

def _row(r: MatchResult) -> str:
    return (
        f"{r.genome:<18} {r.truth_count:>6} {r.pred_count:>6} "
        f"{r.tp:>5} {r.fp:>5} {r.fn:>5}  "
        f"{r.precision:>8.1%} {r.recall:>7.1%} {r.f1:>7.1%}"
    )


print("── pyrodigal only ───────────────────────────────────────────────────────")
print(header)
print(sep)
for filename in GENOMES:
    print(_row(run_validation(CASE_DIR / filename)))

print()
print("── + rescue pass ─────────────────────────────────────────────────────────")
print(header)
print(sep)
for filename in GENOMES:
    print(_row(run_validation(CASE_DIR / filename, use_rescue=True)))

print()
print("── + rescue + phage_mode (nested ORFs) ──────────────────────────────────")
print(header)
print(sep)
for filename in GENOMES:
    print(_row(run_validation(CASE_DIR / filename, use_rescue=True, phage_mode=True)))

print()
print("Match criterion: same strand, reciprocal coordinate overlap ≥ 50%")
print("Rescue gate     : SD motif + codon usage (gap regions only)")
print("Phage_mode gate : position-weighted SD + codon usage (nested ORFs)")
