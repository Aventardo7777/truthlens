"""Layer 3 -- Pattern Forensics.

Targets anomalies of the *whole pattern* rather than single values:
suspiciously stable group means/variances, repeated value blocks,
and duplicated row structures across time.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from scipy import stats as sps

from backend.models import Finding, LAYER_PATTERN, SEVERITY_HIGH, SEVERITY_MODERATE


def _mk(idx: int, **kw) -> Finding:
    return Finding(id=f"P{idx:02d}", layer=LAYER_PATTERN, **kw)


def run_pattern_scan(df: pd.DataFrame, cat_cols: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    fid = 1
    num = df.select_dtypes(include=[np.number])

    # ---- 1. repeated value blocks (same value many times in a column) ----
    for col in num.columns:
        s = num[col].dropna()
        if len(s) < 50:
            continue
        vc = s.value_counts()
        if vc.empty:
            continue
        top_val, top_n = vc.index[0], int(vc.iloc[0])
        if top_n >= max(10, 0.03 * len(s)) and s.nunique() > 10:
            findings.append(_mk(fid,
                category="value_pileup",
                title=f"变量「{col}」存在数值堆积 (Value Pile-up)",
                severity=SEVERITY_MODERATE,
                evidence_level="high",
                stat_summary=f"值 {top_val} 重复出现 {top_n} 次，占该列的 {top_n / len(s) * 100:.1f}%。",
                evidence={"column": col, "value": top_val, "count": top_n,
                          "pct": round(top_n / len(s) * 100, 2)},
                why_it_matters=(
                    "同一精确数值高频堆积意味着该列不是连续测量——"
                    "它可能是被填充的默认值、复制的数据块或粗步长取整的结果。"
                ),
                possible_causes=["缺失被默认值填充", "手工复制数据", "按固定步长报价/取整"],
                what_it_does_not_prove="堆积在离散计价数据（如定价档位）中完全正常。",
                next_steps=["核对堆积值是否等于默认值/占位符", "剔除堆积后重看分布"],
            ))
            fid += 1

    # ---- 2. group statistics too consistent (ANOVA-like) ------------------
    if cat_cols:
        for cat in cat_cols[:5]:
            groups = df.groupby(cat, observed=True)
            if groups.ngroups < 3 or groups.ngroups > 50:
                continue
            for col in num.columns:
                vals = [g.dropna().values for _, g in groups[col]]
                vals = [v for v in vals if len(v) >= 8]
                if len(vals) < 3:
                    continue
                means = np.array([v.mean() for v in vals])
                stds = np.array([v.std() for v in vals])
                if np.isnan(means).any() or np.isnan(stds).any():
                    continue
                # between-group dispersion: how similar are group means/stds
                mean_cv = float(means.std() / abs(means.mean())) if means.mean() != 0 else np.inf
                spread_cv = float(stds.std() / stds.mean()) if stds.mean() > 0 else np.inf
                # group means almost identical AND group stds almost identical
                if mean_cv < 0.02 and spread_cv < 0.08:
                    findings.append(_mk(fid,
                        category="group_uniformity",
                        title=f"分组间统计量不自然地一致 (Unnatural Group Uniformity)",
                        severity=SEVERITY_HIGH,
                        evidence_level="moderate",
                        stat_summary=(
                            f"按「{cat}」分组后，「{col}」各组均值的变异系数仅 {mean_cv:.4f}，"
                            f"各组标准差的变异系数仅 {spread_cv:.4f}。"
                        ),
                        evidence={
                            "group_column": cat, "value_column": col,
                            "mean_cv": round(mean_cv, 5), "std_cv": round(spread_cv, 5),
                            "n_groups": len(vals),
                        },
                        why_it_matters=(
                            "不同子群的数据几乎不可能拥有完全相同的均值和标准差——"
                            "真实业务中各区域、各渠道之间总存在天然差异。"
                            "当各组的二阶统计量高度一致时，"
                            "最合理的解释之一是：各组数据由同一个模板复制后加微扰生成。"
                        ),
                        possible_causes=[
                            "各分组数据由同一生成模板复制",
                            "数据被归一化/标准化后再拼接",
                            "该分组维度与该数值确实无关（合法但少见）",
                        ],
                        what_it_does_not_prove="统计一致性可能来自真实的同质总体，需结合业务常识判断。",
                        next_steps=["对比各组的完整分布（分位数、直方图）而非仅均值方差",
                                    "对两组间做 KS 检验，看分布是否近乎完全重合"],
                    ))
                    fid += 1

    # ---- 3. duplicated row segments (block repetition) ---------------------
    # A pasted block shows up as *many pairs of identical rows sharing the
    # same offset*: rows k..k+L appear again at k+d..k+d+L. Detect by counting
    # identical-row pairs by their distance.
    try:
        num_only = num.fillna(-9e99)
        if len(num_only) >= 60 and num_only.shape[1] >= 2:
            tuples = list(map(tuple, num_only.round(6).values))
            pos_map: dict[tuple, list[int]] = {}
            for i, t in enumerate(tuples):
                pos_map.setdefault(t, []).append(i)
            offsets: dict[int, int] = {}
            for poss in pos_map.values():
                for a in range(len(poss)):
                    for b in range(a + 1, len(poss)):
                        d = poss[b] - poss[a]
                        if 0 < d < len(tuples):
                            offsets[d] = offsets.get(d, 0) + 1
            # a block copy produces a large count for a single offset
            best_off, best_cnt = max(offsets.items(), key=lambda kv: kv[1]) if offsets else (0, 0)
            if best_cnt >= 8 and best_off >= 10 and best_cnt >= 0.01 * len(tuples):
                findings.append(_mk(fid,
                    category="repeated_blocks",
                    title="检测到整段复制粘贴的数据块 (Repeated Row Blocks)",
                    severity=SEVERITY_HIGH,
                    evidence_level="high",
                    stat_summary=(
                        f"{best_cnt} 对完全相同的数据行彼此相隔固定的 {best_off} 行——"
                        f"这是整段复制粘贴的典型指纹。"
                    ),
                    evidence={"n_identical_pairs_at_offset": int(best_cnt),
                              "fixed_offset": int(best_off),
                              "rows": int(len(tuples))},
                    why_it_matters=(
                        "数据中出现大量「完全相同的行、且间距恒定」的结构，"
                        "几乎只可能来自整段复制粘贴：为扩充数据量，将一段历史记录"
                        "原样粘贴到表尾。这会让样本的独立性假设失效，重复部分"
                        "对统计结论产生不成比例的权重。"
                    ),
                    possible_causes=[
                        "人工复制粘贴扩表",
                        "脚本以错误偏移循环写入",
                        "报表模板复制后未清除旧数据",
                    ],
                    what_it_does_not_prove="偏移恒定的重复行也可能是合法的定期快照结构，需结合业务判断。",
                    next_steps=[
                        "定位该偏移下的重复行对并检查其行号范围",
                        "确认是否所有重复段都来自同一时间区间",
                    ],
                ))
                fid += 1
    except Exception:
        pass

    # ---- 4. column pair near-identical values (not just correlation) -------
    cols = [c for c in num.columns if num[c].nunique() > 2]
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = num[cols[i]], num[cols[j]]
            if a.std() > 0 and b.std() > 0:
                scaled_gap = (a - b).abs().mean() / max(a.std(), 1e-12)
                if scaled_gap < 0.02 and abs(a.corr(b)) > 0.99:
                    findings.append(_mk(fid,
                        category="column_copy",
                        title=f"「{cols[j]}」疑似「{cols[i]}」的复制 (Suspected Column Copy)",
                        severity=SEVERITY_MODERATE,
                        evidence_level="high",
                        stat_summary=f"两列的标准化平均差异仅 {scaled_gap:.4f}，相关系数 {a.corr(b):.4f}。",
                        evidence={"columns": [cols[i], cols[j]], "scaled_gap": round(float(scaled_gap), 5)},
                        why_it_matters="一列的值几乎逐行等于另一列，说明它不是独立测量，而是复制或线性变换的结果。",
                        possible_causes=["复制列改名", "公式派生列", "数据生成时的冗余"],
                        what_it_does_not_prove="派生列在报表中很常见，本身无害。",
                        next_steps=["检查两列差值的分布；确认派生关系是否符合业务定义"],
                    ))
                    fid += 1

    return findings
