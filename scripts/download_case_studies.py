#!/usr/bin/env python3
"""
Download additional phage/small genome case studies from NCBI GenBank.
Uses Biopython Entrez (already in the venv).

Usage:
    python scripts/download_case_studies.py
"""
import os
import time
from pathlib import Path
from Bio import Entrez, SeqIO

Entrez.email = "giae-dev@example.com"

CASE_STUDIES_DIR = Path(__file__).resolve().parents[1] / "case_studies"

# (filename, accession, description)
GENOMES = [
    # ── Lambdoid / Siphoviridae ──────────────────────────────────────────
    ("HK97.gb",       "NC_002167", "Enterobacteria phage HK97 — lambdoid, headful packaging"),
    ("HK022.gb",      "NC_002166", "Enterobacteria phage HK022 — lambdoid, anti-termination"),
    ("P22_434.gb",    "NC_001417", "Enterobacteria phage 434 — lambdoid immunity"),
    ("phage_21.gb",   "NC_007533", "Enterobacteria phage 21 — lambdoid"),
    ("phage_P1.gb",   "NC_005856", "Enterobacteria phage P1 — large temperate, generalized transduction"),
    ("phage_P2.gb",   "NC_001895", "Enterobacteria phage P2 — temperate, satellite of P4"),
    ("phage_186.gb",  "NC_001317", "Enterobacteria phage 186 — temperate, CI/CII regulation"),

    # ── Podoviridae (short tails) ────────────────────────────────────────
    ("T3.gb",         "NC_003298", "Enterobacteria phage T3 — T7 family, RNA polymerase"),
    ("SP6.gb",        "NC_004602", "Salmonella phage SP6 — podoviridae, host-range determinant"),
    ("N4.gb",         "NC_008720", "Enterobacteria phage N4 — podovirus, unique virion-packaged RNAP"),
    ("gh-1.gb",       "NC_004665", "Pseudomonas phage gh-1 — podoviridae"),

    # ── Myoviridae (contractile tails) ──────────────────────────────────
    ("SP01.gb",       "NC_004168", "Bacillus phage SP01 — large myovirus, HMU DNA"),
    ("Felix01.gb",    "NC_005282", "Salmonella phage Felix O1 — broad host range myovirus"),
    ("phiEco32.gb",   "NC_010483", "Enterobacteria phage phiEco32 — jumbo myovirus"),

    # ── Bacillus phages ──────────────────────────────────────────────────
    ("SPP1.gb",       "NC_004166", "Bacillus phage SPP1 — siphovirus, DNA injection model"),
    ("phi105.gb",     "NC_004167", "Bacillus phage phi105 — temperate, integrase family"),

    # ── Staphylococcal phages ────────────────────────────────────────────
    ("80alpha.gb",    "NC_009526", "Staphylococcus phage 80alpha — pathogenicity island helper"),
    ("phiNM1.gb",     "NC_007044", "Staphylococcus phage phiNM1 — virulence conversion"),

    # ── Listeria phages ──────────────────────────────────────────────────
    ("A118.gb",       "NC_003313", "Listeria phage A118 — siphovirus, biocontrol candidate"),

    # ── Unusual / diverse ────────────────────────────────────────────────
    ("PRD1.gb",       "NC_001421", "Enterobacteria phage PRD1 — tectiviridae, inner membrane"),
    ("MS2.gb",        "NC_001417", "Enterobacteria phage MS2 — RNA phage, minimal genome"),
    ("G4.gb",         "NC_001420", "Enterobacteria phage G4 — microviridae, ssDNA"),
    ("crAssphage.gb", "NC_024711", "crAssphage — most abundant human gut phage"),
]

def download(filename: str, accession: str, description: str) -> bool:
    dest = CASE_STUDIES_DIR / filename
    if dest.exists():
        print(f"  skip  {filename} (already exists)")
        return True

    print(f"  fetch {filename}  [{accession}]  {description[:60]}")
    try:
        handle = Entrez.efetch(
            db="nucleotide",
            id=accession,
            rettype="gb",
            retmode="text",
        )
        data = handle.read()
        handle.close()

        if not data.strip() or "Error" in data[:200]:
            print(f"         ✗ empty or error response")
            return False

        dest.write_text(data)
        print(f"         ✓ saved ({len(data):,} bytes)")
        return True

    except Exception as e:
        print(f"         ✗ failed: {e}")
        return False


def main():
    CASE_STUDIES_DIR.mkdir(exist_ok=True)
    print(f"\n▶ Downloading {len(GENOMES)} genomes → {CASE_STUDIES_DIR}\n")

    ok = fail = skip = 0
    for filename, accession, description in GENOMES:
        dest = CASE_STUDIES_DIR / filename
        if dest.exists():
            skip += 1
            print(f"  skip  {filename}")
            continue

        success = download(filename, accession, description)
        if success:
            ok += 1
        else:
            fail += 1

        time.sleep(0.4)  # NCBI rate limit: max 3 req/s without API key

    print(f"\n▶ Done — {ok} downloaded · {skip} skipped · {fail} failed")
    if fail:
        print("  Failed genomes may have wrong accessions or be unavailable. Check NCBI manually.")


if __name__ == "__main__":
    main()
