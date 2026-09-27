from datetime import date

import pytest

from analytics_worker.pipeline import PipelineConfig, run_pipeline
from analytics_worker.repository import PostgresRepository
from analytics_worker.sync import validate_records
from analytics_worker.synthetic import generate_market

pytestmark = pytest.mark.integration


def test_seed_pipeline_roundtrip(clean_db):
    import psycopg

    repo = PostgresRepository(clean_db)
    df, _ = generate_market(1200, seed=3, start=date(2024, 6, 1), months=18)
    assert repo.upsert_listings(df.to_dict("records")) == len(df)
    assert repo.upsert_listings(df.head(10).to_dict("records")) == 10  # idempotent upsert

    loaded = repo.load_listings()
    assert len(loaded) == len(df)
    assert set(loaded["status"]) <= {"active", "sold", "withdrawn"}

    result = run_pipeline(
        repo, PipelineConfig(as_of=date(2025, 11, 30), seed=2, cv_folds=3), code_version="it"
    )
    with psycopg.connect(clean_db) as conn:
        run = conn.execute(
            "SELECT status, code_version, random_seed, metrics->>'n_sales' FROM model_runs "
            "WHERE id = %s",
            (result.run_id,),
        ).fetchone()
        assert run == ("succeeded", "it", 2, str(result.metrics["n_sales"]))
        n_trends = conn.execute("SELECT count(*) FROM market_trends").fetchone()[0]
        assert n_trends == result.metrics["n_segments"]
        base = conn.execute(
            "SELECT index_value FROM price_index WHERE model_run_id = %s ORDER BY period LIMIT 1",
            (result.run_id,),
        ).fetchone()[0]
        assert float(base) == 100.0
        n_val = conn.execute(
            "SELECT count(*) FROM property_valuations WHERE model_run_id = %s", (result.run_id,)
        ).fetchone()[0]
        assert n_val == result.metrics["n_valuations"] > 0

    # a re-run upserts trends (unique per segment/period) and adds a new provenance row
    run_pipeline(repo, PipelineConfig(as_of=date(2025, 11, 30), seed=2, cv_folds=3))
    with psycopg.connect(clean_db) as conn:
        assert conn.execute("SELECT count(*) FROM market_trends").fetchone()[0] == n_trends
        assert conn.execute("SELECT count(*) FROM model_runs").fetchone()[0] == 2


def test_sync_records_satisfy_database_constraints(clean_db):
    rows = [
        {
            "mls_number": "S1",
            "title": "Sold home",
            "property_type": "residential",
            "status": "sold",
            "price": "400000",
            "sale_price": "390000",
            "listing_date": "2025-01-01",
            "sold_date": "2025-02-01",
            "address": "1 Main",
            "city": "Austin",
            "state": "tx",
            "zip_code": "78701",
            "square_feet": "2000",
        }
    ]
    valid, res = validate_records(rows)
    assert res.failed == 0
    assert PostgresRepository(clean_db).upsert_listings(valid) == 1


def test_listings_api_against_postgres(clean_db):
    from listings_api.app import create_app
    from listings_api.cache import ResponseCache
    from listings_api.config import Settings

    repo = PostgresRepository(clean_db)
    df, _ = generate_market(900, seed=9, start=date(2024, 9, 1), months=15)
    repo.upsert_listings(df.to_dict("records"))
    run_pipeline(repo, PipelineConfig(as_of=date(2025, 11, 30), seed=1, cv_folds=3))

    settings = Settings(database_url=clean_db, rate_limit_enabled=False, trusted_proxies=0)
    client = create_app(settings, cache=ResponseCache(None, 1)).test_client()
    assert client.get("/readyz").status_code == 200

    page = client.get("/api/v1/listings?city=Austin&sort=-price&per_page=5").json
    prices = [row["price"] for row in page["listings"]]
    assert prices == sorted(prices, reverse=True)
    assert page["pagination"]["total"] == int(
        ((df.city == "Austin") & (df.status == "active")).sum()
    )

    listing_id = page["listings"][0]["id"]
    detail = client.get(f"/api/v1/listings/{listing_id}").json["listing"]
    assert detail["valuation"]["interval_low"] < detail["valuation"]["estimated_value"]

    created = client.post(
        "/api/v1/listings",
        json={
            "mls_number": "IT-1",
            "title": "Integration home",
            "property_type": "residential",
            "price": 500000,
            "address": "2 Test Rd",
            "city": "Austin",
            "state": "TX",
            "zip_code": "78702",
            "square_feet": 2000,
        },
    )
    assert created.status_code == 201
    assert created.json["listing"]["price_per_sqft"] == 250.0
    new_id = created.json["listing"]["id"]
    assert (
        client.post("/api/v1/listings", json={**created.json["listing"]} | {"id": None}).status_code
        == 422
    )
    conflict = client.patch(f"/api/v1/listings/{new_id}", json={"status": "sold"})
    assert conflict.status_code == 422  # DB check constraint surfaces as problem details
    assert client.delete(f"/api/v1/listings/{new_id}").status_code == 204

    summary = client.get("/api/v1/market/summary").json["summary"]
    assert summary["active_listings"] > 0
    assert set(summary["by_property_type"]) <= {"residential", "multi_family", "commercial"}
    assert client.get("/api/v1/market/trends?city=Austin").json["trends"]
    index = client.get("/api/v1/market/price-index").json
    assert index["series"][0]["index_value"] == 100.0
    assert client.get("/api/v1/model-runs/latest").json["model_run"]["status"] == "succeeded"


def test_metrics_service_against_postgres(clean_db):
    from prometheus_client import CollectorRegistry, generate_latest

    from metrics_service.collector import MarketCollector
    from metrics_service.source import PostgresSource

    repo = PostgresRepository(clean_db)
    df, _ = generate_market(900, seed=10, start=date(2024, 9, 1), months=15)
    repo.upsert_listings(df.to_dict("records"))
    run_pipeline(repo, PipelineConfig(as_of=date(2025, 11, 30), seed=1, cv_folds=3))

    registry = CollectorRegistry()
    registry.register(MarketCollector(PostgresSource(clean_db)))
    text = generate_latest(registry).decode()
    assert "kubeestatehub_exporter_up 1.0" in text
    assert 'kubeestatehub_avm_coverage{model="hedonic_conformal"}' in text
    assert (
        'kubeestatehub_model_run_last_success_timestamp_seconds{pipeline="market-analytics"}'
        in text
    )
    assert "kubeestatehub_price_index " in text


def test_api_readiness_requires_schema_version(clean_db):
    import psycopg

    from listings_api.app import create_app
    from listings_api.cache import ResponseCache
    from listings_api.config import Settings
    from listings_api.repository import REQUIRED_SCHEMA_VERSION

    client = create_app(
        Settings(database_url=clean_db, rate_limit_enabled=False, trusted_proxies=0),
        cache=ResponseCache(None, 1),
    ).test_client()
    assert client.get("/readyz").status_code == 200
    with psycopg.connect(clean_db, autocommit=True) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version = %s", (REQUIRED_SCHEMA_VERSION,))
        try:
            assert client.get("/readyz").status_code == 503
            assert client.get("/livez").status_code == 200
        finally:
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (%s, 'test')",
                (REQUIRED_SCHEMA_VERSION,),
            )
