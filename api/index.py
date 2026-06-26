"""Vercel ASGI entry point for GIAE FastAPI backend."""
import sys
import os
from pathlib import Path

# Make src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Vercel filesystem is read-only — redirect writes to /tmp
os.environ.setdefault("VERCEL", "1")

from giae_api.main import app  # noqa: E402  (import after path setup)

# Vercel expects the ASGI app to be named `app`
__all__ = ["app"]
