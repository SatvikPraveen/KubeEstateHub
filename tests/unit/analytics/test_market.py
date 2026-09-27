from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from analytics_worker.market import (
    MarketConfig,
    active_inventory,
    closed_sales,
    compute_market_trends,
    market_snapshot,
)
from analytics_worker.synthetic import GroundTruth, generate_market


def _frame(rows):
    base = {
        "price": 100.0,
        "sale_price": None,
        "square_feet": 1000,
        "status": "active",
        "listing_date": date(2025, 1, 1),
        "sold_date": None,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_closed_sales_window_is_left_open_right_closed():
    df = _frame(
        [
            {"status": "sold", "sale_price": 1.0, "sold_date": date(2025, 1, 10)},
            {"status": "sold", "sale_price": 1.0, "sold_date": date(2025, 1, 31)},
            {"status": "sold", "sale_price": 1.0, "sold_date": date(2025, 2, 1)},
        ]
    )
    assert len(closed_sales(df, date(2025, 1, 10), date(2025, 1, 31))) == 1


def test_active_inventory_counts_listings_sold_after_as_of():
    df = _frame(
        [
            {"status": "active"},
            {"status": "pending"},
            {"status": "sold", "sale_price": 1.0, "sold_date": date(2025, 3, 1)},
            {"status": "sold", "sale_price": 1.0, "sold_date": date(2025, 1, 15)},
            {"status": "withdrawn"},
            {"status": "active", "listing_date": date(2025, 6, 1)},
        ]
    )
    assert active_inventory(df, date(2025, 2, 1)) == 3


def test_snapshot_indicators_on_hand_computed_example():
    as_of = date(2025, 3, 31)
    sold = [
        {
            "status": "sold",
            "price": 100_000.0,
            "sale_price": 98_000.0 + i * 1000,
            "square_feet": 1000,
            "listing_date": as_of - timedelta(days=40),
            "sold_date": as_of - timedelta(days=10 + i),
        }
        for i in range(9)
    ]
    active = [{"status": "active", "listing_date": as_of - timedelta(days=5)} for _ in range(6)]
    snap = market_snapshot(
        _frame(sold + active),
        city="Austin",
        state="TX",
        property_type=None,
        as_of=as_of,
        config=MarketConfig(window_days=90),
    )
    assert snap.n_sales == 9
    assert snap.n_active == 6
    assert snap.median_sale_price == pytest.approx(102_000.0)
    assert snap.median_sale_price_ci_low <= 102_000.0 <= snap.median_sale_price_ci_high
    assert snap.median_price_per_sqft == pytest.approx(102.0)
    assert snap.median_days_on_market == pytest.approx(26.0)
    assert snap.sale_to_list_ratio == pytest.approx(1.02)
    monthly_rate = 9 / (90 / 30.4375)
    assert snap.months_of_supply == pytest.approx(6 / monthly_rate)
    assert snap.absorption_rate == pytest.approx(monthly_rate / 6)
    assert snap.trend_direction == "insufficient_data"


def test_empty_segment_has_no_ratios():
    snap = market_snapshot(
        _frame([{"status": "active"}]),
        city="X",
        state="TX",
        property_type=None,
        as_of=date(2025, 3, 1),
    )
    assert snap.n_sales == 0
    assert snap.months_of_supply is None
    assert snap.median_sale_price is None


def _single_city(growth):
    base = GroundTruth()
    city = replace(base.cities["Austin"], monthly_growth=growth, weight=1.0)
    return replace(base, cities={"Austin": city}, noise_sigma=0.08)


@pytest.mark.parametrize(("growth", "expected"), [(0.012, "up"), (-0.012, "down")])
def test_trend_detects_true_appreciation(growth, expected):
    df, _ = generate_market(4000, seed=21, months=18, truth=_single_city(growth))
    snaps = compute_market_trends(df, as_of=date(2025, 6, 30), include_all_types=True)
    overall = next(s for s in snaps if s.property_type is None)
    assert overall.trend_direction == expected
    true_pct = 100 * np.expm1(growth)
    assert overall.trend_slope_ci_low <= true_pct <= overall.trend_slope_ci_high


def test_no_trend_is_usually_flat():
    df, _ = generate_market(4000, seed=22, months=18, truth=_single_city(0.0))
    snaps = compute_market_trends(df, as_of=date(2025, 6, 30))
    overall = next(s for s in snaps if s.property_type is None)
    assert overall.trend_direction == "flat"


def test_compute_market_trends_segments(market):
    df, _ = market
    snaps = compute_market_trends(df, as_of=date(2025, 12, 31))
    cities = df["city"].nunique()
    segments = df.groupby(["city", "state", "property_type"]).ngroups
    assert len(snaps) == segments + cities
    assert all(s.period_end == date(2025, 12, 31) for s in snaps)
    record = snaps[0].to_record()
    assert set(record) >= {"city", "months_of_supply", "trend_direction"}
