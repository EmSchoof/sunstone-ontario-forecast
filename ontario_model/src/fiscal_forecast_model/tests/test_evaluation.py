import numpy as np

from fiscal_forecast_model.modeling.evaluation import conformal_halfwidth, rolling_origin


def test_rolling_origin_never_sees_the_future():
    y = np.arange(20, dtype=float)
    seen = []

    def fp(y_tr, X_tr, x_next):
        seen.append(y_tr.max())
        return 0.0

    bt = rolling_origin(y, None, fp, min_train=5)
    assert list(bt.test_idx) == list(range(5, 20))
    assert seen == [t - 1 for t in bt.test_idx]  # max training value is y[t-1]


def test_train_mask_excludes_rows_from_fit_but_keeps_them_as_tests():
    y = np.arange(15, dtype=float)
    mask = np.ones(15, bool)
    mask[[8, 9]] = False
    sizes = []
    bt = rolling_origin(y, None, lambda yt, X, x: sizes.append(len(yt)) or 0.0, 5, mask)
    assert 8 in bt.test_idx and 9 in bt.test_idx
    assert sizes[-1] == 14 - 2


def test_conformal_halfwidth_finite_sample():
    e = np.arange(1, 11, dtype=float)  # 10 errors
    assert conformal_halfwidth(e, 0.8) == 9.0  # ceil(11 * 0.8) = 9th smallest
    assert conformal_halfwidth(e[:3], 0.9) == float("inf")
