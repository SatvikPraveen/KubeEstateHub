"""Scrape-time Prometheus collector.

Metrics are computed from the database when Prometheus scrapes (not by a background
loop), with a short TTL cache so that several scrapers (HA Prometheus pairs) do not
multiply database load. A failed refresh keeps serving the last good snapshot and sets
``kubeestatehub_exporter_up`` to 0 so alerts fire on staleness rather than on gaps.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator

from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector

from .source import Snapshot, Source

log = logging.getLogger(__name__)


def _num(value) -> float | None:
    return None if value is None else float(value)


class MarketCollector(Collector):
    def __init__(self, source: Source, ttl_seconds: float = 30.0, clock=time.time) -> None:
        self._source = source
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._fetched_at = float("-inf")
        self._last_ok = False
        self._last_duration = 0.0

    def _refresh(self) -> Snapshot | None:
        with self._lock:
            now = self._clock()
            if self._snapshot is not None and now - self._fetched_at < self._ttl:
                return self._snapshot
            started = time.perf_counter()
            try:
                self._snapshot = self._source.fetch()
                self._last_ok = True
                self._fetched_at = now
            except Exception as exc:
                log.warning("metrics refresh failed: %s", exc)
                self._last_ok = False
            self._last_duration = time.perf_counter() - started
            return self._snapshot

    def collect(self) -> Iterator[Metric]:
        snap = self._refresh()
        up = GaugeMetricFamily(
            "kubeestatehub_exporter_up", "1 if the last database refresh succeeded"
        )
        up.add_metric([], 1.0 if self._last_ok else 0.0)
        yield up
        dur = GaugeMetricFamily(
            "kubeestatehub_exporter_refresh_duration_seconds", "Duration of the last refresh"
        )
        dur.add_metric([], self._last_duration)
        yield dur
        if snap is None:
            return

        listings = GaugeMetricFamily(
            "kubeestatehub_listings",
            "Listings by status and property type",
            labels=["status", "property_type"],
        )
        for status, ptype, n in snap.listings:
            listings.add_metric([status, ptype], n)
        yield listings

        median = GaugeMetricFamily(
            "kubeestatehub_median_list_price_dollars",
            "Median list price of active listings (segments with >= 5 listings)",
            labels=["city", "property_type"],
        )
        for city, ptype, value in snap.median_list_price:
            median.add_metric([city, ptype], value)
        yield median

        labels = ["city", "state", "property_type"]
        families = {
            "months_of_supply": GaugeMetricFamily(
                "kubeestatehub_months_of_supply", "Months of supply", labels=labels
            ),
            "absorption_rate": GaugeMetricFamily(
                "kubeestatehub_absorption_rate", "Monthly sales / active inventory", labels=labels
            ),
            "median_days_on_market": GaugeMetricFamily(
                "kubeestatehub_median_days_on_market", "Median days on market", labels=labels
            ),
            "trend_slope_pct_per_month": GaugeMetricFamily(
                "kubeestatehub_trend_slope_percent_per_month",
                "Theil-Sen slope of log median $/sqft",
                labels=labels,
            ),
            "mann_kendall_p": GaugeMetricFamily(
                "kubeestatehub_trend_mann_kendall_p_value",
                "Mann-Kendall two-sided p-value",
                labels=labels,
            ),
        }
        direction = GaugeMetricFamily(
            "kubeestatehub_trend_direction",
            "1 for the segment's current trend direction",
            labels=[*labels, "direction"],
        )
        for row in snap.trends:
            key = [row["city"], row["state"], row["property_type"]]
            for column, family in families.items():
                value = _num(row.get(column))
                if value is not None:
                    family.add_metric(key, value)
            direction.add_metric([*key, row["trend_direction"]], 1.0)
        yield from families.values()
        yield direction

        last = GaugeMetricFamily(
            "kubeestatehub_model_run_last_success_timestamp_seconds",
            "Finish time of the latest successful run",
            labels=["pipeline"],
        )
        for pipeline, finished in snap.last_success.items():
            if finished is not None:
                last.add_metric([pipeline], finished.timestamp())
        yield last

        cv = snap.latest_metrics.get("cross_validation", {})
        for metric, help_text in (
            ("median_ape", "Cross-validated median absolute percentage error"),
            ("ppe10", "Share of cross-validated estimates within 10% of sale price"),
            ("coverage", "Empirical coverage of the conformal prediction interval"),
            ("mean_relative_width", "Mean relative width of the conformal prediction interval"),
        ):
            family = GaugeMetricFamily(f"kubeestatehub_avm_{metric}", help_text, labels=["model"])
            for model, values in cv.items():
                if metric in values:
                    family.add_metric([model], float(values[metric]))
            yield family

        if snap.latest_index is not None:
            index = GaugeMetricFamily(
                "kubeestatehub_price_index", "Latest hedonic price index (base = 100)"
            )
            index.add_metric([], snap.latest_index)
            yield index
