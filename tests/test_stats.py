import numpy as np

from ontario_forecast import stats


def test_ols_recovers_coefficients():
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    y = 1.5 + 2.0 * x + rng.normal(scale=0.01, size=200)
    b = stats.ols(y, x[:, None])
    assert np.allclose(b, [1.5, 2.0], atol=0.01)


def test_vif_orthogonal_is_one_and_collinear_is_large():
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=500), rng.normal(size=500)
    assert np.allclose(stats.vif(np.column_stack([a, b])), 1.0, atol=0.05)
    assert stats.vif(np.column_stack([a, a + 1e-3 * b]))[0] > 100


def test_rolling_origin_never_sees_the_future():
    y = np.arange(20, dtype=float)
    seen = []

    def fp(y_tr, X_tr, x_next):
        seen.append(y_tr.max())
        return 0.0

    bt = stats.rolling_origin(y, None, fp, min_train=5)
    # at each origin t, the largest training value must be y[t-1] = t-1
    assert list(bt.test_idx) == list(range(5, 20))
    assert seen == [t - 1 for t in bt.test_idx]


def test_rolling_origin_train_mask_excludes_rows_but_keeps_them_in_test():
    y = np.arange(15, dtype=float)
    mask = np.ones(15, bool)
    mask[[8, 9]] = False
    sizes = []
    bt = stats.rolling_origin(y, None, lambda yt, X, x: sizes.append(len(yt)) or 0.0, 5, mask)
    assert 8 in bt.test_idx and 9 in bt.test_idx
    assert sizes[-1] == 14 - 2


def test_conformal_halfwidth_finite_sample():
    e = np.arange(1, 11, dtype=float)            # 10 errors
    assert stats.conformal_halfwidth(e, 0.8) == 9.0  # ceil(11*0.8)=9th smallest
    assert stats.conformal_halfwidth(e[:3], 0.9) == float("inf")


def test_pearson_ci_contains_r_and_drops_nans():
    x = np.array([1, 2, 3, 4, 5, np.nan, 7, 8.0])
    y = np.array([2, 4, 5, 4, 5, 9, 8, 9.0])
    c = stats.pearson(x, y)
    assert c.n == 7 and c.lo < c.r < c.hi
