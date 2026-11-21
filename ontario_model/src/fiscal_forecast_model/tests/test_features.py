import numpy as np

from fiscal_forecast_model.modeling.features import fit_mask, lag, shock_mask


def test_lag_shifts_forward_without_lookahead():
    assert np.array_equal(lag(np.array([1.0, 2, 3]))[1:], [1.0, 2.0])
    assert np.isnan(lag(np.array([1.0, 2, 3]))[0])
    assert np.isnan(lag(np.array([1.0, 2]), k=5)).all()


def test_fit_mask_drops_shock_and_following_period_only():
    years = np.arange(2018, 2026)
    ok = fit_mask(years, (2020, 2021, 2022))
    assert dict(zip(years.tolist(), ok.tolist(), strict=True)) == {
        2018: True,
        2019: True,
        2020: False,
        2021: False,
        2022: False,
        2023: False,
        2024: True,
        2025: True,
    }
    assert shock_mask(years, (2020,)).sum() == 1
