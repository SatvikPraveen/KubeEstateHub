# Validation results

All numbers below can be regenerated. Seeds are fixed, and the commands are given for
each section. They were produced on 2026-09-27 at commit `7f90898`
(numpy 2.5, pandas 3.0, Python 3.13).

## 1. Estimator validation (Monte Carlo)

Command:

```bash
make benchmark    # = python -m analytics_worker benchmark --replications 50
```

The study uses 50 independent synthetic markets. Each has 3,000 listings over 24 months,
the data-generating process of methodology §3 with noise σ = 0.12, and a common
appreciation of 0.5%/month so the model is correctly specified.

Replications: 50, listings per market: 3000, folds: 5, nominal interval coverage: 90%, base seed: 42.

| Coefficient | True | Bias | RMSE | 95% Wald coverage |
|---|---:|---:|---:|---:|
| `log_sqft` | 0.8500 | -0.00131 | 0.01296 | 0.94 |
| `bedrooms` | -0.0200 | -0.00040 | 0.00491 | 0.88 |
| `bathrooms` | 0.0600 | +0.00091 | 0.00634 | 0.90 |
| `age` | -0.0040 | -0.00002 | 0.00013 | 0.94 |

Price index RMSE (index points, base = 100): 3.043 (sd 1.716).

| Model | Median APE | MAPE | PPE10 | PPE20 | Interval coverage | Relative width |
|---|---:|---:|---:|---:|---:|---:|
| hedonic_conformal | 8.20% | 9.81% | 58.92% | 89.79% | 0.902 ± 0.006 | 0.405 |
| comparables_conformal | 10.34% | 12.71% | 48.63% | 80.09% | 0.902 ± 0.008 | 0.530 |
**Reading the table.**

* **Coefficient recovery.**
  * Coefficients are recovered with negligible bias: every |bias| is under 10% of the
    RMSE.
  * The HC1 Wald intervals cover the true values close to nominal. The 0.88 for
    `bedrooms` falls within about two binomial standard errors of 0.95, since the
    standard error at 50 replications is 0.031. It is consistent with the mild
    small-sample anti-conservatism of HC1 when regressors are correlated, and bedrooms
    are strongly correlated with log sqft here.
  * HC3 is a drop-in alternative if this matters.
* **Accuracy floor.**
  * The hedonic AVM's median APE of 8.2% is essentially the irreducible floor. With
    log-normal noise σ = 0.12, the median of $\lvert e^{\varepsilon}-1\rvert$ is about
    $0.6745\,\sigma \approx 8.1\%$.
  * A correctly specified model cannot do better, so the gap is the price of estimation
    error.
  * Comparable sales (kNN) are about 2 points worse and have 31% wider intervals. That is
    expected when the parametric model is correct. Comparables become competitive under
    misspecification.
* **Coverage.** Both conformal intervals achieve 0.902 empirical coverage against a 0.90
  target, with a between-replication SD of about 0.007. That matches the finite-sample
  guarantee, which lies in $[1-\alpha, 1-\alpha + 1/(n+1)]$.
* **Price index.** The price-index RMSE of about 3 index points is dominated by the base
  month, which is thinly traded because listings only start selling after about 40 days
  on market. Chaining the index or choosing a base month by volume would reduce it.

## 2. Misspecification: pooled time effects

Command: `PYTHONPATH=src/analytics-worker python hack/trend_study.py` (Dallas–Austin line).

With city-specific appreciation (the default synthetic market), a pooled time-dummy
model cannot represent diverging paths. The city coefficient then estimates the level
difference *averaged over the sample window*:

$$\hat\alpha_{\text{Dallas}} \to (\alpha_D - \alpha_A) + (g_D - g_A)\,\bar m .$$

With a true level difference of −0.080, a growth difference of −0.002/month and a mean
sale month $\bar m = 12.4$, the predicted value is **−0.1048**. Across 30 replications the
observed estimate is **−0.1031** (SD 0.0066). The model behaves exactly as theory
predicts. This is why methodology §8 lists per-city indices as the next extension.

## 3. Trend classifier: size and power

Command: `PYTHONPATH=src/analytics-worker python hack/trend_study.py` (first table).

The setup is a single-city market with 2,000 listings over 18 months (about 90 sales per
month), classified at α = 0.05 over 100 replications per row.

| True drift (%/month) | Classified up | Classified down | Classified flat | Slope CI covers truth |
|---:|---:|---:|---:|---:|
| 0.00 | 0.03 | 0.06 | 0.91 | 0.91 |
| 0.20 | 0.11 | 0.00 | 0.89 | 0.91 |
| 0.40 | 0.35 | 0.00 | 0.65 | 0.91 |
| 0.80 | 0.91 | 0.00 | 0.09 | 0.91 |
| 1.21 | 1.00 | 0.00 | 0.00 | 0.91 |

* **False positives.** The empirical false-positive rate under no trend is 0.09. That is
  within about 1.4 binomial standard errors of 0.05 at 100 replications, so it is not a
  significant excess. It is still reported as observed.
* **Power** reaches 0.9 at about 0.8%/month, roughly 10% a year. Smaller drifts are
  mostly reported as `flat`, which is the intended conservative behaviour.
* **Direction errors.** The classifier never labels a rising market "down".
* **Slope interval.** Sen's interval covers the true slope 91% of the time against 95%
  nominal. It is an asymptotic interval applied to about 12 monthly points.

**Baseline: the v1 heuristic.** The previous worker compared the mean sale price of the
last two weeks with that of the first two weeks of a 30-day window, and called ±5% a
trend. `hack/trend_study.py` reproduces it on the same kind of markets with **no trend at
all**, over 300 replications:

| Listings in market | Labelled "up" | Labelled "down" | Labelled "stable" |
|---:|---:|---:|---:|
| 2,000 | 0.32 | 0.42 | 0.26 |
| 8,000 | 0.34 | 0.28 | 0.38 |

The heuristic reports a trend in flat markets **62–74% of the time**, against the new
classifier's 9%. Raw weekly means mix homes of different sizes and quality, so their
week-to-week variance dwarfs a 5% band. More data barely helps, because the window is
fixed at 30 days.

## 4. Service performance

Command: `make up && make load-test RATE=…` (k6 script `tests/load/listings-api.js`).

* **Stack:** the docker compose stack on an Apple M5 laptop. The Docker VM has 10 vCPUs
  and 8 GB. The API runs 2 gunicorn workers × 4 threads, and requests go through the
  nginx proxy.
* **Load model:** open arrival rate. The mix is 60% filtered list queries, 25% listing
  detail with valuation, 10% market summary and 5% trends, over 4,000 listings.
* **Rate limiting:** the per-client limit was raised for these runs. A single k6 source
  otherwise gets correct 429s after 600 requests a minute, as observed in a first run.
* **Duration:** one run per configuration, 60 s at plateau. Treat the numbers as
  indicative, not as a benchmark.

| Target rate | Achieved rps | p50 | p95 | p99 | Errors | Latency SLO (p99 ≤ 500 ms) |
|---:|---:|---:|---:|---:|---:|:--|
| 200 | 162 | 1.7 ms | 4.5 ms | 44 ms | 0 | met |
| 400 | 320 | 1.0 ms | 51 ms | 294 ms | 0 | met |
| 800 | 624 | 42 ms | 637 ms | 802 ms | 0 | **violated** (saturation) |

The achieved rate includes the ramp phases. The knee lies between about 320 and 620 rps
for this configuration. Saturation shows up as queueing latency, not errors. The API
sheds no requests, so the HPA (CPU 70%) must scale out before the knee. In Kubernetes,
each replica adds capacity roughly linearly until PostgreSQL connections become the limit.

**Cache ablation (null result).** Disabling Redis changed nothing measurable:

| Rate | p99 with cache | p99 without cache |
|---:|---:|---:|
| 200 | 44 ms | 46 ms |
| 400 | 294 ms | 215 ms |

At this data size the working set sits in PostgreSQL's buffer cache. Indexed queries cost
about 1 ms, so the bottleneck is Python request handling, not the database. The cache
will matter with larger tables, slower storage or expensive aggregate endpoints. It is
kept because it degrades gracefully, but this result does **not** support a claim that
it improves latency today.

## 5. Threats to validity

* **Synthetic data.** The data-generating process matches the hedonic model's functional
  form, which favours the hedonic AVM in §1. Real transaction data would test robustness
  to misspecification. The conformal guarantee does not depend on it.
* **Single hardware configuration.** Performance numbers come from one machine with one
  run each. Tail latencies on a laptop VM are noisy.
* **Temporal exchangeability.** The conformal intervals are validated under random
  k-fold splits. A time-forward backtest (train on months ≤ t, test on t + 1) is the
  stricter protocol for production AVMs. The `model_runs` history makes it possible to
  run later against real data.
