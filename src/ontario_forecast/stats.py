"""Small-sample statistics in plain numpy.

Written for ~20 annual observations: every function returns n alongside the
estimate so results are never reported without their sample size.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import erf, sqrt

import numpy as np

# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------


def add_const(X: np.ndarray) -> np.ndarray:
    X = np.atleast_2d(np.asarray(X, float))
    if X.shape[0] == 1 and X.size > 1:
        X = X.T
    return np.column_stack([np.ones(len(X)), X]) if X.size else np.ones((len(X), 1))


def ols(y: np.ndarray, X: np.ndarray | None) -> np.ndarray:
    """OLS coefficients with intercept first. X=None -> intercept only (sample mean)."""
    Xc = np.ones((len(y), 1)) if X is None else add_const(X)
    beta, *_ = np.linalg.lstsq(Xc, np.asarray(y, float), rcond=None)
    return beta


def r_squared(y: np.ndarray, X: np.ndarray) -> float:
    beta = ols(y, X)
    resid = y - add_const(X) @ beta
    ss_tot = np.sum((y - y.mean()) ** 2)
    return 1.0 - np.sum(resid**2) / ss_tot if ss_tot > 0 else np.nan


def vif(X: np.ndarray) -> np.ndarray:
    """Variance inflation factor per column. >5 signals strong multicollinearity."""
    X = np.asarray(X, float)
    out = np.empty(X.shape[1])
    for j in range(X.shape[1]):
        others = np.delete(X, j, axis=1)
        r2 = r_squared(X[:, j], others) if others.shape[1] else 0.0
        out[j] = np.inf if r2 >= 1 else 1.0 / (1.0 - r2)
    return out


# ---------------------------------------------------------------------------
# Correlation with honest uncertainty
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Corr:
    r: float
    lo: float
    hi: float
    p: float
    n: int


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def pearson(x: np.ndarray, y: np.ndarray, conf: float = 0.95) -> Corr:
    """Pearson r with Fisher-z CI and two-sided p (normal approx; drops NaN pairs)."""
    m = ~(np.isnan(x) | np.isnan(y))
    x, y, n = x[m], y[m], int(m.sum())
    if n < 4 or x.std() == 0 or y.std() == 0:
        return Corr(np.nan, np.nan, np.nan, np.nan, n)
    r = float(np.corrcoef(x, y)[0, 1])
    r_c = min(max(r, -0.999999), 0.999999)
    z, se = np.arctanh(r_c), 1 / sqrt(n - 3)
    zc = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}[conf]
    p = 2 * (1 - _norm_cdf(abs(z) / se))
    return Corr(r, float(np.tanh(z - zc * se)), float(np.tanh(z + zc * se)), p, n)


def _rank(a: np.ndarray) -> np.ndarray:
    order = a.argsort(kind="mergesort")
    ranks = np.empty(len(a))
    ranks[order] = np.arange(1, len(a) + 1)
    for v in np.unique(a):                      # average ties
        idx = a == v
        if idx.sum() > 1:
            ranks[idx] = ranks[idx].mean()
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> Corr:
    """Rank correlation: robust to the single extreme COVID years."""
    m = ~(np.isnan(x) | np.isnan(y))
    return pearson(_rank(x[m]), _rank(y[m]))


# ---------------------------------------------------------------------------
# Time-series backtesting (expanding window, strictly chronological)
# ---------------------------------------------------------------------------

FitPredict = Callable[[np.ndarray, np.ndarray | None, np.ndarray | None], float]
"""fit_predict(y_train, X_train, x_next) -> one-step-ahead prediction."""


@dataclass(frozen=True)
class Backtest:
    test_idx: np.ndarray
    pred: np.ndarray
    actual: np.ndarray

    @property
    def errors(self) -> np.ndarray:
        return self.actual - self.pred


def rolling_origin(y: np.ndarray, X: np.ndarray | None, fit_predict: FitPredict,
                   min_train: int, train_mask: np.ndarray | None = None) -> Backtest:
    """Expanding-window one-step-ahead backtest.

    At origin t the model sees ONLY rows < t (never row t or later), mimicking a
    forecast made at the end of year t-1. `train_mask` can exclude rows (e.g.
    COVID years) from fitting without removing them from the test set.
    """
    y = np.asarray(y, float)
    n = len(y)
    keep = np.ones(n, bool) if train_mask is None else np.asarray(train_mask, bool)
    idx, preds = [], []
    for t in range(min_train, n):
        tr = np.flatnonzero(keep[:t])          # strictly before t
        if len(tr) < min_train:
            continue
        Xtr = None if X is None else X[tr]
        xnext = None if X is None else X[t]
        preds.append(fit_predict(y[tr], Xtr, xnext))
        idx.append(t)
    idx = np.asarray(idx, int)
    return Backtest(idx, np.asarray(preds, float), y[idx])


def mae(e: np.ndarray) -> float:
    return float(np.mean(np.abs(e)))


def rmse(e: np.ndarray) -> float:
    return float(np.sqrt(np.mean(e**2)))


def conformal_halfwidth(abs_errors: np.ndarray, coverage: float = 0.8) -> float:
    """Split-conformal quantile of out-of-sample |errors|.

    Uses the finite-sample (n+1) correction; with few errors the interval is
    deliberately wide. Returns inf if there are too few errors for the coverage.
    """
    e = np.sort(np.abs(np.asarray(abs_errors, float)))
    n = len(e)
    k = int(np.ceil((n + 1) * coverage))
    return float(e[k - 1]) if 1 <= k <= n else float("inf")
