"""Shared time-series feature helpers (numpy). One definition of lags and shock masks,
used by variable selection (02) and scenarios (03) so both apply identical rules."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def lag(a: np.ndarray, k: int = 1) -> np.ndarray:
    """Shift forward by k periods; the first k values become NaN. Never looks ahead."""
    a = np.asarray(a, float)
    out = np.full(len(a), np.nan)
    if k < len(a):
        out[k:] = a[: len(a) - k]
    return out


def shock_mask(periods: np.ndarray, shock_periods: Iterable[int]) -> np.ndarray:
    """True where the period is a shock period (e.g. COVID fiscal years)."""
    return np.isin(periods, list(shock_periods))


def fit_mask(periods: np.ndarray, shock_periods: Iterable[int]) -> np.ndarray:
    """Rows allowed for FITTING: not a shock period and not the period right after one.

    The period after a shock carries the shock in its lag-1 driver (e.g. FY2023's
    lagged growth is the FY2022 rebound), which would dominate a small regression.
    Excluded rows are still scored as test points.
    """
    periods = np.asarray(periods)
    shock = set(shock_periods)
    return ~np.isin(periods, list(shock)) & ~np.isin(periods - 1, list(shock))
