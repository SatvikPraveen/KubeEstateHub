"""Log-linear hedonic pricing model with a time-dummy price index.

Model (Rosen, 1974; de Haan & Diewert, 2013, *Handbook on Residential Property Price
Indices*, ch. 5)::

    log(P_i) = b0 + b1 log(sqft_i) + b2 beds_i + b3 baths_i + b4 age_i
               + sum_c a_c [city_i = c] + sum_k t_k [type_i = k]
               + sum_p g_p [period_i = p] + e_i

* Categorical levels use treatment coding; the alphabetically first level (and the
  earliest period) is the reference.
* Coefficient covariance is heteroskedasticity-robust (HC1; White, 1980; MacKinnon &
  White, 1985).
* Back-transformation to price level uses Duan's (1983) smearing estimator.
* The price index is ``100 * exp(g_p - var(g_p) / 2)`` (Kennedy, 1981), which corrects the
  small-sample bias of exponentiating a dummy coefficient.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .stats import normal_quantile

NUMERIC_FEATURES: tuple[str, ...] = ("log_sqft", "bedrooms", "bathrooms", "age")
CATEGORICAL_FEATURES: tuple[str, ...] = ("city", "property_type")
PERIOD = "period"


def prepare(df: pd.DataFrame, *, reference_date: str = "sold_date") -> pd.DataFrame:
    """Derive model features. ``age`` and ``period`` are measured at ``reference_date``."""
    out = df.copy()
    ref = pd.to_datetime(out[reference_date], errors="coerce")
    out["log_sqft"] = np.log(pd.to_numeric(out["square_feet"], errors="coerce").astype(float))
    out["age"] = ref.dt.year - pd.to_numeric(out["year_built"], errors="coerce")
    out[PERIOD] = ref.dt.to_period("M").dt.to_timestamp()
    for col in ("bedrooms", "bathrooms"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
    return out


def sales_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Closed sales with complete model features."""
    prepared = prepare(df)
    mask = (prepared["status"] == "sold") & prepared["sale_price"].notna()
    cols = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES, PERIOD]
    mask &= prepared[cols].notna().all(axis=1)
    return prepared.loc[mask].reset_index(drop=True)


@dataclass
class HedonicModel:
    columns: list[str]
    beta: np.ndarray
    cov: np.ndarray
    sigma2: float
    smearing: float
    levels: dict[str, list] = field(default_factory=dict)
    n_obs: int = 0
    r_squared: float = float("nan")

    # ----- design -------------------------------------------------------------------
    def design(
        self, df: pd.DataFrame, *, period: pd.Timestamp | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Design matrix for ``df`` (already ``prepare``-d) and a validity mask.

        Rows with missing numeric features or categorical levels unseen during fitting
        are marked invalid (their row in the matrix is zero).
        """
        n = len(df)
        x = np.zeros((n, len(self.columns)))
        valid = np.ones(n, dtype=bool)
        col_index = {c: i for i, c in enumerate(self.columns)}
        x[:, col_index["const"]] = 1.0
        for feat in NUMERIC_FEATURES:
            vals = df[feat].to_numpy(dtype=float)
            valid &= np.isfinite(vals)
            x[:, col_index[feat]] = np.nan_to_num(vals)
        periods = df[PERIOD] if period is None else pd.Series([period] * n, index=df.index)
        sources = {**{c: df[c] for c in CATEGORICAL_FEATURES}, PERIOD: periods}
        for name, series in sources.items():
            levels = self.levels[name]
            values = series.to_numpy()
            known = np.isin(values, levels)
            valid &= known
            for level in levels[1:]:
                x[:, col_index[f"{name}[{level}]"]] = values == level
        x[~valid] = 0.0
        return x, valid

    # ----- inference -----------------------------------------------------------------
    def predict_log(self, df: pd.DataFrame, *, period: pd.Timestamp | None = None):
        """Mean of log price, its standard error, and the validity mask."""
        x, valid = self.design(df, period=period)
        mu = x @ self.beta
        se = np.sqrt(np.einsum("ij,jk,ik->i", x, self.cov, x))
        mu[~valid] = np.nan
        se[~valid] = np.nan
        return mu, se, valid

    def predict(
        self,
        df: pd.DataFrame,
        *,
        period: pd.Timestamp | None = None,
        confidence: float = 0.9,
    ) -> pd.DataFrame:
        """Point estimate (smearing-corrected mean) and a parametric prediction interval."""
        mu, se, valid = self.predict_log(df, period=period)
        z = normal_quantile(1 - (1 - confidence) / 2)
        pred_se = np.sqrt(self.sigma2 + se**2)
        return pd.DataFrame(
            {
                "estimate": np.exp(mu) * self.smearing,
                "low": np.exp(mu - z * pred_se),
                "high": np.exp(mu + z * pred_se),
                "valid": valid,
            },
            index=df.index,
        )

    def coefficient(self, name: str) -> tuple[float, float]:
        i = self.columns.index(name)
        return float(self.beta[i]), float(np.sqrt(self.cov[i, i]))

    @property
    def latest_period(self) -> pd.Timestamp:
        return self.levels[PERIOD][-1]

    def price_index(self) -> pd.DataFrame:
        """Time-dummy hedonic index, base (earliest) period = 100."""
        rows = []
        for p in self.levels[PERIOD]:
            name = f"{PERIOD}[{p}]"
            if name in self.columns:
                g, se = self.coefficient(name)
                value = 100.0 * np.exp(g - 0.5 * se**2)
                rows.append((p, value, value * se))
            else:
                rows.append((p, 100.0, 0.0))
        return pd.DataFrame(rows, columns=["period", "index_value", "std_error"])


def fit_hedonic(sales: pd.DataFrame) -> HedonicModel:
    """Fit by OLS on ``sales`` as returned by :func:`sales_sample`."""
    if sales.empty:
        raise ValueError("no sales to fit")
    levels: dict[str, list] = {c: sorted(sales[c].dropna().unique()) for c in CATEGORICAL_FEATURES}
    levels[PERIOD] = sorted(sales[PERIOD].dropna().unique())
    columns = ["const", *NUMERIC_FEATURES]
    for name in (*CATEGORICAL_FEATURES, PERIOD):
        columns += [f"{name}[{lvl}]" for lvl in levels[name][1:]]

    model = HedonicModel(
        columns, np.zeros(len(columns)), np.zeros((len(columns),) * 2), 0.0, 1.0, levels
    )
    x, valid = model.design(sales)
    if not valid.all():  # pragma: no cover - sales_sample guarantees completeness
        raise ValueError("sales contain incomplete rows")
    y = np.log(sales["sale_price"].to_numpy(dtype=float))
    n, k = x.shape
    if n <= k:
        raise ValueError(f"need more observations ({n}) than parameters ({k})")
    rank = np.linalg.matrix_rank(x)
    if rank < k:
        raise ValueError(f"design matrix is rank deficient (rank {rank} < {k} columns)")

    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    bread = np.linalg.inv(x.T @ x)
    xe = x * resid[:, None]
    cov = bread @ (xe.T @ xe) @ bread * (n / (n - k))
    sigma2 = float(resid @ resid / (n - k))
    tss = float(((y - y.mean()) ** 2).sum())

    model.beta = beta
    model.cov = cov
    model.sigma2 = sigma2
    model.smearing = float(np.mean(np.exp(resid)))
    model.n_obs = n
    model.r_squared = 1.0 - float(resid @ resid) / tss if tss > 0 else float("nan")
    return model
