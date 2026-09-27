"""Persistence boundary. The pipeline depends on the :class:`Repository` protocol only,
so it can be exercised end-to-end in tests with :class:`InMemoryRepository`."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import pandas as pd

LISTING_COLUMNS: tuple[str, ...] = (
    "id",
    "mls_number",
    "title",
    "property_type",
    "status",
    "price",
    "sale_price",
    "bedrooms",
    "bathrooms",
    "square_feet",
    "year_built",
    "address",
    "city",
    "state",
    "zip_code",
    "latitude",
    "longitude",
    "listing_date",
    "sold_date",
)

UPSERT_COLUMNS: tuple[str, ...] = tuple(c for c in LISTING_COLUMNS if c != "id")

TREND_COLUMNS: tuple[str, ...] = (
    "city",
    "state",
    "property_type",
    "period_start",
    "period_end",
    "n_sales",
    "n_active",
    "median_sale_price",
    "median_sale_price_ci_low",
    "median_sale_price_ci_high",
    "median_price_per_sqft",
    "median_days_on_market",
    "sale_to_list_ratio",
    "months_of_supply",
    "absorption_rate",
    "trend_slope_pct_per_month",
    "trend_slope_ci_low",
    "trend_slope_ci_high",
    "mann_kendall_tau",
    "mann_kendall_p",
    "trend_direction",
)


class Repository(Protocol):
    def load_listings(self) -> pd.DataFrame: ...
    def start_run(
        self, pipeline: str, code_version: str, seed: int, parameters: Mapping[str, Any]
    ) -> str: ...
    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        n_observations: int | None,
        metrics: Mapping[str, Any],
        error: str | None = None,
    ) -> None: ...
    def write_trends(self, run_id: str, rows: Sequence[Mapping[str, Any]]) -> None: ...
    def write_price_index(self, run_id: str, index: pd.DataFrame) -> None: ...
    def write_valuations(self, run_id: str, rows: Sequence[Mapping[str, Any]]) -> None: ...
    def upsert_listings(self, rows: Sequence[Mapping[str, Any]]) -> int: ...


def _clean(value: Any) -> Any:
    """Convert numpy/pandas scalars and NaN to plain Python for the DB driver."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    if hasattr(value, "item"):
        value = value.item()
        if isinstance(value, float) and value != value:
            return None
    if value is pd.NaT:
        return None
    return value


@dataclass
class InMemoryRepository:
    listings: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=list(LISTING_COLUMNS))
    )
    runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    trends: list[dict[str, Any]] = field(default_factory=list)
    price_index: list[dict[str, Any]] = field(default_factory=list)
    valuations: list[dict[str, Any]] = field(default_factory=list)

    def load_listings(self) -> pd.DataFrame:
        return self.listings.copy()

    def start_run(
        self, pipeline: str, code_version: str, seed: int, parameters: Mapping[str, Any]
    ) -> str:
        run_id = str(uuid.uuid4())
        self.runs[run_id] = {
            "pipeline": pipeline,
            "code_version": code_version,
            "random_seed": seed,
            "parameters": dict(parameters),
            "status": "running",
            "started_at": datetime.now(UTC),
        }
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        n_observations: int | None,
        metrics: Mapping[str, Any],
        error: str | None = None,
    ) -> None:
        self.runs[run_id].update(
            status=status,
            n_observations=n_observations,
            metrics=dict(metrics),
            error=error,
            finished_at=datetime.now(UTC),
        )

    def write_trends(self, run_id: str, rows: Sequence[Mapping[str, Any]]) -> None:
        self.trends.extend({**r, "model_run_id": run_id} for r in rows)

    def write_price_index(self, run_id: str, index: pd.DataFrame) -> None:
        self.price_index.extend({**r, "model_run_id": run_id} for r in index.to_dict("records"))

    def write_valuations(self, run_id: str, rows: Sequence[Mapping[str, Any]]) -> None:
        self.valuations.extend({**r, "model_run_id": run_id} for r in rows)

    def upsert_listings(self, rows: Sequence[Mapping[str, Any]]) -> int:
        incoming = pd.DataFrame(list(rows))
        if incoming.empty:
            return 0
        existing = self.listings
        if not existing.empty:
            existing = existing[~existing["mls_number"].isin(incoming["mls_number"])]
        start = int(self.listings["id"].max()) + 1 if len(self.listings) else 1
        incoming.insert(0, "id", range(start, start + len(incoming)))
        frames = [f for f in (existing, incoming) if not f.empty]
        self.listings = pd.concat(frames, ignore_index=True)
        return len(incoming)


class PostgresRepository:
    """psycopg 3 implementation. One short transaction per write keeps locks brief."""

    def __init__(self, dsn: str) -> None:
        import psycopg  # imported lazily so the pure-analytics modules have no DB dependency

        self._psycopg = psycopg
        self._dsn = dsn

    def _connect(self):
        return self._psycopg.connect(self._dsn, autocommit=False)

    def load_listings(self) -> pd.DataFrame:
        cols = ", ".join(LISTING_COLUMNS)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {cols} FROM listings WHERE status <> 'deleted'")  # noqa: S608 - constant columns
            rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=list(LISTING_COLUMNS))
        for col in ("price", "sale_price", "bathrooms", "latitude", "longitude"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
        for col in ("property_type", "status"):
            df[col] = df[col].astype(str)
        return df

    def start_run(
        self, pipeline: str, code_version: str, seed: int, parameters: Mapping[str, Any]
    ) -> str:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO model_runs (pipeline, code_version, random_seed, parameters) "
                "VALUES (%s, %s, %s, %s::jsonb) RETURNING id",
                (pipeline, code_version, seed, json.dumps(parameters, default=str)),
            )
            (run_id,) = cur.fetchone()
        return str(run_id)

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        n_observations: int | None,
        metrics: Mapping[str, Any],
        error: str | None = None,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE model_runs SET status = %s, n_observations = %s, metrics = %s::jsonb, "
                "error = %s, finished_at = now() WHERE id = %s",
                (status, n_observations, json.dumps(metrics, default=str), error, run_id),
            )

    def write_trends(self, run_id: str, rows: Sequence[Mapping[str, Any]]) -> None:
        if not rows:
            return
        cols = ("model_run_id", *TREND_COLUMNS)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in (*TREND_COLUMNS[5:], "model_run_id"))
        sql = (
            f"INSERT INTO market_trends ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "  # noqa: S608
            "ON CONFLICT ON CONSTRAINT market_trends_unique DO UPDATE SET "
            f"{updates}, computed_at = now()"
        )
        params = [(run_id, *(_clean(r.get(c)) for c in TREND_COLUMNS)) for r in rows]
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(sql, params)

    def write_price_index(self, run_id: str, index: pd.DataFrame) -> None:
        if index.empty:
            return
        params = [
            (
                run_id,
                pd.Timestamp(r.period).date(),
                _clean(r.index_value),
                _clean(r.std_error),
                int(r.n_sales),
            )
            for r in index.itertuples()
        ]
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO price_index (model_run_id, period, index_value, std_error, n_sales) "
                "VALUES (%s, %s, %s, %s, %s)",
                params,
            )

    def write_valuations(self, run_id: str, rows: Sequence[Mapping[str, Any]]) -> None:
        if not rows:
            return
        cols = (
            "listing_id",
            "method",
            "estimated_value",
            "interval_low",
            "interval_high",
            "confidence_level",
        )
        params = [(run_id, *(_clean(r.get(c)) for c in cols)) for r in rows]
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO property_valuations (model_run_id, listing_id, method, estimated_value, "
                "interval_low, interval_high, confidence_level) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT ON CONSTRAINT property_valuations_unique DO NOTHING",
                params,
            )

    def upsert_listings(self, rows: Sequence[Mapping[str, Any]]) -> int:
        if not rows:
            return 0
        cols = [c for c in UPSERT_COLUMNS if any(c in r for r in rows)]
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "mls_number")
        sql = (
            f"INSERT INTO listings ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "  # noqa: S608
            f"ON CONFLICT (mls_number) DO UPDATE SET {updates}"
        )
        params = [tuple(_clean(r.get(c)) for c in cols) for r in rows]
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(sql, params)
        return len(params)


def chunked(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
