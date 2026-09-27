import json
from datetime import date

import pandas as pd
import pytest

from analytics_worker import __main__ as cli
from analytics_worker.pipeline import PipelineConfig, run_pipeline
from analytics_worker.repository import InMemoryRepository, _clean
from analytics_worker.sync import (
    ListingRecord,
    SyncFilters,
    read_source,
    run_sync,
    validate_records,
)
from analytics_worker.synthetic import generate_market


@pytest.fixture
def repo():
    df, _ = generate_market(1500, seed=8, start=date(2024, 6, 1), months=18)
    r = InMemoryRepository()
    r.upsert_listings(df.to_dict("records"))
    return r


def test_pipeline_writes_all_outputs_with_provenance(repo):
    result = run_pipeline(
        repo, PipelineConfig(as_of=date(2025, 11, 30), seed=1, cv_folds=3), code_version="test"
    )
    run = repo.runs[result.run_id]
    assert run["status"] == "succeeded"
    assert run["code_version"] == "test"
    assert run["random_seed"] == 1
    assert run["parameters"]["as_of"] == "2025-11-30"
    assert repo.trends and all(t["model_run_id"] == result.run_id for t in repo.trends)
    assert repo.price_index and repo.price_index[0]["index_value"] == 100.0
    assert sum(r["n_sales"] for r in repo.price_index) == result.metrics["n_sales"]
    open_ids = set(repo.listings.loc[repo.listings["status"].isin(["active", "pending"]), "id"])
    assert {v["listing_id"] for v in repo.valuations} <= open_ids
    assert all(
        v["interval_low"] < v["estimated_value"] < v["interval_high"] for v in repo.valuations
    )
    cv = result.metrics["cross_validation"]["hedonic_conformal"]
    assert cv["median_ape"] < 0.15
    json.dumps(result.metrics, default=str)  # provenance must be serialisable


def test_pipeline_is_deterministic_given_seed(repo):
    cfg = PipelineConfig(as_of=date(2025, 11, 30), seed=5, cv_folds=3)
    a = run_pipeline(repo, cfg).metrics
    b = run_pipeline(repo, cfg).metrics
    a.pop("duration_seconds")
    b.pop("duration_seconds")
    assert a == b


def test_pipeline_skips_model_on_small_samples():
    df, _ = generate_market(60, seed=1)
    r = InMemoryRepository()
    r.upsert_listings(df.to_dict("records"))
    res = run_pipeline(r, PipelineConfig(as_of=date(2025, 12, 31)))
    assert "model_skipped" in res.metrics
    assert r.valuations == []


def test_pipeline_records_failures(repo, monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(repo, "load_listings", boom)
    with pytest.raises(RuntimeError):
        run_pipeline(repo)
    (run,) = repo.runs.values()
    assert run["status"] == "failed"
    assert "db down" in run["error"]


VALID = {
    "mls_number": "M1",
    "title": "Home",
    "property_type": "residential",
    "price": "350000",
    "address": "1 Main",
    "city": "Austin",
    "state": "tx",
    "zip_code": "78701",
}


def test_listing_record_normalises_and_validates():
    rec = ListingRecord.model_validate({**VALID, "bedrooms": "", "square_feet": "1800"})
    assert rec.state == "TX"
    assert rec.bedrooms is None
    assert rec.square_feet == 1800
    with pytest.raises(ValueError, match="sold listings"):
        ListingRecord.model_validate({**VALID, "status": "sold"})
    with pytest.raises(ValueError, match="precedes"):
        ListingRecord.model_validate(
            {**VALID, "listing_date": "2025-02-01", "sold_date": "2025-01-01"}
        )


def test_validate_records_counts_failures_and_filters():
    rows = [
        VALID,
        {**VALID, "mls_number": "M2", "price": "-1"},
        {**VALID, "mls_number": "M3", "property_type": "land"},
        {**VALID, "mls_number": "M4", "price": "5000000"},
    ]
    valid, res = validate_records(
        rows, SyncFilters(property_types=frozenset({"residential"}), price_max=1e6)
    )
    assert [v["mls_number"] for v in valid] == ["M1"]
    assert (res.processed, res.failed, res.filtered) == (4, 1, 2)
    assert res.errors and res.errors[0].startswith("row 1")


def test_sync_csv_file_end_to_end(tmp_path):
    path = tmp_path / "feed.csv"
    pd.DataFrame([VALID, {**VALID, "mls_number": "M2", "city": "Dallas"}]).to_csv(path, index=False)
    repo = InMemoryRepository()
    res = run_sync(repo, "csv", f"file://{path}", batch_size=1)
    assert res.succeeded == 2
    assert set(repo.listings["mls_number"]) == {"M1", "M2"}
    res = run_sync(repo, "csv", str(path), filters=SyncFilters(city="dallas"))
    assert res.succeeded == 1 and len(repo.listings) == 2  # upsert, not duplicate


def test_read_source_api_payload_shapes(tmp_path):
    p = tmp_path / "feed.json"
    p.write_text(json.dumps({"listings": [VALID]}))
    assert read_source("api", str(p)) == [VALID]
    p.write_text(json.dumps({"listings": {"bad": 1}}))
    with pytest.raises(ValueError, match="list"):
        read_source("api", str(p))
    with pytest.raises(ValueError, match="unsupported"):
        read_source("xml", str(p))


def test_clean_converts_numpy_and_nan():
    import numpy as np

    assert _clean(np.float64("nan")) is None
    assert _clean(float("nan")) is None
    assert _clean(np.int64(3)) == 3
    assert _clean(pd.NaT) is None
    assert _clean("x") == "x"


def test_cli_parser_and_benchmark(capsys):
    args = cli.build_parser().parse_args(["pipeline", "--as-of", "2025-01-31", "--seed", "3"])
    assert args.as_of == date(2025, 1, 31) and args.seed == 3
    assert (
        cli.main(
            [
                "benchmark",
                "--replications",
                "2",
                "--n",
                "800",
                "--folds",
                "3",
                "--format",
                "markdown",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Wald coverage" in out and "hedonic_conformal" in out


def test_cli_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="DATABASE_URL"):
        cli.main(["pipeline"])
