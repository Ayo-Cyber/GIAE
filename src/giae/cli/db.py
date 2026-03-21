"""
Database management commands for GIAE.

Handles downloading and formatting of local databases for plugins.
"""

import logging
import shutil
import subprocess
import urllib.request
from pathlib import Path

import click

logger = logging.getLogger(__name__)


@click.group(name="db")
def db_cli() -> None:
    """Manage local databases for GIAE plugins."""
    pass


@db_cli.command(name="download")
@click.argument("name", type=click.Choice(["swissprot", "pfam", "esm", "prosite"]))
@click.option("--force", is_flag=True, help="Force re-download")
def download_db(name: str, force: bool) -> None:
    """Download and prepare local databases."""
    base_dir = Path.home() / ".giae"
    base_dir.mkdir(parents=True, exist_ok=True)

    if name == "swissprot":
        _setup_blast_db(base_dir / "blast", force)
    elif name == "pfam":
        _setup_hmmer_db(base_dir / "hmmer", force)
    elif name == "esm":
        _setup_esm_model(base_dir / "ai", force)
    elif name == "prosite":
        _setup_prosite_db(base_dir / "prosite", force)


def _setup_blast_db(path: Path, force: bool) -> None:
    """Setup BLAST database."""
    path.mkdir(parents=True, exist_ok=True)
    db_name = "swissprot"
    target = path / db_name

    if (target.parent / (db_name + ".pin")).exists() and not force:
        click.echo(f"BLAST database usage: {target}")
        click.echo("Already installed. Use --force to reinstall.")
        return

    click.echo("Downloading E. coli Reference Proteome from UniProt...")

    if not shutil.which("makeblastdb"):
        click.echo("Error: 'makeblastdb' not found. Please install NCBI BLAST+.")
        return

    # Download a real subset: E. coli K12 reference proteome from UniProt
    url = (
        "https://rest.uniprot.org/uniprotkb/stream?format=fasta&query=%28proteome%3AUP000000625%29"
    )
    fasta_path = path / "swissprot.fasta"

    try:
        urllib.request.urlretrieve(url, fasta_path)
        click.echo(f"Downloaded {fasta_path.stat().st_size / 1024 / 1024:.1f} MB of sequences.")

        click.echo("Running makeblastdb...")
        subprocess.run(
            [
                "makeblastdb",
                "-in",
                str(fasta_path),
                "-dbtype",
                "prot",
                "-out",
                str(target),
                "-title",
                "SwissProt (E. coli ref)",
            ],
            check=True,
            capture_output=True,
        )
        click.echo(f"Database created at: {target}")
    except Exception as e:
        click.echo(f"Failed to create DB: {e}")
    finally:
        if fasta_path.exists():
            fasta_path.unlink()


def _setup_hmmer_db(path: Path, force: bool) -> None:
    """Setup HMMER database."""
    path.mkdir(parents=True, exist_ok=True)
    db_name = "pfam.hmm"
    target = path / db_name

    if target.exists() and not force:
        click.echo(f"HMM database usage: {target}")
        click.echo("Already installed. Use --force to reinstall.")
        return

    click.echo("Setting up Pfam HMM database...")
    if not shutil.which("hmmpress"):
        click.echo("Error: 'hmmpress' not found. Please install HMMER3.")
        return

    # Similar placeholder logic
    click.echo("HMMER database setup requires 'Pfam-A.hmm'. Please download manually for now.")
    click.echo(f"Place 'Pfam-A.hmm' at: {target}")
    # We can't easily fake an HMM file without running hmmbuild on a sequence.


def _setup_esm_model(path: Path, _force: bool) -> None:
    """Setup ESM-2 model."""
    path.mkdir(parents=True, exist_ok=True)
    click.echo("ESM-2 models are handled automatically by 'fair-esm' cache.")
    click.echo("This command is a placeholder for pre-downloading models.")


def _setup_prosite_db(path: Path, force: bool) -> None:
    """Download PROSITE pattern database from ExPASy."""
    path.mkdir(parents=True, exist_ok=True)
    target = path / "prosite.dat"

    if target.exists() and not force:
        click.echo(f"PROSITE database: {target}")
        click.echo("Already installed. Use --force to reinstall.")
        return

    url = "https://ftp.expasy.org/databases/prosite/prosite.dat"
    click.echo(f"Downloading PROSITE patterns from {url}...")

    try:
        urllib.request.urlretrieve(url, str(target))
        click.echo(f"Downloaded PROSITE database to: {target}")

        # Verify the file
        from giae.analysis.prosite import parse_prosite_file

        count = sum(1 for _ in parse_prosite_file(target))
        click.echo(f"Verified: {count} patterns available.")
    except Exception as e:
        click.echo(f"Download failed: {e}")
        if target.exists():
            target.unlink()


@db_cli.command(name="status")
def db_status() -> None:
    """Show status of local databases."""
    base_dir = Path.home() / ".giae"

    databases = [
        ("PROSITE", base_dir / "prosite" / "prosite.dat"),
        ("BLAST (SwissProt)", base_dir / "blast" / "swissprot.pin"),
        ("HMMER (Pfam)", base_dir / "hmmer" / "pfam.hmm"),
    ]

    # Also check bundled PROSITE
    bundled = Path(__file__).parent.parent / "data" / "prosite" / "prosite.dat"

    click.echo("Database Status:\n")
    for name, path in databases:
        status = "✅ Installed" if path.exists() else "❌ Not found"
        click.echo(f"  {name}: {status}")
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            click.echo(f"    Path: {path} ({size_mb:.1f} MB)")

    if bundled.exists():
        size_mb = bundled.stat().st_size / (1024 * 1024)
        click.echo(f"\n  PROSITE (bundled): ✅ Available ({size_mb:.1f} MB)")

    # Check external tools
    click.echo("\nExternal Tools:\n")
    blast_available = shutil.which("blastp") is not None
    hmmer_available = shutil.which("hmmscan") is not None
    click.echo(f"  BLAST+: {'✅ Found' if blast_available else '❌ Not installed'}")
    click.echo(f"  HMMER3: {'✅ Found' if hmmer_available else '❌ Not installed'}")
