"""GIAE 'brain' stress benchmark — full interpretation across many genomes.

Runs the full GIAE interpretation pipeline over every GenBank genome in
case_studies/ in one or more evidence modes (local / online), capturing
per-genome quality + performance metrics. Results are written incrementally
so the run is crash-safe and resumable.

Per (genome, mode) it records:
  total_genes, interpreted, success_rate, high/moderate/low conf, failed,
  dark_matter (= total - interpreted), processing_time_s, wall_time_s, status.

Run (background, both modes):
  .venv/bin/python post_assets/brain_benchmark.py --modes local,online -w 4

Resume after an interruption (skips finished rows):
  .venv/bin/python post_assets/brain_benchmark.py --resume

Outputs:
  post_assets/brain_benchmark_results.csv   — one row per (genome, mode)
  post_assets/brain_benchmark.md            — human-readable summary table
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASE_DIR = ROOT / "case_studies"
GIAE = ROOT / ".venv" / "bin" / "giae"
OUT_CSV = ROOT / "post_assets" / "brain_benchmark_results.csv"
OUT_MD = ROOT / "post_assets" / "brain_benchmark.md"

FIELDS = [
    "genome", "mode", "status", "total_genes", "interpreted", "success_rate",
    "high", "moderate", "low", "failed", "dark_matter",
    "processing_time_s", "wall_time_s", "error",
]


def load_done() -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    if OUT_CSV.exists():
        with OUT_CSV.open() as f:
            for row in csv.DictReader(f):
                if row.get("status") == "ok":
                    done.add((row["genome"], row["mode"]))
    return done


def append_row(row: dict) -> None:
    new = not OUT_CSV.exists()
    with OUT_CSV.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


def run_one(gb: Path, mode: str, workers: int, timeout: int) -> dict:
    row = {"genome": gb.stem, "mode": mode}
    out = Path(tempfile.gettempdir()) / f"giae_{gb.stem}_{mode}.json"
    cmd = [
        str(GIAE), "interpret", str(gb), "--mode", mode, "--phage",
        "-w", str(workers), "-f", "json", "-o", str(out), "--no-cache",
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        row.update(status="timeout", wall_time_s=round(time.time() - t0, 1),
                   error=f"exceeded {timeout}s")
        return row
    row["wall_time_s"] = round(time.time() - t0, 1)
    if proc.returncode != 0 or not out.exists():
        row.update(status="error",
                   error=(proc.stderr or proc.stdout or "no output")[-300:].replace("\n", " "))
        return row
    try:
        d = json.loads(out.read_text())
        s = d.get("statistics", {})
        total = s.get("total_genes", 0)
        interp = s.get("interpreted_genes", 0)
        row.update(
            status="ok",
            total_genes=total,
            interpreted=interp,
            success_rate=s.get("success_rate", ""),
            high=s.get("high_confidence", ""),
            moderate=s.get("moderate_confidence", ""),
            low=s.get("low_confidence", ""),
            failed=s.get("failed", ""),
            dark_matter=max(total - interp, 0),
            processing_time_s=round(d.get("processing_time_seconds", 0), 1),
        )
    except Exception as e:  # noqa: BLE001
        row.update(status="parse_error", error=str(e)[:300])
    return row


def write_markdown() -> None:
    if not OUT_CSV.exists():
        return
    rows = list(csv.DictReader(OUT_CSV.open()))
    lines = [
        "# GIAE Brain Benchmark", "",
        f"Full interpretation across `case_studies/` genomes. {len(rows)} runs.", "",
        "| Genome | Mode | Genes | Interp % | High | Mod | Low | Dark | Time (s) | Status |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['genome']} | {r['mode']} | {r.get('total_genes','')} | "
            f"{r.get('success_rate','')} | {r.get('high','')} | {r.get('moderate','')} | "
            f"{r.get('low','')} | {r.get('dark_matter','')} | "
            f"{r.get('processing_time_s','')} | {r.get('status','')} |"
        )
    ok = [r for r in rows if r.get("status") == "ok"]
    if ok:
        def fnum(r, k):
            try:
                return float(r.get(k) or 0)
            except ValueError:
                return 0.0
        tot_genes = sum(int(r.get("total_genes") or 0) for r in ok)
        tot_time = sum(fnum(r, "processing_time_s") for r in ok)
        avg_sr = sum(fnum(r, "success_rate") for r in ok) / len(ok)
        lines += [
            "", "## Totals (ok runs)", "",
            f"- Runs: {len(ok)} / {len(rows)}",
            f"- Genes interpreted across runs: {tot_genes}",
            f"- Mean interpretation rate: {avg_sr:.1f}%",
            f"- Total processing time: {tot_time/60:.1f} min",
        ]
    OUT_MD.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="local,online", help="comma-separated: local,online,offline")
    ap.add_argument("-w", "--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=5400, help="per-run timeout (s)")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    genomes = sorted(CASE_DIR.glob("*.gb"))
    if not genomes:
        print(f"No genomes in {CASE_DIR}", file=sys.stderr)
        return 1
    done = load_done() if args.resume else set()

    total = len(genomes) * len(modes)
    n = 0
    print(f"Benchmarking {len(genomes)} genomes × {len(modes)} modes "
          f"= {total} runs (workers={args.workers}, timeout={args.timeout}s)", flush=True)
    # mode as outer loop: finish all of one mode before the next, so a flaky
    # network mode never blocks getting a complete dataset for the other.
    for mode in modes:
        for gb in genomes:
            n += 1
            if (gb.stem, mode) in done:
                print(f"[{n}/{total}] skip {gb.stem} ({mode}) — already done", flush=True)
                continue
            print(f"[{n}/{total}] {gb.stem} ({mode}) …", flush=True)
            row = run_one(gb, mode, args.workers, args.timeout)
            append_row(row)
            write_markdown()
            print(f"    -> {row['status']} "
                  f"genes={row.get('total_genes','?')} "
                  f"interp%={row.get('success_rate','?')} "
                  f"dark={row.get('dark_matter','?')} "
                  f"giae_time={row.get('processing_time_s','?')}s "
                  f"wall={row.get('wall_time_s','?')}s", flush=True)
    print("DONE. Results: post_assets/brain_benchmark_results.csv + brain_benchmark.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
