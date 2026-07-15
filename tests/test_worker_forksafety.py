"""Fork-safety & lifecycle tests for the Celery worker interpreters.

The interpreters must be built lazily inside the worker process, never at
module import in the Celery parent — otherwise fork-unsafe C extensions
(pyhmmer, torch) are inherited across the prefork fork and crash. These tests
lock in the lazy-per-process contract and the env-var plugin toggles.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def worker(monkeypatch):
    # Ensure a clean flag environment and a fresh per-process cache each test.
    for var in ("GIAE_ENABLE_DIAMOND", "GIAE_ENABLE_HMMER", "GIAE_ENABLE_ESM",
                "GIAE_ENABLE_UNIPROT", "GIAE_ENABLE_BLAST"):
        monkeypatch.delenv(var, raising=False)
    from giae_api import worker as w
    importlib.reload(w)
    return w


def test_no_module_level_interpreters(worker):
    """Interpreters must NOT be constructed at import (that runs pre-fork)."""
    assert not hasattr(worker, "_default_interpreter")
    assert not hasattr(worker, "_phage_interpreter")
    assert worker._interpreters == {}  # cache empty until first use


def test_lazy_build_and_cache(worker):
    a = worker.get_interpreter(False)
    b = worker.get_interpreter(False)
    assert a is b                       # cached per process
    assert worker._interpreters         # now populated
    phage = worker.get_interpreter(True)
    assert phage is not a
    assert phage.phage_mode is True
    assert a.phage_mode is False


def test_flag_parsing(worker, monkeypatch):
    assert worker._flag("GIAE_ENABLE_HMMER", False) is False
    assert worker._flag("GIAE_ENABLE_DIAMOND", True) is True
    for truthy in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("GIAE_ENABLE_HMMER", truthy)
        assert worker._flag("GIAE_ENABLE_HMMER", False) is True
    for falsy in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("GIAE_ENABLE_HMMER", falsy)
        assert worker._flag("GIAE_ENABLE_HMMER", True) is False


def test_env_toggles_reach_interpreter(worker, monkeypatch):
    monkeypatch.setenv("GIAE_ENABLE_DIAMOND", "false")
    interp = worker._build_interpreter(False)
    assert interp.use_diamond is False


def test_warm_signal_populates_cache(worker):
    """worker_process_init handler builds the default interpreter (post-fork)."""
    worker._interpreters.clear()
    worker._warm_interpreter()
    assert False in worker._interpreters
