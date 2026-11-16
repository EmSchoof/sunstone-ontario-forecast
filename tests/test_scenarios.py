import json

import numpy as np
import pytest

from ontario_forecast.modeling import scenarios
from ontario_forecast.modeling.model import GrowthForecaster


def test_quantiles_ordered_and_band_widens():
    rng = np.random.default_rng(0)
    errors = np.array([-0.05, -0.02, 0.0, 0.01, 0.03, 0.04, -0.01, 0.02])
    g = scenarios.bootstrap_growth(np.full(5, 0.02), errors, 5000, rng)
    f = scenarios.fan(scenarios.levels_from_growth(100.0, g), 2026, (0.1, 0.5, 0.9), len(errors))
    lo, mid, hi = f.values
    assert np.all(lo <= mid) and np.all(mid <= hi)
    assert np.all(np.diff(hi - lo) > 0)  # uncertainty grows with horizon
    assert list(f.years) == [2026, 2027, 2028, 2029, 2030]


def test_zero_errors_give_deterministic_compound_growth():
    rng = np.random.default_rng(0)
    g = scenarios.bootstrap_growth(np.full(3, np.log(1.1)), np.zeros(6), 10, rng)
    lv = scenarios.levels_from_growth(100.0, g)
    assert np.allclose(lv[0], [110, 121, 133.1])


def test_too_few_errors_rejected():
    with pytest.raises(ValueError):
        scenarios.bootstrap_growth(np.zeros(3), np.array([0.1, 0.2]), 10, np.random.default_rng(0))


def test_ar1_recursion_without_noise():
    g = scenarios.ar1_growth(0.01, 0.5, 0.1, np.zeros(6), 3, 2, np.random.default_rng(0))
    assert np.allclose(g[0], [0.06, 0.04, 0.03])


def test_fan_final_and_rows_match_values():
    vals = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    f = scenarios.Fan(np.array([2026, 2027]), (0.1, 0.5, 0.9), vals, np.zeros((2, 2)), 9)
    assert f.final() == (2.0, 4.0, 6.0)
    rows = f.rows("tot_revenue", "USD", "trend")
    assert len(rows) == 6 and rows[-1] == {
        "metric": "tot_revenue",
        "period": 2027,
        "quantile": 0.9,
        "value": 6.0,
        "units": "USD",
        "model": "trend",
        "n_errors": 9,
    }


def test_percentile_of_budget_value():
    samples = np.tile(np.arange(100.0)[:, None], (1, 2))
    f = scenarios.Fan(np.array([2026, 2027]), (0.1, 0.5, 0.9), np.zeros((3, 2)), samples, 10)
    assert f.percentile_of(25.0, 2027) == 0.25


def test_model_json_roundtrip_keeps_errors(tmp_path):
    m = GrowthForecaster(target="tot_revenue_real")
    m.calibrate(np.array([0.025]), np.array([0.01, -0.02, 0.03, -0.01, 0.0]), 2025)
    m.save(tmp_path / "m.json")
    m2 = GrowthForecaster.load(tmp_path / "m.json")
    assert m2.coef == pytest.approx([0.025])
    assert m2.backtest_errors == m.backtest_errors
    assert json.loads((tmp_path / "m.json").read_text())["trained_through_fy"] == 2025


def test_predict_with_driver():
    m = GrowthForecaster(target="x", predictors=["d"]).calibrate(np.array([0.01, 0.5]), np.zeros(6), 2025)
    out = m.predict(100.0, np.array([0.02]))
    assert out["growth"] == pytest.approx(0.02)
    assert out["lower"] == out["point"] == out["upper"]  # zero errors -> zero width


def test_centered_errors_keep_the_model_forecast_in_the_middle():
    # A "no change" model must not drift at the average of its past errors.
    rng = np.random.default_rng(0)
    biased = np.array([0.06, 0.09, 0.12, -0.05, -0.02, 0.04, -0.07, -0.06, 0.11])  # mean +0.024
    g = scenarios.bootstrap_growth(np.zeros(5), biased, 20_000, rng)
    assert abs(g.mean()) < 0.002
    raw = scenarios.bootstrap_growth(np.zeros(5), biased, 20_000, rng, center=False)
    assert raw.mean() == pytest.approx(biased.mean(), abs=0.002)
