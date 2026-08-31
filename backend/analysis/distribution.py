"""Layer 2/3 -- Distribution analysis: shape, skew, kurtosis, histogram data."""
from __future__ import annotations

import pandas as pd
import numpy as np
from scipy import stats as sps

from backend.models import Finding, LAYER_STATISTICAL, SEVERITY_MODERATE


def _mk(idx: int, **kw) -> Finding:
    return Finding(id=f"D{idx:02d}", layer=LAYER_STATISTICAL, **kw)


def run_distribution_scan(df: pd.DataFrame, max_hist_cols: int = 12) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    hist_data: dict[str, dict] = {}
    shapes: dict[str, dict] = {}
    fid = 1
    num = df.select_dtypes(include=[np.number])

    for col in num.columns:
        s = num[col].dropna()
        if len(s) < 30 or s.nunique() < 5:
            continue
        skew = float(sps.skew(s))
        kurt = float(sps.kurtosis(s))  # excess
        shapes[col] = {"skew": round(skew, 3), "kurtosis": round(kurt, 3),
                       "mean": round(float(s.mean()), 4), "std": round(float(s.std()), 4)}

        # histogram for dashboard
        if len(hist_data) < max_hist_cols:
            try:
                counts, edges = np.histogram(s, bins=24)
                hist_data[col] = {
                    "bins": [round(float(e), 4) for e in edges],
                    "counts": [int(c) for c in counts],
                }
            except Exception:
                pass

        if abs(skew) > 2:
            findings.append(_mk(fid,
                category="extreme_skew",
                title=f"变量「{col}」分布严重偏斜 (Skewness = {skew:.2f})",
                severity=SEVERITY_MODERATE,
                evidence_level="moderate",
                stat_summary=f"偏度 {skew:.2f}，峰度 {kurt:.2f}，均值/中位数 = {s.mean() / s.median():.2f}"
                             if s.median() != 0 else f"偏度 {skew:.2f}，峰度 {kurt:.2f}。",
                evidence={"column": col, "skew": round(skew, 3), "kurtosis": round(kurt, 3)},
                why_it_matters=(
                    "极端偏斜下，均值不再是位置的良好度量，t 检验与线性模型的基本假设失效。"
                    "若该变量理论上应近似对称，强偏斜可能暗示存在未处理的截断、下限堆积或录入异常。"
                ),
                possible_causes=["自然重尾（收入、销量）", "零值/最小值堆积", "截断抽样"],
                what_it_does_not_prove="偏斜是分布属性而非数据缺陷；许多业务量天然右偏。",
                next_steps=["改用中位数与分位数描述；建模前做对数变换"],
            ))
            fid += 1

    return findings, {"shapes": shapes, "histograms": hist_data}
