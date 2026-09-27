"""Robust, dependency-light statistics used throughout the analytics pipeline.

All functions are pure and deterministic given an explicit ``numpy.random.Generator``.
Implementations follow the cited references and are cross-validated against SciPy in
the unit tests when SciPy is available.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
from numpy.typing import ArrayLike, NDArray

_STD_NORMAL = NormalDist()


def normal_quantile(p: float) -> float:
    """Inverse CDF of the standard normal distribution."""
    return _STD_NORMAL.inv_cdf(p)


def _as_1d(x: ArrayLike) -> NDArray[np.float64]:
    arr = np.asarray(x, dtype=float).ravel()
    return arr[np.isfinite(arr)]


@dataclass(frozen=True)
class ConfidenceInterval:
    estimate: float
    low: float
    high: float
    confidence: float


def bootstrap_ci(
    x: ArrayLike,
    statistic: Callable[..., NDArray[np.float64]] = np.median,
    *,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    rng: np.random.Generator | None = None,
) -> ConfidenceInterval:
    """Percentile bootstrap confidence interval (Efron & Tibshirani, 1993, ch. 13).

    ``statistic`` must accept an ``axis`` keyword (e.g. ``np.median``, ``np.mean``) so that
    all resamples are evaluated in one vectorised call.
    """
    data = _as_1d(x)
    if data.size == 0:
        raise ValueError("bootstrap_ci requires at least one finite observation")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    rng = rng if rng is not None else np.random.default_rng(0)
    estimate = float(statistic(data))
    if data.size == 1:
        return ConfidenceInterval(estimate, estimate, estimate, confidence)
    idx = rng.integers(0, data.size, size=(n_resamples, data.size))
    replicates = statistic(data[idx], axis=1)
    alpha = 1.0 - confidence
    low, high = np.quantile(replicates, [alpha / 2, 1 - alpha / 2])
    return ConfidenceInterval(estimate, float(low), float(high), confidence)


def median_abs_deviation(x: ArrayLike, *, scale: float = 1.4826) -> float:
    """MAD scaled to be a consistent estimator of sigma under normality."""
    data = _as_1d(x)
    if data.size == 0:
        raise ValueError("median_abs_deviation requires data")
    return float(scale * np.median(np.abs(data - np.median(data))))


@dataclass(frozen=True)
class TheilSenResult:
    slope: float
    intercept: float
    low_slope: float
    high_slope: float
    confidence: float


def theil_sen(t: ArrayLike, y: ArrayLike, *, confidence: float = 0.95) -> TheilSenResult:
    """Theil-Sen slope estimator with Sen's (1968) distribution-free confidence interval.

    Robust to up to ~29% arbitrary outliers (breakdown point 1 - 1/sqrt(2)).
    The interval uses the normal approximation to Kendall's S, as in
    ``scipy.stats.theilslopes``.
    """
    t_arr = np.asarray(t, dtype=float).ravel()
    y_arr = np.asarray(y, dtype=float).ravel()
    if t_arr.shape != y_arr.shape:
        raise ValueError("t and y must have the same length")
    mask = np.isfinite(t_arr) & np.isfinite(y_arr)
    t_arr, y_arr = t_arr[mask], y_arr[mask]
    n = t_arr.size
    if n < 2:
        raise ValueError("theil_sen requires at least two points")

    i, j = np.triu_indices(n, k=1)
    dt = t_arr[j] - t_arr[i]
    keep = dt != 0
    if not keep.any():
        raise ValueError("theil_sen requires at least two distinct t values")
    slopes = np.sort((y_arr[j] - y_arr[i])[keep] / dt[keep])
    slope = float(np.median(slopes))
    intercept = float(np.median(y_arr) - slope * np.median(t_arr))

    z = normal_quantile(1 - (1 - confidence) / 2)
    n_slopes = slopes.size
    # Variance of Kendall's S (ties in t ignored, matching scipy's default "separate" method)
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    c = z * math.sqrt(var_s)
    # Order-statistic ranks from Sen (1968); identical to scipy.stats.theilslopes.
    lo_idx = max(round((n_slopes - c) / 2.0) - 1, 0)
    hi_idx = min(round((n_slopes + c) / 2.0), n_slopes - 1)
    return TheilSenResult(
        slope, intercept, float(slopes[lo_idx]), float(slopes[hi_idx]), confidence
    )


@dataclass(frozen=True)
class MannKendallResult:
    s: int
    var_s: float
    z: float
    p_value: float
    tau: float

    def direction(self, alpha: float = 0.05) -> str:
        if self.p_value >= alpha:
            return "flat"
        return "up" if self.s > 0 else "down"


def mann_kendall(y: ArrayLike) -> MannKendallResult:
    """Two-sided Mann-Kendall monotonic trend test with tie correction.

    References: Mann (1945); Kendall (1975); Hipel & McLeod (1994) for the tie-corrected
    variance ``Var(S) = [n(n-1)(2n+5) - sum_k t_k(t_k-1)(2t_k+5)] / 18`` and the
    continuity-corrected statistic ``Z = (S - sgn(S)) / sqrt(Var(S))``.
    """
    data = _as_1d(y)
    n = data.size
    if n < 3:
        raise ValueError("mann_kendall requires at least three observations")
    i, j = np.triu_indices(n, k=1)
    s = int(np.sign(data[j] - data[i]).sum())
    _, counts = np.unique(data, return_counts=True)
    ties = counts[counts > 1].astype(float)
    var_s = (n * (n - 1) * (2 * n + 5) - float(np.sum(ties * (ties - 1) * (2 * ties + 5)))) / 18.0
    if var_s <= 0:
        return MannKendallResult(s, var_s, 0.0, 1.0, 0.0)
    z = (s - np.sign(s)) / math.sqrt(var_s)
    p_value = math.erfc(abs(z) / math.sqrt(2.0))
    tau = s / (n * (n - 1) / 2.0)
    return MannKendallResult(s, var_s, float(z), float(p_value), float(tau))
