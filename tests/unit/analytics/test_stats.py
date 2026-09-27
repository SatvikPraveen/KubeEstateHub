import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analytics_worker.stats import bootstrap_ci, mann_kendall, median_abs_deviation, theil_sen

scipy_stats = pytest.importorskip("scipy.stats")


class TestTheilSen:
    @pytest.mark.parametrize("n", [5, 12, 40, 150])
    def test_matches_scipy_reference(self, n):
        rng = np.random.default_rng(n)
        t = np.arange(n, dtype=float)
        y = 0.3 * t + rng.standard_t(3, size=n)
        ours = theil_sen(t, y)
        ref = scipy_stats.theilslopes(y, t, 0.95)
        assert ours.slope == pytest.approx(ref.slope)
        assert ours.intercept == pytest.approx(ref.intercept)
        assert ours.low_slope == pytest.approx(ref.low_slope)
        assert ours.high_slope == pytest.approx(ref.high_slope)

    def test_robust_to_gross_outliers(self):
        t = np.arange(30, dtype=float)
        y = 2.0 * t + 1.0
        y[[3, 11, 20]] = 1e6  # 10% contamination
        assert theil_sen(t, y).slope == pytest.approx(2.0)

    def test_rejects_degenerate_input(self):
        with pytest.raises(ValueError, match="distinct"):
            theil_sen([1, 1, 1], [1, 2, 3])
        with pytest.raises(ValueError, match="two points"):
            theil_sen([1], [1])

    @given(st.floats(-5, 5), st.floats(-100, 100))
    def test_exact_on_noiseless_lines(self, slope, intercept):
        t = np.arange(10, dtype=float)
        res = theil_sen(t, slope * t + intercept)
        assert res.slope == pytest.approx(slope, abs=1e-9)
        assert res.low_slope <= res.slope <= res.high_slope


class TestMannKendall:
    def test_tau_matches_kendall_tau_b_without_ties(self):
        rng = np.random.default_rng(3)
        y = np.cumsum(rng.normal(size=50))
        ref = scipy_stats.kendalltau(np.arange(50), y)
        assert mann_kendall(y).tau == pytest.approx(ref.statistic)

    def test_detects_monotonic_trend(self):
        res = mann_kendall(np.arange(20) + np.random.default_rng(0).normal(0, 0.5, 20))
        assert res.p_value < 1e-4
        assert res.direction() == "up"

    def test_constant_series_is_flat(self):
        res = mann_kendall([5, 5, 5, 5])
        assert res.p_value == 1.0
        assert res.direction() == "flat"

    def test_tie_correction_reduces_variance(self):
        n = 10
        no_ties = mann_kendall(np.arange(n, dtype=float))
        with_ties = mann_kendall([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
        assert with_ties.var_s < no_ties.var_s == pytest.approx(n * (n - 1) * (2 * n + 5) / 18)

    @pytest.mark.slow
    def test_size_under_null_is_close_to_nominal(self):
        rng = np.random.default_rng(123)
        rejections = [mann_kendall(rng.normal(size=24)).p_value < 0.05 for _ in range(2000)]
        # binomial sd at p=0.05, n=2000 is ~0.005;
        # the continuity correction makes the test slightly conservative
        assert 0.025 <= np.mean(rejections) <= 0.065


class TestBootstrap:
    def test_interval_contains_estimate_and_is_reproducible(self):
        x = np.random.default_rng(1).lognormal(12, 0.4, 200)
        a = bootstrap_ci(x, rng=np.random.default_rng(7))
        b = bootstrap_ci(x, rng=np.random.default_rng(7))
        assert a == b
        assert a.low <= a.estimate <= a.high

    def test_single_observation_degenerates(self):
        ci = bootstrap_ci([42.0])
        assert (ci.low, ci.estimate, ci.high) == (42.0, 42.0, 42.0)

    def test_ignores_non_finite_and_validates(self):
        ci = bootstrap_ci([1.0, 2.0, np.nan, 3.0, np.inf], np.mean)
        assert ci.estimate == pytest.approx(2.0)
        with pytest.raises(ValueError, match="finite"):
            bootstrap_ci([np.nan])
        with pytest.raises(ValueError, match="confidence"):
            bootstrap_ci([1.0, 2.0], confidence=1.5)

    @pytest.mark.slow
    def test_mean_interval_coverage(self):
        rng = np.random.default_rng(99)
        hits = 0
        reps = 300
        for _ in range(reps):
            x = rng.normal(10, 2, 60)
            ci = bootstrap_ci(x, np.mean, n_resamples=800, rng=rng)
            hits += ci.low <= 10 <= ci.high
        assert 0.89 <= hits / reps <= 0.98


@settings(max_examples=50)
@given(st.lists(st.floats(-1e6, 1e6), min_size=1, max_size=50))
def test_mad_is_non_negative_and_scale_equivariant(xs):
    mad = median_abs_deviation(xs)
    assert mad >= 0
    assert median_abs_deviation(np.asarray(xs) * 3) == pytest.approx(3 * mad, rel=1e-9, abs=1e-6)


def test_mad_consistent_for_normal_sigma():
    x = np.random.default_rng(5).normal(0, 2.5, 20000)
    assert median_abs_deviation(x) == pytest.approx(2.5, rel=0.03)
    assert not math.isnan(median_abs_deviation([1.0]))
