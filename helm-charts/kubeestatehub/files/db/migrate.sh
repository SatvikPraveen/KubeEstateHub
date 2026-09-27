#!/bin/sh
# Apply versioned SQL migrations in lexical order, exactly once each.
#
# * Each migration runs in a single transaction together with its bookkeeping row.
# * A SHA-256 checksum is recorded; editing an already-applied migration is a hard
#   error, so every environment provably runs the same DDL.
# * POSIX sh only: runs in postgres:*-alpine (busybox) as well as in CI.
#
# Connection settings come from the standard libpq variables (PGHOST, PGUSER, ...).
# Usage: migrate.sh [migrations-dir]
set -eu

DIR="${1:-$(dirname "$0")/migrations}"
WAIT_SECONDS="${MIGRATE_WAIT_SECONDS:-120}"
export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"

i=0
until pg_isready -q; do
  i=$((i + 1))
  if [ "$i" -ge "$WAIT_SECONDS" ]; then
    echo "migrate: database not ready after ${WAIT_SECONDS}s" >&2
    exit 1
  fi
  sleep 1
done

psql -v ON_ERROR_STOP=1 -qX -c "CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    checksum   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"

applied=0
for file in "$DIR"/*.sql; do  # glob expansion is already lexically sorted
  version="$(basename "$file" .sql)"
  sum="$(sha256sum "$file" | cut -d' ' -f1)"
  recorded="$(psql -qXAt -v ON_ERROR_STOP=1 -v v="$version" <<SQL
SELECT checksum FROM schema_migrations WHERE version = :'v';
SQL
)"
  if [ -n "$recorded" ]; then
    if [ "$recorded" != "$sum" ]; then
      echo "migrate: checksum mismatch for $version (applied $recorded, file $sum)" >&2
      exit 2
    fi
    continue
  fi
  echo "migrate: applying $version"
  psql -qX -v ON_ERROR_STOP=1 --single-transaction -v v="$version" -v s="$sum" <<SQL
\i $file
INSERT INTO schema_migrations (version, checksum) VALUES (:'v', :'s');
SQL
  applied=$((applied + 1))
done

echo "migrate: done ($applied applied)"
