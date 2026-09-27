"""End-to-end batch pipeline: market indicators, price index, model evaluation and
valuations of open listings, written with full provenance to ``model_runs``."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd

from . import __version__
from .conformal import SplitConformal
from .evaluation import comparables_conformal, cross_validate, hedonic_conformal
from .hedonic import NUMERIC_FEATURES, PERIOD, fit_hedonic, prepare, sales_sample
from .market import OPEN_STATUSES, MarketConfig, compute_market_trends
from .repository import Repository

log = logging.getLogger(__name__)
PIPELINE_NAME = "market-analytics"


@dataclass(frozen=True)
class PipelineConfig:
    as_of: date | None = None
    seed: int = 0
    cv_folds: int = 5
    alpha: float = 0.10
    calibration_fraction: float = 0.2
    min_sales_for_model: int = 200
    market: MarketConfig = field(default_factory=MarketConfig)

    def parameters(self) -> dict[str, Any]:
        params = asdict(self)
        params["as_of"] = (self.as_of or datetime.now(UTC).date()).isoformat()
        return params


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    metrics: dict[str, Any]


def _value_open_listings(
    df: pd.DataFrame, sales: pd.DataFrame, cfg: PipelineConfig, rng: np.random.Generator
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    perm = rng.permutation(len(sales))
    n_cal = max(1, round(len(sales) * cfg.calibration_fraction))
    proper, cal = sales.iloc[perm[n_cal:]], sales.iloc[perm[:n_cal]]
    model = fit_hedonic(proper)
    conformal = SplitConformal.calibrate(
        cal["sale_price"].to_numpy(), model.predict(cal)["estimate"].to_numpy(), alpha=cfg.alpha
    )
    open_listings = df[df["status"].isin(OPEN_STATUSES)]
    if open_listings.empty:
        return [], {"conformal_log_quantile": conformal.quantile}
    prepared = prepare(open_listings, reference_date="listing_date")
    pred = model.predict(prepared, period=model.latest_period)
    low, high = conformal.interval(pred["estimate"].to_numpy())
    rows = [
        {
            "listing_id": int(lid),
            "method": "hedonic_conformal",
            "estimated_value": round(float(est), 2),
            "interval_low": round(float(lo), 2),
            "interval_high": round(float(hi), 2),
            "confidence_level": conformal.confidence,
        }
        for lid, est, lo, hi, ok in zip(
            prepared["id"], pred["estimate"], low, high, pred["valid"], strict=True
        )
        if ok and np.isfinite(est)
    ]
    return rows, {
        "conformal_log_quantile": conformal.quantile,
        "valuation_period": str(model.latest_period.date()),
        "n_open_listings": len(open_listings),
    }


def run_pipeline(
    repo: Repository, config: PipelineConfig | None = None, *, code_version: str = __version__
) -> PipelineResult:
    cfg = config or PipelineConfig()
    as_of = cfg.as_of or datetime.now(UTC).date()
    run_id = repo.start_run(PIPELINE_NAME, code_version, cfg.seed, cfg.parameters())
    started = time.perf_counter()
    n_sales: int | None = None
    try:
        df = repo.load_listings()
        trends = compute_market_trends(df, as_of=as_of, config=cfg.market, seed=cfg.seed)
        repo.write_trends(run_id, [t.to_record() for t in trends])
        sales = sales_sample(df)
        n_sales = len(sales)
        metrics: dict[str, Any] = {
            "as_of": as_of.isoformat(),
            "n_listings": len(df),
            "n_sales": n_sales,
            "n_segments": len(trends),
            "segments_trending_up": sum(t.trend_direction == "up" for t in trends),
            "segments_trending_down": sum(t.trend_direction == "down" for t in trends),
        }
        if n_sales >= cfg.min_sales_for_model:
            model = fit_hedonic(sales)
            index = model.price_index()
            counts = sales.groupby(PERIOD).size()
            index["n_sales"] = index["period"].map(counts).fillna(0).astype(int)
            repo.write_price_index(run_id, index)
            metrics["hedonic"] = {
                "n": model.n_obs,
                "r_squared": model.r_squared,
                "residual_sigma": float(np.sqrt(model.sigma2)),
                "smearing": model.smearing,
                "coefficients": {
                    f: dict(zip(("estimate", "hc1_se"), model.coefficient(f), strict=True))
                    for f in NUMERIC_FEATURES
                },
            }
            metrics["cross_validation"] = {
                "hedonic_conformal": cross_validate(
                    sales,
                    hedonic_conformal(cfg.alpha, cfg.calibration_fraction),
                    k=cfg.cv_folds,
                    seed=cfg.seed,
                )["pooled"],
                "comparables_conformal": cross_validate(
                    sales,
                    comparables_conformal(
                        alpha=cfg.alpha, calibration_fraction=cfg.calibration_fraction
                    ),
                    k=cfg.cv_folds,
                    seed=cfg.seed,
                )["pooled"],
            }
            valuations, extra = _value_open_listings(
                df, sales, cfg, np.random.default_rng(cfg.seed)
            )
            repo.write_valuations(run_id, valuations)
            metrics.update(extra, n_valuations=len(valuations))
        else:
            metrics["model_skipped"] = (
                f"need >= {cfg.min_sales_for_model} complete sales, have {n_sales}"
            )
        metrics["duration_seconds"] = round(time.perf_counter() - started, 3)
        repo.finish_run(run_id, status="succeeded", n_observations=n_sales, metrics=metrics)
        log.info("pipeline succeeded", extra={"run_id": run_id, "metrics": metrics})
        return PipelineResult(run_id, metrics)
    except Exception as exc:
        repo.finish_run(
            run_id,
            status="failed",
            n_observations=n_sales,
            metrics={"duration_seconds": round(time.perf_counter() - started, 3)},
            error=f"{type(exc).__name__}: {exc}",
        )
        log.exception("pipeline failed", extra={"run_id": run_id})
        raise
