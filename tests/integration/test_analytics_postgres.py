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
