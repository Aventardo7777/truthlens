"""Layer 4 -- Data fingerprint & Integrity Score.

The fingerprint is a set of compact signatures that characterize a dataset
(distribution, correlation, missingness, digit structure, duplication).
The integrity score is a weighted aggregate of finding severities mapped
onto six dimensions.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from backend.models import (
    Finding, IntegrityScore, ScanResult, verdict_for,
    LAYER_HEALTH, LAYER_STATISTICAL, LAYER_PATTERN, LAYER_BASELINE,
)


def _sig(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def build_fingerprint(df: pd.DataFrame, corr: dict, digit: dict) -> dict:
    num = df.select_dtypes(include=[np.number])
    # correlation eigenvalue signature
    eig_sig = ""
    try:
        if num.shape[1] >= 3:
            corr_mx = num.corr().fillna(0).values
            eig = np.linalg.eigvalsh(corr_mx)
            eig_sig = _sig(np.round(eig, 4).tolist())
    except Exception:
        pass
    # distribution signature: quantiles per column
    quant = {}
    for col in num.columns[:30]:
        s = num[col].dropna()
        if len(s) > 10:
            quant[col] = [round(float(x), 4) for x in s.quantile([0.05, 0.25, 0.5, 0.75, 0.95])]
    # missingness signature
    miss = {c: int(df[c].isna().sum()) for c in df.columns}
    dup_rate = float(df.duplicated().mean())
    return {
        "distribution_signature": _sig(quant),
        "correlation_signature": eig_sig or _sig(sorted(corr.get("edges", []), key=str)[:50]),
        "missingness_signature": _sig(miss),
        "digit_signature": _sig(digit),
        "duplication_signature": _sig({"dup_rate": round(dup_rate, 6)}),
        "row_count": int(len(df)),
        "col_count": int(df.shape[1]),
        "sha256_preview": hashlib.sha256(
            df.head(100).to_csv(index=False).encode()).hexdigest()[:32],
    }


DIMENSION_RULES = [
    # dimension name, categories feeding it, base score
    ("完整性", {"missing_values", "time_gaps"}, 100),
    ("一致性", {"mixed_type", "categorical_pollution", "illegal_values", "constant_column"}, 100),
    ("分布自然度", {"benford_deviation", "last_digit_bias", "extreme_skew"}, 100),
    ("异常程度", {"outliers", "level_shift"}, 100),
    ("重复风险", {"duplicates", "repeated_blocks", "column_copy", "near_duplicate_column",
               "value_pileup", "correlation_concentration"}, 100),
    ("模式异常", {"abnormal_stability", "group_uniformity", "dependency_anomaly",
              "high_correlation", "benford_deviation"}, 100),
]


def compute_integrity_score(findings: list[Finding]) -> IntegrityScore:
    by_cat: dict[str, float] = {}
    for f in findings:
        by_cat[f.category] = by_cat.get(f.category, 0) + f.score_penalty

    dimensions: dict[str, int] = {}
    for name, cats, base in DIMENSION_RULES:
        penalty = sum(by_cat.get(c, 0) for c in cats)
        dimensions[name] = int(max(0, min(100, base - penalty * 4)))

    # total: weighted mix, capped 5..98
    weights = {"完整性": 0.20, "一致性": 0.15, "分布自然度": 0.15,
               "异常程度": 0.15, "重复风险": 0.20, "模式异常": 0.15}
    total = sum(dimensions[k] * w for k, w in weights.items())
    total = int(max(5, min(98, round(total))))
    verdict = verdict_for(total)

    n_high = sum(1 for f in findings if f.severity == "high")
    if n_high == 0 and total >= 70:
        explanation = "数据不存在明显结构性损坏，各维度指标均在合理范围内。"
    elif n_high <= 2 and total >= 55:
        explanation = "数据整体可用，但检测到若干值得人工调查的统计模式，建议在关键用途前复核。"
    else:
        explanation = "数据存在多个高风险取证发现，在重要决策场景中建议先修复或溯源后再使用。"

    return IntegrityScore(total=total, verdict=verdict, dimensions=dimensions, explanation=explanation)
