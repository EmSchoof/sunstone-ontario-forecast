# %% [markdown]
# # 02 - Variable selection for the revenue forecasts
#
# Targets: real log-growth of (a) Transient Occupancy Tax and (b) sales tax.
#
# Guardrails against misleading results:
# * **Pre-specified candidates.** A short list chosen from economic reasoning
#   BEFORE looking at correlations. Searching many variables on ~20 points will
#   always "find" something (data dredging / curse of dimensionality).
# * **Parameter budget.** Roughly 10 observations per estimated slope. With the
#   smallest training window of 10 years, that allows 1 predictor.
# * **Growth rates, not levels** (spurious regression; see 01_eda).
# * **Lagged drivers.** A same-year predictor is unknown when the forecast is made;
#   using it would leak future information. Lag-1 only ("nowcast" shown as context).
# * **Selection by out-of-sample error**, never in-sample R^2 or p-values.
#   Expanding-window, chronological backtest; all models scored on the SAME years.
# * **Baselines must be beaten** (naive = no change, drift = average growth).
#   If nothing beats them, the baseline is the answer, and that is reportable.
# * **Multiple comparisons.** Screening p-values are Holm-adjusted and descriptive only.
# * **COVID.** Fitting excludes COVID-affected rows; scoring is shown with and without them.
# * **MAE/RMSE in dollars**, not MAPE (unstable when growth is near zero).

# %%
import csv
import itertools
import json

import numpy as np

from ontario_forecast import config, stats
from ontario_forecast.db import load_panel
from ontario_forecast.evaluation import mae, rmse, rolling_origin
from ontario_forecast.features import fit_mask, lag, shock_mask
from ontario_forecast.model import GrowthForecaster

P = load_panel()
fy = P["fy"]
covid = shock_mask(fy, config.COVID_SHOCK_FYS)
TARGETS = config.FORECAST_TARGETS

# Pre-registered candidates: name -> (rationale, expected sign)
CANDIDATES = {
    "dlog_msa_leisure_jobs": ("regional hospitality demand", "+"),
    "dlog_msa_nonfarm_jobs": ("regional business cycle", "+"),
    "dlog_msa_transport_jobs": ("logistics/airport activity (Ontario's base)", "+"),
    "dlog_laus_employment": ("Ontario resident employment -> local spending", "+"),
    "dlog_cpi_lodging": ("hotel prices (TOT is % of room revenue)", "+"),
    "d_msa_unemployment_rate": ("labor-market slack", "-"),
}
MIN_TRAIN = 10


X_LAG = {k: lag(P[k]) for k in CANDIDATES}
train_ok = fit_mask(fy, config.COVID_SHOCK_FYS)  # COVID FYs + the FY after; still scored

# %% [markdown]
# ## 1. Parameter budget

# %%
n_growth = int(np.isfinite(P["dlog_tot_real"]).sum())
max_k = max(1, MIN_TRAIN // 10)
print(f"Growth observations: {n_growth}; smallest training window: {MIN_TRAIN}")
print(f"-> at most {max_k} predictor(s) per model; {len(CANDIDATES)} pre-specified candidates.")

# %% [markdown]
# ## 2. Screening (descriptive): correlations with CIs, Holm-adjusted

# %%
for tname, t in TARGETS.items():
    ycol = t["growth"]
    y = P[ycol]
    rows = []
    for c in CANDIDATES:
        for timing, x in (("nowcast", P[c]), ("lag-1", X_LAG[c])):
            for label, m in (("all", np.ones(len(fy), bool)), ("exCOVID", ~covid)):
                rows.append((c, timing, label, stats.pearson(x[m], y[m]), stats.spearman(x[m], y[m])))
    reject, p_adj = stats.adjust_pvalues([r[3].p for r in rows], method="holm")
    print(f"\n=== {tname}: {ycol}   ({len(rows)} tests, Holm-adjusted) ===")
    print(
        f"{'candidate':26s} {'timing':8s} {'sample':7s} {'r':>6s} {'95% CI':>15s} "
        f"{'rho':>6s} {'n':>3s} {'p_adj':>6s}"
    )
    for (c, timing, label, pr, sp), pa, rej in zip(rows, p_adj, reject, strict=True):
        print(
            f"{c:26s} {timing:8s} {label:7s} {pr.r:+6.2f} [{pr.lo:+.2f},{pr.hi:+.2f}] "
            f"{sp.r:+6.2f} {pr.n:3d} {pa:6.3f}{' *' if rej else ''}"
        )
print(
    "\nWide CIs at n~20 are expected. Sign flips between 'all' and 'exCOVID' mean the "
    "relationship is driven by the pandemic, not a stable driver."
)

# %% [markdown]
# ## 3. Multicollinearity among candidates (VIF)
# MSA nonfarm, leisure and transport jobs move together. Including correlated
# drivers inflates coefficient variance and makes signs unreliable.

# %%
names = list(CANDIDATES)
Xc = np.column_stack([X_LAG[k] for k in names])
ok_rows = np.isfinite(Xc).all(axis=1) & train_ok
for k, v in zip(names, stats.vif(Xc[ok_rows]), strict=True):
    print(f"VIF {k:26s} {v:6.1f}{'  <- high' if v > 5 else ''}")

# %% [markdown]
# ## 4. Out-of-sample backtest: baselines vs single-driver models

# %%


def fp_naive(y_tr, X_tr, x_next):
    return 0.0  # no growth = last year's level


def fp_drift(y_tr, X_tr, x_next):
    return float(np.mean(y_tr))  # average historical growth


def fp_ols(y_tr, X_tr, x_next):
    b = stats.ols_params(y_tr, X_tr)
    return float(b[0] + b[1:] @ np.atleast_1d(x_next))


def models_for(ycol: str) -> dict[str, tuple[list[str], np.ndarray | None, object]]:
    m = {
        "naive": ([], None, fp_naive),
        "drift": ([], None, fp_drift),
        "AR(1)": ([f"lag1_{ycol}"], lag(P[ycol])[:, None], fp_ols),
    }
    for c in CANDIDATES:
        m[c] = ([c], X_LAG[c][:, None], fp_ols)
    if max_k >= 2:
        for a, b in itertools.combinations(CANDIDATES, 2):
            m[f"{a}+{b}"] = ([a, b], np.column_stack([X_LAG[a], X_LAG[b]]), fp_ols)
    return m


results, selected = [], {}
for tname, t in TARGETS.items():
    ycol, levcol = t["growth"], t["level_real"]
    y_all, level = P[ycol], P[levcol]
    models = models_for(ycol)
    # Common sample: rows where the target AND every model's inputs exist, so all
    # models are scored on identical test years (otherwise the comparison is unfair).
    valid = np.isfinite(y_all)
    for _, X, _ in models.values():
        if X is not None:
            valid &= np.isfinite(X).all(axis=1)
    idx = np.flatnonzero(valid)
    y, fyv, cov = y_all[idx], fy[idx], covid[idx]
    prev_level = level[idx - 1]

    scores = {}
    for name, (preds, X, fp) in models.items():
        bt = rolling_origin(y, None if X is None else X[idx], fp, MIN_TRAIN, train_mask=train_ok[idx])
        # Growth errors -> dollar errors using the known prior-year level
        err_usd = prev_level[bt.test_idx] * (np.exp(bt.actual) - np.exp(bt.pred))
        ex = ~cov[bt.test_idx]
        scores[name] = dict(
            target=tname,
            model=name,
            predictors=preds,
            n_test=len(bt.test_idx),
            n_test_ex_covid=int(ex.sum()),
            mae_usd=mae(err_usd),
            rmse_usd=rmse(err_usd),
            mae_usd_ex_covid=mae(err_usd[ex]),
            rmse_usd_ex_covid=rmse(err_usd[ex]),
            _growth_err=bt.errors[ex],
            _X=X,
            _test_fys=fyv[bt.test_idx],
        )
    naive = scores["naive"]
    for s in scores.values():
        s["rel_mae_vs_naive"] = s["mae_usd"] / naive["mae_usd"]
        s["rel_mae_vs_naive_ex_covid"] = s["mae_usd_ex_covid"] / naive["mae_usd_ex_covid"]
        results.append(s)

    print(
        f"\n=== {tname}: test FYs {naive['_test_fys'].min()}-{naive['_test_fys'].max()} "
        f"(n={naive['n_test']}, "
        f"ex-COVID n={naive['n_test_ex_covid']}) ==="
    )
    print(f"{'model':28s} {'MAE $M':>8s} {'rel':>5s} {'MAE exC $M':>11s} {'rel exC':>8s}")
    for s in sorted(scores.values(), key=lambda s: s["mae_usd_ex_covid"]):
        print(
            f"{s['model']:28s} {s['mae_usd']/1e6:8.2f} {s['rel_mae_vs_naive']:5.2f} "
            f"{s['mae_usd_ex_covid']/1e6:11.2f} {s['rel_mae_vs_naive_ex_covid']:8.2f}"
        )

    # Selection rule: must beat naive on BOTH samples; among those, prefer the
    # simplest (fewest predictors) model within 5% of the best ex-COVID MAE.
    eligible = [
        s for s in scores.values() if s["rel_mae_vs_naive"] < 1 and s["rel_mae_vs_naive_ex_covid"] < 1
    ]
    if eligible:
        floor = min(s["mae_usd_ex_covid"] for s in eligible)
        near = [s for s in eligible if s["mae_usd_ex_covid"] <= 1.05 * floor]
        best = min(near, key=lambda s: (len(s["predictors"]), s["mae_usd_ex_covid"]))
    else:
        best = naive
    selected[tname] = best
    print(f"-> selected: {best['model']}")
    print(
        "   Note: the winner's backtest MAE is optimistic (it was picked as the best of "
        f"{len(scores)} on these years)."
    )

# %% [markdown]
# ## 5. Persist the decision: fit with statsmodels, store coefficients (numpy/json model)

# %%
config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
with open(config.REPORTS_DIR / "variable_selection.csv", "w", newline="") as f:
    cols = [k for k in results[0] if not k.startswith("_")]
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in results:
        w.writerow({k: (";".join(v) if isinstance(v, list) else v) for k, v in r.items() if k in cols})

for tname, best in selected.items():
    ycol, levcol = TARGETS[tname]["growth"], TARGETS[tname]["level_real"]
    X = best["_X"]
    fit_rows = np.isfinite(P[ycol]) & train_ok
    if X is not None:
        fit_rows &= np.isfinite(X).all(axis=1)
    if best["model"] == "naive":
        coef = np.array([0.0])
    else:
        coef = stats.ols_params(P[ycol][fit_rows], None if X is None else X[fit_rows])
    model = GrowthForecaster(target=levcol, predictors=best["predictors"], coverage=0.8)
    model.calibrate(coef, best["_growth_err"], last_fy=int(fy[fit_rows].max()))
    model.save(config.MODELS_DIR / f"{tname}_model.json")
    print(
        f"{tname}: saved {best['model']} -> models/{tname}_model.json  "
        f"(80% half-width {model.interval_halfwidth:.3f} log-growth, "
        f"{len(model.backtest_errors)} out-of-sample errors)"
    )

print(json.dumps({k: v["model"] for k, v in selected.items()}, indent=2))
