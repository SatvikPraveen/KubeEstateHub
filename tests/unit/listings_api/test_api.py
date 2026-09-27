from __future__ import annotations

import pytest

from listings_api.repository import build_filters
from listings_api.schemas import ListingQuery

from .conftest import VALID_LISTING, make_app


def create(client, **overrides):
    return client.post("/api/v1/listings", json={**VALID_LISTING, **overrides})


class TestHealth:
    def test_liveness_ignores_database(self, repo, client):
        repo.healthy = False
        assert client.get("/livez").status_code == 200

    def test_readiness_reflects_database(self, repo, client):
        assert client.get("/readyz").json["database"] == "ok"
        repo.healthy = False
        resp = client.get("/readyz")
        assert resp.status_code == 503
        assert resp.mimetype == "application/problem+json"
        assert client.get("/health").status_code == 503


class TestListings:
    def test_create_normalises_and_returns_location(self, client):
        resp = create(client)
        assert resp.status_code == 201
        body = resp.json["listing"]
        assert body["state"] == "TX"
        assert body["price"] == 450000.0
        assert resp.headers["Location"] == f"/api/v1/listings/{body['id']}"

    def test_duplicate_mls_is_conflict(self, client):
        create(client)
        resp = create(client)
        assert resp.status_code == 409
        assert "MLS-1" in resp.json["detail"]

    @pytest.mark.parametrize(
        ("overrides", "field"),
        [
            ({"price": -5}, "price"),
            ({"state": "Texas"}, "state"),
            ({"zip_code": "abc"}, "zip_code"),
            ({"property_type": "castle"}, "property_type"),
            ({"unexpected": 1}, "unexpected"),
            ({"image_url": "javascript:alert(1)"}, "image_url"),
        ],
    )
    def test_validation_errors_are_problem_details(self, client, overrides, field):
        resp = create(client, **overrides)
        assert resp.status_code == 422
        assert resp.mimetype == "application/problem+json"
        assert any(e["field"] == field for e in resp.json["errors"])

    def test_sold_requires_outcome(self, client):
        resp = create(client, status="sold")
        assert resp.status_code == 422
        assert "sale_price" in resp.json["errors"][0]["message"]

    def test_non_json_body_is_bad_request(self, client):
        assert client.post("/api/v1/listings", data="nope").status_code == 400

    def test_get_update_delete_lifecycle(self, client):
        lid = create(client).json["listing"]["id"]
        assert (
            client.get(f"/api/v1/listings/{lid}").json["listing"]["title"] == "Craftsman bungalow"
        )
        resp = client.patch(f"/api/v1/listings/{lid}", json={"price": 425000})
        assert resp.status_code == 200
        assert resp.json["listing"]["price"] == 425000.0
        assert client.patch(f"/api/v1/listings/{lid}", json={}).status_code == 422
        assert client.delete(f"/api/v1/listings/{lid}").status_code == 204
        assert client.get(f"/api/v1/listings/{lid}").status_code == 404
        assert client.delete(f"/api/v1/listings/{lid}").status_code == 404
        assert client.patch(f"/api/v1/listings/{lid}", json={"price": 1}).status_code == 404

    def test_pagination_caps_page_size(self, client):
        for i in range(5):
            create(client, mls_number=f"M{i}")
        body = client.get("/api/v1/listings?per_page=1000&page=2").json
        assert body["pagination"] == {"page": 2, "per_page": 100, "total": 5, "pages": 1}
        assert body["listings"] == []
        body = client.get("/api/v1/listings?per_page=2").json
        assert body["pagination"]["pages"] == 3
        assert len(body["listings"]) == 2

    @pytest.mark.parametrize(
        "qs", ["per_page=0", "page=abc", "min_price=10&max_price=5", "sort=id", "evil=1"]
    )
    def test_invalid_queries_rejected(self, client, qs):
        assert client.get(f"/api/v1/listings?{qs}").status_code == 422


class TestCaching:
    def test_read_through_and_generation_invalidation(self, repo, client):
        create(client)
        first = client.get("/api/v1/listings?city=austin")
        second = client.get("/api/v1/listings?city=austin")
        assert (first.headers["X-Cache"], second.headers["X-Cache"]) == ("MISS", "HIT")
        assert first.json == second.json
        assert repo.calls.count("list") == 1
        create(client, mls_number="MLS-2")  # write bumps the generation
        third = client.get("/api/v1/listings?city=austin")
        assert third.headers["X-Cache"] == "MISS"
        assert third.json["pagination"]["total"] == 2

    def test_without_redis_cache_is_bypassed(self, repo):
        client = make_app(repo, None).test_client()
        assert client.get("/api/v1/listings").headers["X-Cache"] == "BYPASS"


class TestAuthAndLimits:
    def test_write_token_enforced_with_constant_time_compare(self, repo, redis):
        client = make_app(repo, redis, write_token="s3cret").test_client()
        assert create(client).status_code == 401
        bad = client.post(
            "/api/v1/listings", json=VALID_LISTING, headers={"Authorization": "Bearer nope"}
        )
        assert bad.status_code == 401
        ok = client.post(
            "/api/v1/listings", json=VALID_LISTING, headers={"Authorization": "Bearer s3cret"}
        )
        assert ok.status_code == 201
        assert client.get("/api/v1/listings").status_code == 200  # reads stay public

    def test_write_rate_limit(self, repo, redis):
        client = make_app(
            repo, redis, rate_limit_enabled=True, rate_limit_write="2 per minute"
        ).test_client()
        codes = [create(client, mls_number=f"R{i}").status_code for i in range(3)]
        assert codes == [201, 201, 429]
        assert client.get("/api/v1/listings").status_code == 200  # reads use the default limit
        assert client.get("/livez").status_code == 200


class TestMarketAndProvenance:
    def test_summary_serialises_decimals(self, client):
        body = client.get("/api/v1/market/summary?city=Austin").json["summary"]
        assert body["median_list_price"] == 123.45
        assert body["city"] == "Austin"

    def test_trends_and_index(self, client):
        assert client.get("/api/v1/market/trends").json["trends"][0]["period_end"] == "2025-01-31"
        assert client.get("/api/v1/market/price-index").json["series"] == []
        assert client.get("/api/v1/market/trends?property_type=castle").status_code == 422

    def test_model_run(self, repo, client):
        assert client.get("/api/v1/model-runs/latest").status_code == 404
        repo.run = {"id": "abc", "metrics": {"n_sales": 3}}
        assert client.get("/api/v1/model-runs/latest").json["model_run"]["metrics"]["n_sales"] == 3


class TestObservability:
    def test_request_id_propagates_or_is_generated(self, client):
        assert (
            client.get("/livez", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"]
            == "abc-123"
        )
        generated = client.get("/livez", headers={"X-Request-ID": "bad id <script>"}).headers[
            "X-Request-ID"
        ]
        assert len(generated) == 32

    def test_metrics_use_route_templates(self, client):
        create(client)
        client.get("/api/v1/listings/1")
        client.get("/api/v1/listings/999")
        text = client.get("/metrics").get_data(as_text=True)
        assert 'route="/api/v1/listings/<int:listing_id>"' in text
        assert 'route="/api/v1/listings/1"' not in text
        assert "listings_cache_events_total" in text

    def test_openapi_documents_every_api_route(self, client):
        spec = client.get("/openapi.json").json
        assert spec["openapi"].startswith("3.1")
        documented = set(spec["paths"])
        app = client.application
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith("/api/"):
                assert rule.rule.replace("<int:listing_id>", "{listing_id}") in documented
        assert "ListingCreate" in spec["components"]["schemas"]

    def test_cors_only_when_configured(self, repo, redis):
        client = make_app(repo, redis, cors_origins=("https://app.example",)).test_client()
        resp = client.get("/livez", headers={"Origin": "https://app.example"})
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.example"
        plain = make_app(repo, redis).test_client().get("/livez", headers={"Origin": "https://x"})
        assert "Access-Control-Allow-Origin" not in plain.headers


def test_build_filters_is_parameterised():
    q = ListingQuery(
        city="Austin'; DROP TABLE listings;--", min_price=1, max_price=2, q="pool", min_bedrooms=3
    )
    where, params = build_filters(q)
    assert "DROP" not in where
    assert params == ["active", "Austin'; DROP TABLE listings;--", 1, 2, 3, "%pool%"]
    assert where.count("%s") == len(params)


def test_cache_degrades_on_redis_errors():
    from listings_api.cache import ResponseCache

    class Broken:
        def __getattr__(self, _):
            def fail(*_a, **_k):
                raise ConnectionError("redis down")

            return fail

    cache = ResponseCache(Broken(), 5)
    assert cache.key("x", {}) is None
    assert cache.get("k") is None
    cache.set("k", {"a": 1})
    cache.invalidate()
    assert cache.ping() is False
