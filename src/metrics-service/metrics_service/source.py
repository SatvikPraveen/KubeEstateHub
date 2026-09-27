"""Database queries behind the exporter. Kept separate so the collector can be tested
with an in-memory snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class Snapshot:
    listings: list[tuple[str, str, int]] = field(default_factory=list)  # status, type, count
    median_list_price: list[tuple[str, str, float]] = field(
        default_factory=list
    )  # city, type, price
    trends: list[dict[str, Any]] = field(default_factory=list)
    last_success: dict[str, datetime] = field(default_factory=dict)  # pipeline -> finished_at
    latest_metrics: dict[str, Any] = field(default_factory=dict)  # metrics JSON of latest run
    latest_index: float | None = None


class Source(Protocol):
    def fetch(self) -> Snapshot: ...
    def ping(self) -> None: ...


class PostgresSource:
    def __init__(self, dsn: str, statement_timeout_ms: int = 5000) -> None:
        self._dsn = dsn
        self._options = f"-c statement_timeout={statement_timeout_ms}"

    def _connect(self):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(
            self._dsn,
            options=self._options,
            row_factory=dict_row,
            application_name="metrics-service",
            connect_timeout=5,
        )

    def ping(self) -> None:
        with self._connect() as conn:
            conn.execute("SELECT 1")

    def fetch(self) -> Snapshot:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status::text, property_type::text, count(*) AS n FROM listings "
                "GROUP BY 1, 2"
            )
            listings = [(r["status"], r["property_type"], r["n"]) for r in cur.fetchall()]
            cur.execute("""
                SELECT city, property_type::text,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median
                FROM listings WHERE status = 'active' GROUP BY 1, 2 HAVING count(*) >= 5
            """)
            medians = [(r["city"], r["property_type"], float(r["median"])) for r in cur.fetchall()]
            cur.execute("""
                SELECT DISTINCT ON (city, state, property_type)
                       city, state, coalesce(property_type::text, 'all') AS property_type,
                       months_of_supply, absorption_rate, median_days_on_market, n_sales,
                       trend_slope_pct_per_month, mann_kendall_p, trend_direction
                FROM market_trends ORDER BY city, state, property_type, period_end DESC, computed_at DESC
            """)
            trends = cur.fetchall()
            cur.execute(
                "SELECT pipeline, max(finished_at) AS t FROM model_runs "
                "WHERE status = 'succeeded' GROUP BY pipeline"
            )
            last_success = {r["pipeline"]: r["t"] for r in cur.fetchall()}
            cur.execute(
                "SELECT id, metrics FROM model_runs WHERE status = 'succeeded' "
                "ORDER BY finished_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            latest_metrics = row["metrics"] if row else {}
            latest_index = None
            if row:
                cur.execute(
                    "SELECT index_value FROM price_index WHERE model_run_id = %s "
                    "ORDER BY period DESC LIMIT 1",
                    (row["id"],),
                )
                idx = cur.fetchone()
                latest_index = float(idx["index_value"]) if idx else None
        return Snapshot(listings, medians, trends, last_success, latest_metrics or {}, latest_index)
