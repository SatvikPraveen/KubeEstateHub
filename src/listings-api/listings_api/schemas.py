"""Request validation. The same models generate the OpenAPI component schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PropertyType = Literal["residential", "commercial", "industrial", "land", "multi_family"]
Status = Literal["active", "pending", "sold", "withdrawn", "expired"]
SortKey = Literal[
    "-listing_date", "listing_date", "price", "-price", "price_per_sqft", "-price_per_sqft"
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ListingBase(_Strict):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    property_type: PropertyType
    status: Status = "active"
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2, description="List price (USD)")
    sale_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    bedrooms: int | None = Field(default=None, ge=0, le=100)
    bathrooms: Decimal | None = Field(default=None, ge=0, le=100, max_digits=3, decimal_places=1)
    square_feet: int | None = Field(default=None, gt=0, le=10_000_000)
    lot_size_sqft: int | None = Field(default=None, gt=0)
    year_built: int | None = Field(default=None, ge=1800, le=2100)
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    zip_code: str = Field(pattern=r"^\d{5}(-\d{4})?$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    listing_date: date | None = None
    sold_date: date | None = None
    agent_name: str | None = Field(default=None, max_length=100)
    agent_email: str | None = Field(
        default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    agent_phone: str | None = Field(default=None, max_length=30)
    image_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")
    thumbnail_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")

    @field_validator("state", mode="before")
    @classmethod
    def _upper_state(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v


class ListingCreate(ListingBase):
    mls_number: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")

    @model_validator(mode="after")
    def _sold_consistency(self) -> ListingCreate:
        if self.status == "sold" and (self.sale_price is None or self.sold_date is None):
            raise ValueError("status 'sold' requires sale_price and sold_date")
        if self.sold_date and self.listing_date and self.sold_date < self.listing_date:
            raise ValueError("sold_date must not precede listing_date")
        return self


class ListingUpdate(_Strict):
    """Partial update: every field optional; explicit nulls clear nullable columns."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    status: Status | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    sale_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    sold_date: date | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=100)
    bathrooms: Decimal | None = Field(default=None, ge=0, le=100, max_digits=3, decimal_places=1)
    square_feet: int | None = Field(default=None, gt=0, le=10_000_000)
    agent_name: str | None = Field(default=None, max_length=100)
    agent_email: str | None = Field(
        default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    agent_phone: str | None = Field(default=None, max_length=30)
    image_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")
    thumbnail_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")

    @model_validator(mode="after")
    def _not_empty(self) -> ListingUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class ListingQuery(_Strict):
    page: int = Field(default=1, ge=1, le=10_000)
    per_page: int = Field(default=20, ge=1)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    property_type: PropertyType | None = None
    status: Status = "active"
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_bedrooms: int | None = Field(default=None, ge=0)
    q: str | None = Field(default=None, min_length=2, max_length=100, description="Title search")
    sort: SortKey = "-listing_date"

    @model_validator(mode="after")
    def _price_range(self) -> ListingQuery:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must not exceed max_price")
        return self


class MarketQuery(_Strict):
    city: str | None = Field(default=None, max_length=100)
    property_type: PropertyType | None = None
