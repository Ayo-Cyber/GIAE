"""Fetch canonical prokaryotic annotation-benchmark genomes from NCBI.

These reference genomes recur across genome-annotation benchmarks
(Prokka, Bakta, PGAP, DFAST). Each is a finished, curated RefSeq record, so
its embedded CDS annotation serves as ground truth for F1 scoring — the same
basis bakta_comparison.py already uses.

Downloads full GenBank (rettype=gbwithparts, so CON records include sequence)
into benchmark_genomes/. Skips files already present.

  .venv/bin/python post_assets/fetch_benchmark_genomes.py            # small+medium tier
  .venv/bin/python post_assets/fetch_benchmark_genomes.py --all      # + large genomes
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "benchmark_genomes"
EFETCH = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=nuccore&id={acc}&rettype=gbwithparts&retmode=text"
)

# (filename, accession, approx_genes, tier)  tier: small|medium|large
GENOMES = [
    # ── small: minimal / classic genomes — fast, great smoke tests ──
    ("Mycoplasma_genitalium_G37",   "NC_000908.2",  525, "small"),
    ("Mycoplasma_pneumoniae_M129",  "NC_000912.1",  690, "small"),
    ("Haemophilus_influenzae_Rd",   "NC_000907.1", 1700, "small"),   # 1st sequenced genome (1995)
    # ── medium: standard references ──
    ("Bacillus_subtilis_168",       "NC_000964.3", 4400, "medium"),
    ("Staphylococcus_aureus_8325",  "NC_007795.1", 2870, "medium"),
    ("Listeria_monocytogenes_EGDe", "NC_003210.1", 2900, "medium"),
    ("Caulobacter_vibrioides_NA1000","NC_011916.1", 3900, "medium"),
    ("Methanocaldococcus_jannaschii","NC_000909.1", 1770, "medium"),  # archaeon, breadth
    # ── large: canonical heavy references ──
    ("Escherichia_coli_K12_MG1655", "NC_000913.3", 4400, "large"),   # THE reference genome
    ("Pseudomonas_aeruginosa_PAO1", "NC_002516.2", 5700, "large"),
    ("Mycobacterium_tuberculosis_H37Rv", "NC_000962.3", 4000, "large"),
    ("Salmonella_Typhimurium_LT2",  "NC_003197.2", 4600, "large"),
]


def fetch(acc: str) -> str:
    with urllib.request.urlopen(EFETCH.format(acc=acc), timeout=120) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="include large genomes too")
    ap.add_argument("--tiers", default="", help="comma list: small,medium,large (overrides --all)")
    args = ap.parse_args()

    if args.tiers:
        tiers = {t.strip() for t in args.tiers.split(",")}
    else:
        tiers = {"small", "medium", "large"} if args.all else {"small", "medium"}

    OUT_DIR.mkdir(exist_ok=True)
    targets = [g for g in GENOMES if g[3] in tiers]
    print(f"Fetching {len(targets)} genomes (tiers={sorted(tiers)}) -> {OUT_DIR}")
    ok = 0
    for name, acc, genes, tier in targets:
        dest = OUT_DIR / f"{name}.gb"
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"  skip {name} ({acc}) — present")
            ok += 1
            continue
        print(f"  fetch {name} ({acc}, ~{genes} genes, {tier}) …", flush=True)
        try:
            text = fetch(acc)
        except Exception as e:  # noqa: BLE001
            print(f"    ERROR: {e}", file=sys.stderr)
            continue
        if "ORIGIN" not in text:
            print(f"    WARN: no ORIGIN/sequence in {acc} — skipping", file=sys.stderr)
            continue
        dest.write_text(text)
        bp = "".join(c for c in text.split("ORIGIN", 1)[-1] if c.isalpha())
        print(f"    saved {dest.name}  ({len(text)//1024} KB, ~{len(bp)//1000} kbp)")
        ok += 1
        time.sleep(0.4)  # be polite to NCBI
    print(f"Done: {ok}/{len(targets)} available in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
