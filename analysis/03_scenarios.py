# %% [markdown]
# # 03 - Final export: three statistically likely outcomes
#
# For each proposal metric: Downside (P10), Central (P50), Upside (P90), for the
# next `SCENARIO_HORIZON` fiscal years, from bootstrapped out-of-sample errors of
# the model chosen in 02. These are the **status-quo baselines**: no program effect
# is assumed, so the City can measure Stay +1 / Career Pathways against them.
#
# Outputs (reports/final/): one PNG + SVG per metric, scenarios.pdf (all pages),
# scenarios_summary.csv (the table view of every charted number).
#
#   python analysis/03_scenarios.py      (after 01 and 02)

# %%
import matplotlib
import numpy as np

matplotlib.use("Agg")  # file export only; must precede pyplot (imported by charts)

from ontario_forecast import config, scenarios  # noqa: E402
from ontario_forecast.charts import fan_chart, pct, usd_m  # noqa: E402
from ontario_forecast.db import fetch, load_panel  # noqa: E402
from ontario_forecast.features import fit_mask  # noqa: E402
from ontario_forecast.model import GrowthForecaster  # noqa: E402
from ontario_forecast.reporting import export_figures, write_csv  # noqa: E402

config.FINAL_DIR.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(config.SCENARIO_SEED)
H, N, Q = config.SCENARIO_HORIZON, config.SCENARIO_SIMS, config.SCENARIO_QUANTILES
band = f"{(Q[-1] - Q[0]):.0%}"  # "80%" for (0.10, 0.90)
P = load_panel()
fy = P["fy"]
fit_ok = fit_mask(fy, config.COVID_SHOCK_FYS)
fy_label = lambda v: f"FY{int(v) % 100:02d}"  # noqa: E731

# Inflation assumption for nominal dollars: trailing 10-FY mean CPI-LA growth.
dlog_cpi = np.diff(np.log(P["cpi_la"]))
infl = float(np.nanmean(dlog_cpi[-10:]))
print(f"Nominal conversion assumes {np.expm1(infl):.2%}/yr inflation (CPI-LA, trailing 10 FYs)")

pages, summary = [], []


def growth_paths(model: GrowthForecaster, ycol: str) -> np.ndarray:
    return scenarios.model_growth(model, P, ycol, fit_ok, H, N, rng)


# %% [markdown]
# ## Revenue scenarios (TOT, sales tax), nominal dollars

# %%
# Budget reference markers come from marts.headline_metrics: the City's adopted budget
# (data/manual/city_budget_revenue.csv) if loaded, otherwise the proposal figure, labeled as such.
H_M = fetch("select metric, period, value, is_fallback from marts.headline_metrics")


def budget_marker(metric: str) -> tuple[int, float, str] | None:
    hit = np.flatnonzero(H_M["metric"] == metric)
    if not len(hit) or not np.isfinite(H_M["value"][hit[0]]):
        return None
    i = hit[0]
    label = (
        "FY27 budget (proposal figure, unverified)" if H_M["is_fallback"][i] else "City FY27 adopted budget"
    )
    return int(H_M["period"][i]), float(H_M["value"][i]), label


for key, t in config.FORECAST_TARGETS.items():
    ycol, levcol, name = t["growth"], t["level"], t["label"]
    ref = budget_marker(t["budget_metric"])
    # Sales-tax budget marker only from the City budget itself: the proposal's figure
    # appears to use a different definition than State Controller actuals.
    if key == "sales_tax" and ref and "proposal" in ref[2]:
        ref = None
    path = config.MODELS_DIR / f"{key}_model.json"
    if not path.exists():
        print(f"{key}: run analysis/02_variable_selection.py first")
        continue
    model = GrowthForecaster.load(path)
    g = growth_paths(model, ycol)
    last = float(P[levcol][-1])
    f = scenarios.fan(
        scenarios.levels_from_growth(last, g, infl), int(fy[-1]) + 1, Q, len(model.backtest_errors)
    )
    lo, mid, hi = f.final()
    ac = scenarios.error_autocorr(model.backtest_errors)
    model_label = ", ".join(model.predictors) or "trend"

    sub = (
        f"FY{f.years[-1]}: central {usd_m(mid)}, {band} of outcomes between {usd_m(lo)} and "
        f"{usd_m(hi)}. Model: {model_label} ({len(model.backtest_errors)} "
        f"out-of-sample errors)."
    )
    reference = None
    if ref and ref[0] in f.years:
        reference = ref
        pctl = f.percentile_of(ref[1], ref[0])
        sub += f"\nThe {ref[2]} ({usd_m(ref[1])}) sits at the {pctl:.0%} percentile " "of simulated outcomes."
    fig = fan_chart(
        f,
        fy,
        P[levcol],
        title=f"Ontario {name}: three likely outcomes",
        subtitle=sub,
        fmt=usd_m,
        x_label=fy_label,
        reference=reference,
        source=(
            "Source: CA State Controller city revenues (sales tax incl. in-lieu, FY2005-16). "
            f"Simulated {N:,} paths from out-of-sample errors; excludes pandemic-scale shocks; "
            f"assumes {np.expm1(infl):.1%}/yr inflation; no policy effect assumed."
            + (f" Error autocorrelation {ac:+.2f}." if np.isfinite(ac) else "")
        ),
    )
    pages.append((key, fig))
    summary += f.rows(levcol, "USD nominal (fiscal year)", model_label)

# %% [markdown]
# ## Share of employed residents working in Ontario (LODES)
# Modeled on the logit scale so simulated shares stay inside (0, 1). Same
# discipline as the revenue models: drift chosen only if it beats naive out of sample.

# %%
L = fetch(
    "select cy, share_residents_work_local s from staging.lodes_ontario_cy "
    "where share_residents_work_local is not null order by cy"
)
if len(L.get("cy", [])) >= 12:
    cy = L["cy"]
    paths, model_label, n_err = scenarios.share_paths(cy, L["s"], config.LODES_COVID_YEARS, H, N, rng)
    f = scenarios.fan(paths, int(cy[-1]) + 1, Q, n_err)
    lo, mid, hi = f.final()
    fig = fan_chart(
        f,
        cy,
        L["s"],
        title="Employed Ontario residents who work in Ontario",
        subtitle=(
            f"{f.years[-1]}: central {pct(mid)}, {band} of outcomes between {pct(lo)} and {pct(hi)} "
            f"if nothing changes. Model: {model_label} "
            f"({n_err} out-of-sample errors). Career Pathways success = beating this band."
        ),
        fmt=pct,
        x_label=lambda v: f"{int(v)}",
        source=(
            "Source: Census LEHD LODES 8 origin-destination, all jobs (JT00), CA main + aux. "
            f"Simulated {N:,} paths on the logit scale from out-of-sample errors; "
            "2020-21 excluded from fitting; no policy effect assumed."
        ),
    )
    pages.append(("live_work_share", fig))
    summary += f.rows("share_residents_work_local", "share (calendar year)", model_label, digits=4)
else:
    print("LODES not loaded (or < 12 years): skipping the live/work chart.")

# %% [markdown]
# ## Export

# %%
export_figures(pages, config.FINAL_DIR, suffix="_scenarios", pdf_name="scenarios.pdf")
write_csv(summary, config.FINAL_DIR / "scenarios_summary.csv")
