"""Synthetic housing market with known ground truth.

Used to validate the estimators (parameter recovery, index recovery, interval coverage,
trend-test size and power) and to seed demo environments reproducibly. The
data-generating process is exactly the hedonic model in :mod:`hedonic` plus
city-specific appreciation, so estimates can be compared with true values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CitySpec:
    state: str
    effect: float  # log-price level relative to the model intercept
    monthly_growth: float  # log appreciation per month
    center: tuple[float, float]  # (lat, lon)
    weight: float = 1.0


DEFAULT_CITIES: dict[str, CitySpec] = {
    "Austin": CitySpec("TX", 0.00, 0.006, (30.2672, -97.7431), 1.2),
    "Dallas": CitySpec("TX", -0.08, 0.004, (32.7767, -96.7970), 1.0),
    "Houston": CitySpec("TX", -0.15, 0.002, (29.7604, -95.3698), 1.3),
    "San Antonio": CitySpec("TX", -0.25, 0.000, (29.4241, -98.4936), 0.8),
    "Tampa": CitySpec("FL", -0.10, -0.004, (27.9506, -82.4572), 0.7),
}


@dataclass(frozen=True)
class GroundTruth:
    intercept: float = 6.3
    log_sqft: float = 0.85
    bedrooms: float = -0.02
    bathrooms: float = 0.06
    age: float = -0.004
    type_effects: dict[str, float] = field(
        default_factory=lambda: {"residential": 0.0, "multi_family": -0.05, "commercial": 0.10}
    )
    type_weights: dict[str, float] = field(
        default_factory=lambda: {"residential": 0.8, "multi_family": 0.1, "commercial": 0.1}
    )
    noise_sigma: float = 0.12
    cities: dict[str, CitySpec] = field(default_factory=lambda: dict(DEFAULT_CITIES))


def generate_market(
    n: int = 3000,
    *,
    seed: int = 42,
    start: date = date(2024, 1, 1),
    months: int = 24,
    truth: GroundTruth | None = None,
    sold_fraction: float = 0.8,
) -> tuple[pd.DataFrame, GroundTruth]:
    """Generate ``n`` listings; closed sales carry ``sale_price`` and ``sold_date``.

    The observation window ends at ``start + months``; listings whose sale would fall
    after the window stay active (right-censoring, as in real MLS snapshots).
    """
    truth = truth or GroundTruth()
    rng = np.random.default_rng(seed)
    cities = list(truth.cities)
    weights = np.array([truth.cities[c].weight for c in cities])
    city = rng.choice(cities, size=n, p=weights / weights.sum())
    types = list(truth.type_effects)
    type_p = np.array([truth.type_weights.get(t, 0.0) for t in types])
    ptype = rng.choice(types, size=n, p=type_p / type_p.sum())

    sqft = np.clip(np.exp(rng.normal(7.5, 0.35, n)), 450, 9000).round()
    beds = np.clip(np.round(sqft / 650 + rng.normal(0, 0.7, n)), 1, 7)
    baths = np.clip(np.round((beds * 0.6 + rng.normal(0.4, 0.4, n)) * 2) / 2, 1, 6)
    year_built = rng.integers(1950, 2025, n)

    start_ts = pd.Timestamp(start)
    end_ts = start_ts + pd.DateOffset(months=months)
    horizon = (end_ts - start_ts).days
    listing_offset = rng.integers(0, horizon, n)
    listing_date = start_ts + pd.to_timedelta(listing_offset, unit="D")
    dom = np.round(7 + rng.gamma(2.0, 18.0, n)).astype(int)
    sold_date = listing_date + pd.to_timedelta(dom, unit="D")
    will_sell = rng.random(n) < sold_fraction
    is_sold = will_sell & (sold_date < end_ts)

    city_effect = np.array([truth.cities[c].effect for c in city])
    growth = np.array([truth.cities[c].monthly_growth for c in city])
    type_effect = np.array([truth.type_effects[t] for t in ptype])
    ref_date = pd.DatetimeIndex(np.where(is_sold, sold_date, listing_date))
    month_idx = (ref_date.year - start_ts.year) * 12 + (ref_date.month - start_ts.month)
    age = ref_date.year - year_built
    log_value = (
        truth.intercept
        + truth.log_sqft * np.log(sqft)
        + truth.bedrooms * beds
        + truth.bathrooms * baths
        + truth.age * age
        + city_effect
        + type_effect
        + growth * month_idx
        + rng.normal(0, truth.noise_sigma, n)
    )
    value = np.exp(log_value)
    list_premium = np.exp(rng.normal(0.02, 0.02, n))
    list_price = np.round(value * list_premium, -2)
    sale_price = np.where(is_sold, np.round(value, -2), np.nan)

    status = np.where(is_sold, "sold", "active").astype(object)
    withdrawn = (~is_sold) & (rng.random(n) < 0.1)
    status[withdrawn] = "withdrawn"
    lat = np.array([truth.cities[c].center[0] for c in city]) + rng.normal(0, 0.05, n)
    lon = np.array([truth.cities[c].center[1] for c in city]) + rng.normal(0, 0.05, n)

    df = pd.DataFrame(
        {
            "mls_number": [f"SYN{seed:04d}-{i:06d}" for i in range(n)],
            "title": [
                f"{int(b)} bd {t.replace('_', ' ')} in {c}"
                for b, t, c in zip(beds, ptype, city, strict=True)
            ],
            "property_type": ptype,
            "status": status,
            "price": list_price,
            "sale_price": sale_price,
            "bedrooms": beds.astype(int),
            "bathrooms": baths,
            "square_feet": sqft.astype(int),
            "year_built": year_built,
            "address": [f"{rng.integers(100, 9999)} Synthetic Way" for _ in range(n)],
            "city": city,
            "state": [truth.cities[c].state for c in city],
            "zip_code": [f"{rng.integers(10000, 99999)}" for _ in range(n)],
            "latitude": lat.round(6),
            "longitude": lon.round(6),
            "listing_date": listing_date.date,
            "sold_date": pd.Series(sold_date.date).where(is_sold, None).to_numpy(),
        }
    )
    return df, truth
