# Service level objectives

## SLIs and SLOs

Both SLOs apply to the listings API, measured at the service over a rolling 30 days.
Probe and metrics routes (`/livez`, `/readyz`, `/health`, `/metrics`) are excluded.

| SLO | SLI (PromQL source) | Target | Error budget |
|---|---|---|---|
| Availability | share of requests that are not 5xx (`http_requests_total{status=~"5.."}`) | 99.5% | 0.5%, about 3.6 h of full outage in 30 days |
| Latency | share of requests completing in ≤ 500 ms (`http_request_duration_seconds_bucket{le="0.5"}`) | 99% | 1% of requests may be slower |

**Why these numbers.**

* **Availability.** The API serves an analytics dashboard, not a transactional system,
  so 99.5% leaves room for single-replica PostgreSQL maintenance.
* **Latency.** 500 ms is the point where the dashboard feels sluggish. The load test
  ([results.md](results.md) §4) shows p99 near 44 ms at 200 rps per two-worker replica,
  so the target leaves headroom for noisy neighbours.
* **Metric design.** Histogram buckets include 0.5 s exactly, which makes the latency
  SLI an exact count rather than an interpolated quantile.

Model quality has its own objectives. They are not user-facing SLOs, but they are
alerting thresholds:

| Objective | Metric | Threshold | Rationale |
|---|---|---|---|
| Valuation interval calibration | `kubeestatehub_avm_coverage{model="hedonic_conformal"}` | ≥ 0.85 (nominal 0.90) | With about 3,000 CV sales, the SD of empirical coverage is $\sqrt{0.9\cdot0.1/3000}\approx0.0055$. So 0.85 is more than 9 SD from nominal, which means real miscalibration such as distribution shift, not noise |
| Valuation accuracy | `kubeestatehub_avm_median_ape` | ≤ 15% | about twice the 8.2% achieved on validation data |
| Freshness | `time() - kubeestatehub_model_run_last_success_timestamp_seconds` | ≤ 36 h | the pipeline runs daily, so one missed run is tolerated |

## Burn-rate alerting

Alerts use the multi-window, multi-burn-rate scheme from *The Site Reliability Workbook*,
ch. 5. The burn rate is the error ratio divided by the budget: a burn rate of 1 uses
exactly the whole budget in 30 days.

| Severity | Long window | Short window | Burn rate | Budget spent before firing |
|---|---|---|---|---|
| page | 1 h | 5 m | 14.4 | 2% |
| page | 6 h | 30 m | 6 | 5% |
| ticket | 1 d | 2 h | 3 | 10% |
| ticket | 3 d | 6 h | 1 | 10% |

An alert requires both windows to exceed the threshold. The long window gives
significance, and the short window makes the alert resolve quickly once the problem
stops. The recording rules (`kubeestatehub:api_error_ratio:rate{5m,30m,1h,2h,6h,1d,3d}`)
keep evaluation cheap.

Everything above is tested with `promtool test rules`
(`observability/prometheus/rules.test.yaml`):

* A 10% error incident that starts after an hour of healthy traffic does **not** page at
  +10 min, because only the 5-minute window burns. It **does** page at +65 min.
* A 0.1% error rate never alerts.
* Probe traffic with 100% errors is ignored.
* The latency, coverage and staleness alerts fire exactly when specified.

## Error budget policy

* **Budget remaining > 50%.** Ship freely. Chaos experiments (`experiments/chaos`) are
  allowed in staging.
* **25–50%.** Releases need a rollback plan. Prioritise reliability items from recent
  incidents.
* **< 25%.** Freeze feature releases for the API. Only fixes and reliability work ship
  until the budget recovers.
* **Exhausted.** Postmortem required. Freeze until the 30-day window rolls past the
  incident.

The Grafana dashboard (`observability/grafana/kubeestatehub-overview.json`) shows the
remaining budget, the 1 h burn rate, RED metrics per route and all model-quality signals.
