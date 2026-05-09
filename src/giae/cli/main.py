"""Main CLI for GIAE.

Provides command-line interface for genome interpretation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from giae.engine.interpreter import GenomeInterpretationSummary, InterpretationResult
    from giae.models.genome import Genome

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from giae import __version__
from giae.cli.db import db_cli
from giae.cli.serve import serve_command, worker_command

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="giae")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, debug: bool) -> None:
    """GIAE - Genome Interpretation & Annotation Engine.

    An explainable, evidence-centric framework for genomic interpretation.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug

    # Configure logging
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    elif verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
        )


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "-f",
    "output_format",
    default="summary",
    type=click.Choice(["summary", "json", "detailed"]),
    help="Output format",
)
def parse(input_file: Path, output_format: str) -> None:
    """Parse a genome file and show basic information.

    Supports FASTA and GenBank formats.
    """
    from giae.parsers import ParserError, parse_genome

    try:
        with console.status("[bold green]Parsing genome file..."):
            genome = parse_genome(input_file)

        if output_format == "json":
            from giae.output.json_export import export_genome_json

            click.echo(export_genome_json(genome, include_sequence=False))
        elif output_format == "detailed":
            _print_genome_detailed(genome)
        else:
            _print_genome_summary(genome)

    except ParserError as e:
        console.print(f"[red]Error parsing file:[/red] {e}")
        raise SystemExit(1) from None


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.option(
    "--format",
    "-f",
    "output_format",
    default="html",
    type=click.Choice(["html", "report", "json"]),
    help="Output format",
)
@click.option(
    "--workers",
    "-w",
    default=1,
    type=click.IntRange(1, 16),
    help="Number of parallel workers (default: 1)",
)
@click.option(
    "--mode",
    default="online",
    type=click.Choice(["online", "local", "offline"]),
    show_default=True,
    help=(
        "Evidence mode: 'online' enables UniProt + InterPro APIs; "
        "'local' uses local BLAST/HMMER only (no network); "
        "'offline' uses bundled GenBank annotations + PROSITE only."
    ),
)
@click.option("--no-uniprot", is_flag=True, hidden=True, help="Deprecated — use --mode offline")
@click.option("--no-interpro", is_flag=True, hidden=True, help="Deprecated — use --mode offline")
@click.option("--no-cache", is_flag=True, help="Disable disk caching of API responses")
@click.option(
    "--phage",
    "phage_mode",
    is_flag=True,
    help="Enable phage-aware nested ORF detection (recovers overlapping genes)",
)
@click.pass_context
def interpret(
    ctx: click.Context,
    input_file: Path,
    output: Path | None,
    output_format: str,
    workers: int,
    mode: str,
    no_uniprot: bool,
    no_interpro: bool,
    no_cache: bool,
    phage_mode: bool,
) -> None:
    """Interpret a genome and generate functional predictions.

    This is the main command that runs the full interpretation pipeline.
    """
    from giae.engine.interpreter import GenomeInterpretationSummary, Interpreter
    from giae.models.interpretation import ConfidenceLevel
    from giae.parsers import ParserError, parse_genome

    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        # Parse genome
        with console.status("[bold green]Parsing genome file..."):
            genome = parse_genome(input_file)

        console.print(f"[green]Loaded genome:[/green] {genome.name}")
        console.print(f"  Length: {genome.length:,} bp | GC: {genome.gc_content}%")
        console.print(f"  Genes: {genome.gene_count}")
        console.print()

        # Warn if deprecated flags are used alongside --mode
        if no_uniprot or no_interpro:
            console.print(
                "[yellow]Warning: --no-uniprot / --no-interpro are deprecated. "
                "Use --mode offline instead.[/yellow]"
            )

        # Map --mode to plugin flags.  Deprecated --no-* flags override as before.
        use_uniprot = (mode == "online") and not no_uniprot
        use_interpro = (mode == "online") and not no_interpro
        use_local_blast = mode in ("online", "local")
        use_hmmer = mode in ("online", "local")

        # Run interpretation
        interpreter = Interpreter(
            use_uniprot=use_uniprot,
            use_interpro=use_interpro,
            use_local_blast=use_local_blast,
            use_hmmer=use_hmmer,
            use_cache=not no_cache,
            phage_mode=phage_mode,
        )

        if verbose:
            console.print(f"  [dim]Mode: {mode}[/dim]")
            motif_count = len(interpreter.motif_scanner.motifs)
            plugins = interpreter.plugin_manager.active_plugins
            console.print(f"  [dim]Motif patterns: {motif_count}[/dim]")
            if plugins:
                console.print(f"  [dim]Active plugins: {', '.join(plugins)}[/dim]")
            console.print()

        # Pre-populate ORF predictions so the progress bar has a gene count.
        # Uses the same density trigger as interpreter.interpret_genome() — when
        # genome.genes is already populated here, interpret_genome will not re-run
        # ORF finding (density will be above the 0.3 g/kb threshold).
        if interpreter.find_orfs:
            genome_length_kb = len(genome.sequence) / 1000.0
            gene_density = len(genome.genes) / genome_length_kb if genome_length_kb > 0 else 0
            needs_orfs = not genome.genes or (genome_length_kb >= 5.0 and gene_density < 0.3)
            if needs_orfs:
                with console.status("[bold green]Predicting ORFs..."):
                    orfs = interpreter.orf_finder.find_orfs(genome.sequence)
                    orf_genes = interpreter.orf_finder.orfs_to_genes(orfs)
                    if genome.genes:
                        existing_spans = [
                            (g.location.start, g.location.end) for g in genome.genes
                        ]
                        orf_genes = [
                            g for g in orf_genes
                            if not any(
                                g.location.start < e_end and g.location.end > e_start
                                for e_start, e_end in existing_spans
                            )
                        ]
                    for gene in orf_genes:
                        genome.add_gene(gene)
                console.print(f"  ORF prediction: {len(genome.genes)} genes")
                console.print()

        # Use per-gene progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[cyan]{task.fields[gene_name]}[/cyan]"),
            console=console,
        ) as progress:

            task = progress.add_task(
                "Interpreting genes...",
                total=genome.gene_count,
                gene_name="",
            )

            if workers > 1 and genome.gene_count > 1:
                # Parallel interpretation
                from concurrent.futures import ThreadPoolExecutor, as_completed

                parallel_results = []
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {
                        executor.submit(interpreter.interpret_gene, gene): gene
                        for gene in genome.genes
                    }
                    for future in as_completed(futures):
                        gene = futures[future]
                        result = future.result()
                        parallel_results.append((gene, result))
                        progress.update(
                            task,
                            advance=1,
                            gene_name=gene.display_name or gene.id,
                        )

                # Attach interpretations in order
                start_time = datetime.now(timezone.utc)
                for gene, result in parallel_results:
                    if result.interpretation:
                        gene.add_interpretation(result.interpretation)

                all_results = [r for _, r in parallel_results]

                high_conf = sum(
                    1
                    for r in all_results
                    if r.interpretation
                    and r.interpretation.confidence_level == ConfidenceLevel.HIGH
                )
                mod_conf = sum(
                    1
                    for r in all_results
                    if r.interpretation
                    and r.interpretation.confidence_level == ConfidenceLevel.MODERATE
                )
                low_conf = sum(
                    1
                    for r in all_results
                    if r.interpretation
                    and r.interpretation.confidence_level
                    in (ConfidenceLevel.LOW, ConfidenceLevel.SPECULATIVE)
                )
                summary = GenomeInterpretationSummary(
                    genome_id=genome.id,
                    genome_name=genome.name,
                    total_genes=len(genome.genes),
                    interpreted_genes=sum(1 for r in all_results if r.interpretation),
                    high_confidence_count=high_conf,
                    moderate_confidence_count=mod_conf,
                    low_confidence_count=low_conf,
                    failed_genes=sum(1 for r in all_results if not r.success),
                    processing_time_seconds=0.0,
                    results=all_results,
                )
            else:
                # Sequential interpretation with progress updates
                start_time = datetime.now(timezone.utc)
                sequential_results: list[InterpretationResult] = []
                for gene in genome.genes:
                    progress.update(
                        task,
                        gene_name=gene.display_name or gene.id,
                    )
                    result = interpreter.interpret_gene(gene)
                    sequential_results.append(result)
                    if result.interpretation:
                        gene.add_interpretation(result.interpretation)
                    progress.advance(task)

                end_time = datetime.now(timezone.utc)
                processing_time = (end_time - start_time).total_seconds()

                high_conf = sum(
                    1
                    for r in sequential_results
                    if r.interpretation
                    and r.interpretation.confidence_level == ConfidenceLevel.HIGH
                )
                mod_conf = sum(
                    1
                    for r in sequential_results
                    if r.interpretation
                    and r.interpretation.confidence_level == ConfidenceLevel.MODERATE
                )
                low_conf = sum(
                    1
                    for r in sequential_results
                    if r.interpretation
                    and r.interpretation.confidence_level
                    in (ConfidenceLevel.LOW, ConfidenceLevel.SPECULATIVE)
                )

                summary = GenomeInterpretationSummary(
                    genome_id=genome.id,
                    genome_name=genome.name,
                    total_genes=len(genome.genes),
                    interpreted_genes=sum(1 for r in sequential_results if r.interpretation),
                    high_confidence_count=high_conf,
                    moderate_confidence_count=mod_conf,
                    low_confidence_count=low_conf,
                    failed_genes=sum(1 for r in sequential_results if not r.success),
                    processing_time_seconds=processing_time,
                    results=sequential_results,
                )

        # Wire in novel gene discovery (novelty scorer needs the full summary)
        summary.novel_gene_report = interpreter.novelty_scorer.analyze(genome, summary)

        # Warn about skipped evidence layers
        skipped_counts: dict[str, int] = {}
        for r in summary.results:
            for layer in r.skipped_layers:
                skipped_counts[layer] = skipped_counts.get(layer, 0) + 1
        for layer, count in skipped_counts.items():
            console.print(
                f"[yellow]Warning: {layer} layer failed for {count}/{len(summary.results)} "
                f"genes (network error or timeout)[/yellow]"
            )

        # Output results
        if output_format == "json":
            from giae.output.json_export import export_interpretation_json

            json_output = export_interpretation_json(summary)
            if output:
                output.write_text(json_output)
                console.print(f"[green]Results written to:[/green] {output}")
            else:
                click.echo(json_output)
        elif output_format == "html":
            from giae.output.html_report import HTMLReportGenerator

            generator = HTMLReportGenerator()
            html_output = generator.generate(genome, summary)
            if output:
                output.write_text(html_output)
                console.print(f"[green]HTML report written to:[/green] {output}")
                import webbrowser

                webbrowser.open(output.resolve().as_uri())
            else:
                click.echo(html_output)
        else:
            from giae.output.report import ReportGenerator

            text_generator = ReportGenerator()
            report = text_generator.generate(genome, summary)

            if output:
                output.write_text(report)
                console.print(f"[green]Report written to:[/green] {output}")
            else:
                console.print(report)

        # Print summary
        _print_interpretation_summary(summary)

    except ParserError as e:
        console.print(f"[red]Error parsing file:[/red] {e}")
        raise SystemExit(1) from None
    except Exception as e:
        console.print(f"[red]Error during interpretation:[/red] {e}")
        raise SystemExit(1) from None


@cli.command()
@click.argument("sequence", type=str)
@click.option(
    "--type",
    "-t",
    "seq_type",
    default="protein",
    type=click.Choice(["protein", "nucleotide"]),
    help="Sequence type",
)
def quick(sequence: str, seq_type: str) -> None:
    """Quick interpretation of a raw sequence.

    Useful for quickly checking a single sequence.
    """
    from giae.engine.interpreter import Interpreter

    interpreter = Interpreter()
    result = interpreter.quick_interpret(sequence, sequence_type=seq_type)

    console.print(Panel(result, title="Interpretation"))


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
def analyze(input_file: Path) -> None:
    """Analyze a genome without full interpretation.

    Shows evidence extraction results without hypothesis generation.
    """
    from giae.analysis.motif import MotifScanner
    from giae.parsers import parse_genome

    genome = parse_genome(input_file)
    scanner = MotifScanner()

    console.print(f"[bold]Analyzing:[/bold] {genome.name}")
    console.print(f"Genes: {genome.gene_count}")
    console.print()

    table = Table(title="Motif Analysis")
    table.add_column("Gene", style="cyan")
    table.add_column("Motifs Found", style="green")
    table.add_column("Top Motif", style="yellow")

    for gene in genome.genes[:20]:  # Limit output
        matches = scanner.scan(gene.protein.sequence if gene.protein else gene.sequence)
        if matches:
            top_motif = matches[0].motif_name
            table.add_row(gene.display_name, str(len(matches)), top_motif)
        else:
            table.add_row(gene.display_name, "0", "-")

    console.print(table)

    if genome.gene_count > 20:
        console.print(f"\n[dim]Showing first 20 of {genome.gene_count} genes[/dim]")


@cli.command()
def info() -> None:
    """Show information about GIAE and its capabilities."""
    info_text = f"""
[bold cyan]GIAE - Genome Interpretation & Annotation Engine[/bold cyan]
Version: {__version__}

[bold]Capabilities:[/bold]
  - Parse FASTA and GenBank genome files
  - Detect Open Reading Frames (ORFs)
  - Scan for functional motifs and domains
  - PROSITE pattern database (1,800+ patterns, bundled)
  - Generate functional hypotheses with confidence scoring
  - Produce explainable, evidence-backed interpretations
  - Parallel gene interpretation (--workers flag)

[bold]Supported Analysis:[/bold]
  - ORF prediction (6-frame translation)
  - Motif/domain scanning (PROSITE + 9 builtin patterns)
  - BLAST homology search (requires local BLAST+)
  - HMMER domain search (requires pyhmmer)
  - UniProt API search (online, optional)
  - Confidence scoring with uncertainty tracking

[bold]Output Formats:[/bold]
  - Human-readable reports (Markdown)
  - Machine-readable JSON
  - Summary tables

[bold]Example Usage:[/bold]
  giae parse genome.fasta
  giae interpret genome.gb -o report.md
  giae interpret genome.gb -w 4 --no-uniprot
  giae quick MKVLIAGKSTFAM -t protein
  giae db status
  giae -v interpret genome.gb
"""
    console.print(Panel(info_text, title="About GIAE"))


def _print_genome_summary(genome: Genome) -> None:
    """Print a brief genome summary."""
    console.print(
        Panel(
            f"""
[bold]{genome.name}[/bold]
{genome.description or "No description"}

Length: {genome.length:,} bp
GC Content: {genome.gc_content}%
Genes: {genome.gene_count}
Source: {genome.source_file.name}
Format: {genome.file_format}
""",
            title="Genome Summary",
        )
    )


def _print_genome_detailed(genome: Genome) -> None:
    """Print detailed genome information."""
    _print_genome_summary(genome)

    if genome.genes:
        table = Table(title="Gene Annotations")
        table.add_column("Locus Tag", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Start", justify="right")
        table.add_column("End", justify="right")
        table.add_column("Strand")
        table.add_column("Product")

        for gene in genome.genes[:50]:
            product = ""
            if gene.protein and gene.protein.product_name:
                product = gene.protein.product_name[:40]

            table.add_row(
                gene.locus_tag or "-",
                gene.name or "-",
                str(gene.location.start),
                str(gene.location.end),
                "+" if gene.strand.value == 1 else "-",
                product,
            )

        console.print(table)


def _print_interpretation_summary(summary: GenomeInterpretationSummary) -> None:
    """Print interpretation summary statistics."""
    novel = summary.novel_gene_report

    novel_lines = ""
    if novel and novel.has_novel_genes:
        novel_lines = f"""
Novel Gene Discovery:
  Dark Matter:  {novel.dark_matter_count} (no evidence)
  Weak Signal:  {novel.weak_evidence_count}
  Conflicting:  {novel.conflict_count}"""
        if novel.candidates:
            top = novel.candidates[0]
            novel_lines += f"\n  Top Target:   {top.display_name} ({top.priority_label})"

    console.print()
    console.print(
        Panel(
            f"""
[bold]Interpretation Complete[/bold]

Total Genes: {summary.total_genes}
Interpreted: {summary.interpreted_genes} ({summary.success_rate:.1f}%)

Confidence Breakdown:
  High:     {summary.high_confidence_count}
  Moderate: {summary.moderate_confidence_count}
  Low:      {summary.low_confidence_count}
  Failed:   {summary.failed_genes}{novel_lines}

Processing Time: {summary.processing_time_seconds:.2f}s
""",
            title="Summary",
            border_style="green",
        )
    )


cli.add_command(db_cli)
cli.add_command(serve_command)
cli.add_command(worker_command)

if __name__ == "__main__":
    cli()
