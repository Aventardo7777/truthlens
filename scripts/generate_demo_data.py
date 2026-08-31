"""Generate the bundled demo dataset: suspicious_sales.xlsx

Design: a regional sales ledger that *looks* perfectly normal at a glance,
but contains seven carefully planted forensic signals:

  1. Exact duplicate rows  (copy-paste expansion, ~6%)
  2. Repeated row blocks   (rows 600-659 duplicated verbatim)
  3. Extreme outliers      (a few absurdly large deal amounts)
  4. Near-duplicate column (total = 3.02 * amount, a mechanical formula)
  5. Abnormally stable variance in a quarterly series (tampered)
  6. Benford + last-digit deviation in one money column (manually keyed)
  7. Missing values scattered in a non-random pattern
  8. A sudden level shift mid-series (data splice)

Run:  python scripts/generate_demo_data.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(20260831)
N = 1200

# ---------------------------------------------------------------- base data
dates = pd.date_range("2024-01-01", periods=N, freq="16h")
regions = np.array(["华东", "华北", "华南", "西南", "东北"])
region_col = rng.choice(regions, size=N, p=[0.30, 0.25, 0.20, 0.15, 0.10])
salesperson = np.array([f"SP-{i:03d}" for i in rng.integers(1, 42, size=N)])
product = rng.choice(["标准版", "专业版", "企业版", "旗舰版"], size=N, p=[0.4, 0.3, 0.2, 0.1])

# units: mildly seasonal, right-skewed
units = rng.poisson(lam=8, size=N).astype(float) + rng.exponential(4, size=N)
units = np.round(units).clip(1, None)

# unit price by product tier
price_map = {"标准版": 320.0, "专业版": 580.0, "企业版": 1200.0, "旗舰版": 2100.0}
noise = rng.normal(1.0, 0.08, size=N)
unit_price = np.array([price_map[p] for p in product]) * noise
unit_price = np.round(unit_price, 2)

# amount = units * unit_price (real dependency)
amount = np.round(units * unit_price, 2)

# ---------------------------------------------------------------- anomalies
# (4) near-duplicate column: total = amount * 3.02 exactly (tax+multiply formula)
total = np.round(amount * 3.02, 2)

# (5) abnormally stable monthly target series -- 'monthly_target' is the
#     tampered spreadsheet column: constant base level + tiny fixed noise,
#     so its rolling variance barely moves across the whole period
monthly_target = np.array([245000.0 + rng.normal(0, 400) for _ in range(N)])
monthly_target = np.round(monthly_target, 2)

# (8) level shift: unit prices jump 350% after July 2024 (spliced data source)
shift_mask = dates > pd.Timestamp("2024-07-01")
unit_price[shift_mask] = np.round(unit_price[shift_mask] * 4.5, 2)
amount = np.round(units * unit_price, 2)
total = np.round(amount * 3.02, 2)

# (6) manually keyed 'discount' column with digit preferences:
#     discount avoids leading 1s and over-uses 8 (lucky number keying)
discount = []
for _ in range(N):
    d = rng.choice([3, 5, 6, 7, 8, 8, 8, 9, 12, 15])  # heavy 8s, few 1-leading
    cents = rng.choice([.08, .18, .28, .38, .48, .58, .68, .88])  # 8-ending tails
    discount.append(round(float(d) + cents, 2))
discount = np.array(discount)

# (6b) hand-entered cash invoice amounts: log-uniform base (≈ Benford) with
#      ~20% of values replaced by "nice" 8-prefixed numbers (manual keying)
#      -> a clear, classic Benford deviation for accounting-style auditing
base_cash = np.exp(rng.uniform(np.log(100), np.log(480000), N))
n_fake = int(N * 0.20)
fake_idx = rng.choice(N, n_fake, replace=False)
base_cash[fake_idx] = 8 * 10 ** rng.integers(1, 5, n_fake) + 0.88
cash_invoice = np.round(base_cash, 2)

# (3) extreme outliers in amount
outlier_idx = rng.choice(N, size=6, replace=False)
amount[outlier_idx] = amount[outlier_idx] * rng.uniform(15, 40, size=6).round(1)
total[outlier_idx] = np.round(amount[outlier_idx] * 3.02, 2)

# (7) non-random missingness: 华南 records often lack discount
miss_mask = (region_col == "华南") & (rng.random(N) < 0.45)
discount[miss_mask] = np.nan

df = pd.DataFrame({
    "order_id": [f"SO-2024-{i:05d}" for i in range(N)],
    "order_date": dates.strftime("%Y-%m-%d %H:%M"),
    "region": region_col,
    "salesperson": salesperson,
    "product": product,
    "units": units.astype(int),
    "unit_price": unit_price,
    "amount": amount,
    "total_incl_tax": total,
    "discount": discount,
    "cash_invoice": cash_invoice,
    "monthly_target": monthly_target,
})

# (1)+(2) duplicates: append copied blocks verbatim at the tail (order_id
# keeps its original value -- exactly like a real copy-paste expansion).
# Deliberately NOT re-sorted: a pasted block stays contiguous, which is
# itself a forensic signal (repeated row blocks).
block_a = df.iloc[600:660].copy()          # 60-row verbatim block
block_b = df.iloc[900:930].copy()          # 30-row second block
scattered = df.sample(70, random_state=7).copy()  # scattered exact dupes
tampered = pd.concat([df, block_a, block_b, scattered], ignore_index=True)

out = Path(__file__).resolve().parent.parent / "datasets" / "examples"
out.mkdir(parents=True, exist_ok=True)
tampered.to_excel(out / "suspicious_sales.xlsx", index=False)

print(f"demo dataset written: {out / 'suspicious_sales.xlsx'}")
print(f"rows={len(tampered)} cols={tampered.shape[1]}")
