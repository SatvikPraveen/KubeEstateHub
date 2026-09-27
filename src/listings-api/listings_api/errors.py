"""RFC 9457 ``application/problem+json`` error responses."""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, Response, jsonify, request
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)
PROBLEM_JSON = "application/problem+json"


class ApiError(Exception):
    def __init__(self, status: int, title: str, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or title)
        self.status, self.title, self.detail, self.extra = status, title, detail, extra


def problem(
    status: int, title: str, detail: str | None = None, **extra: Any
) -> tuple[Response, int]:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "instance": request.path,
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    resp = jsonify(body)
    resp.mimetype = PROBLEM_JSON
    return resp, status


def _validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "field": ".".join(str(p) for p in err["loc"]) or None,
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors(include_url=False, include_context=False)
    ]


def register(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        return problem(exc.status, exc.title, exc.detail, **exc.extra)

    @app.errorhandler(ValidationError)
    def _validation(exc: ValidationError):
        return problem(422, "Validation failed", errors=_validation_errors(exc))

    @app.errorhandler(HTTPException)
    def _http(exc: HTTPException):
        extra = {}
        if exc.code == 429:
            extra["retry_after"] = exc.description
            return problem(429, "Too Many Requests", "rate limit exceeded", **extra)
        return problem(exc.code or 500, exc.name, exc.description if exc.code != 404 else None)

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        log.exception("unhandled error")
        return problem(500, "Internal Server Error")
