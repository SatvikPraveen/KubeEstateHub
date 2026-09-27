"""Data access. Routes depend on :class:`ListingsRepository`; tests supply a fake."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from .schemas import ListingQuery

LISTING_FIELDS = (
    "id",
    "mls_number",
    "title",
    "description",
    "property_type",
    "status",
    "price",
    "sale_price",
    "bedrooms",
    "bathrooms",
    "square_feet",
    "lot_size_sqft",
    "year_built",
    "price_per_sqft",
    "address",
    "city",
    "state",
    "zip_code",
    "latitude",
    "longitude",
    "listing_date",
    "sold_date",
    "agent_name",
    "agent_email",
    "agent_phone",
    "image_url",
    "thumbnail_url",
    "created_at",
    "updated_at",
)

SORTS = {
    "-listing_date": "listing_date DESC, id DESC",
    "listing_date": "listing_date ASC, id ASC",
    "price": "price ASC, id ASC",
    "-price": "price DESC, id DESC",
    "price_per_sqft": "price_per_sqft ASC NULLS LAST, id ASC",
    "-price_per_sqft": "price_per_sqft DESC NULLS LAST, id DESC",
}


# Newest migration this code depends on. Readiness fails until it has been applied, so
# pods never receive traffic against an older schema (the migrate Job runs concurrently).
REQUIRED_SCHEMA_VERSION = "0002_analytics_schema"


class SchemaNotReadyError(RuntimeError):
    pass


class DuplicateListingError(Exception):
    pass


class ConstraintViolationError(Exception):
    pass


class ListingsRepository(Protocol):
    def ping(self) -> None: ...
    def list_listings(
        self, query: ListingQuery, *, limit: int, offset: int
    ) -> tuple[list[dict], int]: ...
    def get_listing(self, listing_id: int) -> dict | None: ...
    def create_listing(self, data: Mapping[str, Any]) -> dict: ...
    def update_listing(self, listing_id: int, data: Mapping[str, Any]) -> dict | None: ...
    def delete_listing(self, listing_id: int) -> bool: ...
    def market_summary(self, city: str | None, property_type: str | None) -> dict: ...
    def market_trends(self, city: str | None, property_type: str | None) -> list[dict]: ...
    def price_index(self) -> dict: ...
    def latest_model_run(self) -> dict | None: ...


def build_filters(query: ListingQuery) -> tuple[str, list[Any]]:
    clauses = ["status = %s"]
    params: list[Any] = [query.status]
    if query.city:
        clauses.append("lower(city) = lower(%s)")
        params.append(query.city)
    if query.state:
        clauses.append("state = upper(%s)")
        params.append(query.state)
    if query.property_type:
        clauses.append("property_type = %s")
        params.append(query.property_type)
    if query.min_price is not None:
        clauses.append("price >= %s")
        params.append(query.min_price)
    if query.max_price is not None:
        clauses.append("price <= %s")
        params.append(query.max_price)
    if query.min_bedrooms is not None:
        clauses.append("bedrooms >= %s")
        params.append(query.min_bedrooms)
    if query.q:
        clauses.append("title ILIKE %s")
        params.append(f"%{query.q}%")
    return " AND ".join(clauses), params


class PostgresListingsRepository:
    def __init__(self, pool) -> None:
        self._pool = pool

    def _conn(self):
        return self._pool.connection()

    def _dict_cursor(self, conn):
        from psycopg.rows import dict_row

        return conn.cursor(row_factory=dict_row)

    def ping(self) -> None:
        with self._conn() as conn:
            applied = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = %s)",
                (REQUIRED_SCHEMA_VERSION,),
            ).fetchone()[0]
        if not applied:
            raise SchemaNotReadyError(f"schema migration {REQUIRED_SCHEMA_VERSION} not applied")

    def list_listings(
        self, query: ListingQuery, *, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        where, params = build_filters(query)
        cols = ", ".join(LISTING_FIELDS)
        with self._conn() as conn, self._dict_cursor(conn) as cur:
            cur.execute(f"SELECT count(*) AS n FROM listings WHERE {where}", params)  # noqa: S608
            total = cur.fetchone()["n"]
            cur.execute(
                f"SELECT {cols} FROM listings WHERE {where} ORDER BY {SORTS[query.sort]} LIMIT %s OFFSET %s",  # noqa: S608
                [*params, limit, offset],
            )
            return cur.fetchall(), total

    def get_listing(self, listing_id: int) -> dict | None:
        cols = ", ".join(f"l.{c}" for c in LISTING_FIELDS)
        sql = f"""
            SELECT {cols},
                   v.estimated_value, v.interval_low, v.interval_high, v.confidence_level,
                   v.method AS valuation_method, v.model_run_id AS valuation_model_run_id,
                   v.created_at AS valued_at
            FROM listings l
            LEFT JOIN LATERAL (
                SELECT * FROM property_valuations pv
                WHERE pv.listing_id = l.id ORDER BY pv.created_at DESC LIMIT 1
            ) v ON true
            WHERE l.id = %s AND l.status <> 'deleted'
        """  # noqa: S608 - constant column list
        with self._conn() as conn, self._dict_cursor(conn) as cur:
            cur.execute(sql, (listing_id,))
            row = cur.fetchone()
        if row is None:
            return None
        valuation_keys = (
            "estimated_value",
            "interval_low",
            "interval_high",
            "confidence_level",
            "valuation_method",
            "valuation_model_run_id",
            "valued_at",
        )
        valuation = {k: row.pop(k) for k in valuation_keys}
        row["valuation"] = valuation if valuation["estimated_value"] is not None else None
        return row

    def create_listing(self, data: Mapping[str, Any]) -> dict:
        import psycopg

        cols = [k for k, v in data.items() if v is not None]
        placeholders = ", ".join(["%s"] * len(cols))
        returning = ", ".join(LISTING_FIELDS)
        sql = f"INSERT INTO listings ({', '.join(cols)}) VALUES ({placeholders}) RETURNING {returning}"  # noqa: S608
        try:
            with self._conn() as conn, self._dict_cursor(conn) as cur:
                cur.execute(sql, [data[c] for c in cols])
                return cur.fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise DuplicateListingError(str(data.get("mls_number"))) from exc
        except psycopg.errors.CheckViolation as exc:
            raise ConstraintViolationError(
                exc.diag.constraint_name or "check constraint failed"
            ) from exc

    def update_listing(self, listing_id: int, data: Mapping[str, Any]) -> dict | None:
        import psycopg

        unknown = set(data) - set(LISTING_FIELDS)
        if unknown:
            raise ValueError(f"unknown columns: {sorted(unknown)}")
        assignments = ", ".join(f"{c} = %s" for c in data)
        returning = ", ".join(LISTING_FIELDS)
        sql = f"UPDATE listings SET {assignments} WHERE id = %s AND status <> 'deleted' RETURNING {returning}"  # noqa: S608
        try:
            with self._conn() as conn, self._dict_cursor(conn) as cur:
                cur.execute(sql, [*data.values(), listing_id])
                return cur.fetchone()
        except psycopg.errors.CheckViolation as exc:
            raise ConstraintViolationError(
                exc.diag.constraint_name or "check constraint failed"
            ) from exc

    def delete_listing(self, listing_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE listings SET status = 'deleted' WHERE id = %s AND status <> 'deleted'",
                (listing_id,),
            )
            return cur.rowcount == 1

    def market_summary(self, city: str | None, property_type: str | None) -> dict:
        clauses, params = ["status <> 'deleted'"], []
        if city:
            clauses.append("lower(city) = lower(%s)")
            params.append(city)
        if property_type:
            clauses.append("property_type = %s")
            params.append(property_type)
        where = " AND ".join(clauses)
        sql = f"""
            SELECT
              count(*) FILTER (WHERE status = 'active')                             AS active_listings,
              count(*) FILTER (WHERE status = 'pending')                            AS pending_listings,
              count(*) FILTER (WHERE status = 'sold'
                               AND sold_date > CURRENT_DATE - 90)                   AS sales_last_90d,
              percentile_cont(0.5) WITHIN GROUP (ORDER BY price)
                FILTER (WHERE status = 'active')                                    AS median_list_price,
              percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price)
                FILTER (WHERE status = 'sold' AND sold_date > CURRENT_DATE - 90)    AS median_sale_price_90d,
              percentile_cont(0.5) WITHIN GROUP (ORDER BY price_per_sqft)
                FILTER (WHERE status = 'active')                                    AS median_price_per_sqft,
              percentile_cont(0.5) WITHIN GROUP (ORDER BY sold_date - listing_date)
                FILTER (WHERE status = 'sold' AND sold_date > CURRENT_DATE - 90)    AS median_days_on_market
            FROM listings WHERE {where}
        """  # noqa: S608 - clauses are constants, values are parameters
        by_type_sql = f"""
            SELECT property_type, count(*) AS n FROM listings
            WHERE {where} AND status = 'active' GROUP BY property_type ORDER BY n DESC
        """  # noqa: S608
        by_city_sql = f"""
            SELECT city, state, count(*) FILTER (WHERE status = 'active') AS active,
                   count(*) FILTER (WHERE status = 'sold' AND sold_date > CURRENT_DATE - 90) AS sales_90d
            FROM listings WHERE {where} GROUP BY city, state ORDER BY active DESC LIMIT 20
        """  # noqa: S608
        with self._conn() as conn, self._dict_cursor(conn) as cur:
            cur.execute(sql, params)
            summary = cur.fetchone()
            cur.execute(by_type_sql, params)
            summary["by_property_type"] = {r["property_type"]: r["n"] for r in cur.fetchall()}
            cur.execute(by_city_sql, params)
            summary["by_city"] = cur.fetchall()
        sales, active = summary["sales_last_90d"], summary["active_listings"]
        monthly = sales / (90 / 30.4375)
        summary["months_of_supply"] = round(active / monthly, 2) if monthly else None
        return summary

    def market_trends(self, city: str | None, property_type: str | None) -> list[dict]:
        clauses, params = ["TRUE"], []
        if city:
            clauses.append("lower(city) = lower(%s)")
            params.append(city)
        if property_type:
            clauses.append("property_type = %s")
            params.append(property_type)
        sql = f"""
            SELECT DISTINCT ON (city, state, property_type) *
            FROM market_trends WHERE {" AND ".join(clauses)}
            ORDER BY city, state, property_type, period_end DESC, computed_at DESC
        """  # noqa: S608
        with self._conn() as conn, self._dict_cursor(conn) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def latest_model_run(self) -> dict | None:
        with self._conn() as conn, self._dict_cursor(conn) as cur:
            cur.execute(
                "SELECT id, pipeline, code_version, random_seed, status, n_observations, parameters, metrics, "
                "started_at, finished_at FROM model_runs WHERE status = 'succeeded' "
                "ORDER BY finished_at DESC LIMIT 1"
            )
            return cur.fetchone()

    def price_index(self) -> dict:
        """Series from the most recent successful run that produced an index."""
        with self._conn() as conn, self._dict_cursor(conn) as cur:
            cur.execute(
                "SELECT mr.id FROM model_runs mr WHERE mr.status = 'succeeded' "
                "AND EXISTS (SELECT 1 FROM price_index pi WHERE pi.model_run_id = mr.id) "
                "ORDER BY mr.finished_at DESC LIMIT 1"
            )
            run = cur.fetchone()
            if run is None:
                return {"model_run_id": None, "series": []}
            cur.execute(
                "SELECT period, index_value, std_error, n_sales FROM price_index "
                "WHERE model_run_id = %s ORDER BY period",
                (run["id"],),
            )
            return {"model_run_id": run["id"], "series": cur.fetchall()}
