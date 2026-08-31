"""Layer 2 -- Temporal consistency: sampling gaps, level jumps, abnormal stability."""
from __future__ import annotations

import pandas as pd
import numpy as np

from backend.models import Finding, LAYER_STATISTICAL, SEVERITY_MODERATE, SEVERITY_HIGH


def _mk(idx: int, **kw) -> Finding:
    return Finding(id=f"T{idx:02d}", layer=LAYER_STATISTICAL, **kw)


def run_temporal_scan(df: pd.DataFrame, datetime_cols: list[str]) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    series_data: dict[str, dict] = {}
    fid = 1

    if not datetime_cols:
        return findings, series_data

    time_col = datetime_cols[0]
    try:
        ts = pd.to_datetime(df[time_col], errors="coerce")
    except Exception:
        return findings, series_data

    valid = ts.notna()
    if valid.sum() < 30:
        return findings, series_data

    order = np.argsort(ts[valid].values)
    ts_sorted = ts[valid].iloc[order]
    df_sorted = df[valid].iloc[order]

    # ---- sampling gaps ---------------------------------------------------
    diffs = ts_sorted.diff().dropna().dt.total_seconds()
    if len(diffs) > 10:
        med = diffs.median()
        if med > 0:
            gaps = diffs[diffs > 5 * med]
            if len(gaps) > 0:
                gap_days = gaps / 86400
                findings.append(_mk(fid,
                    category="time_gaps",
                    title="时间序列存在采样断层 (Temporal Gaps)",
                    severity=SEVERITY_MODERATE,
                    evidence_level="high",
                    stat_summary=(
                        f"中位采样间隔 {med / 86400:.1f} 天，"
                        f"检测到 {len(gaps)} 处超过 5 倍中位间隔的断层（最长 {gap_days.max():.1f} 天）。"
                    ),
                    evidence={
                        "time_column": time_col,
                        "n_gaps": int(len(gaps)),
                        "median_interval_days": round(med / 86400, 2),
                        "longest_gap_days": round(float(gap_days.max()), 2),
                    },
                    why_it_matters=(
                        "不规则的采样间隔会使基于时间索引的聚合（周报、月报）口径不一致，"
                        "并在时间序列建模中引入伪周期。若断层恰好发生在关键事件期，"
                        "可能意味着数据被选择性删除。"
                    ),
                    possible_causes=["系统停机或维护", "业务淡季停止记录", "数据被过滤或删除后导出"],
                    what_it_does_not_prove="断层是运维常见现象，与数据真实性无必然联系。",
                    next_steps=["对照业务日历确认断层期是否可解释", "重采样到规则频率后再分析"],
                ))
                fid += 1

    # ---- per-numeric-column temporal behaviour ----------------------------
    num_cols = [c for c in df_sorted.select_dtypes(include=[np.number]).columns
                if df_sorted[c].nunique() > 3]
    for col in num_cols[:10]:
        y = df_sorted[col].astype(float)
        if y.notna().sum() < 30:
            continue

        # series for dashboard
        if len(series_data) < 4:
            idx = np.linspace(0, len(y) - 1, min(len(y), 300)).astype(int)
            series_data[col] = {
                "time": [str(pd.Timestamp(ts_sorted.iloc[i]).date()) if not pd.isna(ts_sorted.iloc[i]) else None
                         for i in idx],
                "values": [None if pd.isna(v) else round(float(v), 4)
                           for v in y.iloc[idx]],
            }

        # sudden level shift: max rolling-mean diff vs overall std
        w = max(10, len(y) // 10)
        rm = y.rolling(w, center=True, min_periods=w // 2).mean()
        jumps = rm.diff().abs()
        overall_std = float(y.std())
        if overall_std > 0 and len(jumps.dropna()) > 5:
            max_jump = float(jumps.max())
            jump_ratio = max_jump / overall_std
            if jump_ratio > 1.5:
                pos = int(np.argmax(jumps.values)) if not np.isnan(jumps.values).all() else 0
                findings.append(_mk(fid,
                    category="level_shift",
                    title=f"「{col}」时间序列出现突然跳变 (Sudden Level Shift)",
                    severity=SEVERITY_HIGH if jump_ratio > 2.5 else SEVERITY_MODERATE,
                    evidence_level="moderate",
                    stat_summary=(
                        f"滚动均值最大单次变动为整体标准差的 {jump_ratio:.1f} 倍，"
                        f"发生在 {ts_sorted.iloc[min(pos, len(ts_sorted) - 1)]} 附近。"
                    ),
                    evidence={
                        "column": col,
                        "jump_to_std": round(jump_ratio, 2),
                        "overall_std": round(overall_std, 4),
                    },
                    why_it_matters=(
                        "均值水平在短期内发生远超自身波动的位移，"
                        "对应变点（change point）。它可能来自真实的业务突变"
                        "（政策、促销、事故），也可能来自口径更换、单位调整或人为插入的数据块。"
                    ),
                    possible_causes=[
                        "真实的结构性变化（促销活动、政策调整）",
                        "统计口径或单位在导出时发生变化",
                        "不同来源的数据被拼接",
                    ],
                    what_it_does_not_prove="跳变本身是常见现象，需要业务上下文才能定性。",
                    next_steps=["在跳变点前后对比其他变量是否同步变化", "追查该时段的录入流程变更记录"],
                ))
                fid += 1

        # abnormal stability: rolling std is itself too constant
        rs = y.rolling(w, min_periods=w // 2).std()
        rs = rs.dropna()
        if len(rs) >= 8 and rs.mean() > 0:
            cv_of_std = float(rs.std() / rs.mean())
            if cv_of_std < 0.10:
                findings.append(_mk(fid,
                    category="abnormal_stability",
                    title=f"「{col}」的波动率异常稳定 (Abnormally Constant Variance)",
                    severity=SEVERITY_HIGH,
                    evidence_level="moderate",
                    stat_summary=f"滚动标准差的变异系数仅 {cv_of_std:.3f}（远低于自然序列常见的 0.3+）。",
                    evidence={"column": col, "cv_of_rolling_std": round(cv_of_std, 4),
                              "rolling_std_mean": round(float(rs.mean()), 4)},
                    why_it_matters=(
                        "真实世界的时间序列几乎总会出现波动聚集（volatility clustering）——"
                        "平静期与活跃期交替。若滚动标准差在长期内几乎纹丝不动，"
                        "说明数据的二阶结构不像自然产生，更像由固定参数的生成过程输出。"
                    ),
                    possible_causes=[
                        "数据由固定均值+固定方差的随机过程模拟生成",
                        "人工填表时按固定幅度上下微调",
                        "极高精度的工业过程控制数据（合法场景）",
                    ],
                    what_it_does_not_prove="低波动也可能反映稳定的自动化流程，不能单独定罪。",
                    next_steps=["对残差做 Ljung-Box 检验查看是否存在自相关结构", "询问数据来源是否为系统直采"],
                ))
                fid += 1

    return findings, series_data
