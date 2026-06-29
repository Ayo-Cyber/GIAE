"""Pitch-grade benchmark: GIAE vs Bakta on the same ground truth.

For each genome:
  ground truth   = curated GenBank CDS (coordinates + /product)
  GIAE           = de-novo prediction (genes cleared) + functional interpretation
  Bakta          = annotation from genome FASTA

Two axes, both scored against the same RefSeq truth:
  1. Gene finding   — precision / recall / F1 (reciprocal overlap >= 0.5, same strand)
  2. Function       — of coordinate-matched genes with an *informative* truth product,
                      fraction whose predicted product agrees (token overlap)

Outputs:
  post_assets/benchmark_figure_results.csv
  post_assets/benchmark_figure.png

Run:
  .venv/bin/python post_assets/benchmark_figure.py --genomes case_studies/lambda_phage.gb case_studies/T7.gb
  .venv/bin/python post_assets/benchmark_figure.py --set phages          # all case_studies/*.gb
  .venv/bin/python post_assets/benchmark_figure.py --set bacteria        # benchmark_genomes/*.gb
  .venv/bin/python post_assets/benchmark_figure.py --set all --no-bakta  # GIAE-only, fast
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from giae.engine.interpreter import Interpreter
from giae.parsers.genbank import GenBankParser

ROOT = Path(__file__).resolve().parent.parent
CASE_DIR = ROOT / "case_studies"
BACT_DIR = ROOT / "benchmark_genomes"
BAKTA_DB = Path.home() / ".bakta_db" / "db-light"
OUT_CSV = ROOT / "post_assets" / "benchmark_figure_results.csv"
OUT_PNG = ROOT / "post_assets" / "benchmark_figure.png"

parser = GenBankParser()

# GIAE offline configs — match the deployed worker. Phage mode enables phage-
# specific ORF rescue + nested ORF detection, used automatically for case_studies.
_GIAE = Interpreter(
    use_uniprot=False, use_interpro=False, use_local_blast=False,
    use_diamond=False, use_hmmer=False, use_esm=False, use_cache=False,
)
_GIAE_PHAGE = Interpreter(
    use_uniprot=False, use_interpro=False, use_local_blast=False,
    use_diamond=False, use_hmmer=False, use_esm=False, use_cache=False,
    phage_mode=True,
)

Feature = Tuple[int, int, int, Optional[str]]  # start, end, strand, product

# ── function-text normalisation ──────────────────────────────────────────────
_STOP = {
    "putative", "probable", "predicted", "protein", "domain", "family",
    "containing", "the", "of", "and", "uncharacterized", "conserved",
    "hypothetical", "subunit", "type", "like", "related",
}
_UNINFORMATIVE = re.compile(
    r"^(hypothetical|uncharacteri[sz]ed|unknown|putative)\b", re.I
)


def tokens(product: str | None) -> set[str]:
    if not product:
        return set()
    words = re.sub(r"[^a-z0-9 ]", " ", product.lower()).split()
    return {w for w in words if w not in _STOP and len(w) > 2}


def informative(product: str | None) -> bool:
    if not product or not product.strip():
        return False
    if _UNINFORMATIVE.match(product.strip()):
        return False
    return len(tokens(product)) > 0


def func_agree(pred: str | None, truth: str | None) -> bool:
    tp, tt = tokens(pred), tokens(truth)
    if not tp or not tt:
        return False
    inter = tp & tt
    if not inter:
        return False
    jacc = len(inter) / len(tp | tt)
    return jacc >= 0.34 or tp <= tt or tt <= tp


# ── scoring ──────────────────────────────────────────────────────────────────
def overlap(a: Feature, b: Feature) -> float:
    if a[2] != b[2]:
        return 0.0
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    if inter == 0:
        return 0.0
    return min(inter / (a[1] - a[0]), inter / (b[1] - b[0]))


@dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    func_total: int = 0       # TP genes with informative truth product
    func_ok: int = 0          # of those, agreeing with truth
    func_annotated: int = 0   # TP genes where THIS tool gave an informative function

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def func_acc(self) -> float:
        """Fraction of coord-matched genes with informative truth that also agree on function."""
        return self.func_ok / self.func_total if self.func_total else 0.0

    @property
    def func_precision(self) -> float:
        """When this tool assigns an informative label, fraction that match truth."""
        return self.func_ok / self.func_annotated if self.func_annotated else 0.0

    @property
    def annotate_rate(self) -> float:
        """Fraction of coord-matched genes that received an informative function."""
        return self.func_annotated / self.tp if self.tp else 0.0


def score(pred: list[Feature], truth: list[Feature], thr: float = 0.5) -> Score:
    s = Score()
    used = set()
    for p in pred:
        best, best_j = -1, thr
        for j, t in enumerate(truth):
            if j in used:
                continue
            o = overlap(p, t)
            if o >= best_j:
                best_j, best = o, j
        if best >= 0:
            used.add(best)
            s.tp += 1
            t = truth[best]
            pred_inf = informative(p[3])
            truth_inf = informative(t[3])
            if pred_inf:
                s.func_annotated += 1
            if truth_inf:
                s.func_total += 1
                if pred_inf and func_agree(p[3], t[3]):
                    s.func_ok += 1
        else:
            s.fp += 1
    s.fn = len(truth) - len(used)
    return s


# ── feature extraction ───────────────────────────────────────────────────────
def truth_features(gb: Path) -> list[Feature]:
    g = parser.parse(gb)
    out = []
    for gene in g.genes:
        prod = gene.protein.product_name if gene.protein else None
        out.append((gene.location.start, gene.location.end, gene.location.strand.value, prod))
    return out


def giae_features(gb: Path, phage_mode: bool = False) -> list[Feature]:
    g = parser.parse(gb)
    g.genes.clear()
    g.file_format = "fasta"
    interp = _GIAE_PHAGE if phage_mode else _GIAE
    summary = interp.interpret_genome(g)
    gmap = {x.id: x for x in g.genes}
    out = []
    for r in summary.results:
        gene = gmap.get(r.gene_id)
        if not gene:
            continue
        func = None
        if r.interpretation:
            func = (r.interpretation.metadata or {}).get("normalized_product") or r.interpretation.hypothesis
        loc = gene.location
        out.append((loc.start, loc.end, loc.strand.value, func))
    return out


def bakta_features(gb: Path) -> list[Feature]:
    g = parser.parse(gb)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fasta = tmp / "g.fasta"
        fasta.write_text(f">genome\n{g.sequence}\n")
        out_dir = tmp / "out"
        out_dir.mkdir()
        bakta = ROOT / ".venv" / "bin" / "bakta"
        cmd = [
            str(bakta if bakta.exists() else shutil.which("bakta")),
            "--db", str(BAKTA_DB), "--output", str(out_dir), "--prefix", "g",
            "--min-contig-length", "1",
            "--skip-trna", "--skip-tmrna", "--skip-rrna", "--skip-ncrna",
            "--skip-ncrna-region", "--skip-crispr", "--skip-pseudo",
            "--skip-sorf", "--skip-gap", "--skip-ori", "--skip-plot",
            "--threads", "4", "--force", str(fasta),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        gff = out_dir / "g.gff3"
        if res.returncode != 0 or not gff.exists():
            print(f"    [bakta failed] {res.stderr[-200:]}", file=sys.stderr)
            return []
        out = []
        for line in gff.read_text().splitlines():
            if line.startswith("#") or not line.strip():
                continue
            p = line.split("\t")
            if len(p) < 9 or p[2] != "CDS":
                continue
            try:
                start, end = int(p[3]) - 1, int(p[4])
            except ValueError:
                continue
            strand = -1 if p[6] == "-" else 1
            m = re.search(r"product=([^;]+)", p[8])
            out.append((start, end, strand, m.group(1) if m else None))
        return out


# ── main ─────────────────────────────────────────────────────────────────────
def resolve_genomes(args) -> list[Path]:
    if args.genomes:
        return [Path(p) for p in args.genomes]
    if args.set == "phages":
        return sorted(CASE_DIR.glob("*.gb"))
    if args.set == "bacteria":
        return sorted(BACT_DIR.glob("*.gb"))
    return sorted(CASE_DIR.glob("*.gb")) + sorted(BACT_DIR.glob("*.gb"))


def make_figure(rows: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [r["genome"] for r in rows]
    x = range(len(names))
    w = 0.28
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(max(8, len(names) * 0.7), 9))

    ax1.bar([i - w / 2 for i in x], [float(r["giae_f1"]) for r in rows], w, label="GIAE", color="#6366f1")
    if any(r.get("bakta_f1") for r in rows):
        ax1.bar([i + w / 2 for i in x], [float(r.get("bakta_f1") or 0) for r in rows], w, label="Bakta", color="#94a3b8")
    ax1.set_ylabel("Gene-finding F1"); ax1.set_ylim(0, 1); ax1.legend()
    ax1.set_title("GIAE vs Bakta — gene-finding F1 (vs RefSeq, reciprocal overlap ≥ 0.5)")
    ax1.set_xticks(list(x)); ax1.set_xticklabels(names, rotation=45, ha="right", fontsize=8)

    # Functional: show GIAE annotation-precision (when it labels, is it right?)
    # and Bakta coverage (fraction of informative truth genes it assigns correct labels)
    giae_func = [float(r.get("giae_func_prec") or 0) for r in rows]
    bakta_func = [float(r.get("bakta_func_cov") or 0) for r in rows]
    ax2.bar([i - w / 2 for i in x], giae_func, w, label="GIAE (label precision)", color="#34d399")
    if any(bakta_func):
        ax2.bar([i + w / 2 for i in x], bakta_func, w, label="Bakta (label coverage)", color="#94a3b8")
    ax2.set_ylabel("Functional annotation score"); ax2.set_ylim(0, 1); ax2.legend()
    ax2.set_title(
        "GIAE label precision (when it annotates, % matches RefSeq) vs Bakta coverage"
    )
    ax2.set_xticks(list(x)); ax2.set_xticklabels(names, rotation=45, ha="right", fontsize=8)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=140)
    print(f"figure -> {OUT_PNG}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--genomes", nargs="*", help="explicit .gb paths")
    ap.add_argument("--set", choices=["phages", "bacteria", "all"], default="phages")
    ap.add_argument("--no-bakta", action="store_true")
    ap.add_argument("--no-phage-mode", action="store_true",
                    help="disable phage_mode for case_studies genomes")
    args = ap.parse_args()

    genomes = resolve_genomes(args)
    if not genomes:
        print("no genomes found", file=sys.stderr)
        return 1
    do_bakta = not args.no_bakta and BAKTA_DB.exists()

    # Resume: load rows already written to CSV so we can skip completed genomes
    rows = []
    done_names: set = set()
    fields = [
        "genome", "truth_genes",
        "giae_p", "giae_r", "giae_f1", "giae_func_cov", "giae_func_prec",
        "giae_annotate_rate", "giae_time_s",
        "bakta_p", "bakta_r", "bakta_f1", "bakta_func_cov", "bakta_func_prec",
        "bakta_annotate_rate", "bakta_time_s",
    ]
    if OUT_CSV.exists():
        with OUT_CSV.open(newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)
                done_names.add(row["genome"])
        if done_names:
            print(f"Resuming — {len(done_names)} genomes already done: {sorted(done_names)}", flush=True)

    for gb in genomes:
        if not gb.exists():
            print(f"skip missing {gb}", file=sys.stderr); continue
        if gb.stem in done_names:
            print(f"   skip (already done): {gb.stem}", flush=True); continue
        print(f"== {gb.stem} ==", flush=True)
        try:
            truth = truth_features(gb)
        except Exception as exc:
            print(f"   skip (parse error: {exc})", file=sys.stderr); continue
        # use phage_mode when genome is from case_studies (phage set) unless overridden
        is_phage = str(CASE_DIR) in str(gb.resolve())
        phage_mode = is_phage and not args.no_phage_mode
        t0 = time.time()
        gs = score(giae_features(gb, phage_mode=phage_mode), truth)
        row = {
            "genome": gb.stem, "truth_genes": len(truth),
            "giae_p": f"{gs.precision:.3f}", "giae_r": f"{gs.recall:.3f}",
            "giae_f1": f"{gs.f1:.3f}",
            "giae_func_cov": f"{gs.func_acc:.3f}",       # coverage: % TP with informative truth that agree
            "giae_func_prec": f"{gs.func_precision:.3f}", # precision: when GIAE labels, % correct
            "giae_annotate_rate": f"{gs.annotate_rate:.3f}",
            "giae_time_s": round(time.time() - t0, 1),
        }
        print(
            f"   GIAE  P={gs.precision:.2f} R={gs.recall:.2f} F1={gs.f1:.2f} "
            f"func_cov={gs.func_acc:.2f} func_prec={gs.func_precision:.2f} "
            f"annotate={gs.annotate_rate:.0%} ({row['giae_time_s']}s) [phage={phage_mode}]",
            flush=True,
        )
        if do_bakta:
            t1 = time.time()
            bs = score(bakta_features(gb), truth)
            row.update(
                bakta_p=f"{bs.precision:.3f}", bakta_r=f"{bs.recall:.3f}",
                bakta_f1=f"{bs.f1:.3f}",
                bakta_func_cov=f"{bs.func_acc:.3f}",
                bakta_func_prec=f"{bs.func_precision:.3f}",
                bakta_annotate_rate=f"{bs.annotate_rate:.3f}",
                bakta_time_s=round(time.time() - t1, 1),
            )
            print(
                f"   Bakta P={bs.precision:.2f} R={bs.recall:.2f} F1={bs.f1:.2f} "
                f"func_cov={bs.func_acc:.2f} func_prec={bs.func_precision:.2f} "
                f"annotate={bs.annotate_rate:.0%} ({row['bakta_time_s']}s)",
                flush=True,
            )
        rows.append(row)
        with OUT_CSV.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})

    make_figure(rows)
    # aggregate
    gi_f1 = sum(float(r["giae_f1"]) for r in rows) / len(rows)
    print(f"\nMean GIAE F1: {gi_f1:.3f}")
    if do_bakta:
        bk_f1 = sum(float(r.get("bakta_f1") or 0) for r in rows) / len(rows)
        print(f"Mean Bakta F1: {bk_f1:.3f}")
    print(f"Results: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
