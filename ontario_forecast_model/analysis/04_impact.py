# %% [markdown]
# # 04 - Recommendation impact model: short- and long-term effects
#
# Question: how does each recommendation add to Ontario's fiscal base and local
# employment, by building on the City's existing investments (ONT, Sports Empire,
# Toyota Arena/Capital City, Mills, Downtown, Ontario Ranch)?
#
# Status quo = the baseline forecasts from 02/03. With recommendations = baseline +
# the simulated increment of each recommendation (impact.py), net of City cost.
# Every input carries a source and status. Team assumptions are flagged on every
# chart and listed in impact_inputs_used.csv; replace them with sourced values first.
#
#   python analysis/04_impact.py      (after 02; LODES optional)

# %%
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")

from fiscal_impact_model import config  # noqa: E402
from fiscal_impact_model.db import fetch, load_panel  # noqa: E402
from fiscal_impact_model.modeling import impact, scenarios  # noqa: E402
from fiscal_impact_model.modeling.features import fit_mask  # noqa: E402
from fiscal_impact_model.modeling.model import GrowthForecaster  # noqa: E402
from fiscal_impact_model.reporting.charts import (  # noqa: E402
    compare_fan_chart,
    pathway_chart,
    pct,
    recommendation_lines_chart,
    tornado_chart,
    usd,
    window_bars_chart,
)
from fiscal_impact_model.reporting.export import export_figures, write_csv  # noqa: E402

rng = np.random.default_rng(config.SCENARIO_SEED)
N, H, Q = config.IMPACT_SIMS, config.IMPACT_HORIZON, config.SCENARIO_QUANTILES
WINDOWS = config.IMPACT_WINDOWS
NAMES = impact.REC_NAMES
P = load_panel()
fy = P["fy"]
base_fy = int(fy[-1])
years = np.arange(base_fy + 1, base_fy + 1 + H)
fy_label = lambda v: f"FY{int(v) % 100:02d}"  # noqa: E731
fit_ok = fit_mask(fy, config.COVID_SHOCK_FYS)

A = impact.load_assumptions(config.IMPACT_ASSUMPTIONS)
phases = impact.load_phases(config.IMPACT_PHASES)
anchors = impact.load_anchors(config.ANCHOR_VISITORS)
investments = impact.load_investments(config.CITY_INVESTMENTS)

# %% [markdown]
# ## 1. Official values first
# BLS OEWS medians for the proposal's pathway occupations replace the proposal's
# quoted wages (range = lowest..highest pathway median, mode = their median).

# %%
W = fetch(
    "select year, median_annual_wage from marts.msa_occupation_wages "
    "where median_annual_wage is not null and pathway <> 'benchmark' and pathway not like '%entry%'"
)
if len(W.get("year", [])):
    w = W["median_annual_wage"]
    A["pathway_wage"] = impact.override(
        A["pathway_wage"],
        float(w.min()),
        float(np.median(w)),
        float(w.max()),
        "official",
        f"BLS OEWS {int(W['year'][0])}, Riverside-San Bernardino-Ontario MSA, pathway occupation medians",
    )
print(f"pathway_wage: {A['pathway_wage'].status} ({A['pathway_wage'].source})")

# Room rate from official figures instead of a guess: hotel tax / tax rate = room revenue;
# divided by the city's room supply and an occupancy range, that gives the average rate.
A["adr"] = impact.derive_adr(A, float(P["tot_revenue"][-1]))
print(f"adr: ${A['adr'].low:,.0f} / ${A['adr'].mode:,.0f} / ${A['adr'].high:,.0f}  ({A['adr'].source})")

M = fetch("select metric, value from marts.headline_metrics")
headline = {}
if len(M.get("metric", [])):
    headline = dict(zip(M["metric"].tolist(), M["value"].tolist(), strict=True))

statuses = [a.status for a in A.values()] + [an.overnight.status for an in anchors]
n_assume = sum(s == "assumption" for s in statuses)
FOOT = (
    f"{n_assume} of {len(statuses)} inputs are TEAM ASSUMPTIONS awaiting sources "
    f"(impact_inputs_used.csv). Real FY{base_fy} dollars, net of City cost. Not modeled: "
    "multiplier effects, program effects on the anchors themselves (conservative)."
)

pages = []

# Sanity check on the TOT inputs: implied room-nights vs. actual hotel tax
implied_nights = P["tot_revenue_real"][-1] / (A["tot_rate"].mode * A["adr"].mode)
base_parties = impact.stay1_base_parties(A, anchors)
print(
    f"Implied FY{base_fy} room-nights at mode ADR/rate: {implied_nights:,.0f} "
    "(compare with STR/CVB data when available)"
)
print(
    f"Stay +1 base: {base_parties:,.0f} overnight visitor parties/yr from the anchors = "
    f"{base_parties / implied_nights:.0%} of those room-nights at ONE night each. "
    "At a 2-night average stay, a share above 50% means the anchor inputs claim every hotel "
    "room in the city: lower the visitor counts, overnight shares or dedup factor."
)

# %% [markdown]
# ## 2. What is known: break-even targets, and what blocks an estimate
# Results are reported only when built from sourced inputs. Break-even targets use official tax
# rates, actual tax revenue and the proposal's stated costs only. A projected return for a
# recommendation is reported only once every input behind it has a source; until then the
# script stops here rather than publish numbers built on guesses.

# %%
write_csv(
    [
        {
            "key": k,
            "recommendation": a.recommendation,
            "description": a.description,
            "low": a.low,
            "mode": a.mode,
            "high": a.high,
            "unit": a.unit,
            "status": a.status,
            "source": a.source,
        }
        for k, a in A.items()
    ]
    + [
        {
            "key": an.overnight.key,
            "recommendation": "R2",
            "description": f"{an.name} overnight share",
            "low": an.overnight.low,
            "mode": an.overnight.mode,
            "high": an.overnight.high,
            "unit": "share",
            "status": an.overnight.status,
            "source": an.source,
        }
        for an in anchors
    ],
    config.TABLES_DIR / "impact_inputs_used.csv",
)

gaps = impact.evidence_gaps(A, anchors, config.IMPACT_RECS)
write_csv(gaps, config.TABLES_DIR / "impact_evidence_gaps.csv")
blocked = {r: [g["label"] for g in gaps if g["recommendation"] == NAMES[r]] for r in config.IMPACT_RECS}

tot_fy, st_fy = float(P["tot_revenue"][-1]), float(P["sales_tax_total"][-1])
targets = impact.break_even_targets(A, tot_fy, st_fy)
write_csv(targets, config.TABLES_DIR / "impact_break_even_targets.csv")
# "\\$" keeps matplotlib from reading a pair of dollar signs as math; prints strip it.
kd = lambda v: f"\\${v / 1e3:,.0f}K" if v < 1e6 else f"\\${v / 1e6:,.1f}M"  # noqa: E731
rng_ = lambda lo, hi: f"{kd(lo)}–{kd(hi)}"  # noqa: E731
yr1_lo, yr1_hi = impact.program_cost_range(
    A, [r for r in config.IMPACT_RECS if phases[r][0] == min(s_ for s_, _, _ in phases.values())]
)
yr1_text = f"Year 1 program cost (City + partners, proposal ranges): {rng_(yr1_lo, yr1_hi)}"
print(f"{yr1_text} vs the $500K City cap".replace("\\$", "$"))
for t in targets:
    print(
        f"  {t['recommendation'][:30]}: {rng_(t['value_low'], t['value_high'])} {t['break_even']} "
        f"({t['share_low']:.2%}–{t['share_high']:.2%} of {t['compared_with']})".replace("\\$", "$")
    )

by_rec = {t["recommendation"]: [] for t in targets}
for t in targets:
    by_rec[t["recommendation"]].append(t)
c1 = impact.cost_range(A, "R1")
mk = (A["cost_R2_marketing"].low, A["cost_R2_marketing"].high)
ci = (A["cost_R2_circulator"].low, A["cost_R2_circulator"].high)
c2 = impact.cost_range(A, "R2")
c3 = impact.cost_range(A, "R3")
tax, room = by_rec[NAMES["R2"]]
(sales,) = by_rec[NAMES["R3"]]
pages.append(
    (
        "impact_break_even",
        pathway_chart(
            [
                {
                    "rec": "R1",
                    "name": NAMES["R1"],
                    "chain": f"{rng_(*c1)} a year: staffing and coordination",
                    "kpi": "Not a tax-revenue program: judge it on placements, wages and retention",
                    "short": "—",
                    "long": "—",
                },
                {
                    "rec": "R2",
                    "name": NAMES["R2"],
                    "chain": (
                        f"{rng_(*c2)} a year: marketing and packages {rng_(*mk)} "
                        f"+ evening circulator {rng_(*ci)}"
                    ),
                    "kpi": (
                        f"{rng_(tax['value_low'], tax['value_high'])} more hotel tax a year "
                        f"({rng_(room['value_low'], room['value_high'])} more room revenue)"
                    ),
                    "short": f"{kd(tax['per_100k_city'])} hotel tax",
                    "long": f"{tax['share_low']:.1%}–{tax['share_high']:.1%} of hotel tax",
                },
                {
                    "rec": "R3",
                    "name": NAMES["R3"],
                    "chain": f"{rng_(*c3)} a year: ambassador pilot",
                    "kpi": f"{rng_(sales['value_low'], sales['value_high'])} of net new Downtown sales/yr",
                    "short": f"{kd(sales['per_100k_city'])} new sales",
                    "long": "Needs Downtown's sales base (City's sales-tax consultant)",
                },
            ],
            (
                "Recommendation",
                "Program cost per year\n(proposal, City + partners)",
                "Pays for itself in City\ntax when it adds…",
                "Per \\$100K of\nCity money",
                "Share of today's\ncitywide base",
            ),
            title="What each recommendation must achieve to pay for itself",
            subtitle=(
                "Built only from official tax rates, actual tax revenue and the proposal's stated costs. "
                "The draft doesn't split costs between the City and partners yet; the per-\\$100K column "
                "scales to any City share."
            ),
            source=(
                f"CA State Controller FY{base_fy} (hotel tax {kd(tot_fy)}; Bradley-Burns sales tax "
                f"{kd(st_fy)}); City FY2026-27 budget book (11.75% hotel tax; 1% Bradley-Burns + 1% "
                f"Measure Q, allocation to confirm). Year 1 program cost {rng_(yr1_lo, yr1_hi)} vs the "
                "\\$500K City cap. Projected returns not shown: they need inputs not yet sourced "
                "(impact_evidence_gaps.csv)."
            ),
        ),
    )
)

if any(blocked.values()):
    for r, labels in blocked.items():
        print(
            f"{NAMES[r]}: no projected return reported; {len(labels)} unsourced input(s): {', '.join(labels)}"
        )
    export_figures(pages, config.CHARTS_DIR, suffix="", pdf_name="impact.pdf")
    sys.exit(0)

# %% [markdown]
# ## 2. Status-quo baselines and the simulated increments

# %%


def baseline_real(key: str) -> np.ndarray:
    t = config.FORECAST_TARGETS[key]
    path = config.MODELS_DIR / f"{key}_model.json"
    if not path.exists():
        sys.exit(f"{path.name} missing: run analysis/02_variable_selection.py first")
    model = GrowthForecaster.load(path)
    rho = scenarios.error_persistence(model.backtest_errors)
    g = scenarios.model_growth(model, P, t["growth"], fit_ok, H, N, rng, rho=rho)
    return scenarios.levels_from_growth(float(P[t["level_real"]][-1]), g)


base_tot, base_st = baseline_real("tot"), baseline_real("sales_tax")
res = impact.simulate(
    A, phases, anchors, years, N, rng, baseline_sales_tax=base_st, included=config.IMPACT_RECS
)
SHOWN = {r: NAMES[r] for r in res.included}  # what the charts show
ALL_NAME = f"All recommendations ({', '.join(res.included)})"

# %% [markdown]
# ## 3. Short- vs long-term results per recommendation

# %%
window_rows, summary = [], []
for wname, (a, b) in WINDOWS.items():
    for rec in (*impact.RECS, "ALL"):
        r = None if rec == "ALL" else rec
        p10, p50, p90 = impact.quantiles(impact.window_sum(res.net(r), years, a, b), Q)
        window_rows.append({"rec": rec, "window": wname, "p10": p10, "p50": p50, "p90": p90})
        recs_here = [r] if r else res.included
        measures = {"net_fiscal": res.net(r), "city_cost": sum(res.cost[x] for x in recs_here)}
        measures.update({f"gross_{c}": res.gross(r, c) for c in impact.CHANNELS})
        for m, x in measures.items():
            lo, mid, hi = impact.quantiles(impact.window_sum(x, years, a, b), Q)
            summary.append(
                {
                    "window": wname,
                    "recommendation": NAMES.get(rec, ALL_NAME),
                    "measure": m,
                    "p10": round(lo),
                    "p50": round(mid),
                    "p90": round(hi),
                    "units": f"real FY{base_fy} USD, cumulative",
                }
            )

cum_p50 = np.median(np.cumsum(res.net(), axis=1), axis=0)
be = impact.break_even_year(cum_p50, years)
workers_end = impact.quantiles(res.workers()[:, -1], Q)
residents_end = impact.quantiles(res.residents()[:, -1], Q)
print(f"Median cumulative net turns positive in: {be or 'not within horizon'}")
print(
    f"FY{years[-1]}: +{workers_end[1]:,.0f} residents working in Ontario (P10-P90 "
    f"{workers_end[0]:,.0f}-{workers_end[2]:,.0f}); +{residents_end[1]:,.0f} residents"
)
for m, x in (("added_residents_working_in_ontario", res.workers()), ("added_residents", res.residents())):
    lo, mid, hi = impact.quantiles(x[:, -1], Q)
    summary.append(
        {
            "window": f"FY{years[-1]} level",
            "recommendation": "All recommendations",
            "measure": m,
            "p10": round(lo),
            "p50": round(mid),
            "p90": round(hi),
            "units": "people",
        }
    )


# %% [markdown]
# ## 4. Charts

# %%
# 4a. Pathway (logic model) page
lw_base = headline.get("share_residents_work_local")
lw_text = f" ({pct(lw_base)} today)" if lw_base == lw_base and lw_base is not None else ""


def cell(rec: str, wname: str) -> str:
    r = next(x for x in window_rows if x["rec"] == rec and x["window"] == wname)
    return f"{usd(r['p50'])} ({usd(r['p10'])} to {usd(r['p90'])})"


CHAIN = {
    "R1": (
        "Students -> paid internships with ONT-area employers -> local hires -> residents who live "
        "and work in Ontario -> wages + new households (Ontario Ranch) -> sales + property tax"
    ),
    "R2": (
        "Visitors already coming to ONT, Sports Empire, Toyota Arena, Mills -> Stay +1 adds a night "
        "+ circulator links districts -> hotel tax + visitor spending"
    ),
    "R3": (
        "Downtown ambassadors + clean/safe/green upgrades -> district feels safe and active -> "
        "more evening spending (net of displacement)"
    ),
    "R4": (
        "ONT nonstop Taiwan/Mexico + FTZ 50 + university partners -> employers locate or stay -> "
        "jobs, resident hires, business taxable sales"
    ),
    "SYN": (
        "Career Pathways graduates become the 'structured workforce pipeline' that makes R4 "
        "attraction succeed (R1 strengthens R4)"
    ),
}
KPI = {
    "R1": f"Residents working in Ontario{lw_text}; internship-to-job conversion; starting wage",
    "R2": "Average visitor stay (2.6 days); hotel tax; cross-district visits",
    "R3": "Perceived safety; repeat problem locations; evening foot traffic; district taxable sales",
    "R4": "International partner firms; employer retention; private investment",
    "SYN": "Firms citing the workforce pipeline; pathway hires at attracted firms",
}
wn = list(WINDOWS)
pages.append(
    (
        "impact_pathways",
        pathway_chart(
            [
                {
                    "rec": r,
                    "name": NAMES[r],
                    "chain": CHAIN[r],
                    "kpi": KPI[r],
                    "short": cell(r, wn[0]),
                    "long": cell(r, wn[1]),
                }
                for r in res.included
            ],
            (
                "Recommendation",
                "How it builds on Ontario's investments",
                "Dashboard KPI",
                *(w.replace(" (", "\n(") for w in wn),
            ),
            title="How each recommendation builds Ontario's fiscal base",
            subtitle=(
                "Median cumulative net fiscal impact (P10 to P90) vs the status quo. Short-term results "
                "are small or negative while programs ramp up; long-term value comes from residents "
                "and employers."
            ),
            source=FOOT,
        ),
    )
)

# 4b. Annual net impact by recommendation
pages.append(
    (
        "impact_annual_net",
        recommendation_lines_chart(
            years,
            {r: np.median(res.net(r), axis=0) for r in res.included},
            SHOWN,
            res.net(),
            title="Annual net fiscal impact by recommendation",
            subtitle=(
                f"Median per year; gray band = P10-P90 for all recommendations together. "
                f"Cumulative median turns positive: {be or f'not by FY{years[-1]}'}."
            ),
            source=FOOT,
            fmt=usd,
            x_label=fy_label,
            q=Q,
        ),
    )
)

# 4c. Short vs long term
pages.append(
    (
        "impact_short_vs_long",
        window_bars_chart(
            window_rows,
            wn,
            {**SHOWN, "ALL": ALL_NAME},
            title="Short-term vs long-term net fiscal impact",
            subtitle="Median cumulative net (bar) and P10-P90 range (line), real dollars, after City cost.",
            source=FOOT,
            fmt=usd,
        ),
    )
)

# 4d. Hotel tax: status quo vs with recommendations
prog_tot = base_tot + res.gross(channel="tot")
uplift = np.median(res.gross(channel="tot")[:, -1]) / np.median(base_tot[:, -1])
pages.append(
    (
        "impact_hotel_tax",
        compare_fan_chart(
            years,
            base_tot,
            prog_tot,
            fy,
            P["tot_revenue_real"],
            title="Hotel tax: status quo vs with Stay +1",
            subtitle=(
                f"Stay +1 adds a median {uplift:.1%} to FY{years[-1]} hotel tax. Where bands overlap, the "
                "program effect is smaller than normal year-to-year uncertainty."
            ),
            source="Baseline: CA State Controller TOT, out-of-sample bootstrap. " + FOOT,
            fmt=usd,
            x_label=fy_label,
            q=Q,
            program_label="With Stay +1",
        ),
    )
)

# 4e. Live/work share: status quo vs with Career Pathways + employers
L = fetch(
    "select cy, share_residents_work_local s, employed_residents er from staging.lodes_ontario_cy "
    "where share_residents_work_local is not null order by cy"
)
if len(L.get("cy", [])) >= 12:
    cy = L["cy"]
    h_l = int(years[-1] - cy[-1])
    sq, label, n_err = scenarios.share_paths(cy, L["s"], config.LODES_COVID_YEARS, h_l, N, rng)
    yl = np.arange(cy[-1] + 1, years[-1] + 1)
    add = np.zeros_like(sq)
    idx = np.searchsorted(years, yl)
    ok = (idx < len(years)) & (years[np.minimum(idx, len(years) - 1)] == yl)
    add[:, ok] = res.workers()[:, idx[ok]]
    er = float(L["er"][-1])
    new_resident_workers = add * A["retained_resident_share"].mode
    prog_share = (sq * er + add) / (er + new_resident_workers)
    pages.append(
        (
            "impact_live_work",
            compare_fan_chart(
                yl,
                sq,
                prog_share,
                cy,
                L["s"],
                title="Residents who work in Ontario: status quo vs with recommendations",
                subtitle=(
                    f"Status quo model: {label} ({n_err} out-of-sample errors). Program adds "
                    "residents working locally via Career Pathways, attracted employers and the "
                    "R1->R4 pipeline."
                ),
                source=(
                    "Census LODES 8 (all jobs). Employed residents held at the latest LODES year; "
                    "fiscal years mapped to calendar years. " + FOOT
                ),
                fmt=pct,
                x_label=lambda v: f"{int(v)}",
                q=Q,
                program_label="With recommendations",
            ),
        )
    )
else:
    print("LODES not loaded: skipping the live/work comparison (run ingest for lodes_ontario_flows).")

# 4f. What it leverages: modeled increment by City investment (long term)
long_a, long_b = WINDOWS[wn[1]]
lev = impact.investment_leverage(res, investments, long_a, long_b)
modeled = [x for x in lev if x["p50"] is not None]
unmodeled = [x["investment"] for x in lev if x["p50"] is None]
pages.append(
    (
        "impact_investment_leverage",
        window_bars_chart(
            [
                {"rec": x["investment"], "window": wn[1], "p10": x["p10"], "p50": x["p50"], "p90": x["p90"]}
                for x in modeled
            ],
            [wn[1]],
            {x["investment"]: x["investment"] for x in modeled},
            title="What the recommendations add on top of the City's investments",
            subtitle=(
                "Cumulative gross revenue the recommendations generate through each investment, long term. "
                "Rows overlap (e.g. Ontario Ranch counts property tax from R1 and R4); do not add them up. "
                f"Not quantified yet: {', '.join(unmodeled)}."
            ),
            source=FOOT,
            fmt=usd,
        ),
    )
)

# 4g. What drives the answer: sensitivity (labels come from the `label` column of the inputs file)
base_st_p50 = np.median(base_st, axis=0)[None, :]
torn = impact.tornado(A, phases, anchors, years, base_st_p50, long_a, long_b)
pages.append(
    (
        "impact_sensitivity",
        tornado_chart(
            torn,
            {k: f"{'* ' if a.status == 'assumption' else ''}{a.label}" for k, a in A.items()},
            title="Which inputs move the long-term result most",
            subtitle=(
                "Every input at its single most likely value, swinging one at a time (so the center "
                "differs from the simulation median). * = team assumption: source these first."
            ),
            source=FOOT,
            fmt=usd,
        ),
    )
)

# 4h. Return on City money (benefit-cost) and the "limited investment" each can justify
# Headline = the whole program (start-up years included), in present value at launch.
# The short/long windows only show how the return matures; a late window on its own
# leaves out the start-up years, when the City pays in full and revenue is still ramping.
launch = min(s for s, _, _ in phases.values())
roi_windows = {config.IMPACT_ROI_WINDOW[0]: config.IMPACT_ROI_WINDOW[1], **WINDOWS}
roi = []
for wname, (a, b) in roi_windows.items():
    roi += [{"window": wname, **r} for r in impact.benefit_cost(res, a, b, Q, discount_from=launch)]
yr1 = impact.first_year_city_cost(res, launch, Q)
print(f"Year 1 City cost: {usd(yr1[1])} (P10-P90 {usd(yr1[0])}-{usd(yr1[2])}) vs the $500K cap")
groups = impact.roi_groups(res.included)
for r in roi[: len(groups)]:
    print(
        f"  {r['window']}  {r['group']:36s} ${r['bcr_p50']:.2f} per $1 "
        f"(P10-P90 ${r['bcr_p10']:.2f}-${r['bcr_p90']:.2f}); pays for itself in "
        f"{r['share_sims_break_even']:.0%} of simulations"
    )
# Chart only the groups in the proposal; R4 rows stay in impact_roi.csv.
charted = {c: label for label, c, recs in groups if set(recs) <= set(res.included)}
pages.append(
    (
        "impact_roi",
        window_bars_chart(
            [
                {
                    "rec": r["code"],
                    "window": r["window"],
                    "p10": r["bcr_p10"],
                    "p50": r["bcr_p50"],
                    "p90": r["bcr_p90"],
                }
                for r in roi
                if r["code"] in charted
            ],
            list(roi_windows),
            charted,
            title="Tax revenue returned per $1 of City money",
            subtitle=(
                "Median (bar) and P10-P90 (line), present value. Right of the $1 line, a "
                "recommendation pays for itself in City tax revenue alone. The whole-program panel "
                f"is the headline: it includes the start-up years. Year 1 City cost: {usd(yr1[1])} "
                "(cap $500K)."
            ),
            source=FOOT,
            fmt=lambda v: f"\\${v:.2f}",
            ref_x=1.0,
            ref_label="pays for itself",
        ),
    )
)

# %% [markdown]
# ## 5. Export

# %%
export_figures(pages, config.CHARTS_DIR, suffix="", pdf_name="impact.pdf")
write_csv(summary, config.TABLES_DIR / "impact_summary.csv")
write_csv(lev, config.TABLES_DIR / "impact_investment_leverage.csv")
write_csv(roi, config.TABLES_DIR / "impact_roi.csv")
write_csv(
    [
        {"anchor": k, "p10": round(v[0]), "p50": round(v[1]), "p90": round(v[2])}
        for k, v in (
            (k, impact.quantiles(impact.window_sum(x, years, long_a, long_b), Q))
            for k, x in res.by_anchor.items()
        )
    ],
    config.TABLES_DIR / "impact_stay1_by_anchor.csv",
)
write_csv(
    [
        {"input": k, "net_if_low": round(lo), "net_if_high": round(hi), "net_at_mode": round(b)}
        for k, lo, hi, b in torn
    ],
    config.TABLES_DIR / "impact_sensitivity.csv",
)
