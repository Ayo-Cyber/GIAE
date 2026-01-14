"""Main CLI for GIAE.

Provides command-line interface for genome interpretation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from giae import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="giae")
def cli() -> None:
    """GIAE - Genome Interpretation & Annotation Engine.

    An explainable, evidence-centric framework for genomic interpretation.
    """
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "-f", "output_format", default="summary",
              type=click.Choice(["summary", "json", "detailed"]),
              help="Output format")
def parse(input_file: Path, output_format: str) -> None:
    """Parse a genome file and show basic information.

    Supports FASTA and GenBank formats.
    """
    from giae.parsers import parse_genome, ParserError

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
        raise SystemExit(1)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path),
              help="Output file path")
@click.option("--format", "-f", "output_format", default="report",
              type=click.Choice(["report", "json"]),
              help="Output format")
def interpret(input_file: Path, output: Optional[Path], output_format: str) -> None:
    """Interpret a genome and generate functional predictions.

    This is the main command that runs the full interpretation pipeline.
    """
    from giae.parsers import parse_genome, ParserError
    from giae.engine.interpreter import Interpreter

    try:
        # Parse genome
        with console.status("[bold green]Parsing genome file..."):
            genome = parse_genome(input_file)

        console.print(f"[green]Loaded genome:[/green] {genome.name}")
        console.print(f"  Length: {genome.length:,} bp | GC: {genome.gc_content}%")
        console.print(f"  Genes: {genome.gene_count}")
        console.print()

        # Run interpretation
        interpreter = Interpreter()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Interpreting genome...", total=None)
            summary = interpreter.interpret_genome(genome)
            progress.update(task, completed=True)

        # Output results
        if output_format == "json":
            from giae.output.json_export import export_interpretation_json
            json_output = export_interpretation_json(summary)
            if output:
                output.write_text(json_output)
                console.print(f"[green]Results written to:[/green] {output}")
            else:
                click.echo(json_output)
        else:
            from giae.output.report import ReportGenerator
            generator = ReportGenerator()
            report = generator.generate(genome, summary)

            if output:
                output.write_text(report)
                console.print(f"[green]Report written to:[/green] {output}")
            else:
                console.print(report)

        # Print summary
        _print_interpretation_summary(summary)

    except ParserError as e:
        console.print(f"[red]Error parsing file:[/red] {e}")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error during interpretation:[/red] {e}")
        raise SystemExit(1)


@cli.command()
@click.argument("sequence", type=str)
@click.option("--type", "-t", "seq_type", default="protein",
              type=click.Choice(["protein", "nucleotide"]),
              help="Sequence type")
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
    from giae.parsers import parse_genome
    from giae.analysis.motif import MotifScanner

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
  - Generate functional hypotheses
  - Produce explainable interpretations

[bold]Supported Analysis:[/bold]
  - ORF prediction (6-frame translation)
  - Motif/domain scanning (9 builtin patterns)
  - BLAST homology search (requires local BLAST+)
  - Confidence scoring with uncertainty tracking

[bold]Output Formats:[/bold]
  - Human-readable reports (Markdown)
  - Machine-readable JSON
  - Summary tables

[bold]Example Usage:[/bold]
  giae parse genome.fasta
  giae interpret genome.gb -o report.md
  giae quick MKVLIAGKSTFAM -t protein
"""
    console.print(Panel(info_text, title="About GIAE"))


def _print_genome_summary(genome) -> None:
    """Print a brief genome summary."""
    console.print(Panel(f"""
[bold]{genome.name}[/bold]
{genome.description or 'No description'}

Length: {genome.length:,} bp
GC Content: {genome.gc_content}%
Genes: {genome.gene_count}
Source: {genome.source_file.name}
Format: {genome.file_format}
""", title="Genome Summary"))


def _print_genome_detailed(genome) -> None:
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


def _print_interpretation_summary(summary) -> None:
    """Print interpretation summary statistics."""
    console.print()
    console.print(Panel(f"""
[bold]Interpretation Complete[/bold]

Total Genes: {summary.total_genes}
Interpreted: {summary.interpreted_genes} ({summary.success_rate:.1f}%)

Confidence Breakdown:
  High:     {summary.high_confidence_count}
  Moderate: {summary.moderate_confidence_count}
  Low:      {summary.low_confidence_count}
  Failed:   {summary.failed_genes}

Processing Time: {summary.processing_time_seconds:.2f}s
""", title="Summary", border_style="green"))


if __name__ == "__main__":
    cli()
