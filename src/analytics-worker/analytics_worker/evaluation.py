"""Out-of-sample evaluation of automated valuation models (AVMs).

Metrics follow common AVM practice (IAAO *Standard on Automated Valuation Models*, 2018):

* ``mae`` / ``mape``: mean absolute (percentage) error
* ``median_ape``: median absolute percentage error (robust headline accuracy)
* ``ppe10`` / ``ppe20``: share of estimates within +/-10% / +/-20% of the sale price
* ``coverage`` and ``mean_relative_width`` for prediction intervals
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

import numpy as np
import pandas as pd

from .comparables import ComparableSalesModel
from .conformal import SplitConformal
from .hedonic import fit_hedonic

FitPredict = Callable[[pd.DataFrame, pd.DataFrame, np.random.Generator], pd.DataFrame]


def avm_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    low: np.ndarray | None = None,
    high: np.ndarray | None = None,
) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ok = np.isfinite(y_true) & np.isfinite(y_pred) & (y_true > 0)
    yt, yp = y_true[ok], y_pred[ok]
    if yt.size == 0:
        return {"n": 0}
    ape = np.abs(yp - yt) / yt
    metrics = {
        "n": int(yt.size),
        "mae": float(np.mean(np.abs(yp - yt))),
        "mape": float(np.mean(ape)),
        "median_ape": float(np.median(ape)),
        "ppe10": float(np.mean(ape <= 0.10)),
        "ppe20": float(np.mean(ape <= 0.20)),
    }
    if low is not None and high is not None:
        lo = np.asarray(low, dtype=float)[ok]
        hi = np.asarray(high, dtype=float)[ok]
        metrics["coverage"] = float(np.mean((yt >= lo) & (yt <= hi)))
        metrics["mean_relative_width"] = float(np.mean((hi - lo) / yp))
    return metrics


class CrossValidationResult(TypedDict):
    k: int
    seed: int
    pooled: dict[str, float]
    folds: list[dict[str, float]]


def cross_validate(
    sales: pd.DataFrame,
    fit_predict: FitPredict,
    *,
    k: int = 5,
    seed: int = 0,
) -> CrossValidationResult:
    """K-fold CV with pooled out-of-fold predictions and per-fold dispersion."""
    if len(sales) < k:
        raise ValueError("fewer rows than folds")
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(len(sales)), k)
    pred = np.full(len(sales), np.nan)
    low = np.full(len(sales), np.nan)
    high = np.full(len(sales), np.nan)
    per_fold = []
    for f, test_idx in enumerate(folds):
        train_idx = np.setdiff1d(np.arange(len(sales)), test_idx)
        out = fit_predict(
            sales.iloc[train_idx], sales.iloc[test_idx], np.random.default_rng(seed + f + 1)
        )
        pred[test_idx] = out["estimate"].to_numpy()
        low[test_idx] = out["low"].to_numpy()
        high[test_idx] = out["high"].to_numpy()
        y = sales["sale_price"].to_numpy(dtype=float)[test_idx]
        per_fold.append(avm_metrics(y, pred[test_idx], low[test_idx], high[test_idx]))
    pooled = avm_metrics(sales["sale_price"].to_numpy(dtype=float), pred, low, high)
    median_apes = [m["median_ape"] for m in per_fold if m.get("n")]
    pooled["median_ape_fold_std"] = (
        float(np.std(median_apes, ddof=1)) if len(median_apes) > 1 else 0.0
    )
    return {"k": k, "seed": seed, "pooled": pooled, "folds": per_fold}


def _calibration_split(
    n: int, rng: np.random.Generator, fraction: float
) -> tuple[np.ndarray, np.ndarray]:
    perm = rng.permutation(n)
    n_cal = max(1, round(n * fraction))
    return perm[n_cal:], perm[:n_cal]


def hedonic_conformal(alpha: float = 0.1, calibration_fraction: float = 0.2) -> FitPredict:
    """Hedonic point predictor + split-conformal interval."""

    def fit_predict(
        train: pd.DataFrame, test: pd.DataFrame, rng: np.random.Generator
    ) -> pd.DataFrame:
        proper_idx, cal_idx = _calibration_split(len(train), rng, calibration_fraction)
        proper, cal = train.iloc[proper_idx], train.iloc[cal_idx]
        model = fit_hedonic(proper)
        cal_pred = model.predict(cal)["estimate"].to_numpy()
        conformal = SplitConformal.calibrate(cal["sale_price"].to_numpy(), cal_pred, alpha=alpha)
        est = model.predict(test)["estimate"].to_numpy()
        lo, hi = conformal.interval(est)
        return pd.DataFrame({"estimate": est, "low": lo, "high": hi}, index=test.index)

    return fit_predict


def comparables_conformal(
    k: int = 8, alpha: float = 0.1, calibration_fraction: float = 0.2
) -> FitPredict:
    """kNN comparable-sales predictor (time-adjusted by a hedonic index) + conformal interval."""

    def fit_predict(
        train: pd.DataFrame, test: pd.DataFrame, rng: np.random.Generator
    ) -> pd.DataFrame:
        proper_idx, cal_idx = _calibration_split(len(train), rng, calibration_fraction)
        proper, cal = train.iloc[proper_idx], train.iloc[cal_idx]
        index = fit_hedonic(proper).price_index()
        comps = ComparableSalesModel(k=k).fit(proper, index)
        conformal = SplitConformal.calibrate(
            cal["sale_price"].to_numpy(), comps.predict(cal), alpha=alpha
        )
        est = comps.predict(test)
        lo, hi = conformal.interval(est)
        return pd.DataFrame({"estimate": est, "low": lo, "high": hi}, index=test.index)

    return fit_predict
