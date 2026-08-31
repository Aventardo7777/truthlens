"""Tests for the TruthLens analysis engine."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.analysis.engine import load_dataframe, run_full_scan
from backend.analysis import quality, outliers, correlation, benford, pattern
from backend.analysis.fingerprint import compute_integrity_score
from backend.models import Finding

DEMO = Path(__file__).resolve().parent.parent / "datasets" / "examples" / "suspicious_sales.xlsx"


def _demo_df() -> pd.DataFrame:
    return load_dataframe(DEMO.read_bytes(), DEMO.name)


# ---------------------------------------------------------------------------
# Layer 1 -- data health
# ---------------------------------------------------------------------------
def test_missing_values_detected():
    df = pd.DataFrame({"a": [1, 2, np.nan, 4], "b": ["x", "y", "z", "w"]})
    findings, meta = quality.run_health_scan(df)
    cats = [f.category for f in findings]
    assert "missing_values" in cats


def test_duplicates_detected():
    df = pd.DataFrame({"a": [1, 2, 2, 3], "b": ["x", "y", "y", "z"]})
    findings, _ = quality.run_health_scan(df)
    assert any(f.category == "duplicates" for f in findings)


def test_constant_column_detected():
    df = pd.DataFrame({"a": [1, 1, 1, 1], "b": [1, 2, 3, 4]})
    findings, _ = quality.run_health_scan(df)
    assert any(f.category == "constant_column" for f in findings)


def test_negative_values_detected():
    df = pd.DataFrame({"age": [25, 30, -3, 40, 22, 35, 41, 29, 33, 28, 31, 36]})
    findings, _ = quality.run_health_scan(df)
    assert any(f.category == "illegal_values" for f in findings)


# ---------------------------------------------------------------------------
# Layer 2 -- statistical anomalies
# ---------------------------------------------------------------------------
def test_outliers_detected():
    rng = np.random.default_rng(0)
    vals = rng.normal(100, 10, 500).tolist() + [1000, 1500]
    df = pd.DataFrame({"x": vals, "y": rng.normal(50, 5, 502)})
    findings, _ = outliers.run_outlier_scan(df)
    assert any(f.category == "outliers" and "x" in f.title for f in findings)


def test_near_duplicate_column_detected():
    rng = np.random.default_rng(1)
    a = rng.normal(100, 10, 300)
    df = pd.DataFrame({"a": a, "b": a * 1.01 + 0.001, "c": rng.normal(50, 10, 300)})
    findings, net = correlation.run_correlation_scan(df)
    assert any(f.category == "near_duplicate_column" for f in findings)
    assert len(net["nodes"]) == 3


# ---------------------------------------------------------------------------
# Layer 3 -- digit forensics
# ---------------------------------------------------------------------------
def test_benford_deviation_detected():
    rng = np.random.default_rng(2)
    # log-uniform base plus a strong 8-prefix injection
    base = np.exp(rng.uniform(np.log(100), np.log(500000), 600))
    idx = rng.choice(600, 150, replace=False)
    base[idx] = 8 * 10 ** rng.integers(1, 5, 150)
    df = pd.DataFrame({"amount": np.round(base, 2)})
    findings, digit = benford.run_digit_scan(df)
    assert any(f.category == "benford_deviation" for f in findings)
    assert "amount" in digit and "benford" in digit["amount"]


def test_last_digit_bias_detected():
    # values whose last digit is always 8
    df = pd.DataFrame({"v": np.round(np.random.default_rng(3).uniform(10, 1000, 300), 2) + 0.08})
    findings, _ = benford.run_digit_scan(df)
    assert any(f.category == "last_digit_bias" for f in findings)


# ---------------------------------------------------------------------------
# Pattern forensics
# ---------------------------------------------------------------------------
def test_repeated_blocks_detected():
    rng = np.random.default_rng(4)
    base = pd.DataFrame({
        "x": rng.normal(100, 10, 500),
        "y": rng.normal(50, 5, 500),
        "z": rng.normal(20, 3, 500),
    })
    block = base.iloc[100:160].copy()
    df = pd.concat([base, block, block], ignore_index=True)
    findings = pattern.run_pattern_scan(df, None)
    assert any(f.category == "repeated_blocks" for f in findings)


def test_group_uniformity_detected():
    rng = np.random.default_rng(5)
    g = np.repeat(["A", "B", "C"], 100)
    # identical mean and std across groups
    v = np.concatenate([rng.normal(50, 5, 100) for _ in range(3)])
    df = pd.DataFrame({"group": g, "value": v})
    findings = pattern.run_pattern_scan(df, ["group"])
    assert any(f.category == "group_uniformity" for f in findings)


# ---------------------------------------------------------------------------
# Integrity score
# ---------------------------------------------------------------------------
def test_integrity_score_range():
    findings = [
        Finding(id="X01", layer="statistical", category="outliers", title="t",
                severity="high", evidence_level="high", stat_summary="s")
    ]
    score = compute_integrity_score(findings)
    assert 0 <= score.total <= 100
    assert set(score.dimensions) == {"完整性", "一致性", "分布自然度", "异常程度", "重复风险", "模式异常"}


# ---------------------------------------------------------------------------
# End-to-end on the demo dataset
# ---------------------------------------------------------------------------
def test_demo_dataset_full_scan():
    df = _demo_df()
    result = run_full_scan(df, DEMO.name)
    assert result.n_rows > 1000
    cats = {f.category for f in result.findings}
    # all signature anomalies must be present
    for expected in ("benford_deviation", "repeated_blocks", "level_shift",
                     "dependency_anomaly", "duplicates", "near_duplicate_column"):
        assert expected in cats, f"missing finding category: {expected}"
    assert 0 <= result.integrity.total <= 100
    assert result.integrity.dimensions


def test_demo_dataset_loading_variants():
    df = _demo_df()
    assert df.shape[1] >= 10


def test_csv_loading():
    csv = b"a,b,c\n1,2,3\n4,5,6\n7,8,9\n"
    df = load_dataframe(csv, "data.csv")
    assert df.shape == (3, 3)
