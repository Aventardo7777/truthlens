"""Layer 2 -- Correlation structure analysis.

Flags suspiciously strong linear/monotone relationships and near-duplicate
columns, and builds the variable relationship network used by the dashboard.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from backend.models import Finding, LAYER_STATISTICAL, SEVERITY_MODERATE, SEVERITY_HIGH


def _mk(idx: int, **kw) -> Finding:
    return Finding(id=f"C{idx:02d}", layer=LAYER_STATISTICAL, **kw)


def run_correlation_scan(df: pd.DataFrame) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    num = df.select_dtypes(include=[np.number])
    num = num.loc[:, num.nunique() > 1]
    network = {"nodes": [], "edges": []}
    fid = 1

    for col in df.columns:
        network["nodes"].append({
            "id": col,
            "role": "numeric" if col in num.columns else "other",
            "degree": 0,
        })

    if num.shape[1] < 2:
        return findings, network

    corr = num.corr(method="pearson")
    spear = num.corr(method="spearman")
    pairs: list[tuple[float, str, str]] = []

    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if pd.isna(r):
                continue
            pairs.append((float(r), cols[i], cols[j]))
            if abs(r) >= 0.3:
                network["edges"].append({
                    "source": cols[i],
                    "target": cols[j],
                    "weight": round(abs(float(r)), 3),
                    "sign": "+" if r > 0 else "-",
                    "method": "pearson",
                })

    degree = {n["id"]: 0 for n in network["nodes"]}
    for e in network["edges"]:
        degree[e["source"]] += 1
        degree[e["target"]] += 1
    for n in network["nodes"]:
        n["degree"] = degree.get(n["id"], 0)

    # near-perfect correlations (possible data duplication)
    near = [(r, a, b) for r, a, b in pairs if abs(r) >= 0.995]
    for r, a, b in near:
        findings.append(_mk(fid,
            category="near_duplicate_column",
            title=f"「{a}」与「{b}」近乎完全线性相关 (r = {r:.4f})",
            severity=SEVERITY_HIGH,
            evidence_level="high",
            stat_summary=f"Pearson r = {r:.4f}；两列携带几乎相同的数值信息。",
            evidence={"columns": [a, b], "pearson": round(r, 4),
                      "spearman": round(float(spear.loc[a, b]), 4)},
            why_it_matters=(
                "两个变量呈现近乎完美的线性关系，通常意味着其中一列是另一列的复制、"
                "单位换算或公式推导结果。在回归中同时使用会造成严重多重共线性；"
                "更值得注意的是，若二者在业务上本应彼此独立，这种关系说明数据生成方式可疑。"
            ),
            possible_causes=[
                "同一指标的重复导出（不同命名）",
                "一列由另一列经公式计算得来",
                "为凑列数而复制数据后加噪声",
            ],
            what_it_does_not_prove="强相关在真实数据中也大量存在（如身高与体重），必须结合业务含义判断。",
            next_steps=["逐行对比两列的差值分布", "若确为冗余，建模前删除其一"],
        ))
        fid += 1

    # suspiciously strong correlations (0.9 - 0.995)
    strong = [(r, a, b) for r, a, b in pairs if 0.90 <= abs(r) < 0.995]
    strong.sort(key=lambda t: -abs(t[0]))
    for r, a, b in strong[:3]:
        findings.append(_mk(fid,
            category="high_correlation",
            title=f"「{a}」与「{b}」呈现异常强的线性关系 (r = {r:.3f})",
            severity=SEVERITY_MODERATE,
            evidence_level="moderate",
            stat_summary=f"Pearson r = {r:.3f}（Spearman ρ = {spear.loc[a, b]:.3f}）。",
            evidence={"columns": [a, b], "pearson": round(r, 4),
                      "spearman": round(float(spear.loc[a, b]), 4)},
            why_it_matters=(
                "两变量的线性关系异常紧密，可解释方差超过 80%。"
                "若二者在业务逻辑上不存在直接的数学或因果联系，"
                "这种相关性值得进一步调查：它可能揭示真实的强关联，"
                "也可能指向数据复制、变量泄漏或生成式填充。"
            ),
            possible_causes=[
                "真实的强因果/驱动关系",
                "两变量共享同一底层驱动因素",
                "数据复制或合成生成时未独立采样",
                "目标泄漏（其中一列隐含了另一列的信息）",
            ],
            what_it_does_not_prove="当前证据不足以证明数据被人为修改；高相关本身是常见现象。",
            next_steps=[
                "绘制散点图检查关系是否为线性、是否存在机械生成的痕迹",
                "核对两列的业务定义与采集流程",
            ],
        ))
        fid += 1

    # global correlation concentration
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool)).stack()
    if len(upper) >= 6:
        mean_abs_r = float(upper.abs().mean())
        max_r = float(upper.abs().max())
        if mean_abs_r > 0.6:
            findings.append(_mk(fid,
                category="correlation_concentration",
                title="变量间相关性整体偏高 (Correlation Concentration)",
                severity=SEVERITY_MODERATE,
                evidence_level="moderate",
                stat_summary=f"所有变量对的平均 |r| = {mean_abs_r:.2f}，最大 |r| = {max_r:.2f}。",
                evidence={"mean_abs_r": round(mean_abs_r, 3), "max_abs_r": round(max_r, 3),
                          "n_pairs": int(len(upper))},
                why_it_matters=(
                    "整张相关矩阵普遍偏高通常意味着变量间缺乏独立性——"
                    "要么数据维度本身高度冗余，要么所有变量由同一来源派生。"
                    "对主成分分析与因子分析而言，这会使有效维度被严重高估。"
                ),
                possible_causes=["指标体系设计冗余", "多变量由同一模板生成", "合成数据生成时使用了单一因子"],
                what_it_does_not_prove="相关结构密集不等于造假；金融面板数据中也常见。",
                next_steps=["做 PCA 查看有效维数；检查前几个主成分的解释比例"],
            ))
            fid += 1

    return findings, network
