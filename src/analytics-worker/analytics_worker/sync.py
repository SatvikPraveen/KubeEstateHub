"""Ingest listings from an external feed (CSV or JSON HTTP API) with row-level
validation. Invoked by CronJobs that the RealEstateSync operator manages."""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .repository import Repository, chunked

log = logging.getLogger(__name__)

PropertyType = Literal["residential", "commercial", "industrial", "land", "multi_family"]
Status = Literal["active", "pending", "sold", "withdrawn", "expired"]


class ListingRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    mls_number: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    property_type: PropertyType
    status: Status = "active"
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    sale_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    bedrooms: int | None = Field(default=None, ge=0, le=100)
    bathrooms: Decimal | None = Field(default=None, ge=0, le=100)
    square_feet: int | None = Field(default=None, gt=0)
    year_built: int | None = Field(default=None, ge=1800, le=2100)
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(pattern=r"^[A-Za-z]{2}$")
    zip_code: str = Field(pattern=r"^\d{5}(-\d{4})?$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    listing_date: date | None = None
    sold_date: date | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return None if isinstance(v, str) and v.strip() == "" else v

    @field_validator("state")
    @classmethod
    def _upper_state(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _sold_consistency(self) -> ListingRecord:
        if self.status == "sold" and (self.sale_price is None or self.sold_date is None):
            raise ValueError("sold listings require sale_price and sold_date")
        if self.sold_date and self.listing_date and self.sold_date < self.listing_date:
            raise ValueError("sold_date precedes listing_date")
        return self


@dataclass(frozen=True)
class SyncFilters:
    property_types: frozenset[str] = frozenset()
    price_min: float | None = None
    price_max: float | None = None
    city: str | None = None
    state: str | None = None

    def accepts(self, rec: ListingRecord) -> bool:
        if self.property_types and rec.property_type not in self.property_types:
            return False
        if self.price_min is not None and float(rec.price) < self.price_min:
            return False
        if self.price_max is not None and float(rec.price) > self.price_max:
            return False
        if self.city and rec.city.lower() != self.city.lower():
            return False
        return not (self.state and rec.state != self.state.upper())


@dataclass
class SyncResult:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    filtered: int = 0
    errors: list[str] = field(default_factory=list)


def _read_text(endpoint: str, timeout: float, headers: Mapping[str, str] | None) -> str:
    if endpoint.startswith(("http://", "https://")):
        resp = requests.get(endpoint, timeout=timeout, headers=dict(headers or {}))
        resp.raise_for_status()
        return resp.text
    path = endpoint.removeprefix("file://")
    return Path(path).read_text(encoding="utf-8")


def read_source(
    source_type: str,
    endpoint: str,
    *,
    timeout: float = 30.0,
    headers: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    if source_type == "csv":
        return list(csv.DictReader(io.StringIO(_read_text(endpoint, timeout, headers))))
    if source_type == "api":
        if endpoint.startswith(("http://", "https://")):
            resp = requests.get(endpoint, timeout=timeout, headers=dict(headers or {}))
            resp.raise_for_status()
            payload = resp.json()
        else:
            import json

            payload = json.loads(_read_text(endpoint, timeout, headers))
        records = payload.get("listings", payload) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("API payload must be a list or an object with a 'listings' list")
        return records
    raise ValueError(f"unsupported source type: {source_type!r}")


def validate_records(
    raw: Sequence[Mapping[str, Any]], filters: SyncFilters | None = None, *, max_errors: int = 20
) -> tuple[list[dict[str, Any]], SyncResult]:
    filters = filters or SyncFilters()
    result = SyncResult(processed=len(raw))
    valid: list[dict[str, Any]] = []
    for i, row in enumerate(raw):
        try:
            rec = ListingRecord.model_validate(row)
        except ValidationError as exc:
            result.failed += 1
            if len(result.errors) < max_errors:
                result.errors.append(f"row {i}: {exc.errors()[0]['msg']}")
            continue
        if not filters.accepts(rec):
            result.filtered += 1
            continue
        valid.append(rec.model_dump(exclude_none=False))
    return valid, result


def run_sync(
    repo: Repository,
    source_type: str,
    endpoint: str,
    *,
    batch_size: int = 100,
    filters: SyncFilters | None = None,
    timeout: float = 30.0,
    headers: Mapping[str, str] | None = None,
) -> SyncResult:
    raw = read_source(source_type, endpoint, timeout=timeout, headers=headers)
    valid, result = validate_records(raw, filters)
    for batch in chunked(valid, batch_size):
        result.succeeded += repo.upsert_listings(batch)
    log.info(
        "sync finished",
        extra={
            "processed": result.processed,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "filtered": result.filtered,
        },
    )
    return result
