# 0002. Split-conformal prediction intervals for valuations

* Status: accepted (2026-09)

## Context
A point valuation without uncertainty invites over-confidence. Parametric log-normal
intervals are valid only if the hedonic model is correctly specified, which real housing
data never is (omitted location and condition variables).

## Decision
Wrap every valuation model in split-conformal prediction on log-scale absolute residuals.
Calibrate on a seeded 20% hold-out of the training sales, and report the interval and its
nominal confidence with each valuation.

## Consequences
* Coverage of at least 1 − α holds in finite samples under exchangeability for any model.
  Validated at 0.902 against 0.90 over 50 Monte Carlo markets.
* Coverage is marginal, not per segment, and breaks under distribution shift. It is
  therefore monitored (`kubeestatehub_avm_coverage`) and alerted on below 0.85.
* The model trains on 20% fewer sales. At n ≈ 3,000 the accuracy cost is negligible.
