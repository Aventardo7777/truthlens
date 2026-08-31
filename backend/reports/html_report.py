"""HTML audit report generator -- standalone, zero-dependency, forensic style."""
from __future__ import annotations

import html as _html
from datetime import datetime

_CSS = """
:root{--bg:#0b0e13;--panel:#12161e;--line:#232a36;--fg:#e8ebf0;--dim:#8b94a3;
--accent:#e8b339;--red:#e5484d;--amber:#f5a524;--green:#46a758;--blue:#4c8dff;}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;line-height:1.65;padding:40px 24px}
.wrap{max-width:900px;margin:0 auto}
.mono-dim{color:var(--dim);font-size:12px;letter-spacing:.08em;text-transform:uppercase}
h1{font-size:26px;letter-spacing:.04em;margin:6px 0 2px}
h2{font-size:16px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:40px 0 14px;border-bottom:1px solid var(--line);padding-bottom:8px}
h3{font-size:14px;margin:0 0 6px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:20px;margin:12px 0}
.score-hero{display:flex;align-items:center;gap:28px}
.score-num{font-size:84px;font-weight:700;line-height:1}
.score-verdict{font-size:18px;color:var(--accent);margin-top:4px}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;letter-spacing:.08em;border:1px solid}
.badge.high{color:var(--red);border-color:var(--red)}
.badge.moderate{color:var(--amber);border-color:var(--amber)}
.badge.low{color:var(--dim);border-color:var(--dim)}
.badge.layer{color:var(--blue);border-color:var(--blue)}
table{width:100%;border-collapse:collapse;font-size:13px;margin:10px 0}
th{text-align:left;color:var(--dim);font-weight:400;font-size:11px;letter-spacing:.08em;text-transform:uppercase;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
.finding{border:1px solid var(--line);border-radius:8px;margin:14px 0;overflow:hidden}
.finding-head{background:#171c26;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.finding-body{padding:14px 16px;font-size:13px}
.finding-body p{margin:6px 0}
.lbl{color:var(--dim);font-size:11px;letter-spacing:.1em;text-transform:uppercase}
ul{margin:6px 0 6px 18px}
.dim-bars{display:flex;flex-direction:column;gap:8px}
.dim-row{display:grid;grid-template-columns:110px 1fr 40px;gap:12px;align-items:center;font-size:13px}
.bar{height:10px;background:var(--line);border-radius:5px;overflow:hidden}
.bar>div{height:100%;border-radius:5px}
.kv{display:grid;grid-template-columns:220px 1fr;gap:6px 16px;font-size:13px}
.kv .k{color:var(--dim)}
.note{color:var(--dim);font-size:12px;font-style:italic}
code{background:#1a2029;padding:1px 5px;border-radius:4px;font-size:12px}
@media print{body{background:#fff;color:#111}.panel,.finding{border-color:#ccc}}
"""


def _esc(s) -> str:
    return _html.escape(str(s))


def _badge(sev: str) -> str:
    return f'<span class="badge {sev}">{sev.upper()}</span>'


def _layer_badge(layer: str) -> str:
    names = {"data_health": "LAYER 1 · DATA HEALTH",
             "statistical": "LAYER 2 · STATISTICAL",
             "pattern_forensics": "LAYER 3 · PATTERN",
             "baseline": "BASELINE · SYNTHETIC"}
    return f'<span class="badge layer">{names.get(layer, layer)}</span>'


def _score_color(v: int) -> str:
    if v >= 80:
        return "#46a758"
    if v >= 60:
        return "#f5a524"
    return "#e5484d"


def generate_html_report(result: dict) -> str:
    integ = result["integrity"]
    dims = integ["dimensions"]
    findings = result["findings"]

    dim_rows = "".join(
        f'<div class="dim-row"><span>{_esc(k)}</span>'
        f'<div class="bar"><div style="width:{v}%;background:{_score_color(v)}"></div></div>'
        f'<span style="text-align:right">{v}</span></div>'
        for k, v in dims.items()
    )

    cols_rows = "".join(
        f"<tr><td>{_esc(c['name'])}</td><td>{_esc(c['role'])}</td><td>{_esc(c['dtype'])}</td>"
        f"<td>{c['missing_pct']}%</td><td>{c['unique']}</td></tr>"
        for c in result["columns"]
    )

    findings_html = ""
    for f in findings:
        ev = "".join(
            f'<tr><td style="color:#8b94a3">{_esc(k)}</td><td><code>{_esc(v)}</code></td></tr>'
            for k, v in f["evidence"].items()
        )
        causes = "".join(f"<li>{_esc(c)}</li>" for c in f["possible_causes"])
        steps = "".join(f"<li>{_esc(s)}</li>" for s in f["next_steps"])
        findings_html += f"""
<div class="finding">
  <div class="finding-head">
    <div><span class="mono-dim">FINDING {_esc(f['id'])}</span>
      <h3>{_esc(f['title'])}</h3></div>
    <div style="display:flex;gap:8px;flex-shrink:0">{_layer_badge(f['layer'])}{_badge(f['severity'])}</div>
  </div>
  <div class="finding-body">
    <p><span class="lbl">Statistical summary</span><br>{_esc(f['stat_summary'])}</p>
    <p><span class="lbl">Why it matters</span><br>{_esc(f['why_it_matters'])}</p>
    <p><span class="lbl">Possible causes</span></p><ul>{causes}</ul>
    <p><span class="lbl">What this does not prove</span><br><span class="note">{_esc(f['what_it_does_not_prove'])}</span></p>
    <p><span class="lbl">Recommended next steps</span></p><ul>{steps}</ul>
    <p><span class="lbl">Evidence</span></p>
    <table>{ev}</table>
  </div>
</div>"""

    if not findings:
        findings_html = '<div class="panel"><p>No findings detected.</p></div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>TruthLens Statistical Integrity Report · {_esc(result['case_number'])}</title>
<style>{_CSS}</style></head><body><div class="wrap">

<div class="mono-dim">TRUTHLENS · STATISTICAL INTEGRITY REPORT</div>
<h1>{_esc(result['case_number'])}</h1>
<div class="mono-dim" style="margin-bottom:24px">
Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · File: {_esc(result['filename'])}
· {result['n_rows']} rows × {result['n_cols']} columns</div>

<div class="panel score-hero">
  <div><div class="score-num" style="color:{_score_color(integ['total'])}">{integ['total']}</div>
  <div class="mono-dim">INTEGRITY SCORE / 100</div></div>
  <div>
    <div class="score-verdict">{_esc(integ['verdict'])}</div>
    <p style="color:var(--dim);font-size:13px;max-width:420px">{_esc(integ['explanation'])}</p>
    <p style="font-size:13px">{len(findings)} findings ·
    {sum(1 for f in findings if f['severity']=='high')} high ·
    {sum(1 for f in findings if f['severity']=='moderate')} moderate ·
    {sum(1 for f in findings if f['severity']=='low')} low</p>
  </div>
</div>

<h2>Score Breakdown</h2>
<div class="panel dim-bars">{dim_rows}</div>

<h2>Dataset Overview</h2>
<div class="panel"><div class="kv">
<div class="k">Case number</div><div>{_esc(result['case_number'])}</div>
<div class="k">Scan ID</div><div>{_esc(result['scan_id'])}</div>
<div class="k">Rows / Columns</div><div>{result['n_rows']} / {result['n_cols']}</div>
<div class="k">Distribution fingerprint</div><div><code>{_esc(result['fingerprint']['distribution_signature'])}</code></div>
<div class="k">Correlation fingerprint</div><div><code>{_esc(result['fingerprint']['correlation_signature'])}</code></div>
<div class="k">Missingness fingerprint</div><div><code>{_esc(result['fingerprint']['missingness_signature'])}</code></div>
<div class="k">Digit fingerprint</div><div><code>{_esc(result['fingerprint']['digit_signature'])}</code></div>
</div></div>

<h2>Column Profiles</h2>
<div class="panel"><table>
<tr><th>Column</th><th>Role</th><th>DType</th><th>Missing</th><th>Unique</th></tr>
{cols_rows}</table></div>

<h2>Findings ({len(findings)})</h2>
{findings_html}

<h2>Methodology</h2>
<div class="panel" style="font-size:13px">
<p><b>Layer 1 — Data Health.</b> Missing values, exact duplicates, constant columns, mixed types, illegal values and label inconsistency.</p>
<p><b>Layer 2 — Statistical Anomalies.</b> Robust (MAD-based) z-scores and IQR fences for outliers; Pearson/Spearman correlation screening; skewness/kurtosis shape tests; temporal gaps, level shifts and variance-stability analysis.</p>
<p><b>Layer 3 — Pattern Forensics.</b> Benford first-digit conformity (χ² and Nigrini MAD), last-digit uniformity, value pile-ups, group-statistics uniformity, repeated row blocks and column-copy detection.</p>
<p><b>Synthetic Baseline.</b> I.i.d. bootstrap resampling of each column to test whether the observed dependency structure exceeds what marginal distributions alone would produce.</p>
<p><b>Integrity Score.</b> Weighted aggregation of finding severities over six dimensions (completeness, consistency, distribution naturalness, anomaly level, duplication risk, pattern anomaly).</p>
</div>

<h2>Limitations</h2>
<div class="panel" style="font-size:13px">
<p>TruthLens is a screening tool. Every finding describes a statistical observation, not intent. Benford deviation, high correlation and extreme values all have benign explanations; conversely, well-crafted fabricated data may pass every test. Statistical anomalies are grounds for investigation, never proof of fraud.</p>
</div>

<p class="note" style="margin-top:40px">TruthLens · Data Forensics &amp; Statistical Integrity Engine — generated automatically, for research and audit-support use only.</p>
</div></body></html>"""
