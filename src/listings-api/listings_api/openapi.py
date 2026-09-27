"""OpenAPI 3.1 document generated from the pydantic request models, so the published
contract cannot drift from validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .schemas import ListingCreate, ListingQuery, ListingUpdate, MarketQuery

PROBLEM = {"$ref": "#/components/responses/Problem"}


def _query_params(model: type[BaseModel]) -> list[dict[str, Any]]:
    schema = model.model_json_schema()
    return [
        {
            "name": name,
            "in": "query",
            "required": False,
            "schema": {k: v for k, v in prop.items() if k != "title"},
        }
        for name, prop in schema["properties"].items()
    ]


def _defs(*models: type[BaseModel]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for m in models:
        schema = m.model_json_schema(ref_template="#/components/schemas/{model}")
        out.update(schema.pop("$defs", {}))
        out[m.__name__] = schema
    return out


def build_spec(version: str) -> dict[str, Any]:
    listing_id = {
        "name": "listing_id",
        "in": "path",
        "required": True,
        "schema": {"type": "integer", "minimum": 1},
    }
    json_body = lambda name: {  # noqa: E731
        "required": True,
        "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{name}"}}},
    }
    ok = lambda desc: {"description": desc, "content": {"application/json": {}}}  # noqa: E731
    write_security: list[dict[str, list[str]]] = [{"bearerAuth": []}]
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "KubeEstateHub Listings API",
            "version": version,
            "description": "Property listings, market indicators and model provenance. Errors use RFC 9457 "
            "problem details. Write operations require a bearer token when API_WRITE_TOKEN is configured.",
            "license": {"name": "MIT"},
        },
        "servers": [{"url": "/"}],
        "paths": {
            "/api/v1/listings": {
                "get": {
                    "summary": "Search listings",
                    "operationId": "listListings",
                    "parameters": _query_params(ListingQuery),
                    "responses": {"200": ok("Page of listings"), "422": PROBLEM},
                },
                "post": {
                    "summary": "Create a listing",
                    "operationId": "createListing",
                    "security": write_security,
                    "requestBody": json_body("ListingCreate"),
                    "responses": {
                        "201": ok("Created"),
                        "401": PROBLEM,
                        "409": PROBLEM,
                        "422": PROBLEM,
                        "429": PROBLEM,
                    },
                },
            },
            "/api/v1/listings/{listing_id}": {
                "parameters": [listing_id],
                "get": {
                    "summary": "Get a listing with its latest valuation",
                    "operationId": "getListing",
                    "responses": {"200": ok("Listing"), "404": PROBLEM},
                },
                "patch": {
                    "summary": "Partially update a listing",
                    "operationId": "updateListing",
                    "security": write_security,
                    "requestBody": json_body("ListingUpdate"),
                    "responses": {
                        "200": ok("Updated"),
                        "401": PROBLEM,
                        "404": PROBLEM,
                        "422": PROBLEM,
                    },
                },
                "delete": {
                    "summary": "Soft-delete a listing",
                    "operationId": "deleteListing",
                    "security": write_security,
                    "responses": {
                        "204": {"description": "Deleted"},
                        "401": PROBLEM,
                        "404": PROBLEM,
                    },
                },
            },
            "/api/v1/market/summary": {
                "get": {
                    "summary": "Live market summary",
                    "operationId": "marketSummary",
                    "parameters": _query_params(MarketQuery),
                    "responses": {"200": ok("Summary")},
                }
            },
            "/api/v1/market/trends": {
                "get": {
                    "summary": "Latest statistical trend per segment",
                    "operationId": "marketTrends",
                    "parameters": _query_params(MarketQuery),
                    "responses": {"200": ok("Trends")},
                }
            },
            "/api/v1/market/price-index": {
                "get": {
                    "summary": "Hedonic price index (latest model run)",
                    "operationId": "priceIndex",
                    "responses": {"200": ok("Index series")},
                }
            },
            "/api/v1/model-runs/latest": {
                "get": {
                    "summary": "Provenance and metrics of the latest model run",
                    "operationId": "latestModelRun",
                    "responses": {"200": ok("Model run"), "404": PROBLEM},
                }
            },
            "/livez": {"get": {"summary": "Liveness", "responses": {"200": ok("Alive")}}},
            "/readyz": {
                "get": {"summary": "Readiness", "responses": {"200": ok("Ready"), "503": PROBLEM}}
            },
        },
        "components": {
            "schemas": _defs(ListingCreate, ListingUpdate),
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
            "responses": {
                "Problem": {
                    "description": "RFC 9457 problem details",
                    "content": {
                        "application/problem+json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "title": {"type": "string"},
                                    "status": {"type": "integer"},
                                    "detail": {"type": "string"},
                                    "instance": {"type": "string"},
                                    "errors": {"type": "array"},
                                },
                                "required": ["title", "status"],
                            }
                        }
                    },
                }
            },
        },
    }
