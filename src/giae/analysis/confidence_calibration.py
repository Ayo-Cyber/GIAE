"""Post-hoc confidence calibration for functional interpretations.

The interpreter's raw confidence score (driven by homology percent-identity and
evidence agreement) is over-confident: on the 35-genome homology benchmark the
mean raw confidence was 0.83 while the observed accuracy was 0.54. This module
maps the raw score to a calibrated probability of correctness, using a mapping
fit offline (isotonic regression, 5-fold cross-validated) and shipped as a
small JSON of piecewise-linear knots — see post_assets/recalibrate.py.

At runtime this does a pure-Python piecewise-linear interpolation (isotonic) or
a logistic transform (Platt); no numpy or sklearn dependency. The mapping was
trained on the **homology** configuration, so callers should only apply it to
interpretations that used homology (Diamond/BLAST) evidence — applying it to
motif-only offline calls would be out of distribution. `ConfidenceCalibrator`
loads gracefully: if the mapping file is absent it reports `is_loaded == False`
and `calibrate()` returns None, so the engine simply omits the calibrated field.
"""

from __future__ import annotations

import bisect
import json
import logging
import math
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Version tag recorded alongside each calibrated value, so downstream consumers
# know which mapping produced it. Bump when the mapping is retrained.
CALIBRATION_MODEL = "isotonic-homology-v1"


def _find_mapping() -> Optional[Path]:
    """Locate calibration_mapping.json: bundled package data first, then the
    repo-root data/ dir (mirrors how PROSITE data is resolved)."""
    # 1. bundled package data
    try:
        import importlib.resources

        res = importlib.resources.files("giae") / "data" / "calibration" / "calibration_mapping.json"
        with importlib.resources.as_file(res) as p:
            if p.exists():
                return Path(p)
    except Exception as e:  # noqa: BLE001
        logger.debug("importlib.resources lookup for calibration mapping failed: %s", e)

    # 2. repo-root data/ fallback (src/giae/analysis/ -> repo root is parents[3])
    for base in (
        Path(__file__).resolve().parents[3] / "data" / "calibration",
        Path.cwd() / "data" / "calibration",
    ):
        cand = base / "calibration_mapping.json"
        if cand.exists():
            return cand
    return None


class ConfidenceCalibrator:
    """Maps a raw confidence score to a calibrated P(correct)."""

    def __init__(self, mapping_path: Optional[Path] = None) -> None:
        self._method: Optional[str] = None
        self._x: list[float] = []
        self._y: list[float] = []
        self._a = self._b = 0.0
        path = mapping_path or _find_mapping()
        if path is None:
            logger.info("No confidence-calibration mapping found; calibration disabled.")
            return
        try:
            data = json.loads(Path(path).read_text())
            self._method = data.get("method")
            if self._method == "isotonic":
                self._x = [float(v) for v in data["x"]]
                self._y = [float(v) for v in data["y"]]
                if len(self._x) < 2 or len(self._x) != len(self._y):
                    raise ValueError("isotonic mapping needs matching x/y knots (>=2)")
            elif self._method == "platt":
                self._a = float(data["a"])
                self._b = float(data["b"])
            else:
                raise ValueError(f"unknown calibration method: {self._method!r}")
            logger.info("Loaded confidence calibration (%s) from %s", self._method, path)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to load calibration mapping from %s: %s", path, e)
            self._method = None

    @property
    def is_loaded(self) -> bool:
        return self._method is not None

    def calibrate(self, raw: float) -> Optional[float]:
        """Return calibrated P(correct) for a raw confidence, or None if the
        mapping is not loaded. Result is clamped to [0, 1]."""
        if self._method is None:
            return None
        if self._method == "platt":
            p = 1.0 / (1.0 + math.exp(-(self._a * raw + self._b)))
        else:
            p = self._interp(raw)
        return max(0.0, min(1.0, p))

    def _interp(self, x: float) -> float:
        """Piecewise-linear interpolation over the isotonic knots (clip ends)."""
        xs, ys = self._x, self._y
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = bisect.bisect_right(xs, x)
        x0, x1 = xs[i - 1], xs[i]
        y0, y1 = ys[i - 1], ys[i]
        if x1 == x0:
            return y1
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
