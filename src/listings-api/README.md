# Listings API

Flask 3 REST API for listings, live market indicators and analytics provenance.
The OpenAPI 3.1 document is generated from the pydantic validation models and served at
`GET /openapi.json`, so the contract cannot drift from the implementation.

| Endpoint | Description |
|---|---|
| `GET /api/v1/listings` | Filter (`city`, `state`, `property_type`, `status`, `min_price`, `max_price`, `min_bedrooms`, `q`), sort, paginate |
| `GET /api/v1/listings/{id}` | Listing plus its latest model valuation with a conformal interval |
| `POST` / `PATCH` / `DELETE /api/v1/listings/{id}` | Writes. They need `Authorization: Bearer $API_WRITE_TOKEN` when the token is set, and delete is a soft delete |
| `GET /api/v1/market/summary` | Live aggregates: inventory, medians, days on market, months of supply |
| `GET /api/v1/market/trends` | Latest statistical trend per segment from the analytics pipeline |
| `GET /api/v1/market/price-index` | Hedonic price index from the latest successful model run |
| `GET /api/v1/model-runs/latest` | Code version, seed, parameters and evaluation metrics of that run |
| `GET /livez`, `GET /readyz` | Liveness (process only) and readiness (database reachable) |
| `GET /metrics` | Prometheus RED metrics, aggregated across gunicorn workers |

## Design notes

* **Errors** are RFC 9457 `application/problem+json` documents. Validation failures return
  422 with a per-field `errors` array.
* **Caching:** Redis read-through with generation-based invalidation, so a write costs
  one `INCR`. If Redis is down the API keeps serving from PostgreSQL.
* **Rate limits:** Flask-Limiter with a separate, stricter budget for writes. Storage
  errors fail open.
* **Metrics** are labelled by route template (`/api/v1/listings/<int:listing_id>`), never
  by raw path, which bounds label cardinality.
* **Probes:** liveness never touches the database. A database outage makes pods unready
  instead of restart-looping them.

## Configuration

`DATABASE_URL`, `REDIS_URL`, `API_WRITE_TOKEN`, `CORS_ORIGINS`, `DEFAULT_PAGE_SIZE`,
`MAX_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_WRITE`,
`TRUSTED_PROXIES`, `DB_POOL_MIN`, `DB_POOL_MAX`, `DB_STATEMENT_TIMEOUT_MS`,
`GUNICORN_WORKERS`, `GUNICORN_THREADS`, `LOG_LEVEL`. See `listings_api/config.py`.
