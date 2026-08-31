"""Layer 1 -- Data Health: basic quality screening.

Detects missing values, duplicate rows, constant columns, mixed types,
suspicious negative values, categorical pollution and schema issues.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from backend.models import (
    Finding, LAYER_HEALTH, SEVERITY_LOW, SEVERITY_MODERATE, SEVERITY_HIGH,
    EVIDENCE_HIGH, EVIDENCE_MODERATE,
)


def _mk(idx: int, **kw) -> Finding:
    return Finding(id=f"H{idx:02d}", layer=LAYER_HEALTH, **kw)


def detect_datetime_columns(df: pd.DataFrame) -> list[str]:
    """Column names that parse as datetimes."""
    out = []
    for col in df.columns:
        s = df[col].dropna()
        if s.empty:
            continue
        if pd.api.types.is_datetime64_any_dtype(s):
            out.append(col)
            continue
        if pd.api.types.is_string_dtype(s) or s.dtype == object:
            sample = s.astype(str).head(200)
            try:
                parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
                if parsed.notna().mean() > 0.9:
                    out.append(col)
            except Exception:
                try:
                    parsed = pd.to_datetime(sample, errors="coerce")
                    if parsed.notna().mean() > 0.9:
                        out.append(col)
                except Exception:
                    pass
    return out


def run_health_scan(df: pd.DataFrame) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    meta: dict = {"datetime_columns": detect_datetime_columns(df)}
    n, p = df.shape
    fid = 1

    # ---- missing values ------------------------------------------------
    miss_per_col = df.isna().sum()
    total_missing = int(miss_per_col.sum())
    cells = max(n * p, 1)
    rows_with_missing = int(df.isna().any(axis=1).sum())
    if total_missing > 0:
        pct = 100.0 * total_missing / cells
        row_pct = 100.0 * rows_with_missing / max(n, 1)
        sev = SEVERITY_HIGH if pct > 20 else (SEVERITY_MODERATE if pct > 5 else SEVERITY_LOW)
        worst = miss_per_col[miss_per_col > 0].sort_values(ascending=False).head(5)
        findings.append(_mk(fid,
            category="missing_values",
            title="缺失值 (Missing Values)",
            severity=sev,
            evidence_level=EVIDENCE_MODERATE,
            stat_summary=(
                f"{pct:.1f}% 的单元格缺失；{row_pct:.1f}% 的行至少包含一个缺失值；"
                f"涉及 {int((miss_per_col > 0).sum())} / {p} 个变量。"
            ),
            evidence={
                "total_missing": total_missing,
                "cell_pct": round(pct, 2),
                "rows_with_missing": rows_with_missing,
                "row_pct": round(row_pct, 2),
                "top_columns": {k: int(v) for k, v in worst.items()},
            },
            why_it_matters=(
                "缺失会削弱统计推断的样本基础。若缺失并非完全随机（MCAR），"
                "而是与某些特征相关（如高收入者不愿填报收入），则剩余数据存在系统性偏差，"
                "基于完整样本的均值、相关系数等估计可能失真。"
            ),
            possible_causes=[
                "问卷中可选填字段导致的自然缺失",
                "数据合并（JOIN）时键不匹配产生 NaN",
                "导出或录入过程中的截断",
                "受访者对敏感问题（收入、年龄）系统性回避",
            ],
            what_it_does_not_prove="缺失本身不表明数据被篡改，绝大多数真实业务数据都含有缺失。",
            next_steps=[
                "对缺失变量做 Little's MCAR 检验或对比缺失/非缺失子群的分布",
                "评估缺失列是否参与后续建模，决定删除或插补",
            ],
        ))
        fid += 1

    # ---- exact duplicate rows -----------------------------------------
    dup_mask = df.duplicated(keep=False)
    n_dup_rows = int(dup_mask.sum())
    n_dup_exact = int(df.duplicated().sum())
    if n_dup_rows > 0:
        pct = 100.0 * n_dup_rows / max(n, 1)
        sev = SEVERITY_HIGH if pct > 10 else (SEVERITY_MODERATE if pct > 2 else SEVERITY_LOW)
        findings.append(_mk(fid,
            category="duplicates",
            title="完全重复的记录 (Duplicate Rows)",
            severity=sev,
            evidence_level=EVIDENCE_HIGH,
            stat_summary=(
                f"检测到 {n_dup_exact} 条多余重复行（涉及 {n_dup_rows} 行，占 {pct:.1f}%）。"
            ),
            evidence={
                "duplicate_rows_total": n_dup_rows,
                "redundant_copies": n_dup_exact,
                "pct": round(pct, 2),
            },
            why_it_matters=(
                "重复记录会使样本量虚增、方差被低估，并在建模时造成信息泄露"
                "（训练集与测试集出现同一条记录）。若重复恰好在关键分组中富集，"
                "还可能扭曲组间比较的结论。"
            ),
            possible_causes=[
                "多次导出/追加同一批数据",
                "日志或传感器重复写入",
                "人工复制粘贴填表",
                "为增加样本量而人为复制记录",
            ],
            what_it_does_not_prove="重复更常源于工程失误而非造假意图，需结合业务流程判断。",
            next_steps=[
                "检查重复行的主键或时间戳，确认是否为管道问题",
                "去重前评估重复是否为合法业务事件（如同一客户多次购买）",
            ],
        ))
        fid += 1

    # ---- constant columns ----------------------------------------------
    const_cols = [c for c in df.columns if df[c].dropna().nunique() <= 1]
    if const_cols:
        findings.append(_mk(fid,
            category="constant_column",
            title="常量列 (Constant Columns)",
            severity=SEVERITY_LOW,
            evidence_level=EVIDENCE_HIGH,
            stat_summary=f"{len(const_cols)} 个变量几乎无变化：{', '.join(const_cols[:8])}。",
            evidence={"columns": const_cols},
            why_it_matters="常量列不携带信息，会使相关性计算退化、方差分析报错，通常是坏管道或填充错误的信号。",
            possible_causes=["默认值填充", "配置列被错误导出", "编码错误导致所有值坍缩"],
            what_it_does_not_prove="常量列无害于其他列的可信度，只是信息量为零。",
            next_steps=["在分析前剔除常量列，并追溯其生成逻辑"],
        ))
        fid += 1

    # ---- mixed types in numeric-like columns ----------------------------
    for col in df.columns:
        s = df[col].dropna()
        if not (pd.api.types.is_string_dtype(s) or s.dtype == object) or len(s) == 0:
            continue
        as_num = pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce")
        n_num = int(as_num.notna().sum())
        if 0.3 < n_num / len(s) < 0.95:
            findings.append(_mk(fid,
                category="mixed_type",
                title=f"变量「{col}」类型混杂 (Mixed Types)",
                severity=SEVERITY_MODERATE,
                evidence_level=EVIDENCE_HIGH,
                stat_summary=f"该列 {len(s)} 个非空值中有 {len(s) - n_num} 个无法解析为数字。",
                evidence={"column": col, "numeric": n_num, "non_numeric": len(s) - n_num},
                why_it_matters="类型混杂意味着该列无法直接参与数值计算，且往往暗示录入来源不一致或单位不统一。",
                possible_causes=["Excel 单元格格式混杂", "单位后缀混入数值（如 '120kg'）", "缺失占位符写成了字符串"],
                what_it_does_not_prove="类型问题属于格式质量，与数据真实性无关。",
                next_steps=["抽取非数值样本逐一查看，制定清洗规则"],
            ))
            fid += 1

    # ---- negative values in strictly-positive-looking numeric columns ----
    for col in df.select_dtypes(include=[np.number]).columns:
        s = df[col].dropna()
        if len(s) < 10:
            continue
        neg = int((s < 0).sum())
        if 0 < neg <= max(5, 0.02 * len(s)) and (s >= 0).mean() > 0.9:
            findings.append(_mk(fid,
                category="illegal_values",
                title=f"变量「{col}」存在负值 (Negative Values)",
                severity=SEVERITY_MODERATE,
                evidence_level=EVIDENCE_HIGH,
                stat_summary=f"该列 {neg} 个负值，而其余 {(s >= 0).mean() * 100:.1f}% 的值为非负。",
                evidence={"column": col, "negatives": neg,
                          "examples": s[s < 0].head(5).round(4).tolist()},
                why_it_matters="若该变量在业务上不可能为负（如年龄、数量、价格），负值几乎必然是录入或符号错误。",
                possible_causes=["录入时误加负号", "缺失值被编码为 -1 / -999", "计算溢出"],
                what_it_does_not_prove="少量负值通常是孤立错误，不构成对整体数据真实性的质疑。",
                next_steps=["核对原始记录；确认是否为缺失编码，如是则替换为 NaN"],
            ))
            fid += 1

    # ---- categorical pollution ------------------------------------------
    for col in df.columns:
        s = df[col].dropna()
        if not (pd.api.types.is_string_dtype(s) or s.dtype == object) or len(s) < 20:
            continue
        vals = s.astype(str)
        stripped = vals.str.strip().str.lower()
        n_raw = vals.nunique()
        n_norm = stripped.nunique()
        if n_raw > n_norm * 1.15 and n_raw >= 10:
            findings.append(_mk(fid,
                category="categorical_pollution",
                title=f"分类变量「{col}」标签不统一 (Label Inconsistency)",
                severity=SEVERITY_LOW,
                evidence_level=EVIDENCE_HIGH,
                stat_summary=f"原始取值 {n_raw} 种，忽略大小写与空格后仅 {n_norm} 种。",
                evidence={"column": col, "raw_unique": n_raw, "normalized_unique": n_norm},
                why_it_matters="同一类目的多种写法会稀释分组统计，使类别频数被人为拆分。",
                possible_causes=["多来源数据合并", "手工输入无校验"],
                what_it_does_not_prove="标签不规范是维护问题，不涉及数据真伪。",
                next_steps=["按标准化后的标签重新聚合，验证分组结论是否改变"],
            ))
            fid += 1

    meta["n_findings"] = len(findings)
    return findings, meta
