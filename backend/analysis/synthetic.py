"""Synthetic baseline comparison.

Generates a reference dataset by independently resampling each numeric
column from its own empirical distribution (i.i.d. bootstrap). Any
*dependency structure* in the real data that is dramatically stronger than
what the i.i.d. baseline produces is flagged -- this isolates structure that
cannot be explained by the marginal distributions alone.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from backend.models import Finding, LAYER_BASELINE, SEVERITY_MODERATE, SEVERITY_HIGH


def _mk(idx: int, **kw) -> Finding:
    return Finding(id=f"Y{idx:02d}", layer=LAYER_BASELINE, **kw)


def run_synthetic_test(df: pd.DataFrame, n_boot: int = 30, seed: int = 42) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    result: dict = {"columns": {}}
    num = df.select_dtypes(include=[np.number])
    num = num.loc[:, num.nunique() > 2].dropna(axis=1)
    fid = 1

    if num.shape[1] < 2 or len(num) < 40:
        return findings, result

    rng = np.random.default_rng(seed)
    real_corr = num.corr(method="pearson")

    # distribution of max |r| under i.i.d. resampling of each column
    max_rs = []
    for _ in range(n_boot):
        synth = pd.DataFrame({c: rng.choice(num[c].dropna().values, size=len(num), replace=True)
                              for c in num.columns})
        c = synth.corr(method="pearson").abs()
        upper = c.where(np.triu(np.ones(c.shape), k=1).astype(bool)).stack()
        if len(upper):
            max_rs.append(float(upper.max()))
    if not max_rs:
        return findings, result

    real_upper = real_corr.abs().where(np.triu(np.ones(real_corr.shape), k=1).astype(bool)).stack()
    real_max = float(real_upper.max())
    base_mean, base_std = float(np.mean(max_rs)), float(np.std(max_rs))
    z = (real_max - base_mean) / base_std if base_std > 0 else 0.0

    result["correlation"] = {
        "real_max_abs_r": round(real_max, 4),
        "baseline_mean": round(base_mean, 4),
        "baseline_std": round(base_std, 4),
        "z_score": round(z, 2),
        "n_bootstrap": n_boot,
    }

    # per-column moment comparison
    for col in num.columns[:15]:
        s = num[col].dropna()
        if len(s) < 40:
            continue
        result["columns"][col] = {
            "real_mean": round(float(s.mean()), 4),
            "real_std": round(float(s.std()), 4),
            "real_skew": round(float(s.skew()), 4),
        }

    if z >= 2.0 and real_max > 0.9:
        findings.append(_mk(fid,
            category="dependency_anomaly",
            title="依赖结构显著强于合成基线 (Unusually Strong Dependency Structure)",
            severity=SEVERITY_HIGH if z >= 3 else SEVERITY_MODERATE,
            evidence_level="moderate",
            stat_summary=(
                f"真实数据最大 |r| = {real_max:.3f}；独立重采样基线的最大 |r| "
                f"平均仅 {base_mean:.3f}（σ = {base_std:.3f}），偏离达 {z:.1f} 个标准差。"
            ),
            evidence=result["correlation"],
            why_it_matters=(
                "我们按照每个变量自身的分布独立重抽样，构造了 30 份合成对照数据："
                "它们的边际分布与真实数据一致，唯一区别是变量之间相互独立。"
                "真实数据的变量关联强度远超这一基线，说明其依赖结构无法用"
                "「各变量自然变动」来解释——变量之间存在数学或生成层面的耦合。"
            ),
            possible_causes=[
                "变量间存在真实的强因果/驱动关系",
                "部分变量由公式从其他变量计算得到",
                "数据由多变量模型生成而未独立采样",
            ],
            what_it_does_not_prove=(
                "基线方法只能说明依赖结构异常，不能区分它是真实业务关系还是人为构造；"
                "样本量较小或变量数较多时，该检验的功效有限。"
            ),
            next_steps=["对最强变量对绘制散点图，检查关系形态是否机械", "核对相关变量对的业务定义"],
        ))

    return findings, result
