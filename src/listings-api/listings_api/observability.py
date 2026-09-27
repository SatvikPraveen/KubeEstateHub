"""Request IDs, structured logs and RED metrics with bounded label cardinality."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from datetime import UTC, datetime

from flask import Flask, g, request
from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
IN_FLIGHT = Gauge("http_requests_in_flight", "In-flight HTTP requests")
BUILD_INFO = Gauge("listings_api_build_info", "Build information", ["version", "environment"])

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)


def instrument(app: Flask) -> None:
    access = logging.getLogger("listings_api.access")

    @app.before_request
    def _start() -> None:
        incoming = request.headers.get("X-Request-ID", "")
        g.request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        g.start = time.perf_counter()
        IN_FLIGHT.inc()

    @app.after_request
    def _finish(response):
        elapsed = time.perf_counter() - g.get("start", time.perf_counter())
        # route template, never the raw path: keeps label cardinality bounded
        route = request.url_rule.rule if request.url_rule else "unmatched"
        REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        LATENCY.labels(request.method, route).observe(elapsed)
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers["Server-Timing"] = f"app;dur={elapsed * 1000:.1f}"
        if route not in {"/metrics", "/livez", "/readyz"}:
            access.info(
                "request",
                extra={
                    "request_id": g.get("request_id"),
                    "method": request.method,
                    "route": route,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )
        return response

    @app.teardown_request
    def _teardown(_exc) -> None:
        if "start" in g:
            IN_FLIGHT.dec()
