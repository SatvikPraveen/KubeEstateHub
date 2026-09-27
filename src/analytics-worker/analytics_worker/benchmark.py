"""Monte Carlo validation study on synthetic markets with known ground truth.

For each replication (independent seed) we measure:

1. **Parameter recovery** of the hedonic model under correct specification: bias, RMSE
   and empirical coverage of nominal 95% HC1 Wald intervals.
2. **Price-index recovery:** RMSE between estimated and true index (base = 100).
3. **Out-of-sample accuracy** (k-fold CV) of the hedonic and comparable-sales AVMs and
   the empirical coverage of their split-conformal intervals.

Run ``python -m analytics_worker benchmark`` to reproduce the numbers reported in
``docs/research/results.md``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from .evaluation import comparables_conformal, cross_validate, hedonic_conformal
from .hedonic import fit_hedonic, sales_sample
from .stats import normal_quantile
from .synthetic import CitySpec, GroundTruth, generate_market

RECOVERY_FEATURES = ("log_sqft", "bedrooms", "bathrooms", "age")
COMMON_GROWTH = 0.005


def _well_specified_truth() -> GroundTruth:
    base = GroundTruth()
    cities: dict[str, CitySpec] = {
        name: replace(spec, monthly_growth=COMMON_GROWTH) for name, spec in base.cities.items()
    }
    return replace(base, cities=cities)


def run_benchmark(
    *,
    replications: int = 20,
    n: int = 3000,
    seed: int = 42,
    folds: int = 5,
    alpha: float = 0.1,
    months: int = 24,
) -> dict[str, Any]:
    truth = _well_specified_truth()
    z = normal_quantile(0.975)
    errors: dict[str, list[float]] = {f: [] for f in RECOVERY_FEATURES}
    covered: dict[str, list[bool]] = {f: [] for f in RECOVERY_FEATURES}
    index_rmse: list[float] = []
    cv: dict[str, list[dict[str, float]]] = {"hedonic_conformal": [], "comparables_conformal": []}

    for r in range(replications):
        rep_seed = seed + r
        df, _ = generate_market(n, seed=rep_seed, months=months, truth=truth)
        sales = sales_sample(df)
        model = fit_hedonic(sales)
        for f in RECOVERY_FEATURES:
            est, se = model.coefficient(f)
            true = getattr(truth, f)
            errors[f].append(est - true)
            covered[f].append(abs(est - true) <= z * se)
        idx = model.price_index()
        months_from_base = np.array(
            [
                (p.year - idx["period"].iloc[0].year) * 12 + p.month - idx["period"].iloc[0].month
                for p in idx["period"]
            ]
        )
        true_index = 100 * np.exp(COMMON_GROWTH * months_from_base)
        index_rmse.append(
            float(np.sqrt(np.mean((idx["index_value"].to_numpy() - true_index) ** 2)))
        )
        cv["hedonic_conformal"].append(
            cross_validate(sales, hedonic_conformal(alpha), k=folds, seed=rep_seed)["pooled"]
        )
        cv["comparables_conformal"].append(
            cross_validate(sales, comparables_conformal(alpha=alpha), k=folds, seed=rep_seed)[
                "pooled"
            ]
        )

    def summary(values: list[float]) -> dict[str, float]:
        arr = np.asarray(values, dtype=float)
        return {"mean": float(arr.mean()), "sd": float(arr.std(ddof=1)) if arr.size > 1 else 0.0}

    return {
        "config": {
            "replications": replications,
            "n": n,
            "seed": seed,
            "folds": folds,
            "alpha": alpha,
            "months": months,
            "noise_sigma": truth.noise_sigma,
        },
        "parameter_recovery": {
            f: {
                "true": getattr(truth, f),
                "bias": float(np.mean(errors[f])),
                "rmse": float(np.sqrt(np.mean(np.square(errors[f])))),
                "wald95_coverage": float(np.mean(covered[f])),
            }
            for f in RECOVERY_FEATURES
        },
        "price_index_rmse": summary(index_rmse),
        "cross_validation": {
            name: {
                metric: summary([m[metric] for m in runs])
                for metric in (
                    "median_ape",
                    "mape",
                    "ppe10",
                    "ppe20",
                    "coverage",
                    "mean_relative_width",
                )
            }
            for name, runs in cv.items()
        },
    }


def to_markdown(result: dict[str, Any]) -> str:
    cfg = result["config"]
    lines = [
        f"Replications: {cfg['replications']}, listings per market: {cfg['n']}, "
        f"folds: {cfg['folds']}, nominal interval coverage: {1 - cfg['alpha']:.0%}, base seed: {cfg['seed']}.",
        "",
        "| Coefficient | True | Bias | RMSE | 95% Wald coverage |",
        "|---|---:|---:|---:|---:|",
    ]
    for f, v in result["parameter_recovery"].items():
        lines.append(
            f"| `{f}` | {v['true']:.4f} | {v['bias']:+.5f} | {v['rmse']:.5f} | {v['wald95_coverage']:.2f} |"
        )
    pi = result["price_index_rmse"]
    lines += [
        "",
        f"Price index RMSE (index points, base = 100): {pi['mean']:.3f} (sd {pi['sd']:.3f}).",
        "",
        "| Model | Median APE | MAPE | PPE10 | PPE20 | Interval coverage | Relative width |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in result["cross_validation"].items():
        lines.append(
            f"| {name} | {m['median_ape']['mean']:.2%} | {m['mape']['mean']:.2%} | {m['ppe10']['mean']:.2%} | "
            f"{m['ppe20']['mean']:.2%} | {m['coverage']['mean']:.3f} ± {m['coverage']['sd']:.3f} | "
            f"{m['mean_relative_width']['mean']:.3f} |"
        )
    return "\n".join(lines) + "\n"
