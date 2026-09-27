# 0001. Statistical trend classification

* Status: accepted (2026-09)

## Context
v1 called a market "up" or "down" when the mean sale price of the last two weeks
differed from the first two weeks of a 30-day window by more than ±5%. On simulated
markets with **no** trend, that rule reported a trend 62–74% of the time
(docs/research/results.md §3). Users would act on noise.

## Decision
Use the Theil–Sen slope with Sen's CI to report magnitude and uncertainty, and the
Mann–Kendall test on the log monthly median price per sqft to decide significance.
Report `up` or `down` only when p < 0.05, and `insufficient_data` below 4 qualifying
months.

## Consequences
* The false-positive rate is about 5–9% under the null, and power is 0.9 at 0.8%/month.
* Small real drifts are reported as `flat` until enough months accumulate. That is a
  deliberate bias towards not over-claiming.
* Both statistics are nonparametric and robust to outlier months. The implementation is
  cross-checked against SciPy.
