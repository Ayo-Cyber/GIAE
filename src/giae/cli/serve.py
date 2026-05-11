"""CLI subcommands for running the API server and Celery worker.

Both commands are thin wrappers — they shell out to ``uvicorn`` and
``celery`` so users get the same behaviour as production Docker, just
locally with a single command.

Usage:
    giae serve                       # API on localhost:8000
    giae serve --host 0.0.0.0 -p 80
    giae worker                      # Celery worker, threads pool
    giae worker --concurrency 8
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import click


@click.command(name="serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host")
@click.option("--port", "-p", default=8000, show_default=True, type=int, help="Bind port")
@click.option("--reload", is_flag=True, help="Auto-reload on code change (dev only)")
@click.option(
    "--workers",
    default=1,
    show_default=True,
    type=int,
    help="Number of uvicorn worker processes (ignored when --reload is set)",
)
def serve_command(host: str, port: int, reload: bool, workers: int) -> None:
    """Run the GIAE API server.

    Requires the [api] optional dependencies. Set DATABASE_URL and JWT_SECRET
    via environment variables before running in production.
    """
    if shutil.which("uvicorn") is None:
        click.echo(
            "Error: uvicorn not installed. Install API extras with:\n"
            "  pip install 'giae[api]'",
            err=True,
        )
        sys.exit(1)

    cmd = [
        "uvicorn",
        "giae_api.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")
    elif workers > 1:
        cmd.extend(["--workers", str(workers)])

    click.echo(f"Starting GIAE API at http://{host}:{port}")
    if "JWT_SECRET" not in os.environ and os.getenv("ENV", "dev").lower() not in {"prod", "production"}:
        click.echo("  (using dev JWT secret — set JWT_SECRET for production)")
    sys.exit(subprocess.call(cmd))


@click.command(name="worker")
@click.option(
    "--concurrency",
    "-c",
    default=4,
    show_default=True,
    type=int,
    help="Number of concurrent worker threads",
)
@click.option(
    "--pool",
    default="threads",
    show_default=True,
    type=click.Choice(["threads", "prefork", "solo"]),
    help="Celery executor pool. 'threads' is required when use_hmmer/use_esm are on",
)
@click.option(
    "--loglevel",
    default="info",
    show_default=True,
    type=click.Choice(["debug", "info", "warning", "error"]),
)
def worker_command(concurrency: int, pool: str, loglevel: str) -> None:
    """Run a Celery worker that processes interpretation jobs.

    Requires Redis to be reachable at REDIS_URL (default localhost:6379).
    """
    if shutil.which("celery") is None:
        click.echo(
            "Error: celery not installed. Install API extras with:\n"
            "  pip install 'giae[api]'",
            err=True,
        )
        sys.exit(1)

    cmd = [
        "celery",
        "-A", "giae_api.worker.celery_app",
        "worker",
        "--loglevel", loglevel,
        "--pool", pool,
        "--concurrency", str(concurrency),
    ]
    click.echo(f"Starting GIAE worker (pool={pool}, concurrency={concurrency})")
    sys.exit(subprocess.call(cmd))
