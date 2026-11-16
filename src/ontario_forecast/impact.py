"""Recommendation impact model: what each proposal recommendation ADDS to Ontario's
fiscal base and local-employment outcomes, on top of the status-quo baseline.

Logic model (each arrow is a parameter in data/manual/impact_assumptions.csv):

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
  R4 International &   firms attracted/retained x jobs x additionality -> resident jobs
     employer pipeline (live/work) + wages -> sales tax, and firm taxable sales -> sales tax.
  SYN R1 -> R4         the Career Pathways workforce stock (lagged 1 yr) attracts additional
                       firms: the proposal's "structured workforce pipeline" claim, shown
                       as its own line so it can be judged separately.
  RESIDENCY (R1, R4, SYN)  workers who are new/retained Ontario residents form households
                       (e.g. Ontario Ranch) -> City property tax + household taxable spending.

Every input is a triangular (low, mode, high) range; Monte Carlo propagates them jointly.
Outputs are in real (base-FY) dollars, gross of and net of the City's cost.
Not modeled (stated, not hidden): property tax, multiplier/induced effects, and any
effect of the proposal on the anchors themselves. Omitting these makes the model conservative.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

RECS = ("R1", "R2", "R3", "R4", "SYN")
CHANNELS = ("tot", "sales_tax", "property_tax")
REC_NAMES = {
    "R1": "R1 Career Pathways",
    "R2": "R2 Connected Destination (Stay +1)",
    "R3": "R3 Clean, Safe & Green",
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
    status: str  # official | proposal | assumption
    source: str

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
        out.append(Anchor(r["anchor"], float(r["annual_visitors"]), ovn, r["status"], r["source"]))
    return out


def override(a: Assumption, low: float, mode: float, high: float, status: str, source: str) -> Assumption:
    """Replace a placeholder with an official value (official sources take precedence)."""
    return replace(a, low=low, mode=mode, high=high, status=status, source=source)


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

    def gross(self, rec: str | None = None, channel: str | None = None) -> np.ndarray:
        recs = RECS if rec is None else (rec,)
        chans = CHANNELS if channel is None else (channel,)
        return sum(self.revenue[(r, c)] for r in recs for c in chans)

    def net(self, rec: str | None = None) -> np.ndarray:
        recs = RECS if rec is None else (rec,)
        return self.gross(rec) - sum(self.cost[r] for r in recs)

    def workers(self) -> np.ndarray:
        return sum(self.local_workers.values())

    def residents(self) -> np.ndarray:
        return sum(self.new_residents.values())


def simulate(
    A: dict[str, Assumption],
    phases: dict[str, tuple[int, int, str]],
    anchors: list[Anchor],
    years: np.ndarray,
    n: int,
    rng: np.random.Generator,
    baseline_sales_tax: np.ndarray | None = None,
) -> ImpactResult:
    """Monte Carlo of program increments. baseline_sales_tax: (n, T) or (1, T) real $."""
    years = np.asarray(years)
    T = len(years)
    v = {k: a.draw(n, rng)[:, None] for k, a in A.items()}  # (n, 1) each
    r = {rec: ramp(years, s, f)[None, :] for rec, (s, f, _) in phases.items()}
    active = {rec: (r[rec] > 0).astype(float) for rec in r}
    rate = v["local_sales_tax_rate"]
    zeros = np.zeros((n, T))
    resident_spend = v["taxable_spend_share"] * v["local_capture"] * rate  # $ tax per $ of wages

    # R1 Career Pathways --------------------------------------------------------
    hires = (
        v["r1_interns_full"] * r["R1"] * v["r1_conversion"] * v["r1_additionality"] * v["r1_resident_share"]
    )
    r1_workers = _stock(np.broadcast_to(hires, (n, T)).copy(), v["worker_attrition"])
    r1_tax = r1_workers * v["pathway_wage"] * resident_spend

    # R2 Connected Destination (Stay +1 on top of the City's anchors) -----------
    growth = (1 + v["visitor_growth"]) ** np.arange(T)[None, :]
    r2_tot, r2_st, by_anchor = zeros.copy(), zeros.copy(), {}
    for an in anchors:
        overnight = an.overnight.draw(n, rng)[:, None]
        parties = an.visitors * growth * overnight * v["dedup_factor"] / v["persons_per_room"]
        nights = parties * v["stay1_uptake"] * v["r2_additionality"] * r["R2"]  # +1 night per party
        tot = nights * v["adr"] * v["tot_rate"]
        st = nights * v["persons_per_room"] * v["visitor_daily_taxable_spend"] * rate
        by_anchor[an.name] = tot + st
        r2_tot += tot
        r2_st += st

    # R3 Clean, Safe & Green districts ------------------------------------------
    base_st = zeros if baseline_sales_tax is None else np.broadcast_to(baseline_sales_tax, (n, T))
    r3_st = (
        base_st * v["downtown_share_of_sales"] * v["district_sales_uplift"] * v["r3_additionality"] * r["R3"]
    )

    # R4 International & employer pipeline --------------------------------------
    def firm_channel(jobs_inflow):
        jobs = _stock(np.broadcast_to(jobs_inflow, (n, T)).copy(), v["worker_attrition"])
        workers = jobs * v["r4_resident_share"]
        st = workers * v["pathway_wage"] * resident_spend + jobs * v["r4_taxable_sales_per_job"] * rate
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
        cost={rec: (v[f"cost_{rec}"] * active[rec] if rec in active else zeros) for rec in RECS},
        local_workers=workers,
        new_residents={k: r_[0] for k, r_ in res.items()},
        by_anchor=by_anchor,
    )


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
        out.append((k, lo, hi, base))
    return sorted(out, key=lambda t: -abs(t[2] - t[1]))
