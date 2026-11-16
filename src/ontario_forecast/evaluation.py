"""Forecast evaluation: chronological backtest, error metrics, conformal intervals.

numpy only (imported by the deployed model). No package offers an expanding-window
backtest with a fit mask for this setting without pulling in a full ML stack.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

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


def rolling_origin(
    y: np.ndarray,
    X: np.ndarray | None,
    fit_predict: FitPredict,
    min_train: int,
    train_mask: np.ndarray | None = None,
) -> Backtest:
    """Expanding-window one-step-ahead backtest.

    At origin t the model sees ONLY rows < t, mimicking a forecast made at the end of
    year t-1. `train_mask` drops rows (e.g. COVID years) from fitting but keeps them
    as test points.
    """
    y = np.asarray(y, float)
    keep = np.ones(len(y), bool) if train_mask is None else np.asarray(train_mask, bool)
    idx, preds = [], []
    for t in range(min_train, len(y)):
        tr = np.flatnonzero(keep[:t])  # strictly before t
        if len(tr) < min_train:
            continue
        preds.append(fit_predict(y[tr], None if X is None else X[tr], None if X is None else X[t]))
        idx.append(t)
    idx = np.asarray(idx, int)
    return Backtest(idx, np.asarray(preds, float), y[idx])


def mae(e: np.ndarray) -> float:
    return float(np.mean(np.abs(e)))


def rmse(e: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(e))))


def conformal_halfwidth(errors: np.ndarray, coverage: float = 0.8) -> float:
    """Split-conformal quantile of out-of-sample |errors| with the (n+1) correction.

    Few errors -> deliberately wide; inf if there are too few for the coverage asked.
    """
    e = np.sort(np.abs(np.asarray(errors, float)))
    k = int(np.ceil((len(e) + 1) * coverage))
    return float(e[k - 1]) if 1 <= k <= len(e) else float("inf")
