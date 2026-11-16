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
# Requires: the ingest + transform steps (see README). Stats via targeted
# statsmodels/scipy imports in ontario_forecast.stats.

# %%
import matplotlib.pyplot as plt
import numpy as np

from ontario_forecast import config
from ontario_forecast.db import fetch, load_panel
from ontario_forecast.features import shock_mask
from ontario_forecast.stats import pearson, unit_root

config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
P = load_panel()
fy = P["fy"]
covid = shock_mask(fy, config.COVID_SHOCK_FYS)


def savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(config.FIGURES_DIR / f"{name}.png", dpi=150)
    plt.show()


def shade_covid(ax) -> None:
    ax.axvspan(
        min(config.COVID_SHOCK_FYS) - 0.5,
        max(config.COVID_SHOCK_FYS) + 0.5,
        color="0.85",
        zorder=0,
        label="COVID shock FYs",
    )


# %% [markdown]
# ## 1. Coverage: effective sample size per variable
# Annual data means n is small. Every later decision (how many predictors, how
# much to trust a p-value) depends on these counts.

# %%
print(f"{'variable':45s} {'n':>4s}  {'first':>5s}-{'last':<5s}")
for k, v in P.items():
    if k == "fy" or v.dtype.kind not in "fiu":
        continue
    ok = ~np.isnan(v.astype(float))
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
for ax, col, title in [
    (axes[0], "tot_revenue", "Transient Occupancy Tax"),
    (axes[1], "sales_tax_total", "Sales tax (consistent)"),
]:
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
print(f"{'series':28s} {'n':>3s} {'ADF p':>7s} {'KPSS p':>7s}  verdict")
for col in [
    "tot_revenue_real",
    "sales_tax_total_real",
    "msa_leisure_jobs_k",
    "dlog_tot_real",
    "dlog_sales_tax_real",
    "dlog_msa_leisure_jobs",
]:
    u = unit_root(P[col])
    print(f"{col:28s} {u.n:3d} {u.adf_p:7.3f} {u.kpss_p:7.3f}  {u.verdict}")
print("KPSS p-values are bounded to [0.01, 0.10] by statsmodels' lookup table.")

# %% [markdown]
# ## 6. The COVID shock
# FY2021 TOT fell and FY2022 rebounded sharply. In a 21-point regression, those
# two points can determine the slope by themselves. Check their leverage.

# %%
g = P["dlog_tot_real"]
ok = ~np.isnan(g)
print(f"real TOT growth, all years:      mean {np.nanmean(g):+.3f}  sd {np.nanstd(g):.3f}  n={ok.sum()}")
print(
    f"real TOT growth, ex-COVID FYs:   mean {np.nanmean(g[~covid]):+.3f}  "
    f"sd {np.nanstd(g[~covid]):.3f}  n={(ok & ~covid).sum()}"
)
share = np.nansum(g[covid] ** 2) / np.nansum(g**2)
print(f"COVID FYs account for {share:.0%} of total squared growth variation")

# %% [markdown]
# ## 7. Peer context: real TOT per capita, indexed
# Per-capita ratios are used for *description only*. In regressions, two
# per-capita variables share a denominator and correlate mechanically.

# %%
C = fetch(
    "select city, fy, tot_revenue_real / population as v from marts.city_tax_fy "
    "where tot_revenue_real is not null order by city, fy"
)
fig, ax = plt.subplots(figsize=(9, 4))
base_fy = 2015
for city in np.unique(C["city"]):
    m = C["city"] == city
    f, v = C["fy"][m], C["v"][m]
    if base_fy in f and v[f == base_fy][0] > 0:
        idx = 100 * v / v[f == base_fy][0]
        ax.plot(
            f,
            idx,
            lw=2.5 if city == config.CITY else 0.8,
            color="C3" if city == config.CITY else "0.6",
            label=city if city == config.CITY else None,
        )
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
    ax.plot(L["cy"], 100 * L["share_high_wage_residents_work_local"], marker="o", label="jobs > $3,333/month")
    ax.set(title="Share of employed Ontario residents who work in Ontario", ylabel="%", xlabel="Year")
    ax.legend()
    savefig("05_lodes_live_work_share")

    # Which LODES year did the proposal quote? (diagnostic only; the official value wins)
    lw = config.PROPOSAL_BENCHMARKS["live_and_work_in_ontario"][1]
    hits = [int(y) for i, y in enumerate(L["cy"]) if abs(L["live_and_work"][i] - lw) / lw < 0.02]
    print(f"Proposal's live&work count ({lw:,}) matches LODES year(s): {hits or 'none within 2%'}")
else:
    print("LODES not loaded yet (run ingest without --skip-lodes).")

# %% [markdown]
# ## 8b. Headline numbers: official source first, proposal only as labeled fallback
# Rule: State Controller / Census / BLS / City adopted budget take precedence. Where they
# differ from the proposal text by >5%, the proposal should be updated to the official value.

# %%
M = fetch("select * from marts.headline_metrics")
print(f"{'metric':30s} {'value':>14s} {'period':>6s}  {'vs proposal':>11s}  source")
for i, m in enumerate(M["metric"]):
    v, pv, d = M["value"][i], M["proposal_value"][i], M["pct_diff_vs_proposal"][i]
    shown = f"{v:.1%}" if np.isfinite(v) and abs(v) < 1 else f"{v:,.0f}"
    diff = f"{d:+.1%}" if np.isfinite(d) else "-"
    period = "" if not np.isfinite(M["period"][i]) else str(int(M["period"][i]))
    flag = "  <- FALLBACK" if M["is_fallback"][i] else ""
    print(f"{m:30s} {shown:>14s} {period:>6s}  {diff:>11s}  {M['source'][i]}{flag}")
print(
    "Note: SCO *actual* sales tax and the FY27 *budget* are different metrics; if the City budget "
    "figure is far above SCO actuals, its definition likely differs (confirm before comparing)."
)

# %% [markdown]
# ## 9. County industry pay (career-ladder context, QCEW)

# %%
Q = fetch(
    "select sector, employment, avg_annual_pay from marts.sb_county_sector_cy "
    "where cy = (select max(cy) from marts.sb_county_sector_cy) and sector is not null "
    "order by avg_annual_pay"
)
if len(Q.get("sector", [])):
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(Q["sector"], Q["avg_annual_pay"] / 1e3)
    ax.set(title="San Bernardino County private avg annual pay by sector (latest year)", xlabel="$ thousands")
    savefig("06_county_pay_by_sector")

# %% [markdown]
# ## 10. Pathway wages (OEWS) vs the proposal, and an ACS cross-check of 15.5%
# OEWS is a survey; its medians are MSA-wide (Riverside-San Bernardino-Ontario),
# not Ontario-only. The ACS place-of-work share is a different instrument than
# LODES (survey vs administrative records): agreement within the ACS MOE is support,
# not proof. Only non-overlapping 5-year vintages are compared.

# %%
W = fetch(
    "select soc, occupation, year, median_annual_wage, median_vs_all_occupations, "
    "proposal_median_wage, pct_diff_vs_proposal from marts.msa_occupation_wages"
)
if len(W.get("soc", [])):
    print(
        f"OEWS {int(W['year'][0])} medians (official; use these in the proposal), "
        "Riverside-San Bernardino-Ontario MSA"
    )
    for i, _ in enumerate(W["soc"]):
        d = W["pct_diff_vs_proposal"][i]
        q = (
            f"  proposal ${W['proposal_median_wage'][i]:,.0f} ({d:+.1%})"
            if np.isfinite(W["proposal_median_wage"][i])
            else ""
        )
        print(
            f"  {W['occupation'][i]:55s} ${W['median_annual_wage'][i]:>9,.0f} "
            f"({W['median_vs_all_occupations'][i]:.2f}x all){q}"
        )
else:
    print("OEWS not loaded.")

A = fetch(
    "select geo, acs_year, window_start, share, share_moe90, non_overlapping_vintage "
    "from marts.acs_place_of_work where geo = 'Ontario city' order by acs_year"
)
if len(A.get("acs_year", [])):
    for i, y in enumerate(A["acs_year"]):
        tag = "" if A["non_overlapping_vintage"][i] else "  (overlaps; do not compare to neighbors)"
        print(f"ACS {A['window_start'][i]}-{y}: {A['share'][i]:.1%} +/- {A['share_moe90'][i]:.1%}{tag}")
else:
    print("ACS not loaded (set CENSUS_API_KEY).")

# %% [markdown]
# ## EDA conclusions to carry into variable selection
# * Model **real log-growth**, not levels (trend -> spurious correlation).
# * Use `sales_tax_total` (triple-flip corrected), never the Bradley-Burns line alone.
# * n is ~20 growth observations -> at most 1-2 predictors (see 02).
# * COVID FYs must be handled explicitly; report results with and without them.
# * Per-capita ratios: description only, not regressors.
