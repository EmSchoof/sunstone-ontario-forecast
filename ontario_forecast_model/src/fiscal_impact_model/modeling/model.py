"""Deployable forecaster: numpy + json only.

Training happens in analysis/02 (statsmodels OLS); this class only stores the fitted
coefficients and out-of-sample errors and turns them into forecasts.

Model: g_t = a + b' x_{t-1} + e_t   (g = real log-growth), level_t = level_{t-1} * exp(g_t)
Interval: split-conformal half-width from out-of-sample backtest errors.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from fiscal_impact_model.modeling.evaluation import conformal_halfwidth, mae


@dataclass
class GrowthForecaster:
    target: str
    predictors: list[str] = field(default_factory=list)  # lag-1 growth drivers ([] = trend/naive)
    coef: list[float] = field(default_factory=list)  # [intercept, b1, ...]
    interval_halfwidth: float = float("inf")  # on the log-growth scale
    coverage: float = 0.8
    trained_through_fy: int | None = None
    backtest_mae: float | None = None
    backtest_errors: list[float] = field(default_factory=list)  # signed, ex-COVID, out-of-sample

    def calibrate(self, coef: np.ndarray, backtest_errors: np.ndarray, last_fy: int) -> GrowthForecaster:
        e = np.asarray(backtest_errors, float)
        self.coef = [float(c) for c in coef]
        self.backtest_errors = e.tolist()
        self.interval_halfwidth = conformal_halfwidth(e, self.coverage)
        self.backtest_mae = mae(e)
        self.trained_through_fy = int(last_fy)
        return self

    def predict(self, last_level: float, x_lag: np.ndarray | None = None) -> dict[str, float]:
        b = np.asarray(self.coef)
        g = b[0] + (float(b[1:] @ np.asarray(x_lag, float)) if self.predictors else 0.0)
        h = self.interval_halfwidth
        return {
            "growth": g,
            "point": last_level * np.exp(g),
            "lower": last_level * np.exp(g - h),
            "upper": last_level * np.exp(g + h),
            "coverage": self.coverage,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> GrowthForecaster:
        return cls(**json.loads(path.read_text()))
