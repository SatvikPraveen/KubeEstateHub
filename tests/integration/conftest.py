"""Integration fixtures: a freshly migrated PostgreSQL schema per test session.

Set ``DATABASE_URL`` (e.g. ``postgresql://keh:test@localhost:55432/keh``) to enable.
The schema is dropped and recreated, so never point this at a database you care about.
"""

import os
from pathlib import Path

import pytest

MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"


@pytest.fixture(scope="session")
def database_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
        for path in sorted(MIGRATIONS.glob("*.sql")):
            conn.execute(path.read_text())
    return url


@pytest.fixture
def clean_db(database_url):
    import psycopg

    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE listings, model_runs RESTART IDENTITY CASCADE")
    return database_url
