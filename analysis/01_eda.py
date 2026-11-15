# %% [markdown]
# # 01 - Exploratory data analysis: Ontario fiscal & labor series
#
# Goal: understand the data BEFORE choosing model variables, and surface the
# traps that would make a forecast look better than it is:
#   1. effective sample size (how many years each series really has)
#   2. definitional breaks (TOT rename, sales-tax "triple flip")
#   3. nominal vs real dollars
#   4. trends -> non-stationarity -> spurious correlation in levels
#   5. the COVID shock (FY2020-22) dominating any fit
#   6. reconciling our derived numbers with the figures in the proposal
#
# Run cell by cell in PyCharm (Scientific mode) or top-to-bottom:
#   python analysis/01_eda.py
# Requires: the ingest + transform steps (see README). Uses numpy/matplotlib;
# statsmodels only for unit-root tests (analysis-time dependency).

# %%
import warnings

import matplotlib.pyplot as plt
import numpy as np

from ontario_forecast import config
from ontario_forecast.db import fetch

config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
P = fetch("select * from marts.ontario_fy_panel order by fy")
fy = P["fy"]
covid = np.isin(fy, config.COVID_SHOCK_FYS)


def savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(config.FIGURES_DIR / f"{name}.png", dpi=150)
    plt.show()


def shade_covid(ax) -> None:
    ax.axvspan(min(config.COVID_SHOCK_FYS) - 0.5, max(config.COVID_SHOCK_FYS) + 0.5,
               color="0.85", zorder=0, label="COVID shock FYs")


# %% [markdown]
# ## 1. Coverage: effective sample size per variable
# Annual data means n is small. Every later decision (how many predictors, how
# much to trust a p-value) depends on these counts.

# %%
print(f"{'variable':45s} {'n':>4s}  {'first':>5s}-{'last':<5s}")
for k, v in P.items():
    if k == "fy" or v.dtype.kind not in "f":
        continue
    ok = ~np.isnan(v)
    if ok.any():
        print(f"{k:45s} {ok.sum():4d}  {fy[ok].min():5d}-{fy[ok].max():<5d}")

# %% [markdown]
# ## 2. Definitional break: sales tax "triple flip" (FY2005-FY2016)
# Using the Bradley-Burns line alone shows a fake drop in 2005 and a fake jump in
# 2016. The mart adds the in-lieu payments back (`sales_tax_total`).

# %%
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(fy, P["sales_tax_bradley_burns"] / 1e6, "--", label="Bradley-Burns line only (broken)")
ax.plot(fy, P["sales_tax_total"] / 1e6, lw=2, label="+ in-lieu (consistent series)")
ax.axvspan(2004.5, 2016.5, color="orange", alpha=0.1, label="triple flip FY2005-16")
ax.set(title="Ontario sales & use tax revenue", ylabel="$ millions (nominal)", xlabel="Fiscal year")
ax.legend()
savefig("01_sales_tax_triple_flip")

# %% [markdown]
# ## 3. Nominal vs real
# Revenue growth partly reflects inflation. Models use real (CPI-LA deflated)
# dollars so that "growth" means more activity, not higher prices.

# %%
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for ax, col, title in [(axes[0], "tot_revenue", "Transient Occupancy Tax"),
                       (axes[1], "sales_tax_total", "Sales tax (consistent)")]:
    ax.plot(fy, P[col] / 1e6, label="nominal")
    ax.plot(fy, P[col + "_real"] / 1e6, lw=2, label=f"real (FY{fy.max()} $)")
    shade_covid(ax)
    ax.set(title=title, ylabel="$ millions", xlabel="Fiscal year")
    ax.legend()
savefig("02_nominal_vs_real")

# %% [markdown]
# ## 4. Levels trend; growth rates don't
# Two series that both trend up will correlate strongly in levels even if they
# are unrelated (spurious regression). Compare levels vs growth rates.

# %%
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
z = lambda a: (a - np.nanmean(a)) / np.nanstd(a)  # noqa: E731
for col in ["tot_revenue_real", "msa_leisure_jobs_k", "population"]:
    axes[0].plot(fy, z(P[col]), label=col)
for col in ["dlog_tot_real", "dlog_msa_leisure_jobs", "dlog_population"]:
    axes[1].plot(fy, P[col], marker="o", label=col)
axes[0].set(title="Levels (standardized): shared trend", xlabel="Fiscal year")
axes[1].set(title="Log growth rates", xlabel="Fiscal year")
axes[1].axhline(0, color="k", lw=0.5)
shade_covid(axes[1])
for ax in axes:
    ax.legend(fontsize=8)
savefig("03_levels_vs_growth")

# Demonstration: correlation in levels vs growth
from ontario_forecast.stats import pearson  # noqa: E402

for a, b in [("tot_revenue_real", "population"), ("dlog_tot_real", "dlog_population")]:
    c = pearson(P[a], P[b])
    print(f"corr({a}, {b}) = {c.r:+.2f}  95% CI [{c.lo:+.2f}, {c.hi:+.2f}]  n={c.n}")
print("-> a high level correlation that vanishes in growth rates is a shared trend, not a driver.")

# %% [markdown]
# ## 5. Unit-root tests (stationarity)
# ADF null: unit root (non-stationary). KPSS null: stationary. Using both guards
# against either test's bias. **Caveat:** with n~20 both tests have low power;
# treat results as supporting evidence, not proof. The decision to model growth
# rates rests mainly on economics + the plots above.

# %%
from statsmodels.tsa.stattools import adfuller, kpss  # noqa: E402  (analysis-only dependency)

print(f"{'series':28s} {'n':>3s} {'ADF p':>7s} {'KPSS p':>7s}  verdict")
for col in ["tot_revenue_real", "sales_tax_total_real", "msa_leisure_jobs_k",
            "dlog_tot_real", "dlog_sales_tax_real", "dlog_msa_leisure_jobs"]:
    x = P[col][~np.isnan(P[col])]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # KPSS p-values are table-bounded at 0.01/0.10
        p_adf = adfuller(x, maxlag=2, autolag="AIC")[1]
        p_kpss = kpss(x, regression="c", nlags="auto")[1]
    verdict = ("stationary" if p_adf < 0.10 and p_kpss > 0.05 else
               "non-stationary" if p_adf >= 0.10 and p_kpss <= 0.05 else "inconclusive")
    print(f"{col:28s} {len(x):3d} {p_adf:7.3f} {p_kpss:7.3f}  {verdict}")

# %% [markdown]
# ## 6. The COVID shock
# FY2021 TOT fell and FY2022 rebounded sharply. In a 21-point regression, those
# two points can determine the slope by themselves. Check their leverage.

# %%
g = P["dlog_tot_real"]
ok = ~np.isnan(g)
print(f"real TOT growth, all years:      mean {np.nanmean(g):+.3f}  sd {np.nanstd(g):.3f}  n={ok.sum()}")
print(f"real TOT growth, ex-COVID FYs:   mean {np.nanmean(g[~covid]):+.3f}  "
      f"sd {np.nanstd(g[~covid]):.3f}  n={(ok & ~covid).sum()}")
share = np.nansum(g[covid] ** 2) / np.nansum(g ** 2)
print(f"COVID FYs account for {share:.0%} of total squared growth variation")

# %% [markdown]
# ## 7. Peer context: real TOT per capita, indexed
# Per-capita ratios are used for *description only*. In regressions, two
# per-capita variables share a denominator and correlate mechanically.

# %%
C = fetch("select city, fy, tot_revenue_real / population as v from marts.city_tax_fy "
          "where tot_revenue_real is not null order by city, fy")
fig, ax = plt.subplots(figsize=(9, 4))
base_fy = 2015
for city in np.unique(C["city"]):
    m = C["city"] == city
    f, v = C["fy"][m], C["v"][m]
    if base_fy in f and v[f == base_fy][0] > 0:
        idx = 100 * v / v[f == base_fy][0]
        ax.plot(f, idx, lw=2.5 if city == config.CITY else 0.8,
                color="C3" if city == config.CITY else "0.6",
                label=city if city == config.CITY else None)
shade_covid(ax)
ax.set(title=f"Real TOT per capita, FY{base_fy}=100 (grey = peer cities)", xlabel="Fiscal year")
ax.legend()
savefig("04_peer_tot_per_capita")

# %% [markdown]
# ## 8. Live/work share (LODES) and reconciliation with the proposal

# %%
L = fetch("select * from staging.lodes_ontario_cy order by cy")
if len(L.get("cy", [])):
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(L["cy"], 100 * L["share_residents_work_local"], marker="o", label="all jobs")
    ax.plot(L["cy"], 100 * L["share_high_wage_residents_work_local"], marker="o",
            label="jobs > $3,333/month")
    ax.set(title="Share of employed Ontario residents who work in Ontario", ylabel="%",
           xlabel="Year")
    ax.legend()
    savefig("05_lodes_live_work_share")

    bm = config.PROPOSAL_BENCHMARKS
    for i, y in enumerate(L["cy"]):
        close = abs(L["live_and_work"][i] - bm["live_and_work_in_ontario"]) / bm["live_and_work_in_ontario"]
        if close < 0.02:
            print(f"Year {y} matches proposal: live&work {L['live_and_work'][i]:,} "
                  f"(proposal {bm['live_and_work_in_ontario']:,}), residents "
                  f"{L['employed_residents'][i]:,} (proposal {bm['employed_residents']:,}), "
                  f"inflow {L['inflow_commuters'][i]:,} (proposal {bm['inflow_commuters']:,})")
    print("If no year matches within 2%, the proposal likely used OnTheMap's all-states counts or a "
          "different job type; document which before publishing.")
else:
    print("LODES not loaded yet (run ingest without --skip-lodes).")

# Sales tax: State Controller vs proposal's budget figure
last = -1
print(f"\nFY{fy[last]} sales tax (SCO, Bradley-Burns + in-lieu): ${P['sales_tax_total'][last]/1e6:,.1f}M "
      f"vs proposal FY27 budget ${config.PROPOSAL_BENCHMARKS['sales_tax_fy27_budget']/1e6:,.1f}M")
print("A gap this large suggests different definitions (e.g., add-on transactions tax or "
      "Prop 172 included in the budget). Confirm with the City budget before combining them.")

# %% [markdown]
# ## 9. County industry pay (career-ladder context, QCEW)

# %%
Q = fetch("select sector, employment, avg_annual_pay from marts.sb_county_sector_cy "
          "where cy = (select max(cy) from marts.sb_county_sector_cy) and sector is not null "
          "order by avg_annual_pay")
if len(Q.get("sector", [])):
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(Q["sector"], Q["avg_annual_pay"] / 1e3)
    ax.set(title="San Bernardino County private avg annual pay by sector (latest year)",
           xlabel="$ thousands")
    savefig("06_county_pay_by_sector")

# %% [markdown]
# ## EDA conclusions to carry into variable selection
# * Model **real log-growth**, not levels (trend -> spurious correlation).
# * Use `sales_tax_total` (triple-flip corrected), never the Bradley-Burns line alone.
# * n is ~20 growth observations -> at most 1-2 predictors (see 02).
# * COVID FYs must be handled explicitly; report results with and without them.
# * Per-capita ratios: description only, not regressors.
