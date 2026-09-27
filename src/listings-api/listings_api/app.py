"""Application factory. Dependencies (repository, cache) are injectable for testing."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from flask import Flask, Response, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, CollectorRegistry, generate_latest
from werkzeug.middleware.proxy_fix import ProxyFix

from . import errors, observability
from .cache import ResponseCache
from .config import Settings
from .openapi import build_spec
from .repository import ListingsRepository, PostgresListingsRepository
from .routes import api

VERSION = "2.0.0"
log = logging.getLogger(__name__)


class JSONProvider(DefaultJSONProvider):
    sort_keys = False

    @staticmethod
    def default(o: Any) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime | date):
            return o.isoformat()
        if isinstance(o, UUID):
            return str(o)
        return DefaultJSONProvider.default(o)


@dataclass
class Dependencies:
    settings: Settings
    repo: ListingsRepository
    cache: ResponseCache


def _metrics_registry() -> CollectorRegistry:
    """Aggregate across gunicorn workers when PROMETHEUS_MULTIPROC_DIR is set."""
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return registry
    return REGISTRY


def _postgres_repository(settings: Settings) -> ListingsRepository:
    from psycopg_pool import ConnectionPool

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    pool = ConnectionPool(
        settings.database_url,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        kwargs={
            "options": f"-c statement_timeout={settings.db_statement_timeout_ms}",
            "application_name": "listings-api",
            "autocommit": True,
        },
        open=False,
        timeout=5,
    )
    pool.open(wait=False)
    return PostgresListingsRepository(pool)


def create_app(
    settings: Settings | None = None,
    *,
    repository: ListingsRepository | None = None,
    cache: ResponseCache | None = None,
) -> Flask:
    settings = settings or Settings.from_env()
    observability.configure_logging(settings.log_level)

    app = Flask(__name__)
    app.json_provider_class = JSONProvider
    app.json = JSONProvider(app)
    app.config.update(
        RATELIMIT_ENABLED=settings.rate_limit_enabled,
        RATELIMIT_STORAGE_URI=settings.ratelimit_storage_uri,
        RATELIMIT_HEADERS_ENABLED=True,
        RATELIMIT_SWALLOW_ERRORS=True,  # a Redis outage must not take the API down
        RATELIMIT_IN_MEMORY_FALLBACK_ENABLED=True,
        MAX_CONTENT_LENGTH=256 * 1024,
    )
    if settings.trusted_proxies:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=settings.trusted_proxies, x_proto=settings.trusted_proxies
        )
    if settings.cors_origins:
        CORS(app, origins=list(settings.cors_origins), expose_headers=["X-Request-ID", "X-Cache"])

    deps = Dependencies(
        settings=settings,
        repo=repository if repository is not None else _postgres_repository(settings),
        cache=cache
        if cache is not None
        else ResponseCache.from_url(settings.redis_url, settings.cache_ttl_seconds),
    )
    app.extensions["keh"] = deps

    limiter = Limiter(get_remote_address, app=app, default_limits=[settings.rate_limit_default])
    limiter.limit(
        lambda: settings.rate_limit_write,
        methods=["POST", "PATCH", "DELETE"],
        override_defaults=False,
    )(api)
    app.register_blueprint(api)
    errors.register(app)
    observability.instrument(app)
    observability.BUILD_INFO.labels(VERSION, settings.environment).set(1)
    spec = build_spec(VERSION)
    registry = _metrics_registry()

    @app.get("/livez")
    @limiter.exempt
    def livez():
        # Liveness must not depend on downstream services: a database outage should make
        # pods unready (removed from load balancing), not restart them in a crash loop.
        return jsonify(status="ok", version=VERSION)

    @app.get("/readyz")
    @limiter.exempt
    def readyz():
        try:
            deps.repo.ping()
        except Exception as exc:
            log.warning("readiness check failed: %s", exc)
            return errors.problem(503, "Service Unavailable", "database unreachable")
        return jsonify(
            status="ready", database="ok", cache="ok" if deps.cache.ping() else "disabled"
        )

    app.add_url_rule("/health", "health", readyz)  # backwards-compatible alias

    @app.get("/metrics")
    @limiter.exempt
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    @app.get("/openapi.json")
    def openapi():
        return jsonify(spec)

    return app
