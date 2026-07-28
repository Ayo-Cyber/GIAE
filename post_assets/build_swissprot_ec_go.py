"""Build a compact Swiss-Prot accession -> {EC, GO} map for homology enrichment.

Reads the Swiss-Prot flat file (uniprot_sprot.dat) from STDIN, streaming, and
writes a gzipped TSV: `accession<TAB>ec1,ec2<TAB>GO:xxx|GO:yyy`. Only entries
carrying an EC number or at least one GO term are emitted (keeps the map small).

The Diamond plugin loads this at runtime to attach real, synonym-invariant
GO/EC IDs to homology hits — the fix for the low functional-ID coverage gap.

  curl -s <sprot.dat.gz> | gunzip -c | \
    PYTHONPATH=src .venv/bin/python post_assets/build_swissprot_ec_go.py \
      data/functional/swissprot_ec_go.tsv.gz
"""
from __future__ import annotations

import gzip
import re
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/functional/swissprot_ec_go.tsv.gz")
OUT.parent.mkdir(parents=True, exist_ok=True)

_EC = re.compile(r"EC=([0-9]+\.[0-9]+\.[0-9]+\.[0-9nN-]+)")

acc = None          # primary accession for the current entry
ecs: list[str] = []
gos: list[str] = []
n_in = n_out = 0

with gzip.open(OUT, "wt") as out:
    for line in sys.stdin:
        tag = line[:2]
        if tag == "AC":
            if acc is None:  # first AC line -> primary accession
                acc = line[5:].split(";")[0].strip()
        elif tag == "DE":
            for m in _EC.finditer(line):
                ec = m.group(1)
                if ec not in ecs:
                    ecs.append(ec)
        elif tag == "DR" and line[5:8] == "GO;":
            # DR   GO; GO:0003677; F:DNA binding; ...
            go = line[5:].split(";")[1].strip()
            if go.startswith("GO:") and go not in gos:
                gos.append(go)
        elif line.startswith("//"):
            n_in += 1
            if acc and (ecs or gos):
                out.write(f"{acc}\t{','.join(ecs)}\t{'|'.join(gos)}\n")
                n_out += 1
            acc, ecs, gos = None, [], []
            if n_in % 100000 == 0:
                print(f"  parsed {n_in} entries, {n_out} with EC/GO", file=sys.stderr, flush=True)

print(f"done: {n_in} entries parsed, {n_out} written -> {OUT}", file=sys.stderr)
