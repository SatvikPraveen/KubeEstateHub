# Metrics service

Prometheus exporter for business indicators and **model quality**. Values are computed
from PostgreSQL at scrape time. A TTL cache (`CACHE_TTL_SECONDS`, default 30s) bounds the
database load, and a failed refresh keeps serving the last good snapshot with
`kubeestatehub_exporter_up 0`.

| Metric | Labels | Source |
|---|---|---|
| `kubeestatehub_listings` | status, property_type | `listings` |
| `kubeestatehub_median_list_price_dollars` | city, property_type | active listings |
| `kubeestatehub_months_of_supply`, `_absorption_rate`, `_median_days_on_market` | city, state, property_type | latest `market_trends` |
| `kubeestatehub_trend_slope_percent_per_month`, `_trend_mann_kendall_p_value`, `_trend_direction` | city, state, property_type(, direction) | latest `market_trends` |
| `kubeestatehub_avm_median_ape`, `_ppe10`, `_coverage`, `_mean_relative_width` | model | CV metrics of latest `model_runs` |
| `kubeestatehub_model_run_last_success_timestamp_seconds` | pipeline | `model_runs` |
| `kubeestatehub_price_index` | none | latest `price_index` |

The alert rules in `manifests/components/monitoring` use these metrics to page on stale
pipelines and on conformal coverage dropping below its nominal level (model drift).
