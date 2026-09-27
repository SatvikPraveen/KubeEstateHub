from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from analytics_worker.comparables import ComparableSalesModel
from analytics_worker.conformal import SplitConformal
from analytics_worker.evaluation import (
    avm_metrics,
    comparables_conformal,
    cross_validate,
    hedonic_conformal,
)
from analytics_worker.hedonic import PERIOD, fit_hedonic, prepare, sales_sample
from analytics_worker.synthetic import GroundTruth, generate_market


def _common_growth_truth(growth=0.005):
    base = GroundTruth()
    return replace(
        base, cities={c: replace(s, monthly_growth=growth) for c, s in base.cities.items()}
    )


class TestHedonic:
    def test_recovers_structural_coefficients(self):
        truth = _common_growth_truth()
        df, _ = generate_market(4000, seed=3, truth=truth)
        model = fit_hedonic(sales_sample(df))
        for name in ("log_sqft", "bedrooms", "bathrooms", "age"):
            est, se = model.coefficient(name)
            assert abs(est - getattr(truth, name)) < 4 * se, name

    def test_recovers_city_and_type_effects(self):
        truth = _common_growth_truth()
        df, _ = generate_market(4000, seed=4, truth=truth)
        model = fit_hedonic(sales_sample(df))
        est, se = model.coefficient("city[Houston]")
        assert abs(est - (truth.cities["Houston"].effect - truth.cities["Austin"].effect)) < 4 * se
        est, se = model.coefficient("property_type[residential]")
        assert abs(est - (0.0 - truth.type_effects["commercial"])) < 4 * se

    def test_price_index_tracks_true_appreciation(self):
        growth = 0.008
        df, _ = generate_market(5000, seed=5, truth=_common_growth_truth(growth))
        idx = fit_hedonic(sales_sample(df)).price_index()
        assert idx["index_value"].iloc[0] == 100.0
        months = np.arange(len(idx))
        true = 100 * np.exp(growth * months)
        # the base month is thinly traded, so allow a level offset but require the right slope
        slope = np.polyfit(months, np.log(idx["index_value"]), 1)[0]
        assert slope == pytest.approx(growth, abs=0.0015)
        assert np.corrcoef(idx["index_value"], true)[0, 1] > 0.95

    def test_residuals_behave(self, sales):
        model = fit_hedonic(sales)
        assert 0.8 < model.r_squared < 1.0
        assert np.sqrt(model.sigma2) == pytest.approx(GroundTruth().noise_sigma, rel=0.1)
        assert model.smearing == pytest.approx(np.exp(model.sigma2 / 2), rel=0.01)

    def test_unseen_levels_are_invalid_not_extrapolated(self, sales):
        model = fit_hedonic(sales)
        row = sales.iloc[[0]].copy()
        row["city"] = "Atlantis"
        pred = model.predict(row)
        assert not pred["valid"].iloc[0]
        assert np.isnan(pred["estimate"].iloc[0])

    def test_prediction_interval_orders(self, sales):
        pred = fit_hedonic(sales).predict(sales.head(50))
        assert (pred["low"] < pred["estimate"]).all()
        assert (pred["estimate"] < pred["high"]).all()

    def test_rejects_underdetermined_fits(self, sales):
        with pytest.raises(ValueError, match="more observations"):
            fit_hedonic(sales.head(5))
        with pytest.raises(ValueError, match="no sales"):
            fit_hedonic(sales.head(0))


class TestConformal:
    def test_finite_sample_quantile_rank(self):
        # n = 9, alpha = 0.1 -> rank ceil(10 * 0.9) = 9 -> the largest score
        y = np.ones(9)
        pred = np.exp(np.arange(1, 10) / 100.0)
        cal = SplitConformal.calibrate(y, pred, alpha=0.1)
        assert cal.quantile == pytest.approx(0.09)

    def test_small_calibration_gives_infinite_interval(self):
        cal = SplitConformal.calibrate([1.0, 1.0], [1.1, 0.9], alpha=0.1)
        lo, hi = cal.interval([5.0])
        assert lo[0] == 0 and np.isinf(hi[0])

    def test_validation(self):
        with pytest.raises(ValueError, match="alpha"):
            SplitConformal.calibrate([1.0], [1.0], alpha=0)
        with pytest.raises(ValueError, match="calibration"):
            SplitConformal.calibrate([np.nan], [1.0])

    @pytest.mark.parametrize("alpha", [0.05, 0.1, 0.2])
    def test_marginal_coverage_on_heavy_tailed_errors(self, alpha):
        rng = np.random.default_rng(int(alpha * 100))
        truth = np.exp(rng.normal(12, 0.5, 20000))
        pred = truth * np.exp(rng.standard_t(2, 20000) * 0.1)  # misspecified, heavy tails
        cal = SplitConformal.calibrate(truth[:2000], pred[:2000], alpha=alpha)
        lo, hi = cal.interval(pred[2000:])
        coverage = np.mean((truth[2000:] >= lo) & (truth[2000:] <= hi))
        assert coverage >= 1 - alpha - 0.015


class TestComparables:
    def test_requires_fit(self):
        with pytest.raises(RuntimeError):
            ComparableSalesModel().predict(pd.DataFrame())

    def test_exact_match_returns_its_price_without_time_adjustment(self, sales):
        model = ComparableSalesModel(k=1).fit(sales)
        pred = model.predict(sales.head(20))
        np.testing.assert_allclose(pred, sales["sale_price"].head(20), rtol=1e-6)

    def test_time_adjustment_uses_index_ratio(self, sales):
        index = pd.DataFrame({"period": sorted(sales[PERIOD].unique())})
        index["index_value"] = 100.0 * 1.01 ** np.arange(len(index))
        model = ComparableSalesModel(k=1).fit(sales, index)
        row = sales.iloc[[0]]
        latest = index["period"].iloc[-1]
        ratio = (
            index["index_value"].iloc[-1]
            / index.set_index("period").loc[row[PERIOD].iloc[0], "index_value"]
        )
        assert model.predict(row, period=latest)[0] == pytest.approx(
            row["sale_price"].iloc[0] * ratio
        )

    def test_unknown_segment_is_nan(self, sales):
        row = sales.iloc[[0]].copy()
        row["city"] = "Nowhere"
        assert np.isnan(ComparableSalesModel().fit(sales).predict(row)[0])


class TestEvaluation:
    def test_avm_metrics_definitions(self):
        m = avm_metrics(
            np.array([100.0, 100.0, 100.0, 100.0]),
            np.array([95.0, 110.0, 130.0, np.nan]),
            np.array([90.0, 90.0, 90.0, 0.0]),
            np.array([105.0, 105.0, 105.0, 0.0]),
        )
        assert m["n"] == 3
        assert m["median_ape"] == pytest.approx(0.10)
        assert m["ppe10"] == pytest.approx(2 / 3)
        assert m["coverage"] == pytest.approx(1.0)
        assert avm_metrics(np.array([]), np.array([])) == {"n": 0}

    @pytest.mark.parametrize("factory", [hedonic_conformal, comparables_conformal])
    def test_cross_validated_accuracy_and_coverage(self, sales, factory):
        res = cross_validate(sales, factory(alpha=0.1), k=5, seed=0)
        pooled = res["pooled"]
        assert pooled["n"] == len(sales)
        assert pooled["median_ape"] < 0.13
        assert 0.87 <= pooled["coverage"] <= 0.94
        assert len(res["folds"]) == 5

    def test_cv_requires_enough_rows(self, sales):
        with pytest.raises(ValueError, match="folds"):
            cross_validate(sales.head(3), hedonic_conformal(), k=5)


def test_prepare_derives_age_and_period():
    df = pd.DataFrame(
        {
            "square_feet": [1000],
            "year_built": [2000],
            "bedrooms": [3],
            "bathrooms": [2],
            "sold_date": [date(2025, 3, 17)],
        }
    )
    out = prepare(df)
    assert out["age"].iloc[0] == 25
    assert out[PERIOD].iloc[0] == pd.Timestamp("2025-03-01")
    assert out["log_sqft"].iloc[0] == pytest.approx(np.log(1000))
