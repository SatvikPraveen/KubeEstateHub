"""Market indicators for a geographic/product segment.

Definitions (see docs/research/methodology.md):

* **Days on market (DOM):** ``sold_date - listing_date`` for closed sales.
* **Sale-to-list ratio:** median of ``sale_price / list_price`` over closed sales.
* **Months of supply:** active inventory divided by the monthly closed-sales rate.
* **Absorption rate:** monthly closed-sales rate divided by active inventory.
* **Trend:** Theil-Sen slope of the log monthly median sale price *per square foot*
  (a simple composition adjustment; reported as % per month with Sen's CI) and a
  two-sided Mann-Kendall test on the same series. The direction is ``up`` or
  ``down`` only when the Mann-Kendall p-value is below ``alpha``; otherwise ``flat``.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .stats import bootstrap_ci, mann_kendall, theil_sen

DAYS_PER_MONTH = 30.4375
OPEN_STATUSES = frozenset({"active", "pending"})


@dataclass(frozen=True)
class MarketConfig:
    window_days: int = 90
    trend_months: int = 12
    min_sales_per_month: int = 3
    min_trend_months: int = 4
    alpha: float = 0.05
    confidence: float = 0.95
    n_bootstrap: int = 2000


@dataclass(frozen=True)
class MarketSnapshot:
    city: str
    state: str
    property_type: str | None
    period_start: date
    period_end: date
    n_sales: int
    n_active: int
    median_sale_price: float | None
    median_sale_price_ci_low: float | None
    median_sale_price_ci_high: float | None
    median_price_per_sqft: float | None
    median_days_on_market: float | None
    sale_to_list_ratio: float | None
    months_of_supply: float | None
    absorption_rate: float | None
    trend_slope_pct_per_month: float | None
    trend_slope_ci_low: float | None
    trend_slope_ci_high: float | None
    mann_kendall_tau: float | None
    mann_kendall_p: float | None
    trend_direction: str

    def to_record(self) -> dict[str, object]:
        return asdict(self)


def _to_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def closed_sales(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Closed sales with ``start < sold_date <= end``."""
    sold = _to_dates(df["sold_date"])
    mask = (
        (df["status"] == "sold")
        & df["sale_price"].notna()
        & (sold > pd.Timestamp(start))
        & (sold <= pd.Timestamp(end))
    )
    return df.loc[mask]


def active_inventory(df: pd.DataFrame, as_of: date) -> int:
    """Listings on the market at ``as_of`` (listed, and not closed by then)."""
    listed = _to_dates(df["listing_date"]) <= pd.Timestamp(as_of)
    sold_later = (df["status"] == "sold") & (_to_dates(df["sold_date"]) > pd.Timestamp(as_of))
    return int((listed & (df["status"].isin(OPEN_STATUSES) | sold_later)).sum())


def _pct(log_slope: float) -> float:
    return 100.0 * math.expm1(log_slope)


def _trend(
    df: pd.DataFrame, as_of: date, cfg: MarketConfig
) -> tuple[float | None, float | None, float | None, float | None, float | None, str]:
    start = (pd.Timestamp(as_of) - pd.DateOffset(months=cfg.trend_months)).date()
    sales = closed_sales(df, start, as_of)
    if sales.empty:
        return None, None, None, None, None, "insufficient_data"
    months = _to_dates(sales["sold_date"]).dt.to_period("M")
    ppsf = sales["sale_price"].astype(float) / sales["square_feet"].astype(float)
    frame = pd.DataFrame({"_m": months, "ppsf": ppsf}).dropna()
    monthly = frame.groupby("_m")["ppsf"].agg(["median", "size"])
    monthly = monthly[monthly["size"] >= cfg.min_sales_per_month].sort_index()
    if len(monthly) < cfg.min_trend_months:
        return None, None, None, None, None, "insufficient_data"
    base = monthly.index.min()
    t = np.array([(p - base).n for p in monthly.index], dtype=float)
    y = np.log(monthly["median"].to_numpy(dtype=float))
    ts = theil_sen(t, y, confidence=cfg.confidence)
    mk = mann_kendall(y)
    return (
        _pct(ts.slope),
        _pct(ts.low_slope),
        _pct(ts.high_slope),
        mk.tau,
        mk.p_value,
        mk.direction(cfg.alpha),
    )


def market_snapshot(
    df: pd.DataFrame,
    *,
    city: str,
    state: str,
    property_type: str | None,
    as_of: date,
    config: MarketConfig | None = None,
    rng: np.random.Generator | None = None,
) -> MarketSnapshot:
    """Compute indicators for one segment. ``df`` must already be filtered to it."""
    cfg = config or MarketConfig()
    rng = rng if rng is not None else np.random.default_rng(0)
    period_start = as_of - timedelta(days=cfg.window_days)
    sales = closed_sales(df, period_start, as_of)
    n_sales = len(sales)
    n_active = active_inventory(df, as_of)

    median_price = ci_low = ci_high = ppsf = dom = s2l = None
    if n_sales:
        prices = sales["sale_price"].to_numpy(dtype=float)
        ci = bootstrap_ci(
            prices, np.median, n_resamples=cfg.n_bootstrap, confidence=cfg.confidence, rng=rng
        )
        median_price, ci_low, ci_high = ci.estimate, ci.low, ci.high
        sqft = sales["square_feet"].to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            per_sqft = prices / sqft
        per_sqft = per_sqft[np.isfinite(per_sqft)]
        ppsf = float(np.median(per_sqft)) if per_sqft.size else None
        days = (_to_dates(sales["sold_date"]) - _to_dates(sales["listing_date"])).dt.days
        dom = float(days.median()) if days.notna().any() else None
        s2l = float(np.median(prices / sales["price"].to_numpy(dtype=float)))

    monthly_rate = n_sales / (cfg.window_days / DAYS_PER_MONTH)
    months_of_supply = n_active / monthly_rate if monthly_rate > 0 else None
    absorption = monthly_rate / n_active if n_active > 0 else None

    slope, slope_lo, slope_hi, tau, p_value, direction = _trend(df, as_of, cfg)
    return MarketSnapshot(
        city=city,
        state=state,
        property_type=property_type,
        period_start=period_start,
        period_end=as_of,
        n_sales=n_sales,
        n_active=n_active,
        median_sale_price=median_price,
        median_sale_price_ci_low=ci_low,
        median_sale_price_ci_high=ci_high,
        median_price_per_sqft=ppsf,
        median_days_on_market=dom,
        sale_to_list_ratio=s2l,
        months_of_supply=months_of_supply,
        absorption_rate=absorption,
        trend_slope_pct_per_month=slope,
        trend_slope_ci_low=slope_lo,
        trend_slope_ci_high=slope_hi,
        mann_kendall_tau=tau,
        mann_kendall_p=p_value,
        trend_direction=direction,
    )


def compute_market_trends(
    df: pd.DataFrame,
    *,
    as_of: date,
    config: MarketConfig | None = None,
    include_all_types: bool = True,
    min_listings: int = 1,
    seed: int = 0,
) -> list[MarketSnapshot]:
    """Snapshots for every (city, state, property_type) segment, plus an all-types row
    per city when ``include_all_types`` is true."""
    rng = np.random.default_rng(seed)
    out: list[MarketSnapshot] = []
    for key, seg in df.groupby(["city", "state", "property_type"], sort=True, observed=True):
        city, state, ptype = (str(k) for k in key)
        if len(seg) >= min_listings:
            out.append(
                market_snapshot(
                    seg,
                    city=city,
                    state=state,
                    property_type=ptype,
                    as_of=as_of,
                    config=config,
                    rng=rng,
                )
            )
    if include_all_types:
        for key, seg in df.groupby(["city", "state"], sort=True, observed=True):
            city, state = (str(k) for k in key)
            if len(seg) >= min_listings:
                out.append(
                    market_snapshot(
                        seg,
                        city=city,
                        state=state,
                        property_type=None,
                        as_of=as_of,
                        config=config,
                        rng=rng,
                    )
                )
    return out
