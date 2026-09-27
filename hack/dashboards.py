"""Grafana dashboard definitions as code (rendered to observability/grafana/*.json)."""

from __future__ import annotations

import itertools
from typing import Any

_ids = itertools.count(1)
DS = {"type": "prometheus", "uid": "${datasource}"}


def _panel(
    kind: str,
    title: str,
    exprs: list[tuple[str, str]],
    x: int,
    y: int,
    w: int = 8,
    h: int = 8,
    unit: str = "short",
    description: str = "",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": next(_ids),
        "type": kind,
        "title": title,
        "description": description,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": {"unit": unit, **extra.pop("defaults", {})}, "overrides": []},
        "targets": [
            {"refId": chr(65 + i), "expr": e, "legendFormat": legend, "datasource": DS}
            for i, (e, legend) in enumerate(exprs)
        ],
        "options": extra.pop("options", {}),
        **extra,
    }


def _row(title: str, y: int) -> dict[str, Any]:
    return {
        "id": next(_ids),
        "type": "row",
        "title": title,
        "collapsed": False,
        "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
        "panels": [],
    }


def overview() -> dict[str, Any]:
    api = 'job="listings-api",route!~"/livez|/readyz|/metrics|/health"'

    def thresholds(*steps: tuple[float | None, str]) -> dict[str, Any]:
        return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in steps]}

    panels = [
        _row("Service level objectives (listings API)", 0),
        _panel(
            "stat",
            "Availability (30d)",
            [
                (
                    f'1 - (sum(increase(http_requests_total{{{api},status=~"5.."}}[30d])) '
                    f"/ sum(increase(http_requests_total{{{api}}}[30d])))",
                    "",
                )
            ],
            0,
            1,
            6,
            5,
            unit="percentunit",
            description="SLO: 99.5% of requests are not 5xx",
            defaults={"decimals": 3, "thresholds": thresholds((None, "red"), (0.995, "green"))},
        ),
        _panel(
            "stat",
            "Availability error budget remaining",
            [
                (
                    f'1 - (sum(increase(http_requests_total{{{api},status=~"5.."}}[30d])) '
                    f"/ sum(increase(http_requests_total{{{api}}}[30d]))) / 0.005",
                    "",
                )
            ],
            6,
            1,
            6,
            5,
            unit="percentunit",
            defaults={"thresholds": thresholds((None, "red"), (0.25, "orange"), (0.5, "green"))},
        ),
        _panel(
            "stat",
            "Requests ≤ 500 ms (30d)",
            [
                (
                    f'sum(increase(http_request_duration_seconds_bucket{{{api},le="0.5"}}[30d])) '
                    f"/ sum(increase(http_request_duration_seconds_count{{{api}}}[30d]))",
                    "",
                )
            ],
            12,
            1,
            6,
            5,
            unit="percentunit",
            description="SLO: 99% of requests complete in ≤ 500 ms",
            defaults={"decimals": 3, "thresholds": thresholds((None, "red"), (0.99, "green"))},
        ),
        _panel(
            "stat",
            "Burn rate (1h, availability)",
            [("kubeestatehub:api_error_ratio:rate1h / 0.005", "")],
            18,
            1,
            6,
            5,
            unit="x",
            description="14.4x pages (2% of budget per hour)",
            defaults={"thresholds": thresholds((None, "green"), (1, "orange"), (14.4, "red"))},
        ),
        _row("Traffic, errors, latency (RED)", 6),
        _panel(
            "timeseries",
            "Request rate by route",
            [(f"sum by (route) (rate(http_requests_total{{{api}}}[5m]))", "{{route}}")],
            0,
            7,
            unit="reqps",
        ),
        _panel(
            "timeseries",
            "Error ratio vs SLO",
            [
                ("kubeestatehub:api_error_ratio:rate5m", "5xx ratio (5m)"),
                ("vector(0.005)", "SLO budget"),
            ],
            8,
            7,
            unit="percentunit",
        ),
        _panel(
            "timeseries",
            "Latency quantiles",
            [
                (
                    f"histogram_quantile({q}, sum by (le) (rate(http_request_duration_seconds_bucket{{{api}}}[5m])))",
                    f"p{int(q * 100)}",
                )
                for q in (0.5, 0.95, 0.99)
            ],
            16,
            7,
            unit="s",
        ),
        _row("Valuation model quality", 15),
        _panel(
            "timeseries",
            "Conformal interval coverage (CV)",
            [("kubeestatehub_avm_coverage", "{{model}}"), ("vector(0.9)", "nominal 90%")],
            0,
            16,
            unit="percentunit",
            description="Alert below 85% (> 9 SD from nominal)",
            defaults={"min": 0.7, "max": 1},
        ),
        _panel(
            "timeseries",
            "Median absolute percentage error (CV)",
            [("kubeestatehub_avm_median_ape", "{{model}}")],
            8,
            16,
            unit="percentunit",
        ),
        _panel(
            "stat",
            "Hours since last successful pipeline",
            [("(time() - max(kubeestatehub_model_run_last_success_timestamp_seconds)) / 3600", "")],
            16,
            16,
            unit="h",
            defaults={"thresholds": thresholds((None, "green"), (26, "orange"), (36, "red"))},
        ),
        _row("Market", 24),
        _panel(
            "timeseries",
            "Hedonic price index (base = 100)",
            [("kubeestatehub_price_index", "index")],
            0,
            25,
        ),
        _panel(
            "bargauge",
            "Months of supply by city",
            [('kubeestatehub_months_of_supply{property_type="all"}', "{{city}}")],
            8,
            25,
            options={"orientation": "horizontal", "displayMode": "gradient"},
        ),
        _panel(
            "table",
            "Trend slope %/month (Theil-Sen) and Mann-Kendall p",
            [
                ('kubeestatehub_trend_slope_percent_per_month{property_type="all"}', "{{city}}"),
                ('kubeestatehub_trend_mann_kendall_p_value{property_type="all"}', "{{city}}"),
            ],
            16,
            25,
            options={"showHeader": True},
        ),
        _row("Data platform", 33),
        _panel(
            "timeseries",
            "Listings by status",
            [("sum by (status) (kubeestatehub_listings)", "{{status}}")],
            0,
            34,
        ),
        _panel(
            "timeseries",
            "PostgreSQL connections",
            [
                ("sum by (state) (pg_stat_activity_count)", "{{state}}"),
                ("max(pg_settings_max_connections)", "max"),
            ],
            8,
            34,
        ),
        _panel(
            "timeseries",
            "API cache hit ratio",
            [
                (
                    'sum(rate(listings_cache_events_total{outcome="hit"}[5m]))'
                    " / sum(rate(listings_cache_events_total[5m]))",
                    "hit ratio",
                )
            ],
            16,
            34,
            unit="percentunit",
        ),
    ]
    return {
        "uid": "kubeestatehub-overview",
        "title": "KubeEstateHub · SLOs, model quality and market",
        "tags": ["kubeestatehub"],
        "timezone": "utc",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "1m",
        "time": {"from": "now-24h", "to": "now"},
        "templating": {
            "list": [
                {
                    "name": "datasource",
                    "type": "datasource",
                    "query": "prometheus",
                    "label": "Data source",
                    "current": {},
                }
            ]
        },
        "annotations": {"list": []},
        "panels": panels,
    }


DASHBOARDS = {"kubeestatehub-overview.json": overview}
