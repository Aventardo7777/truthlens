"""Layer 3 -- Digit forensics: Benford's Law & last-digit analysis.

Benford's Law applies to values that span several orders of magnitude and are
not bounded or assigned. Deviation is *not* evidence of fraud -- it can also
reflect truncation, minimum/maximum rules, or the natural generation process.
TruthLens always reports the limitation alongside the statistic.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from scipy import stats as sps

from backend.models import Finding, LAYER_PATTERN, SEVERITY_MODERATE, SEVERITY_HIGH

BENFORD_P = np.array([np.log10(1 + 1 / d) for d in range(1, 10)])


def _mk(idx: int, **kw) -> Finding:
    return Finding(id=f"B{idx:02d}", layer=LAYER_PATTERN, **kw)


def _benford_usable(s: pd.Series) -> bool:
    """Benford analysis requires positive values spanning orders of magnitude."""
    v = s.dropna()
    v = v[v > 0]
    if len(v) < 80:
        return False
    ratio = v.max() / max(v.min(), 1e-12)
    return ratio > 100


def run_digit_scan(df: pd.DataFrame) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    digit_data: dict[str, dict] = {}
    fid = 1
    num = df.select_dtypes(include=[np.number])

    for col in num.columns:
        s = num[col].dropna()

        # ---------- Benford first-digit test ----------
        if _benford_usable(s):
            v = s[s > 0]
            first = v.astype(str).str.replace(".", "", regex=False).str.replace("-", "").str.lstrip("0")
            first = first.str[0].astype(int)
            observed = np.array([(first == d).sum() for d in range(1, 10)], dtype=float)
            total = observed.sum()
            if total > 0:
                expected = BENFORD_P * total
                # chi-square with expected counts; Benford has 8 df
                chi2 = float(((observed - expected) ** 2 / expected).sum())
                p = float(sps.chi2.sf(chi2, 8))
                # MAD (mean absolute deviation) -- Nigrini's metric
                mad = float(np.abs(observed / total - BENFORD_P).mean())
                digit_data.setdefault(col, {})["benford"] = {
                    "observed_pct": [round(float(x / total * 100), 2) for x in observed],
                    "expected_pct": [round(float(x * 100), 2) for x in BENFORD_P],
                    "chi2": round(chi2, 2), "p_value": p, "mad": round(mad, 4),
                }
                # Nigrini thresholds: MAD < 0.006 close, 0.006-0.012 acceptable,
                # 0.012-0.015 marginal, > 0.015 nonconformity
                if mad > 0.015 and p < 0.01:
                    findings.append(_mk(fid,
                        category="benford_deviation",
                        title=f"变量「{col}」与 Benford 分布显著偏离 (MAD = {mad:.4f})",
                        severity=SEVERITY_HIGH if mad > 0.03 else SEVERITY_MODERATE,
                        evidence_level="moderate",
                        stat_summary=(
                            f"首位数字分布与 Benford 律的平均绝对偏差 MAD = {mad:.4f}，"
                            f"χ²(8) = {chi2:.1f}，p = {p:.2e}。"
                        ),
                        evidence={
                            "column": col,
                            "mad": round(mad, 4),
                            "chi2": round(chi2, 2),
                            "p_value": p,
                            "observed_pct": [round(float(x / total * 100), 2) for x in observed],
                            "benford_pct": [round(float(x * 100), 2) for x in BENFORD_P],
                        },
                        why_it_matters=(
                            "许多自然增长过程产生的数据（交易额、人口、测量值）的首位数字"
                            "服从 Benford 分布。系统性偏离——尤其是首位数字 1 过少或 3、4 过多——"
                            "在法务统计中常被用作人工编造数据的筛查线索。"
                        ),
                        possible_causes=[
                            "数值由人工指定或均匀随机生成",
                            "存在上下限约束或四舍五入",
                            "数据集中在狭窄的数值区间（Benford 前提不满足）",
                            "抽样偏差或截断",
                        ],
                        what_it_does_not_prove=(
                            "Benford 偏离本身不能证明数据造假。"
                            "只有当数据集理论上符合 Benford 适用条件时，偏离才具有筛查价值；"
                            "即便如此，它也只是启动进一步调查的线索，不是结论。"
                        ),
                        next_steps=[
                            "确认该变量是否满足 Benford 适用前提（跨越多个数量级、无上限约束）",
                            "结合尾数分布与其他模式证据交叉验证",
                            "若可疑，抽取原始凭证核对",
                        ],
                    ))
                    fid += 1

        # ---------- last-digit uniformity ----------
        has_frac = s.astype(str).str.contains(r"\.\d", regex=True)
        if has_frac.mean() > 0.5 and len(s) >= 60:
            frac = s[has_frac].astype(str).str.split(".").str[-1].str[-1].astype(int)
            observed = np.array([(frac == d).sum() for d in range(10)], dtype=float)
            total = observed.sum()
            if total > 0:
                expected = np.full(10, total / 10)
                chi2 = float(((observed - expected) ** 2 / expected).sum())
                p = float(sps.chi2.sf(chi2, 9))
                digit_data.setdefault(col, {})["last_digit"] = {
                    "observed_pct": [round(float(x / total * 100), 2) for x in observed],
                    "chi2": round(chi2, 2), "p_value": p,
                }
                if p < 0.005:
                    top_digit = int(np.argmax(observed))
                    findings.append(_mk(fid,
                        category="last_digit_bias",
                        title=f"变量「{col}」小数尾数分布异常 (Last-Digit Bias)",
                        severity=SEVERITY_MODERATE,
                        evidence_level="moderate",
                        stat_summary=(
                            f"末位数字「{top_digit}」出现频率达 {observed[top_digit] / total * 100:.1f}%"
                            f"（期望 10%），χ²(9) = {chi2:.1f}，p = {p:.2e}。"
                        ),
                        evidence={
                            "column": col,
                            "dominant_digit": top_digit,
                            "dominant_pct": round(float(observed[top_digit] / total * 100), 2),
                            "chi2": round(chi2, 2),
                            "p_value": p,
                            "observed_pct": [round(float(x / total * 100), 2) for x in observed],
                        },
                        why_it_matters=(
                            "对真实测量或计算得到的小数，末位数字应近似均匀分布。"
                            "若某个数字显著富集，说明末位并非自然产生——"
                            "典型场景是人工编数时偏爱某些数字，或数值由粗粒度模板加固定尾缀生成。"
                        ),
                        possible_causes=[
                            "人工填报时的无意识数字偏好",
                            "数据由模板加常数偏移生成",
                            "四舍五入到固定步长",
                        ],
                        what_it_does_not_prove="尾数偏差也可能来自合理的取整规则（如价格以 .99 结尾）。",
                        next_steps=["查看尾数富集数字对应的具体记录是否集中在特定来源或时期"],
                    ))
                    fid += 1

    return findings, digit_data
