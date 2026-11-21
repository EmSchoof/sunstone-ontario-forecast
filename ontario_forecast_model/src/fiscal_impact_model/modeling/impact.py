"""Recommendation impact model: what each proposal recommendation ADDS to Ontario's
fiscal base and local-employment outcomes, on top of the status-quo baseline.

Logic model (each arrow is a parameter in data/impact_assumptions.csv):

  R1 Career Pathways   interns -> conversions x additionality x resident share -> stock of
                       residents working in Ontario (with attrition) -> wages -> local
                       taxable spending -> sales tax.  Also raises the live/work share.
  R2 Connected Dest.   anchor visits (ONT, Sports Empire, Arena, Mills) x overnight share
                       x dedup x Stay +1 uptake -> added room-nights -> TOT;
                       added visitor-days -> taxable spending -> sales tax.
                       LEVERAGE: the payoff scales with the City's existing anchors, so
                       anchor growth (airport, Sports Empire) multiplies it.
  R3 Clean/Safe/Green  downtown share of taxable sales x district uplift x additionality
                       -> sales tax (applied to the simulated baseline sales tax).
  LOCAL TAX RATE       spending made in person inside Ontario earns the City the 1%
                       Bradley-Burns share PLUS the 1% Measure Q transactions tax (2022).
                       Business-to-business sales of attracted firms earn Bradley-Burns only
                       (Measure Q follows the delivery address, usually outside the city).
  R4 International &   firms attracted/retained x jobs x additionality -> resident jobs
     employer pipeline (live/work) + wages -> sales tax, and firm taxable sales -> sales tax.
  SYN R1 -> R4         the Career Pathways workforce stock (lagged 1 yr) attracts additional
                       firms: the proposal's "structured workforce pipeline" claim, shown
                       as its own line so it can be judged separately.
  RESIDENCY (R1, R4, SYN)  workers who are new/retained Ontario residents form households
                       (e.g. Ontario Ranch) -> City property tax + household taxable spending.
  COUNTERFACTUAL       a placed worker who would have lived in Ontario anyway already spent
                       here: only `stayer_spending_gain` of their local spending is new.
                       Workers who are new/retained residents count in full.

Every input is a triangular (low, mode, high) range; Monte Carlo propagates them jointly.
Outputs are in real (base-FY) dollars, gross of and net of the City's cost. Return on
investment is reported in present value (real `discount_rate`) over the whole program.
Not modeled (stated, not hidden): multiplier/induced effects, spending by non-resident
workers, and any effect of the proposal on the anchors themselves (conservative). Also not
modeled, and NOT conservative: housing supply. A new resident household only adds property
tax and population if the home would otherwise be empty or unbuilt.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

RECS = ("R1", "R2", "R3", "R4", "SYN")
CHANNELS = ("tot", "sales_tax", "property_tax")
REC_NAMES = {
    # Names as the proposal uses them (shortened where a chart needs it).
    "R1": "R1 Career Pathways & Employer Consortium",
    "R2": "R2 Connected Destination Economy",
    "R3": "R3 Clean, Safe & Green Entertainment Districts",
    "R4": "R4 International & employers",
    "SYN": "R1→R4 workforce-led attraction",
}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Assumption:
    key: str
    recommendation: str
    description: str
    low: float
    mode: float
    high: float
    unit: str
    status: str  # official | published (peer-reviewed or industry benchmark) | proposal | assumption
    source: str
    label: str = ""  # short name for charts; falls back to the description

    def draw(self, n: int, rng: np.random.Generator) -> np.ndarray:
        if self.low == self.high:
            return np.full(n, self.mode)
        return rng.triangular(self.low, self.mode, self.high, n)

    def fixed(self, value: float | None = None) -> Assumption:
        """Collapse to a single value (mode by default), for deterministic runs."""
        v = self.mode if value is None else value
        return replace(self, low=v, mode=v, high=v)


@dataclass(frozen=True)
class Anchor:
    name: str
    visitors: float
    overnight: Assumption  # share of visitors staying overnight in Ontario
    status: str
    source: str
    # Share of the venue's count that is one inbound trip. Airports report enplaned +
    # deplaned passengers, so each traveler is counted twice (ONT: about half are arrivals).
    arrival_share: float = 1.0


def _rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_assumptions(path: Path) -> dict[str, Assumption]:
    out = {}
    for r in _rows(path):
        a = Assumption(
            r["key"],
            r["recommendation"],
            r["description"],
            float(r["low"]),
            float(r["mode"]),
            float(r["high"]),
            r["unit"],
            r["status"],
            r["source"],
            r.get("label") or r["description"],
        )
        if not a.low <= a.mode <= a.high:
            raise ValueError(f"{a.key}: need low <= mode <= high")
        out[a.key] = a
    return out


def load_phases(path: Path) -> dict[str, tuple[int, int, str]]:
    return {r["recommendation"]: (int(r["start_fy"]), int(r["full_fy"]), r["name"]) for r in _rows(path)}


def load_investments(path: Path) -> list[dict]:
    return _rows(path)


def load_anchors(path: Path) -> list[Anchor]:
    out = []
    for r in _rows(path):
        ovn = Assumption(
            f"overnight_{r['anchor']}",
            "R2",
            "overnight share",
            float(r["overnight_low"]),
            float(r["overnight_mode"]),
            float(r["overnight_high"]),
            "share",
            "assumption",
            r["source"],
        )
        share = float(r.get("arrival_share") or 1.0)
        if not 0 < share <= 1:
            raise ValueError(f"{r['anchor']}: arrival_share must be in (0, 1]")
        out.append(Anchor(r["anchor"], float(r["annual_visitors"]), ovn, r["status"], r["source"], share))
    return out


def override(a: Assumption, low: float, mode: float, high: float, status: str, source: str) -> Assumption:
    """Replace a placeholder with an official value (official sources take precedence)."""
    return replace(a, low=low, mode=mode, high=high, status=status, source=source)


def derive_adr(A: dict[str, Assumption], tot_revenue: float) -> Assumption:
    """Average daily room rate implied by official figures and an occupancy range.

    room revenue = hotel tax / tax rate;  revenue per available room-night = room revenue /
    (rooms x 365);  average rate = that / occupancy.  Higher occupancy means the same revenue
    was earned over more nights, so a lower rate: the range is inverted.
    """
    revpar = tot_revenue / A["tot_rate"].mode / (A["hotel_rooms"].mode * 365)
    occ = A["hotel_occupancy"]
    return override(
        A["adr"],
        revpar / occ.high,
        revpar / occ.mode,
        revpar / occ.low,
        "assumption",
        f"Derived: hotel tax ${tot_revenue:,.0f} / {A['tot_rate'].mode:.2%} rate / "
        f"{A['hotel_rooms'].mode:,.0f} rooms = ${revpar:,.2f} per available room-night, at "
        f"{occ.low:.0%}-{occ.high:.0%} occupancy (occupancy is the TEAM ASSUMPTION)",
    )


def ramp(years: np.ndarray, start: int, full: int) -> np.ndarray:
    """Program scale by year: 0 before start, rising linearly to 1 at `full`."""
    y = np.asarray(years, float)
    if full <= start:
        return (y >= start).astype(float)
    return np.clip((y - start + 1) / (full - start + 1), 0.0, 1.0)


def _stock(inflow: np.ndarray, attrition: np.ndarray) -> np.ndarray:
    """Cumulative stock with attrition: s_t = s_{t-1} * (1 - a) + inflow_t."""
    s = np.zeros_like(inflow)
    for t in range(inflow.shape[1]):
        s[:, t] = (s[:, t - 1] * (1 - attrition[:, 0]) if t else 0.0) + inflow[:, t]
    return s


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
@dataclass
class ImpactResult:
    years: np.ndarray
    revenue: dict[tuple[str, str], np.ndarray]  # (rec, channel) -> (n, T) real $
    cost: dict[str, np.ndarray]  # rec -> (n, T)
    local_workers: dict[str, np.ndarray]  # rec -> (n, T) added residents working in Ontario
    new_residents: dict[str, np.ndarray]  # rec -> (n, T) added Ontario residents (household members)
    by_anchor: dict[str, np.ndarray] = field(default_factory=dict)  # R2 revenue by anchor
    discount_rate: np.ndarray | None = None  # (n, 1) real annual rate, drawn per simulation
    # Recommendations in the proposal: totals (gross/net/workers with no rec given) cover only
    # these. Others are still simulated and reported on their own, outside the headline.
    included: tuple[str, ...] = RECS

    def pv_factor(self, base_year: int) -> np.ndarray:
        """(n, T) present-value factors: 1 in `base_year`, (1 + d)^-k for k years later."""
        k = np.clip(self.years - base_year, 0, None)[None, :]
        d = np.zeros((1, 1)) if self.discount_rate is None else self.discount_rate
        return (1.0 + d) ** -k

    def gross(self, rec: str | None = None, channel: str | None = None) -> np.ndarray:
        recs = self.included if rec is None else (rec,)
        chans = CHANNELS if channel is None else (channel,)
        return sum(self.revenue[(r, c)] for r in recs for c in chans)

    def net(self, rec: str | None = None) -> np.ndarray:
        recs = self.included if rec is None else (rec,)
        return self.gross(rec) - sum(self.cost[r] for r in recs)

    def workers(self) -> np.ndarray:
        return sum(self.local_workers[r] for r in self.included)

    def residents(self) -> np.ndarray:
        return sum(self.new_residents[r] for r in self.included)


def simulate(
    A: dict[str, Assumption],
    phases: dict[str, tuple[int, int, str]],
    anchors: list[Anchor],
    years: np.ndarray,
    n: int,
    rng: np.random.Generator,
    baseline_sales_tax: np.ndarray | None = None,
    included: tuple[str, ...] = RECS,
) -> ImpactResult:
    """Monte Carlo of program increments. baseline_sales_tax: (n, T) or (1, T) real $.

    City cost of a recommendation = the sum of its cost lines: `cost_<rec>` and any
    `cost_<rec>_<part>` (e.g. R2's marketing and circulator shares).
    """
    years = np.asarray(years)
    T = len(years)
    v = {k: a.draw(n, rng)[:, None] for k, a in A.items()}  # (n, 1) each
    r = {rec: ramp(years, s, f)[None, :] for rec, (s, f, _) in phases.items()}
    active = {rec: (r[rec] > 0).astype(float) for rec in r}
    bb = v["local_sales_tax_rate"]  # Bradley-Burns 1%: follows the point of sale
    rate = bb + v["measure_q_rate"]  # in-person spending inside Ontario also pays Measure Q
    zeros = np.zeros((n, T))
    resident_spend = v["taxable_spend_share"] * v["local_capture"] * rate  # $ tax per $ of wages
    # Counterfactual: residents who would live here anyway already spend here.
    kept = v["retained_resident_share"]
    new_spend = kept + (1 - kept) * v["stayer_spending_gain"]

    # R1 Career Pathways --------------------------------------------------------
    hires = (
        v["r1_interns_full"] * r["R1"] * v["r1_conversion"] * v["r1_additionality"] * v["r1_resident_share"]
    )
    r1_workers = _stock(np.broadcast_to(hires, (n, T)).copy(), v["worker_attrition"])
    r1_tax = r1_workers * v["pathway_wage"] * resident_spend * new_spend

    # R2 Connected Destination (Stay +1 on top of the City's anchors) -----------
    growth = (1 + v["visitor_growth"]) ** np.arange(T)[None, :]
    r2_tot, r2_st, by_anchor = zeros.copy(), zeros.copy(), {}
    for an in anchors:
        overnight = an.overnight.draw(n, rng)[:, None]
        trips = an.visitors * an.arrival_share * growth  # inbound visitor trips
        parties = trips * overnight * v["dedup_factor"] / v["persons_per_room"]
        nights = parties * v["stay1_uptake"] * v["r2_additionality"] * r["R2"]  # +1 night per party
        tot = nights * v["adr"] * v["tot_rate"]
        st = nights * v["persons_per_room"] * v["visitor_daily_taxable_spend"] * rate
        by_anchor[an.name] = tot + st
        r2_tot += tot
        r2_st += st

    # R3 Clean, Safe & Green districts ------------------------------------------
    base_st = zeros if baseline_sales_tax is None else np.broadcast_to(baseline_sales_tax, (n, T))
    # The baseline is Bradley-Burns revenue; district sales are in person, so scale to the full rate.
    r3_st = (
        (base_st * rate / bb)
        * v["downtown_share_of_sales"]
        * v["district_sales_uplift"]
        * v["r3_additionality"]
        * r["R3"]
    )

    # R4 International & employer pipeline --------------------------------------
    def firm_channel(jobs_inflow):
        jobs = _stock(np.broadcast_to(jobs_inflow, (n, T)).copy(), v["worker_attrition"])
        workers = jobs * v["r4_resident_share"]
        st = (
            workers * v["pathway_wage"] * resident_spend * new_spend
            + jobs * v["r4_taxable_sales_per_job"] * bb
        )
        return workers, st

    r4_jobs_in = v["r4_firms_per_year"] * v["r4_jobs_per_firm"] * v["r4_additionality"] * r["R4"]
    r4_workers, r4_st = firm_channel(r4_jobs_in)

    # SYN: Career Pathways stock (lagged one year) makes R4 attraction work better --
    r1_lag = np.concatenate([np.zeros((n, 1)), r1_workers[:, :-1]], axis=1)
    syn_firms = v["r1_to_r4_synergy"] * r1_lag / 100 * (r["R4"] > 0)
    syn_workers, syn_st = firm_channel(syn_firms * v["r4_jobs_per_firm"])

    # RESIDENCY: new/retained resident households -> property tax + household spending --
    def residency(workers):
        households = workers * v["retained_resident_share"]
        prop = households * v["city_property_tax_per_household"]
        hh_st = households * (v["persons_per_household"] - 1) * v["nonworker_spend_per_resident"] * rate
        return households * v["persons_per_household"], prop, hh_st

    workers = {"R1": r1_workers, "R2": zeros, "R3": zeros, "R4": r4_workers, "SYN": syn_workers}
    res = {k: residency(w) for k, w in workers.items()}
    sales = {"R1": r1_tax, "R2": r2_st, "R3": r3_st, "R4": r4_st, "SYN": syn_st}
    revenue = {}
    for rec in RECS:
        revenue[(rec, "tot")] = r2_tot if rec == "R2" else zeros
        revenue[(rec, "sales_tax")] = sales[rec] + res[rec][2]
        revenue[(rec, "property_tax")] = res[rec][1]

    return ImpactResult(
        years=years,
        revenue=revenue,
        cost={rec: _cost(v, rec) * active[rec] if rec in active else zeros for rec in RECS},
        local_workers=workers,
        new_residents={k: r_[0] for k, r_ in res.items()},
        by_anchor=by_anchor,
        discount_rate=v["discount_rate"] if "discount_rate" in v else None,
        included=tuple(included),
    )


def _cost_keys(keys, rec: str) -> list[str]:
    return [k for k in keys if k == f"cost_{rec}" or k.startswith(f"cost_{rec}_")]


def _cost(v: dict[str, np.ndarray], rec: str) -> np.ndarray:
    keys = _cost_keys(v, rec)
    return sum(v[k] for k in keys) if keys else np.zeros((1, 1))


def annual_city_cost(A: dict[str, Assumption], rec: str) -> float:
    """City cost per year once a recommendation runs, all inputs at their most likely value."""
    return float(sum(A[k].mode for k in _cost_keys(A, rec)))


KNOWN = ("official", "published", "proposal")  # statuses with a source behind them

# Inputs each recommendation's simulated result depends on. A result is reported only when
# every one of these has a source (see `evidence_gaps`); otherwise it would be a guess.
INPUTS_BY_REC = {
    "R1": (
        "r1_interns_full", "r1_conversion", "r1_resident_share", "r1_additionality",
        "worker_attrition", "pathway_wage", "taxable_spend_share", "local_capture",
        "stayer_spending_gain", "retained_resident_share", "persons_per_household",
        "city_property_tax_per_household", "nonworker_spend_per_resident",
        "local_sales_tax_rate", "measure_q_rate", "discount_rate",
    ),
    "R2": (
        "visitor_growth", "dedup_factor", "stay1_uptake", "persons_per_room", "hotel_occupancy",
        "tot_rate", "visitor_daily_taxable_spend", "r2_additionality",
        "local_sales_tax_rate", "measure_q_rate", "discount_rate",
    ),
    "R3": (
        "downtown_share_of_sales", "district_sales_uplift", "r3_additionality",
        "local_sales_tax_rate", "measure_q_rate", "discount_rate",
    ),
    "R4": (
        "r4_firms_per_year", "r4_jobs_per_firm", "r4_resident_share", "r4_additionality",
        "r4_taxable_sales_per_job", "r1_to_r4_synergy", "worker_attrition", "pathway_wage",
        "taxable_spend_share", "local_capture", "stayer_spending_gain", "retained_resident_share",
        "local_sales_tax_rate", "measure_q_rate", "discount_rate",
    ),
}  # fmt: skip


def evidence_gaps(A: dict[str, Assumption], anchors: list[Anchor], recs: tuple[str, ...]) -> list[dict]:
    """Every unsourced input standing between a recommendation and a reportable estimate."""
    out = []
    for rec in recs:
        keys = [*INPUTS_BY_REC[rec], *_cost_keys(A, rec)]
        items = [(k, A[k]) for k in keys if k in A]
        if rec == "R2":
            items += [
                (an.overnight.key, replace(an.overnight, label=f"{an.name} overnight share"))
                for an in anchors
            ]
        for k, a in items:
            if a.status not in KNOWN:
                out.append(
                    {
                        "recommendation": REC_NAMES[rec],
                        "input": k,
                        "label": a.label,
                        "status": a.status,
                        "where_to_source": a.source,
                    }
                )
    return out


def cost_range(A: dict[str, Assumption], rec: str) -> tuple[float, float]:
    """(low, high) program cost per year from the stated ranges, no midpoint."""
    keys = _cost_keys(A, rec)
    return float(sum(A[k].low for k in keys)), float(sum(A[k].high for k in keys))


def break_even_targets(A: dict[str, Assumption], tot_revenue: float, sales_tax_bb: float) -> list[dict]:
    """What R2 and R3 must add each year for their own tax revenue to cover their cost.

    Uses only official tax rates, actual tax revenue and the proposal's stated cost ranges, so
    no unsourced input enters. Full program cost is used because the draft does not split it
    between the City and partners; `per_100k_city` scales the target to any City share.
    Steady-state, undiscounted. R2 counts hotel tax only (its visitor sales tax would need an
    unsourced spend-per-visitor figure), so its target is conservative.
    """
    used = ("local_sales_tax_rate", "measure_q_rate", "tot_rate", *_cost_keys(A, "R2"), *_cost_keys(A, "R3"))
    unsourced = [k for k in used if A[k].status not in KNOWN]
    if unsourced:
        raise ValueError(f"break-even targets must use sourced inputs only: {unsourced}")
    bb, tot = A["local_sales_tax_rate"].mode, A["tot_rate"].mode
    rate = bb + A["measure_q_rate"].mode
    taxable_sales = sales_tax_bb / bb

    def row(rec, target, lo, hi, per, baseline, compared, inputs):
        c_lo, c_hi = cost_range(A, rec)
        return {
            "recommendation": REC_NAMES[rec],
            "program_cost_low": c_lo,
            "program_cost_high": c_hi,
            "break_even": target,
            "value_low": lo,
            "value_high": hi,
            "per_100k_city": per,
            "compared_with": compared,
            "baseline": baseline,
            "share_low": lo / baseline,
            "share_high": hi / baseline,
            "inputs": inputs,
        }

    r2_lo, r2_hi = cost_range(A, "R2")
    r3_lo, r3_hi = cost_range(A, "R3")
    return [
        row("R2", "added hotel tax per year", r2_lo, r2_hi, 100_000, tot_revenue,
            "citywide hotel tax (latest fiscal year)",
            "Proposal cost range; hotel tax (State Controller)"),
        row("R2", "added hotel room revenue per year", r2_lo / tot, r2_hi / tot, 100_000 / tot,
            tot_revenue / tot, "citywide hotel room revenue (hotel tax / 11.75%)",
            "Proposal cost range; 11.75% hotel tax rate (Municipal Code 3-6.03)"),
        row("R3", "net new in-person taxable sales per year (after displacement)", r3_lo / rate,
            r3_hi / rate, 100_000 / rate, taxable_sales, "citywide taxable sales (Bradley-Burns base)",
            "Proposal cost range; 1% Bradley-Burns + 1% Measure Q (allocation to confirm with Finance)"),
    ]  # fmt: skip


def program_cost_range(A: dict[str, Assumption], recs) -> tuple[float, float]:
    """(low, high) combined program cost per year for the given recommendations."""
    lows, highs = zip(*(cost_range(A, r) for r in recs), strict=True)
    return float(sum(lows)), float(sum(highs))


def stay1_base_parties(A: dict[str, Assumption], anchors: list[Anchor]) -> float:
    """Overnight visitor parties per year the Stay +1 offer is applied to (all inputs at mode).

    Sanity check: compare with the room-nights implied by actual hotel tax. If the parties
    alone (times a typical stay length) exceed the city's room-nights, the visitor counts,
    overnight shares or dedup factor are too high.
    """
    per_party = A["dedup_factor"].mode / A["persons_per_room"].mode
    return float(sum(an.visitors * an.arrival_share * an.overnight.mode for an in anchors) * per_party)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------
def window_sum(x: np.ndarray, years: np.ndarray, first: int, last: int) -> np.ndarray:
    m = (years >= first) & (years <= last)
    return x[:, m].sum(axis=1)


def quantiles(x: np.ndarray, q=(0.10, 0.50, 0.90)) -> tuple[float, ...]:
    return tuple(float(v) for v in np.quantile(x, q))


def break_even_year(net_cum_p50: np.ndarray, years: np.ndarray) -> int | None:
    """First year the cumulative median net is > 0, counting only from the first year
    the programs change anything (before that the cumulative net is trivially 0)."""
    started = np.flatnonzero(net_cum_p50 != 0)
    if not len(started):
        return None
    hit = np.flatnonzero((net_cum_p50 > 0) & (np.arange(len(years)) >= started[0]))
    return int(years[hit[0]]) if len(hit) else None


def roi_groups(included: tuple[str, ...] = RECS) -> list[tuple[str, str, tuple[str, ...]]]:
    """(label, short code, recs) for each return-on-investment group.

    R4 is grouped with the R1->R4 synergy, which has no cost of its own. When R4 is not in
    the proposal its groups are still reported, labeled as such, and left out of "All".
    """
    out = [(REC_NAMES[r], r, (r,)) for r in ("R1", "R2", "R3")]
    tag = "" if "R4" in included else " (not in proposal)"
    out.append((f"R4 Employers (+ R1→R4 link){tag}", "R4", ("R4", "SYN")))
    # The link's revenue exists only because R1 is funded, so judge the pair with both costs.
    out.append((f"R1 + R4 together (shared cost){tag}", "R1+R4", ("R1", "R4", "SYN")))
    out.append(("All recommendations", "ALL", tuple(included)))
    return out


ROI_GROUPS = {label: recs for label, _, recs in roi_groups()}


def benefit_cost(
    result: ImpactResult,
    first: int,
    last: int,
    q=(0.10, 0.50, 0.90),
    discount_from: int | None = None,
) -> list[dict]:
    """Return on City money per recommendation over [first, last] (real dollars).

    discount_from: if given, revenue and cost are converted to present value in that year
    with each simulation's real discount rate (later dollars count less). None = undiscounted.

    * bcr: tax revenue returned per $1 of City cost, per simulation (1.0 = pays for itself).
    * budgeted_annual_cost: City cost per year the program runs (the proposal's ranges).
    * breakeven_annual_cost: the most the City could spend per year and still be repaid by
      the program's own tax revenue. That is the "limited investment" answer: a City share above
      it has to be justified by non-fiscal outcomes or covered by partners.
    R4 is grouped with the R1->R4 synergy, which has no cost of its own; because that
    synergy is paid for by R1, the "R1 + R4 together" group is the fair test of the pair.
    """
    years = result.years
    m = (years >= first) & (years <= last)
    pv = 1.0 if discount_from is None else result.pv_factor(discount_from)
    out = []
    for label, code, recs in roi_groups(result.included):
        gross = sum(window_sum(result.gross(r) * pv, years, first, last) for r in recs)
        cost_t = (sum(result.cost[r] for r in recs) * pv)[:, m]
        cost = cost_t.sum(axis=1)
        active_years = max(int((cost_t[0] > 0).sum()), 1)  # same phase pattern in every simulation
        ok = cost > 0
        bcr = np.where(ok, gross / np.where(ok, cost, 1.0), np.nan)
        row = {
            "group": label,
            "code": code,
            "first_fy": first,
            "last_fy": last,
            "present_value": discount_from is not None,
            "years_with_cost": active_years,
        }
        row.update(
            zip(
                ("bcr_p10", "bcr_p50", "bcr_p90"),
                np.nanquantile(bcr, q) if ok.any() else (np.nan,) * 3,
                strict=True,
            )
        )
        row["budgeted_annual_cost_p50"] = float(np.median(cost)) / active_years
        row["breakeven_annual_cost_p50"] = float(np.median(gross)) / active_years
        # Share of modeled scenarios, not a real-world probability (input ranges are mostly team estimates)
        row["share_sims_break_even"] = float(np.mean(gross >= cost)) if ok.any() else np.nan
        out.append(row)
    return out


def first_year_city_cost(result: ImpactResult, fy: int, q=(0.10, 0.50, 0.90)) -> tuple[float, ...]:
    """City cost in a single fiscal year (checks the proposal's $500K Year 1 cap)."""
    i = int(np.flatnonzero(result.years == fy)[0])
    return quantiles(sum(result.cost[r][:, i] for r in result.included), q)


def investment_leverage(result: ImpactResult, investments: list[dict], first: int, last: int) -> list[dict]:
    """Cumulative modeled increment (P10/P50/P90, real $) that each City investment enables.

    `modeled_as` tokens: anchor:<name> (R2 revenue at that anchor), rec:<R> (a recommendation's
    gross revenue), channel:<c> (a revenue channel across all recommendations), not_modeled:<why>.
    An investment linked to several tokens sums them (tokens never overlap by construction:
    the ONT anchor covers R2 visitors only; rec:R4/SYN cover business effects).
    """
    out = []
    for inv in investments:
        total, notes = None, []
        for tok in inv["modeled_as"].split(";"):
            kind, _, name = tok.partition(":")
            part = None
            if kind == "anchor" and name in result.by_anchor:
                part = result.by_anchor[name]
            elif kind == "rec" and name not in result.included:
                notes.append(f"{name} not in proposal")
            elif kind == "rec":
                part = result.gross(name)
            elif kind == "channel":
                part = result.gross(channel=name)
            else:
                notes.append(name or tok)
            if part is not None:
                total = part if total is None else total + part
        row = {
            "investment": inv["investment"],
            "recommendations": inv["recommendations"],
            "dashboard_kpi": inv["dashboard_kpi"],
            "note": "; ".join(notes),
        }
        if total is None:
            row.update(p10=None, p50=None, p90=None)
        else:
            row.update(
                zip(
                    ("p10", "p50", "p90"),
                    quantiles(window_sum(total, result.years, first, last)),
                    strict=True,
                )
            )
        out.append(row)
    return out


def tornado(
    A: dict[str, Assumption],
    phases,
    anchors,
    years,
    baseline_sales_tax_p50: np.ndarray,
    first: int,
    last: int,
) -> list[tuple[str, float, float, float]]:
    """One-at-a-time sensitivity of cumulative net impact (all inputs at mode, swing one).

    Returns (key, value_at_low, value_at_high, value_at_mode), largest swing first.
    """
    rng = np.random.default_rng(0)
    fixed = {k: a.fixed() for k, a in A.items()}
    anchors_f = [replace(an, overnight=an.overnight.fixed()) for an in anchors]

    def run(assump):
        res = simulate(assump, phases, anchors_f, years, 1, rng, baseline_sales_tax_p50)
        return float(window_sum(res.net(), years, first, last)[0])

    base = run(fixed)
    out = []
    for k, a in A.items():
        if a.low == a.high:
            continue
        lo = run({**fixed, k: a.fixed(a.low)})
        hi = run({**fixed, k: a.fixed(a.high)})
        if lo == hi:  # no effect on the undiscounted net (e.g. the discount rate)
            continue
        out.append((k, lo, hi, base))
    return sorted(out, key=lambda t: -abs(t[2] - t[1]))
