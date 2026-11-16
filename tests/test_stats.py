"""Wrapper tests: we trust statsmodels/scipy math; we test OUR wiring (shapes, NaNs, constants)."""

import numpy as np

from ontario_forecast.modeling import stats


def test_ols_params_recovers_coefficients_and_intercept_only_is_mean():
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    y = 1.5 + 2.0 * x + rng.normal(scale=0.01, size=200)
    assert np.allclose(stats.ols_params(y, x), [1.5, 2.0], atol=0.01)  # 1-D X = one predictor
    assert np.allclose(stats.ols_params(y), [y.mean()])


def test_vif_orthogonal_near_one_collinear_large():
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=500), rng.normal(size=500)
    assert np.allclose(stats.vif(np.column_stack([a, b])), 1.0, atol=0.05)
    assert stats.vif(np.column_stack([a, a + 1e-3 * b]))[0] > 100


def test_pearson_drops_nans_and_ci_brackets_r():
    x = np.array([1, 2, 3, 4, 5, np.nan, 7, 8.0])
    y = np.array([2, 4, 5, 4, 5, 9, 8, 9.0])
    c = stats.pearson(x, y)
    assert c.n == 7 and c.lo < c.r < c.hi and 0 <= c.p <= 1


def test_adjust_pvalues_passes_nans_through():
    rej, adj = stats.adjust_pvalues([0.001, np.nan, 0.04, 0.5])
    assert np.isnan(adj[1]) and not rej[1]
    assert adj[0] <= adj[2] <= adj[3] and rej[0]


def test_unit_root_verdicts():
    rng = np.random.default_rng(42)
    assert stats.unit_root(rng.normal(size=300)).verdict == "stationary"
    assert stats.unit_root(np.cumsum(rng.normal(size=300))).verdict != "stationary"
