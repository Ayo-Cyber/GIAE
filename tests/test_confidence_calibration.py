"""Tests for post-hoc confidence calibration."""

from __future__ import annotations

import json

import pytest

from giae.analysis.confidence_calibration import ConfidenceCalibrator


def _write_isotonic(tmp_path, x, y):
    p = tmp_path / "calibration_mapping.json"
    p.write_text(json.dumps({"method": "isotonic", "x": x, "y": y}))
    return p


def test_isotonic_interpolation(tmp_path):
    cal = ConfidenceCalibrator(_write_isotonic(tmp_path, [0.0, 0.5, 1.0], [0.0, 0.2, 0.8]))
    assert cal.is_loaded
    assert cal.calibrate(0.0) == pytest.approx(0.0)
    assert cal.calibrate(0.5) == pytest.approx(0.2)
    assert cal.calibrate(1.0) == pytest.approx(0.8)
    # midpoint linear interpolation
    assert cal.calibrate(0.25) == pytest.approx(0.1)
    assert cal.calibrate(0.75) == pytest.approx(0.5)


def test_isotonic_clamps_out_of_range(tmp_path):
    cal = ConfidenceCalibrator(_write_isotonic(tmp_path, [0.2, 1.0], [0.1, 0.6]))
    assert cal.calibrate(-1.0) == pytest.approx(0.1)   # below first knot -> first y
    assert cal.calibrate(5.0) == pytest.approx(0.6)    # above last knot -> last y
    assert 0.0 <= cal.calibrate(0.5) <= 1.0


def test_platt_transform(tmp_path):
    p = tmp_path / "calibration_mapping.json"
    p.write_text(json.dumps({"method": "platt", "a": 2.0, "b": -1.0}))
    cal = ConfidenceCalibrator(p)
    assert cal.is_loaded
    # P = sigmoid(2x - 1); at x=0.5 -> sigmoid(0) = 0.5
    assert cal.calibrate(0.5) == pytest.approx(0.5, abs=1e-6)
    assert 0.0 <= cal.calibrate(0.0) <= 1.0
    assert cal.calibrate(1.0) > cal.calibrate(0.0)  # monotone increasing


def test_missing_mapping_is_graceful(tmp_path):
    cal = ConfidenceCalibrator(tmp_path / "does_not_exist.json")
    assert not cal.is_loaded
    assert cal.calibrate(0.9) is None


def test_bundled_mapping_loads():
    """The mapping shipped in data/calibration/ should be discoverable."""
    cal = ConfidenceCalibrator()
    # If present, it must produce a valid probability; if absent, degrade cleanly.
    if cal.is_loaded:
        v = cal.calibrate(0.95)
        assert v is not None and 0.0 <= v <= 1.0
    else:
        assert cal.calibrate(0.95) is None
