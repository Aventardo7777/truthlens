# Example Analysis — suspicious_sales.xlsx

The bundled demo dataset is a regional sales ledger that *looks* perfectly
normal at a glance — until the forensic engine starts pulling on the threads.
One click on **RUN BUNDLED DEMO** produces the following.

## Scan summary

| | |
|---|---|
| Case number | `TL-20260831-…` (auto-generated) |
| Records / columns | 1,360 rows × 12 columns |
| Integrity Score | **37 / 100 — Low Integrity** |
| Findings | 13 classes, 32 findings |

## Score breakdown

| Dimension | Score |
|---|---|
| 完整性 (Completeness) | 96 |
| 一致性 (Consistency) | 97 |
| 分布自然度 (Distribution naturalness) | 34 |
| 异常程度 (Anomaly level) | 37 |
| 重复风险 (Duplication risk) | 41 |
| 模式异常 (Pattern anomaly) | 44 |

## Selected findings (as reported)

### 1. Repeated row blocks — HIGH
> 90 pairs of completely identical rows are separated by a fixed offset of
> 600 rows. This is the signature of a verbatim copy-paste expansion.

- **Evidence:** `n_identical_pairs_at_offset: 60` and `30`, `fixed_offset: 600/900`
- **Does not prove:** duplicated rows are also common in legitimate snapshot
  structures — verify against the ETL pipeline.

### 2. Benford deviation in `cash_invoice` — HIGH
> First-digit distribution deviates from Benford's Law (MAD = 0.0421,
> χ²(8) = 263, p < 1e-49). Digit 8 is heavily over-represented.

- **Evidence:** observed 8-prefix share ~25% vs. Benford expectation 5.1%
- **Does not prove:** Benford deviation can arise from truncation, minimum/maximum
  constraints, or bounded ranges — it is a screening signal, not proof of fraud.

### 3. Near-duplicate column — HIGH
> `amount` and `total_incl_tax` correlate at r = 1.0000. One column is a
> mechanical transform of the other (`total = amount × 3.02`).

- **Does not prove:** derived columns are normal in reporting; only the
  *formula relationship* is suspicious if undocumented.

### 4. Sudden level shift — MODERATE
> `amount` shows a level jump after July 2024 that is ~1.8× the robust scale
> of the series — consistent with a spliced data source or a change of unit.

### 5. Abnormally constant variance — HIGH
> `monthly_target` has a rolling-std coefficient of variation of 0.06 —
> real-world business targets almost never hold this steady; this is what a
> fixed-parameter generator or a manually smoothed spreadsheet looks like.

### 6. Dependency anomaly vs synthetic baseline — HIGH
> Real max |r| = 1.0000; i.i.d. resampled baselines produce max |r| ≈ 0.28
> (σ ≈ 0.06). The observed dependency structure is ~12σ above what the
> marginals alone can generate.

## Why this demo works

Each planted anomaly lives in a different layer of the pipeline, so the
four-layer architecture is demonstrated end-to-end:

| Layer | Demo signal |
|---|---|
| 1 · Data Health | missing values (non-random, region-correlated) · exact duplicates |
| 2 · Statistical | extreme outliers · level shift · near-duplicate column |
| 3 · Pattern | Benford deviation · last-digit bias · repeated blocks · value pile-up · group uniformity |
| Baseline | dependency anomaly vs i.i.d. bootstrap |
| 4 · Fingerprint | six-dimension integrity score + signatures |

## Reproduce

```bash
# backend running
curl http://localhost:8000/api/demo | python -m json.tool | head
# or in the UI: click RUN BUNDLED DEMO
```
