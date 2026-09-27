"""Split-conformal prediction intervals (Vovk et al., 2005; Lei et al., 2018).

Nonconformity score: absolute error on the log scale, ``|log y - log y_hat|``. For
exchangeable calibration and test points the interval
``[y_hat * exp(-q), y_hat * exp(q)]`` has marginal coverage of at least ``1 - alpha``,
where ``q`` is the ``ceil((n + 1)(1 - alpha))``-th smallest calibration score. The
guarantee is distribution-free and holds for any point predictor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class SplitConformal:
    quantile: float
    alpha: float
    n_calibration: int

    @classmethod
    def calibrate(
        cls, y_true: ArrayLike, y_pred: ArrayLike, *, alpha: float = 0.1
    ) -> SplitConformal:
        if not 0 < alpha < 1:
            raise ValueError("alpha must be in (0, 1)")
        yt = np.asarray(y_true, dtype=float)
        yp = np.asarray(y_pred, dtype=float)
        ok = np.isfinite(yt) & np.isfinite(yp) & (yt > 0) & (yp > 0)
        scores = np.sort(np.abs(np.log(yt[ok]) - np.log(yp[ok])))
        n = scores.size
        if n == 0:
            raise ValueError("no valid calibration pairs")
        rank = math.ceil((n + 1) * (1 - alpha))
        q = math.inf if rank > n else float(scores[rank - 1])
        return cls(quantile=q, alpha=alpha, n_calibration=n)

    @property
    def confidence(self) -> float:
        return 1.0 - self.alpha

    def interval(self, y_pred: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        yp = np.asarray(y_pred, dtype=float)
        if math.isinf(self.quantile):
            return np.zeros_like(yp), np.full_like(yp, np.inf)
        factor = math.exp(self.quantile)
        return yp / factor, yp * factor
