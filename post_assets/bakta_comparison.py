"""Bakta vs GIAE comparison — same ground truth, same scoring.

For each genome:
  1. GenBank file → ground truth CDS spans.
  2. Genome FASTA → Bakta annotation → predicted CDS spans.
  3. Genome FASTA → GIAE (pyrodigal + rescue) → predicted CDS spans.
  4. Both scored with reciprocal overlap ≥ 50% on the same strand.

Run: .venv/bin/python post_assets/bakta_comparison.py
Requires: bakta installed + ~/.bakta_db/db-light present.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from giae.engine.interpreter import Interpreter
from giae.parsers.genbank import GenBankParser

CASE_DIR = Path(__file__).parent.parent / "case_studies"
GENOMES = ["phiX174.gb", "lambda_phage.gb", "T7.gb"]
BAKTA_DB = Path.home() / ".bakta_db" / "db-light"

parser = GenBankParser()

_GIAE_FLAGS = dict(
    use_uniprot=False,
    use_interpro=False,
    use_local_blast=False,
    use_diamond=False,
    use_hmmer=False,
    use_esm=False,
    use_aragorn=False,
    use_barrnap=False,
    use_cache=False,
    use_rescue=True,
    phage_mode=True,
)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MatchResult:
    genome: str
    tool: str
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


# ── Matching ──────────────────────────────────────────────────────────────────

def reciprocal_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    longer = max(a_end - a_start, b_end - b_start)
    return inter / longer if longer else 0.0


def match_genes(
    truth: list[tuple[int, int, int]],
    preds: list[tuple[int, int, int]],
    overlap_threshold: float = 0.5,
) -> tuple[int, int, int]:
    matched_truth: set[int] = set()
    matched_pred: set[int] = set()
    for pi, (ps, pe, pstrand) in enumerate(preds):
        for ti, (ts, te, tstrand) in enumerate(truth):
            if ti in matched_truth or pstrand != tstrand:
                continue
            if reciprocal_overlap(ps, pe, ts, te) >= overlap_threshold:
                matched_truth.add(ti)
                matched_pred.add(pi)
                break
    tp = len(matched_pred)
    return tp, len(preds) - tp, len(truth) - len(matched_truth)


# ── Ground truth ──────────────────────────────────────────────────────────────

def get_truth(gb_path: Path) -> list[tuple[int, int, int]]:
    genome = parser.parse(gb_path)
    return [
        (g.location.start, g.location.end, g.location.strand.value)
        for g in genome.genes
    ]


# ── GIAE predictions ──────────────────────────────────────────────────────────

def run_giae(gb_path: Path) -> list[tuple[int, int, int]]:
    genome = parser.parse(gb_path)
    genome.genes.clear()
    genome.file_format = "fasta"
    Interpreter(**_GIAE_FLAGS).interpret_genome(genome)
    return [
        (g.location.start, g.location.end, g.location.strand.value)
        for g in genome.genes
    ]


# ── Bakta predictions ─────────────────────────────────────────────────────────

def run_bakta(gb_path: Path) -> list[tuple[int, int, int]]:
    """Write genome FASTA, run Bakta, parse GFF3 CDS lines."""
    genome = parser.parse(gb_path)
    seq = genome.sequence

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fasta = tmp / "genome.fasta"
        fasta.write_text(f">genome\n{seq}\n")
        out_dir = tmp / "bakta_out"
        out_dir.mkdir()

        cmd = [
            shutil.which(".venv/bin/bakta") or "bakta",
            "--db", str(BAKTA_DB),
            "--output", str(out_dir),
            "--prefix", "genome",
            "--min-contig-length", "1",
            "--complete",
            "--skip-trna",          # tRNAscan-SE not installed
            "--skip-tmrna",         # tRNAscan-SE dependency
            "--skip-rrna",          # barrnap optional
            "--skip-ncrna",         # Infernal/cmscan not installed
            "--skip-ncrna-region",
            "--skip-crispr",        # PILER-CR not installed
            "--skip-pseudo",        # reduces noise for phage genomes
            "--skip-sorf",          # skip small ORF expert search
            "--skip-gap",
            "--skip-ori",           # blastn not installed
            "--skip-plot",          # matplotlib not needed here
            "--threads", "4",
            "--force",
            str(fasta),
        ]
        # Use the venv bakta binary
        venv_bakta = Path(__file__).parent.parent / ".venv" / "bin" / "bakta"
        if venv_bakta.exists():
            cmd[0] = str(venv_bakta)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [Bakta stderr]: {result.stderr[-400:]}", file=sys.stderr)
            return []

        gff = out_dir / "genome.gff3"
        if not gff.exists():
            return []

        return _parse_bakta_gff(gff.read_text())


def _parse_bakta_gff(gff: str) -> list[tuple[int, int, int]]:
    """Parse Bakta GFF3 for CDS features → (start, end, strand_value)."""
    spans = []
    for line in gff.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        feature_type = parts[2]
        if feature_type != "CDS":
            continue
        try:
            start = int(parts[3]) - 1   # GFF3 1-based → 0-based
            end = int(parts[4])          # 1-based inclusive → 0-based exclusive
            strand_char = parts[6]
        except (ValueError, IndexError):
            continue
        strand_val = -1 if strand_char == "-" else 1
        spans.append((start, end, strand_val))
    return spans


# ── Main ──────────────────────────────────────────────────────────────────────

def _check_bakta() -> bool:
    if not BAKTA_DB.exists():
        print(f"ERROR: Bakta database not found at {BAKTA_DB}")
        print("Run: .venv/bin/bakta_db download --type light --output ~/.bakta_db")
        return False
    venv_bakta = Path(__file__).parent.parent / ".venv" / "bin" / "bakta"
    if not venv_bakta.exists() and not shutil.which("bakta"):
        print("ERROR: bakta binary not found")
        return False
    return True


def _row(r: MatchResult) -> str:
    return (
        f"{r.genome:<18} {r.tool:<8} {r.truth_count:>6} {r.pred_count:>6} "
        f"{r.tp:>5} {r.fp:>5} {r.fn:>5}  "
        f"{r.precision:>8.1%} {r.recall:>7.1%} {r.f1:>7.1%}"
    )


if __name__ == "__main__":
    if not _check_bakta():
        sys.exit(1)

    header = (
        f"{'Genome':<18} {'Tool':<8} {'Truth':>6} {'Pred':>6} {'TP':>5} "
        f"{'FP':>5} {'FN':>5}  {'Precision':>9} {'Recall':>7} {'F1':>7}"
    )
    sep = "-" * 83

    print(header)
    print(sep)

    all_results: list[MatchResult] = []

    for filename in GENOMES:
        gb_path = CASE_DIR / filename
        name = gb_path.stem
        truth = get_truth(gb_path)

        # GIAE
        giae_preds = run_giae(gb_path)
        tp, fp, fn = match_genes(truth, giae_preds)
        giae_r = MatchResult(name, "GIAE", len(truth), len(giae_preds), tp, fp, fn)
        all_results.append(giae_r)
        print(_row(giae_r))

        # Bakta
        print(f"  [running Bakta on {name}...]", end="\r", flush=True)
        bakta_preds = run_bakta(gb_path)
        tp, fp, fn = match_genes(truth, bakta_preds)
        bakta_r = MatchResult(name, "Bakta", len(truth), len(bakta_preds), tp, fp, fn)
        all_results.append(bakta_r)
        print(_row(bakta_r))
        print()

    # Summary delta
    print(sep)
    print("\nΔ F1 (GIAE − Bakta):")
    for i in range(0, len(all_results), 2):
        g, b = all_results[i], all_results[i + 1]
        delta = g.f1 - b.f1
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "=")
        print(f"  {g.genome:<18} {arrow} {delta:+.1%}")

    print()
    print("Match criterion : same strand, reciprocal coordinate overlap ≥ 50%")
    print("GIAE config     : pyrodigal + rescue (no UniProt/BLAST/InterPro)")
    print("Bakta config    : --skip-cds expert (light db, CDS annotation active)")
