"""
Run GIAE in true offline mode (no UniProt, no InterPro, no local BLAST,
no HMMER, no ESM) — matches what a fresh `pip install giae` user gets.
Produces HTML, Markdown, and JSON for one input GenBank.
"""
from __future__ import annotations

import sys
from pathlib import Path

from giae.engine.interpreter import Interpreter
from giae.output.json_export import export_interpretation_json
from giae.parsers.genbank import GenBankParser


def run(input_gb: Path, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    parser = GenBankParser()
    genome = parser.parse(input_gb)

    interpreter = Interpreter(
        use_uniprot=False,
        use_interpro=False,
        use_local_blast=False,
        use_hmmer=False,
        use_esm=False,
        use_cache=True,
    )

    summary = interpreter.interpret_genome(genome)
    summary.novel_gene_report = interpreter.novelty_scorer.analyze(genome, summary)

    # Markdown
    from giae.output.report import ReportGenerator
    md = ReportGenerator().generate(genome, summary)
    (output_dir / f"{stem}.md").write_text(md)

    # HTML
    from giae.output.html_report import HTMLReportGenerator
    html = HTMLReportGenerator().generate(genome, summary)
    (output_dir / f"{stem}.html").write_text(html)

    # JSON
    j = export_interpretation_json(summary)
    (output_dir / f"{stem}.json").write_text(j)

    print(
        f"DONE {stem}: {summary.interpreted_genes}/{summary.total_genes} "
        f"interpreted ({summary.success_rate:.1f}%)"
    )


if __name__ == "__main__":
    in_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    stem = sys.argv[3]
    run(in_path, out_dir, stem)
