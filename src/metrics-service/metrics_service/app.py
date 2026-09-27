from __future__ import annotations

import logging
import os

from flask import Flask, Response, jsonify
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    gc_collector,
    generate_latest,
    platform_collector,
    process_collector,
)

from . import __version__
from .collector import MarketCollector
from .source import PostgresSource, Source

log = logging.getLogger(__name__)


def create_app(source: Source | None = None, *, ttl_seconds: float | None = None) -> Flask:
    if source is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL is required")
        source = PostgresSource(dsn)
    ttl = ttl_seconds if ttl_seconds is not None else float(os.getenv("CACHE_TTL_SECONDS", "30"))

    registry = CollectorRegistry()
    process_collector.ProcessCollector(registry=registry)
    platform_collector.PlatformCollector(registry=registry)
    gc_collector.GCCollector(registry=registry)
    registry.register(MarketCollector(source, ttl_seconds=ttl))

    app = Flask(__name__)

    @app.get("/livez")
    def livez():
        return jsonify(status="ok", version=__version__)

    @app.get("/readyz")
    def readyz():
        try:
            source.ping()
        except Exception as exc:
            log.warning("readiness failed: %s", exc)
            return jsonify(status="unavailable"), 503
        return jsonify(status="ready")

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    return app
