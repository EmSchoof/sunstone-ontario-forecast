"""Analysis-time statistics: thin wrappers over statsmodels / scipy.

Targeted imports only (no `statsmodels.api`), so unused model families are never loaded.
Never imported by the deployed model (`model.py`), which stays numpy + json.
Every result carries its sample size n, because n~20 here.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from scipy.stats import pearsonr, spearmanr
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tools.tools import add_constant
from statsmodels.tsa.stattools import adfuller, kpss


def _pairs(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return x[m], y[m]


# ---- Regression -------------------------------------------------------------


def ols_params(y: np.ndarray, X: np.ndarray | None = None) -> np.ndarray:
    """OLS coefficients, intercept first. X=None -> intercept only (the sample mean)."""
    y = np.asarray(y, float)
    if X is None:
        Xc = np.ones((len(y), 1))
    else:
        Xc = add_constant(np.asarray(X, float).reshape(len(y), -1), has_constant="add")
    return OLS(y, Xc).fit().params


def vif(X: np.ndarray) -> np.ndarray:
    """Variance inflation factor per column (constant added). >5 = strong collinearity."""
    Xc = add_constant(np.asarray(X, float), has_constant="add")
    return np.array([variance_inflation_factor(Xc, j) for j in range(1, Xc.shape[1])])


# ---- Correlation -------------------------------------------------------------


@dataclass(frozen=True)
class Corr:
    r: float
    lo: float
    hi: float
    p: float
    n: int

    @classmethod
    def undefined(cls, n: int) -> Corr:
        """Too few points (or a constant series) to estimate a correlation."""
        return cls(np.nan, np.nan, np.nan, np.nan, n)


def _estimable(x: np.ndarray, y: np.ndarray) -> bool:
    return len(x) >= 4 and x.std() > 0 and y.std() > 0


def pearson(x: np.ndarray, y: np.ndarray, conf: float = 0.95) -> Corr:
    """Pearson r with exact t-test p-value and Fisher-z CI (scipy); NaN pairs dropped."""
    x, y = _pairs(x, y)
    if not _estimable(x, y):
        return Corr.undefined(len(x))
    res = pearsonr(x, y)
    ci = res.confidence_interval(confidence_level=conf)
    return Corr(float(res.statistic), float(ci.low), float(ci.high), float(res.pvalue), len(x))


def spearman(x: np.ndarray, y: np.ndarray) -> Corr:
    """Spearman rho (robust to the extreme COVID years). No CI: scipy gives none."""
    x, y = _pairs(x, y)
    if not _estimable(x, y):
        return Corr.undefined(len(x))
    res = spearmanr(x, y)
    return Corr(float(res.statistic), np.nan, np.nan, float(res.pvalue), len(x))


def adjust_pvalues(p: np.ndarray, method: str = "holm", alpha: float = 0.05):
    """Family-wise correction (Holm: as safe as Bonferroni, more power). NaNs pass through."""
    p = np.asarray(p, float)
    adj, rej = np.full_like(p, np.nan), np.zeros(p.shape, bool)
    ok = np.isfinite(p)
    if ok.any():
        rej[ok], adj[ok], *_ = multipletests(p[ok], alpha=alpha, method=method)
    return rej, adj


# ---- Stationarity --------------------------------------------------------------


@dataclass(frozen=True)
class UnitRoot:
    adf_stat: float
    adf_p: float  # H0: unit root
    kpss_stat: float
    kpss_p: float  # H0: stationary (p bounded to [0.01, 0.10] by statsmodels' table)
    n: int
    verdict: str


def unit_root(x: np.ndarray, adf_maxlag: int = 2) -> UnitRoot:
    """ADF + KPSS together; low power at n~20, so treat as supporting evidence only."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    # result_object=False pins the tuple return (statsmodels >= 0.15 asks callers to choose).
    adf_stat, adf_p, *_ = adfuller(x, maxlag=adf_maxlag, autolag="AIC", result_object=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InterpolationWarning)
        kpss_stat, kpss_p, *_ = kpss(x, regression="c", nlags="auto", result_object=False)
    verdict = (
        "stationary"
        if adf_p < 0.10 and kpss_p > 0.05
        else "non-stationary"
        if adf_p >= 0.10 and kpss_p <= 0.05
        else "inconclusive"
    )
    return UnitRoot(float(adf_stat), float(adf_p), float(kpss_stat), float(kpss_p), len(x), verdict)
