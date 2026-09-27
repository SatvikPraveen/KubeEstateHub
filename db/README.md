# Database

PostgreSQL 16 schema, managed as ordered, immutable SQL migrations.

| File | Purpose |
|------|---------|
| `migrations/0001_core_schema.sql` | Listings table, enums, indexes (incl. trigram search), `updated_at` trigger |
| `migrations/0002_analytics_schema.sql` | Analytics outputs with provenance: `model_runs`, `market_trends`, `price_index`, `property_valuations` |
| `migrate.sh` | POSIX migration runner (works in `postgres:*-alpine`, CI, and locally) |

## Guarantees

* **Exactly-once:** applied versions are recorded in `schema_migrations`.
* **Atomic:** each file and its bookkeeping row run in one transaction.
* **Immutable:** the SHA-256 of each applied file is stored; if an applied migration is
  edited, `migrate.sh` exits with status 2. Add a new migration instead.
* **Provenance:** every analytics row references the `model_runs` row (code version,
  random seed, parameters, evaluation metrics) that produced it.

## Running

```bash
export PGHOST=localhost PGUSER=kubeestatehub PGPASSWORD=... PGDATABASE=kubeestatehub
db/migrate.sh
```

In Kubernetes the `db-migrate` Job mounts the migrations from a ConfigMap that is
generated from this directory (`make generate`); CI fails if the two drift.
