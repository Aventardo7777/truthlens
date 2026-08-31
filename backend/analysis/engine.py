"""TruthLens analysis engine -- orchestrates the four forensic layers."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend.models import ColumnProfile, Finding, ScanResult
from backend.analysis import quality, outliers, correlation, distribution, temporal, benford, pattern, synthetic
from backend.analysis.fingerprint import build_fingerprint, compute_integrity_score

logger = logging.getLogger("truthlens.engine")

PIPELINE_STEPS = [
    "Schema Analysis",
    "Distribution Scan",
    "Outlier Detection",
    "Correlation Mapping",
    "Pattern Forensics",
    "Integrity Assessment",
]


def load_dataframe(raw: bytes, filename: str) -> pd.DataFrame:
    """Load CSV / Excel bytes into a DataFrame."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xls")):
        try:
            import io
            return pd.read_excel(io.BytesIO(raw), engine="openpyxl")
        except Exception:
            # fall back to CSV parse in case of csv-in-xlsx naming
            return pd.read_csv(io.BytesIO(raw))
    else:
        import io
        for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(raw), encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError("无法解析文件：既不是有效的 Excel 也不是可识别编码的 CSV。")


def _classify_columns(df: pd.DataFrame, datetime_cols: list[str]) -> list[ColumnProfile]:
    profiles = []
    for col in df.columns:
        s = df[col]
        missing = int(s.isna().sum())
        unique = int(s.nunique(dropna=True))
        if col in datetime_cols:
            role = "datetime"
        elif unique <= 1:
            role = "constant"
        elif pd.api.types.is_numeric_dtype(s):
            role = "numeric"
        elif pd.api.types.is_string_dtype(s) and unique > 0.9 * max(len(s) - missing, 1):
            role = "text"
        else:
            role = "categorical"
        stats: dict = {}
        if role == "numeric":
            ss = s.dropna()
            if len(ss):
                stats = {
                    "mean": round(float(ss.mean()), 4),
                    "std": round(float(ss.std()), 4),
                    "min": round(float(ss.min()), 4),
                    "max": round(float(ss.max()), 4),
                    "median": round(float(ss.median()), 4),
                }
        elif role == "categorical":
            top = s.value_counts().head(5)
            stats = {"top_values": {str(k): int(v) for k, v in top.items()}}
        profiles.append(ColumnProfile(
            name=str(col), dtype=str(s.dtype), role=role,
            count=int(len(s)), missing=missing,
            missing_pct=round(100.0 * missing / max(len(s), 1), 2),
            unique=unique, stats=stats,
        ))
    return profiles


def run_full_scan(df: pd.DataFrame, filename: str = "upload") -> ScanResult:
    """Run the complete forensic pipeline on a DataFrame."""
    t0 = time.time()
    scan_id = uuid.uuid4().hex[:12]
    case_number = "TL-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + scan_id[:6].upper()

    findings: list[Finding] = []

    # Layer 1 -- data health
    h_findings, meta = quality.run_health_scan(df)
    findings.extend(h_findings)
    datetime_cols = meta["datetime_columns"]

    # Layer 2 -- statistical anomalies
    o_findings, outlier_stats = outliers.run_outlier_scan(df)
    findings.extend(o_findings)

    c_findings, network = correlation.run_correlation_scan(df)
    findings.extend(c_findings)

    d_findings, dist_data = distribution.run_distribution_scan(df)
    findings.extend(d_findings)

    t_findings, series_data = temporal.run_temporal_scan(df, datetime_cols)
    findings.extend(t_findings)

    # Layer 3 -- pattern forensics
    b_findings, digit_data = benford.run_digit_scan(df)
    findings.extend(b_findings)

    cat_cols = [p.name for p in _classify_columns(df, datetime_cols) if p.role == "categorical"]
    p_findings = pattern.run_pattern_scan(df, cat_cols)
    findings.extend(p_findings)

    # Baseline
    y_findings, synth = synthetic.run_synthetic_test(df)
    findings.extend(y_findings)

    # Layer 4 -- fingerprint & integrity
    fingerprint = build_fingerprint(df, network, digit_data)
    integrity = compute_integrity_score(findings)

    profiles = _classify_columns(df, datetime_cols)
    charts = {
        "histograms": dist_data.get("histograms", {}),
        "series": series_data,
        "digits": digit_data,
        "shapes": dist_data.get("shapes", {}),
        "outliers": outlier_stats,
    }

    result = ScanResult(
        scan_id=scan_id,
        case_number=case_number,
        filename=filename,
        created_at=datetime.now(timezone.utc).isoformat(),
        n_rows=int(len(df)),
        n_cols=int(df.shape[1]),
        columns=profiles,
        findings=findings,
        integrity=integrity,
        correlation_network=network,
        charts=charts,
        synthetic_comparison=synth,
        fingerprint=fingerprint,
        pipeline_steps=PIPELINE_STEPS,
    )
    logger.info("scan %s completed in %.2fs, %d findings, score=%d",
                scan_id, time.time() - t0, len(findings), integrity.total)
    return result
