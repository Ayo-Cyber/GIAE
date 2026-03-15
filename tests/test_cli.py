"""Tests for GIAE CLI."""

import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from giae.cli.main import cli

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def test_version_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "giae" in result.output.lower()

def test_help_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.output.lower()

# Avoid invoking the full analyze command directly in quick tests as it pulls in everything,
# but we can test that passing a missing file immediately fails cleanly.
def test_analyze_missing_file():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "missing_file_xyz.gb"])
    assert result.exit_code != 0
    assert "missing_file_xyz" in result.output or "No such file or directory" in result.output
