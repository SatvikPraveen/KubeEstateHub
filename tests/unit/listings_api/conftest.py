from __future__ import annotations

import itertools
from datetime import date
from decimal import Decimal

import pytest

from listings_api.app import create_app
from listings_api.cache import ResponseCache
from listings_api.config import Settings
from listings_api.repository import DuplicateListingError


class FakeRedis:
    def __init__(self):
        self.store: dict[str, bytes] = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, _ttl, value):
        self.store[key] = value.encode() if isinstance(value, str) else value

    def incr(self, key):
        self.store[key] = str(int(self.store.get(key, b"0")) + 1).encode()

    def ping(self):
        return True


class FakeRepo:
    def __init__(self):
        self.rows: dict[int, dict] = {}
        self.ids = itertools.count(1)
        self.calls: list[str] = []
        self.healthy = True
        self.run = None

    def ping(self):
        if not self.healthy:
            raise ConnectionError("down")

    def list_listings(self, query, *, limit, offset):
        self.calls.append("list")
        rows = [r for r in self.rows.values() if r["status"] == query.status]
        if query.city:
            rows = [r for r in rows if r["city"].lower() == query.city.lower()]
        return rows[offset : offset + limit], len(rows)

    def get_listing(self, listing_id):
        self.calls.append("get")
        row = self.rows.get(listing_id)
        return None if row is None or row["status"] == "deleted" else {**row, "valuation": None}

    def create_listing(self, data):
        if any(r["mls_number"] == data["mls_number"] for r in self.rows.values()):
            raise DuplicateListingError(data["mls_number"])
        row = {**data, "id": next(self.ids)}
        self.rows[row["id"]] = row
        return row

    def update_listing(self, listing_id, data):
        row = self.get_listing(listing_id)
        if row is None:
            return None
        self.rows[listing_id].update(data)
        return self.rows[listing_id]

    def delete_listing(self, listing_id):
        if self.get_listing(listing_id) is None:
            return False
        self.rows[listing_id]["status"] = "deleted"
        return True

    def market_summary(self, city, property_type):
        return {
            "active_listings": len(self.rows),
            "median_list_price": Decimal("123.45"),
            "city": city,
        }

    def market_trends(self, city, property_type):
        return [
            {"city": city or "Austin", "trend_direction": "flat", "period_end": date(2025, 1, 31)}
        ]

    def price_index(self):
        return {"model_run_id": None, "series": []}

    def latest_model_run(self):
        return self.run


VALID_LISTING = {
    "mls_number": "MLS-1",
    "title": "Craftsman bungalow",
    "property_type": "residential",
    "price": 450000,
    "address": "1 Main St",
    "city": "Austin",
    "state": "tx",
    "zip_code": "78701",
    "square_feet": 1800,
}


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def redis():
    return FakeRedis()


def make_app(repo, redis=None, **overrides):
    settings = Settings(**{"rate_limit_enabled": False, "trusted_proxies": 0, **overrides})
    return create_app(settings, repository=repo, cache=ResponseCache(redis, 60))


@pytest.fixture
def client(repo, redis):
    return make_app(repo, redis).test_client()
