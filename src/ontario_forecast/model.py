"""Deployable forecaster: numpy + json only (no pandas, no statsmodels).

Model: log-growth of the target regressed on lagged growth of <= max_k drivers,
   g_t = a + b' x_{t-1} + e_t,   level_t = level_{t-1} * exp(g_t)
Prediction interval: split-conformal half-width from out-of-sample backtest errors,
so the interval reflects how wrong the model actually was on unseen years.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from ontario_forecast import stats


@dataclass
class GrowthForecaster:
    target: str
    predictors: list[str] = field(default_factory=list)   # names of lag-1 growth drivers
    coef: list[float] = field(default_factory=list)       # [intercept, b1, ...]
    interval_halfwidth: float = float("inf")              # on log-growth scale
    coverage: float = 0.8
    trained_through_fy: int | None = None
    backtest_mae: float | None = None

    def fit(self, y_growth: np.ndarray, X_lag: np.ndarray | None, backtest_abs_errors: np.ndarray,
            last_fy: int) -> GrowthForecaster:
        self.coef = stats.ols(y_growth, X_lag if self.predictors else None).tolist()
        self.interval_halfwidth = stats.conformal_halfwidth(backtest_abs_errors, self.coverage)
        self.backtest_mae = stats.mae(backtest_abs_errors)
        self.trained_through_fy = int(last_fy)
        return self

    def predict(self, last_level: float, x_lag: np.ndarray | None = None) -> dict[str, float]:
        b = np.asarray(self.coef)
        g = b[0] + (float(np.dot(b[1:], x_lag)) if self.predictors else 0.0)
        h = self.interval_halfwidth
        return {"growth": g, "point": last_level * np.exp(g),
                "lower": last_level * np.exp(g - h), "upper": last_level * np.exp(g + h),
                "coverage": self.coverage}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> GrowthForecaster:
        return cls(**json.loads(path.read_text()))
