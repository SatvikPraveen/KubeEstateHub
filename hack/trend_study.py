#!/usr/bin/env python3
"""Size/power study of the trend classifier and a misspecification check of the pooled
hedonic index (docs/research/results.md, sections 3 and 4).

    PYTHONPATH=src/analytics-worker python hack/trend_study.py
"""

from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd

from analytics_worker.hedonic import fit_hedonic, sales_sample
from analytics_worker.market import compute_market_trends
from analytics_worker.synthetic import GroundTruth, generate_market


def single(growth):
    base = GroundTruth()
    city = replace(base.cities["Austin"], monthly_growth=growth, weight=1.0)
    return replace(base, cities={"Austin": city})


reps = 100
print(
    "| True drift (%/month) | Classified up | Classified down | Classified flat | Slope CI covers truth |"
)
print("|---:|---:|---:|---:|---:|")
for g in (0.0, 0.002, 0.004, 0.008, 0.012):
    up = down = flat = cover = 0
    for r in range(reps):
        df, _ = generate_market(2000, seed=1000 + r, months=18, truth=single(g))
        snap = next(
            s for s in compute_market_trends(df, as_of=date(2025, 6, 30)) if s.property_type is None
        )
        up += snap.trend_direction == "up"
        down += snap.trend_direction == "down"
        flat += snap.trend_direction == "flat"
        t = 100 * np.expm1(g)
        cover += snap.trend_slope_ci_low <= t <= snap.trend_slope_ci_high
    print(
        f"| {100 * np.expm1(g):.2f} | {up / reps:.2f} | {down / reps:.2f} | {flat / reps:.2f} | {cover / reps:.2f} |"
    )

# misspecification: city-specific growth with pooled time dummies
ests = []
for r in range(30):
    df, truth = generate_market(4000, seed=2000 + r)
    m = fit_hedonic(sales_sample(df))
    ests.append(m.coefficient("city[Dallas]")[0])
s = sales_sample(generate_market(4000, seed=2000)[0])
mean_month = ((s["period"].dt.year - 2024) * 12 + s["period"].dt.month - 1).mean()
gt = GroundTruth().cities
pred = (gt["Dallas"].effect - gt["Austin"].effect) + (
    gt["Dallas"].monthly_growth - gt["Austin"].monthly_growth
) * mean_month
print(
    f"\nDallas-Austin: true level {gt['Dallas'].effect - gt['Austin'].effect:.3f}, mean sale month {mean_month:.1f}, "
    f"predicted pooled estimate {pred:.4f}, observed mean {np.mean(ests):.4f} (sd {np.std(ests, ddof=1):.4f}, 30 reps)"
)


def v1_rule(df, as_of):
    """The v1 worker's heuristic, reproduced for comparison: weekly mean sale price over the
    last 30 days; last-two-weeks mean vs first-two-weeks mean; +/-5% => up/down."""
    start = as_of - timedelta(days=30)
    sold = pd.to_datetime(df.sold_date)
    s = df[(df.status == "sold") & (sold > pd.Timestamp(start)) & (sold <= pd.Timestamp(as_of))]
    weeks = (
        s.assign(w=pd.to_datetime(s.sold_date).dt.to_period("W")).groupby("w")["sale_price"].mean()
    )
    weeks = weeks.sort_index()
    if len(weeks) < 2:
        return "insufficient"
    recent = weeks.iloc[-2:].mean()
    older = weeks.iloc[:2].mean() if len(weeks) >= 4 else recent
    return "up" if recent > older * 1.05 else "down" if recent < older * 0.95 else "stable"


print("\nv1 heuristic on markets with NO trend (300 replications):")
for n in (2000, 8000):
    labels = [
        v1_rule(
            generate_market(n, seed=5000 + r, months=18, truth=single(0.0))[0], date(2025, 6, 30)
        )
        for r in range(300)
    ]
    share = pd.Series(labels).value_counts(normalize=True).round(3).to_dict()
    print(f"  {n} listings: {share}")
