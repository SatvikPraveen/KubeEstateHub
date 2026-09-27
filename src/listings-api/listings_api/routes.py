from __future__ import annotations

import hmac
import json
import math
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from .errors import ApiError
from .repository import ConstraintViolationError, DuplicateListingError
from .schemas import ListingCreate, ListingQuery, ListingUpdate, MarketQuery

api = Blueprint("api", __name__, url_prefix="/api/v1")


def _deps():
    return current_app.extensions["keh"]


def _normalise(body: Any) -> Any:
    """Round-trip through the app JSON provider so cached and fresh responses match."""
    return json.loads(current_app.json.dumps(body))


def _json_body() -> dict[str, Any]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "Bad Request", "request body must be a JSON object")
    return body


def require_write_token() -> None:
    token = _deps().settings.write_token
    if not token:
        return
    header = request.headers.get("Authorization", "")
    scheme, _, supplied = header.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(supplied.encode(), token.encode()):
        raise ApiError(401, "Unauthorized", "a valid bearer token is required for write operations")


def _cached(namespace: str, params: dict[str, Any], producer) -> tuple[Any, int, dict[str, str]]:
    cache = _deps().cache
    key = cache.key(namespace, params)
    if (hit := cache.get(key)) is not None:
        return jsonify(hit), 200, {"X-Cache": "HIT"}
    body = _normalise(producer())
    cache.set(key, body)
    return jsonify(body), 200, {"X-Cache": "MISS" if key else "BYPASS"}


@api.get("/listings")
def list_listings():
    deps = _deps()
    args: dict[str, Any] = request.args.to_dict()
    args.setdefault("per_page", deps.settings.default_page_size)
    query = ListingQuery.model_validate(args)
    per_page = min(query.per_page, deps.settings.max_page_size)

    def produce() -> dict[str, Any]:
        rows, total = deps.repo.list_listings(
            query, limit=per_page, offset=(query.page - 1) * per_page
        )
        return {
            "listings": rows,
            "pagination": {
                "page": query.page,
                "per_page": per_page,
                "total": total,
                "pages": math.ceil(total / per_page) if total else 0,
            },
        }

    return _cached("list", {**query.model_dump(mode="json"), "per_page": per_page}, produce)


@api.get("/listings/<int:listing_id>")
def get_listing(listing_id: int):
    def produce() -> dict[str, Any]:
        row = _deps().repo.get_listing(listing_id)
        if row is None:
            raise ApiError(404, "Not Found", f"listing {listing_id} does not exist")
        return {"listing": row}

    return _cached("get", {"id": listing_id}, produce)


@api.post("/listings")
def create_listing():
    require_write_token()
    payload = ListingCreate.model_validate(_json_body())
    deps = _deps()
    try:
        row = deps.repo.create_listing(payload.model_dump())
    except DuplicateListingError as exc:
        raise ApiError(409, "Conflict", f"MLS number {exc} already exists") from exc
    except ConstraintViolationError as exc:
        raise ApiError(422, "Constraint violation", str(exc)) from exc
    deps.cache.invalidate()
    resp = jsonify(_normalise({"listing": row}))
    resp.headers["Location"] = f"/api/v1/listings/{row['id']}"
    return resp, 201


@api.patch("/listings/<int:listing_id>")
def update_listing(listing_id: int):
    require_write_token()
    payload = ListingUpdate.model_validate(_json_body())
    deps = _deps()
    try:
        row = deps.repo.update_listing(listing_id, payload.model_dump(exclude_unset=True))
    except ConstraintViolationError as exc:
        raise ApiError(422, "Constraint violation", str(exc)) from exc
    if row is None:
        raise ApiError(404, "Not Found", f"listing {listing_id} does not exist")
    deps.cache.invalidate()
    return jsonify(_normalise({"listing": row}))


@api.delete("/listings/<int:listing_id>")
def delete_listing(listing_id: int):
    require_write_token()
    deps = _deps()
    if not deps.repo.delete_listing(listing_id):
        raise ApiError(404, "Not Found", f"listing {listing_id} does not exist")
    deps.cache.invalidate()
    return "", 204


@api.get("/market/summary")
def market_summary():
    q = MarketQuery.model_validate(request.args.to_dict())
    return _cached(
        "summary",
        q.model_dump(),
        lambda: {"summary": _deps().repo.market_summary(q.city, q.property_type)},
    )


@api.get("/market/trends")
def market_trends():
    q = MarketQuery.model_validate(request.args.to_dict())
    return _cached(
        "trends",
        q.model_dump(),
        lambda: {"trends": _deps().repo.market_trends(q.city, q.property_type)},
    )


@api.get("/market/price-index")
def price_index():
    return _cached("index", {}, lambda: _deps().repo.price_index())


@api.get("/model-runs/latest")
def latest_model_run():
    run = _deps().repo.latest_model_run()
    if run is None:
        raise ApiError(404, "Not Found", "no successful model run yet")
    return jsonify(_normalise({"model_run": run}))
