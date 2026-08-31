"""Layer 2 -- Outlier detection: robust univariate extreme-value screening.

Uses both IQR fences (distribution-free) and robust z-scores (median / MAD),
so results stay meaningful for skewed data where classic z-scores misfire.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from backend.models import Finding, LAYER_STATISTICAL, SEVERITY_LOW, SEVERITY_MODERATE, SEVERITY_HIGH


def _mk(idx: int, **kw) -> Finding:
    return Finding(id=f"S{idx:02d}", layer=LAYER_STATISTICAL, **kw)


def run_outlier_scan(df: pd.DataFrame, max_cols: int = 30) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    per_col: dict[str, dict] = {}
    fid = 1
    num_df = df.select_dtypes(include=[np.number])

    for col in num_df.columns:
        s = num_df[col].dropna()
        if len(s) < 20 or s.nunique() < 3:
            continue

        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        iqr_out = s[(s < lo) | (s > hi)]

        # robust z (MAD-based)
        med = s.median()
        mad = (s - med).abs().median()
        if mad > 0:
            rz = 0.6745 * (s - med) / mad
            max_rz = float(rz.abs().max())
            n_rz = int((rz.abs() > 3.5).sum())
        else:
            max_rz = 0.0
            n_rz = 0

        pct = 100.0 * len(iqr_out) / len(s)
        per_col[col] = {
            "iqr_outliers": int(len(iqr_out)),
            "iqr_pct": round(pct, 2),
            "max_robust_z": round(max_rz, 2),
            "fences": [round(float(lo), 4), round(float(hi), 4)],
        }

        if max_rz >= 5 or (pct > 1 and len(iqr_out) >= 5 and iqr > 0):
            extreme = s.loc[rz.abs().idxmax()] if mad > 0 else None
            examples = iqr_out.sort_values(ascending=False).head(5).round(4).tolist() if len(iqr_out) else []
            sev = SEVERITY_HIGH if max_rz >= 8 else SEVERITY_MODERATE
            findings.append(_mk(fid,
                category="outliers",
                title=f"变量「{col}」检测到极端值 (Extreme Outliers)",
                severity=sev,
                evidence_level="moderate",
                stat_summary=(
                    f"最极端观测的稳健 Z 分数约 {max_rz:.1f}"
                    + (f"，偏离中位数 {abs(float(extreme) - med):.4g}" if extreme is not None else "")
                    + f"；IQR 规则标记 {len(iqr_out)} 个离群点（{pct:.1f}%）。"
                ),
                evidence={
                    "column": col,
                    "max_robust_z": round(max_rz, 2),
                    "n_beyond_3.5rz": n_rz,
                    "iqr_outliers": int(len(iqr_out)),
                    "iqr_pct": round(pct, 2),
                    "example_values": examples,
                    "median": round(float(med), 4),
                },
                why_it_matters=(
                    f"该观测值位于总体分布的极端区域，距离中位数约 {max_rz:.1f} 个稳健标准差。"
                    "若数据近似正态，如此极端的取值在随机样本中出现的概率不足万分之一；"
                    "它对均值、回归系数等敏感统计量具有不成比例的影响力。"
                ),
                possible_causes=[
                    "真实极端事件（大客户、爆款订单、设备故障）",
                    "录入错误（多打一个零、小数点错位）",
                    "单位混用（元与万元并存）",
                    "测量设备故障或传感器漂移",
                ],
                what_it_does_not_prove="极端值是重尾分布（如收入、销量）的正常组成部分，不能仅凭大小判定其为错误。",
                next_steps=[
                    "回溯极端记录的原始凭证或日志",
                    "用对数变换或稳健统计量（中位数、截尾均值）复核结论是否被其主导",
                ],
            ))
            fid += 1

    return findings, per_col
