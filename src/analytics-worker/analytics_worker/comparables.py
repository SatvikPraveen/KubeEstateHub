"""Comparable-sales ("comps") valuation via distance-weighted k-nearest neighbours.

Comparables are restricted to the same city and property type and matched on
standardised structural features. Sale prices are deflated to constant-quality base
period prices with a price index and re-inflated to the valuation period of each target
(``price * I(target) / I(sale_period)``), mirroring appraisal time adjustments.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .hedonic import NUMERIC_FEATURES, PERIOD


@dataclass
class ComparableSalesModel:
    k: int = 8
    eps: float = 1e-6
    _groups: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)
    _index: dict[pd.Timestamp, float] = field(default_factory=dict)
    _mean: np.ndarray | None = None
    _std: np.ndarray | None = None

    def _log_index(self, periods: pd.Series) -> np.ndarray:
        if not self._index:
            return np.zeros(len(periods))
        latest = self._index[max(self._index)]
        vals = periods.map(self._index).to_numpy(dtype=float)
        return np.log(np.where(np.isfinite(vals), vals, latest) / 100.0)

    def fit(
        self, sales: pd.DataFrame, price_index: pd.DataFrame | None = None
    ) -> ComparableSalesModel:
        """``sales`` as returned by ``hedonic.sales_sample``."""
        if price_index is not None and not price_index.empty:
            self._index = dict(zip(price_index["period"], price_index["index_value"], strict=True))
        feats = sales[list(NUMERIC_FEATURES)].to_numpy(dtype=float)
        self._mean = feats.mean(axis=0)
        std = feats.std(axis=0)
        self._std = np.where(std > 0, std, 1.0)
        base_log_price = np.log(sales["sale_price"].to_numpy(dtype=float)) - self._log_index(
            sales[PERIOD]
        )
        z = (feats - self._mean) / self._std
        self._groups = {
            key: (z[rows], base_log_price[rows])
            for key, rows in sales.groupby(["city", "property_type"], observed=True).indices.items()
        }
        return self

    def predict(self, df: pd.DataFrame, *, period: pd.Timestamp | None = None) -> np.ndarray:
        """Value each row at its own ``period`` (or at ``period`` if given; the latest
        indexed period when neither is available)."""
        if self._mean is None or self._std is None:
            raise RuntimeError("model is not fitted")
        out = np.full(len(df), np.nan)
        feats = df[list(NUMERIC_FEATURES)].to_numpy(dtype=float)
        z = (feats - self._mean) / self._std
        use_row_period = period is None and PERIOD in df
        target = df[PERIOD] if use_row_period else pd.Series([period] * len(df), index=df.index)
        shift = self._log_index(target)
        keys = list(zip(df["city"], df["property_type"], strict=True))
        for i, key in enumerate(keys):
            group = self._groups.get(key)
            if group is None or not np.isfinite(z[i]).all():
                continue
            gz, gy = group
            dist = np.sqrt(((gz - z[i]) ** 2).sum(axis=1))
            k = min(self.k, dist.size)
            nearest = np.argpartition(dist, k - 1)[:k]
            w = 1.0 / (dist[nearest] + self.eps)
            out[i] = float(np.exp(np.sum(w * gy[nearest]) / w.sum() + shift[i]))
        return out
