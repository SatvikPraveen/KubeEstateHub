from datetime import UTC, datetime

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from metrics_service.app import create_app
from metrics_service.collector import MarketCollector
from metrics_service.source import Snapshot

SNAPSHOT = Snapshot(
    listings=[("active", "residential", 10), ("sold", "residential", 4)],
    median_list_price=[("Austin", "residential", 450000.0)],
    trends=[
        {
            "city": "Austin",
            "state": "TX",
            "property_type": "all",
            "months_of_supply": 3.5,
            "absorption_rate": 0.28,
            "median_days_on_market": 31.0,
            "n_sales": 40,
            "trend_slope_pct_per_month": 0.6,
            "mann_kendall_p": 0.01,
            "trend_direction": "up",
        },
        {
            "city": "Tampa",
            "state": "FL",
            "property_type": "residential",
            "months_of_supply": None,
            "absorption_rate": None,
            "median_days_on_market": None,
            "n_sales": 0,
            "trend_slope_pct_per_month": None,
            "mann_kendall_p": None,
            "trend_direction": "insufficient_data",
        },
    ],
    last_success={"market-analytics": datetime(2026, 1, 1, tzinfo=UTC)},
    latest_metrics={
        "cross_validation": {
            "hedonic_conformal": {"median_ape": 0.08, "coverage": 0.9, "ppe10": 0.6}
        }
    },
    latest_index=104.2,
)


class FakeSource:
    def __init__(self, snapshot=SNAPSHOT):
        self.snapshot = snapshot
        self.calls = 0
        self.fail = False

    def fetch(self):
        self.calls += 1
        if self.fail:
            raise ConnectionError("db down")
        return self.snapshot

    def ping(self):
        if self.fail:
            raise ConnectionError("db down")


def scrape(collector) -> str:
    registry = CollectorRegistry()
    registry.register(collector)
    return generate_latest(registry).decode()


def value(text: str, series: str) -> float:
    for line in text.splitlines():
        if line.startswith(series + " "):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"{series} not found")


def test_exports_business_and_model_quality_metrics():
    text = scrape(MarketCollector(FakeSource()))
    assert value(text, 'kubeestatehub_listings{property_type="residential",status="active"}') == 10
    assert (
        value(
            text,
            'kubeestatehub_median_list_price_dollars{city="Austin",property_type="residential"}',
        )
        == 450000
    )
    assert (
        value(text, 'kubeestatehub_months_of_supply{city="Austin",property_type="all",state="TX"}')
        == 3.5
    )
    assert (
        value(
            text,
            'kubeestatehub_trend_direction{city="Austin",direction="up",property_type="all",state="TX"}',
        )
        == 1
    )
    assert value(text, 'kubeestatehub_avm_coverage{model="hedonic_conformal"}') == 0.9
    assert value(text, "kubeestatehub_price_index") == pytest.approx(104.2)
    assert value(
        text, 'kubeestatehub_model_run_last_success_timestamp_seconds{pipeline="market-analytics"}'
    ) == pytest.approx(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
    assert value(text, "kubeestatehub_exporter_up") == 1
    # null indicators are omitted rather than exported as 0
    assert 'kubeestatehub_months_of_supply{city="Tampa"' not in text


def test_ttl_cache_bounds_database_load():
    now = [0.0]
    source = FakeSource()
    collector = MarketCollector(source, ttl_seconds=30, clock=lambda: now[0])
    scrape(collector)
    scrape(collector)
    assert source.calls == 1
    now[0] = 31
    scrape(collector)
    assert source.calls == 2


def test_failed_refresh_serves_stale_snapshot_and_flags_down():
    now = [0.0]
    source = FakeSource()
    collector = MarketCollector(source, ttl_seconds=1, clock=lambda: now[0])
    scrape(collector)
    source.fail = True
    now[0] = 5
    text = scrape(collector)
    assert value(text, "kubeestatehub_exporter_up") == 0
    assert "kubeestatehub_listings{" in text  # last good data still exported


def test_no_data_yet_exports_only_health():
    source = FakeSource()
    source.fail = True
    text = scrape(MarketCollector(source))
    assert value(text, "kubeestatehub_exporter_up") == 0
    assert "kubeestatehub_listings" not in text


def test_http_endpoints():
    source = FakeSource()
    client = create_app(source, ttl_seconds=0).test_client()
    assert client.get("/livez").status_code == 200
    assert client.get("/readyz").status_code == 200
    body = client.get("/metrics").get_data(as_text=True)
    assert "kubeestatehub_listings" in body
    assert "process_cpu_seconds_total" in body or "python_info" in body
    source.fail = True
    assert client.get("/readyz").status_code == 503
    assert client.get("/livez").status_code == 200


def test_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app()
