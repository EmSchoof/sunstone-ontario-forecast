"""Scenario engine: three statistically likely outcomes (P10 / P50 / P90).
numpy + scipy.special (analysis-time; never imported by the deployed model).

Method (bootstrap of OUT-OF-SAMPLE errors):
    g_{T+h} = mu_h + e*,  e* drawn with replacement from the model's rolling-origin
    forecast errors (ex-COVID). Those errors were made on years the model had not
    seen, so they already contain parameter-estimation error, not just noise.
    Paths are accumulated (levels: L_T * exp(sum g); shares: logistic(logit_T + sum g))
    and quantiles are taken per year.

How to read the output:
    The P10 line means "in 10% of simulated outcomes, that year comes in below this
    value". It is a per-year bound, not one single simulated path. P10-P90 holds 80%
    of outcomes.

Known limits (state them next to the charts):
    * iid resampling ignores autocorrelation in errors (check `error_autocorr`).
    * ~10 errors give a coarse distribution; tails beyond P10/P90 are unreliable.
    * Pandemic-scale shocks are excluded because COVID-year errors are excluded.
    * No policy effect is modeled: this is the status-quo baseline the proposal's
      programs should be measured against.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from scipy.special import expit, logit

from ontario_forecast.modeling.evaluation import mae, rolling_origin
from ontario_forecast.modeling.features import fit_mask, shock_mask


@dataclass(frozen=True)
class Fan:
    years: np.ndarray
    quantiles: tuple[float, ...]
    values: np.ndarray  # (len(quantiles), horizon)
    samples: np.ndarray  # (n_sims, horizon) simulated outcomes
    n_errors: int

    def q(self, p: float) -> np.ndarray:
        return self.values[self.quantiles.index(p)]

    def final(self) -> tuple[float, ...]:
        """Values of each quantile in the last forecast year (e.g. P10, P50, P90)."""
        return tuple(float(v) for v in self.values[:, -1])

    def rows(self, metric: str, units: str, model: str, digits: int = 0) -> list[dict]:
        """Long-format records of every charted number (the chart's table view)."""
        return [
            {
                "metric": metric,
                "period": int(yr),
                "quantile": q,
                "value": round(float(v), digits),
                "units": units,
                "model": model,
                "n_errors": self.n_errors,
            }
            for q, vals in zip(self.quantiles, self.values, strict=True)
            for yr, v in zip(self.years, vals, strict=True)
        ]

    def percentile_of(self, value: float, year: int) -> float:
        """Share of simulated outcomes below `value` in `year` (e.g. a budget figure)."""
        h = int(np.flatnonzero(self.years == year)[0])
        return float(np.mean(self.samples[:, h] < value))


def bootstrap_growth(mu: np.ndarray, errors: np.ndarray, n_sims: int, rng: np.random.Generator) -> np.ndarray:
    """(n_sims, horizon) growth draws: mu[h] + resampled out-of-sample error."""
    e = np.asarray(errors, float)
    e = e[~np.isnan(e)]
    if e.size < 5:
        raise ValueError(f"only {e.size} out-of-sample errors; too few to simulate")
    mu = np.asarray(mu, float)
    return mu[None, :] + rng.choice(e, size=(n_sims, len(mu)), replace=True)


def ar1_growth(
    a: float,
    b: float,
    last_growth: float,
    errors: np.ndarray,
    horizon: int,
    n_sims: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """AR(1) recursion on growth: g_t = a + b g_{t-1} + e*."""
    shocks = bootstrap_growth(np.zeros(horizon), errors, n_sims, rng)
    g = np.empty_like(shocks)
    prev = np.full(n_sims, float(last_growth))
    for h in range(horizon):
        prev = a + b * prev + shocks[:, h]
        g[:, h] = prev
    return g


def share_paths(
    periods: np.ndarray,
    shares: np.ndarray,
    shock_periods: Iterable[int],
    horizon: int,
    n_sims: int,
    rng: np.random.Generator,
    min_train: int = 8,
) -> tuple[np.ndarray, str, int]:
    """Status-quo simulation of a bounded share (e.g. live/work) on the logit scale.

    Drift is used only if it beats no-change out of sample (same discipline as 02).
    Returns (paths (n_sims, horizon) in share units, model label, n out-of-sample errors).
    """
    z = logit(np.asarray(shares, float))
    dz, p = np.diff(z), np.asarray(periods)[1:]
    fit_ok, scored = fit_mask(p, shock_periods), ~shock_mask(p, shock_periods)
    drift = rolling_origin(dz, None, lambda y, X, x: float(np.mean(y)), min_train, fit_ok)
    naive = rolling_origin(dz, None, lambda y, X, x: 0.0, min_train, fit_ok)
    ex = scored[drift.test_idx]
    use_drift = mae(drift.errors[ex]) < mae(naive.errors[ex])
    bt = drift if use_drift else naive
    mu = np.full(horizon, float(np.mean(dz[fit_ok])) if use_drift else 0.0)
    paths = expit(z[-1] + np.cumsum(bootstrap_growth(mu, bt.errors[ex], n_sims, rng), axis=1))
    return paths, ("trend" if use_drift else "no change"), int(ex.sum())


def model_growth(
    model,
    panel: dict,
    growth_col: str,
    fit_rows: np.ndarray,
    horizon: int,
    n_sims: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Simulated real log-growth paths (n_sims, horizon) for a saved GrowthForecaster.

    AR(1): recursion from the last observed growth. Lag-1 drivers: year 1 uses the last
    observed driver; later years use the driver's average over the fitting rows (its
    future values are unknown). Trend/naive: intercept only.
    """
    b = np.asarray(model.coef)
    e = np.asarray(model.backtest_errors)
    if model.predictors == [f"lag1_{growth_col}"]:
        return ar1_growth(b[0], b[1], panel[growth_col][-1], e, horizon, n_sims, rng)
    mu = np.full(horizon, b[0])
    if model.predictors:
        x_last = np.array([panel[p][-1] for p in model.predictors])
        x_mean = np.array([np.nanmean(panel[p][fit_rows]) for p in model.predictors])
        mu[0] = b[0] + b[1:] @ x_last
        mu[1:] = b[0] + b[1:] @ x_mean
    return bootstrap_growth(mu, e, n_sims, rng)


def fan(samples: np.ndarray, first_year: int, quantiles: tuple[float, ...], n_errors: int) -> Fan:
    years = np.arange(first_year, first_year + samples.shape[1])
    return Fan(years, tuple(quantiles), np.quantile(samples, quantiles, axis=0), samples, n_errors)


def levels_from_growth(last_level: float, growth: np.ndarray, log_inflation: float = 0.0) -> np.ndarray:
    """Real log-growth paths -> level paths (nominal if log_inflation > 0)."""
    return last_level * np.exp(np.cumsum(growth + log_inflation, axis=1))


def error_autocorr(errors: np.ndarray) -> float:
    """Lag-1 autocorrelation of errors; |r| > ~0.4 means iid bootstrap understates risk."""
    e = np.asarray(errors, float)
    e = e[~np.isnan(e)]
    return float(np.corrcoef(e[:-1], e[1:])[0, 1]) if len(e) > 3 else float("nan")
