# TruthLens Architecture

TruthLens runs a **four-layer forensic pipeline**. The statistics engine
(Python) computes evidence; a deterministic explanation layer translates it
into plain language. An LLM can optionally be plugged in to enrich narrative —
but never to *decide* whether data is fraudulent.

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14 · TS · dark forensic-terminal UI)         │
│  Upload → Scan animation → Dashboard → Investigator Mode        │
└───────────────▲───────────────────────────────┬─────────────────┘
                │ HTTP (fetch, CORS)            │ report export
                │                               ▼
┌───────────────┴───────────────────────────────────────────────┐
│  FastAPI (backend/api/main.py)                                │
│  /api/analyze · /api/demo · /api/analyses/{id}/report        │
└───────────────▲───────────────────────────────────────────────┘
                │
┌───────────────┴───────────────────────────────────────────────┐
│  Analysis Engine (backend/analysis/)                          │
│                                                               │
│  Layer 1  Data Health      quality.py                         │
│  Layer 2  Statistical      outliers.py correlation.py         │
│                            distribution.py temporal.py        │
│  Layer 3  Pattern          benford.py pattern.py              │
│  Baseline Synthetic        synthetic.py                       │
│  Layer 4  Fingerprint      fingerprint.py                     │
│            + Integrity Score                                  │
└───────────────┬───────────────────────────────────────────────┘
                │
        ┌───────▼────────┐    ┌───────────────────────┐
        │ SQLite storage │    │ Reports: HTML / PDF / │
        │ (scan history) │    │ JSON                  │
        └────────────────┘    └───────────────────────┘
```

## The four layers

1. **Data Health** — schema-level hygiene: missingness, duplicates, constant
   columns, mixed types, illegal values, label pollution.
2. **Statistical Anomalies** — robust z-scores (MAD-based), IQR fences,
   Pearson/Spearman correlation screening, skewness/kurtosis, temporal gaps,
   level shifts, volatility-stability checks.
3. **Pattern Forensics** — Benford first-digit conformity (χ² + Nigrini MAD),
   last-digit uniformity, value pile-ups, cross-group statistic uniformity,
   repeated-row-block detection, column-copy detection.
4. **Synthetic Baseline** — i.i.d. bootstrap per column; compares the real
   dependency structure against what marginals alone would generate.

## Evidence model

Every detection becomes a `Finding`:

```
id, layer, category, severity, evidence_level
stat_summary, evidence
why_it_matters
possible_causes[]
what_it_does_not_prove
next_steps[]
```

**`what_it_does_not_prove` is mandatory** — TruthLens never states "this is
fabricated". It reports evidence and plausible causes.

## Integrity Score

Six dimensions (完整性 / 一致性 / 分布自然度 / 异常程度 / 重复风险 / 模式异常)
each start at 100 and are penalized by the severities of findings that map to
them. The total is a weighted combination, capped 5–98.

## API surface

| Method | Path | Description |
|---|---|---|
| GET  | `/api/health` | liveness probe |
| POST | `/api/analyze` | upload CSV/Excel → full scan result |
| GET  | `/api/demo` | run bundled `suspicious_sales.xlsx` |
| GET  | `/api/analyses` | list past scans (SQLite) |
| GET  | `/api/analyses/{id}` | fetch a scan result |
| GET  | `/api/analyses/{id}/report?format=html\|pdf\|json` | export report |
