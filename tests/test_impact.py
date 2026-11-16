"""Impact model tests: mechanics on the real input files, deterministic (all inputs at mode)."""

from dataclasses import replace

import numpy as np
import pytest

from ontario_forecast import config
from ontario_forecast.modeling import impact

YEARS = np.arange(2026, 2037)


@pytest.fixture(scope="module")
def inputs():
    A = impact.load_assumptions(config.IMPACT_ASSUMPTIONS)
    phases = impact.load_phases(config.IMPACT_PHASES)
    anchors = impact.load_anchors(config.ANCHOR_VISITORS)
    fixed = {k: a.fixed() for k, a in A.items()}
    anchors_f = [replace(an, overnight=an.overnight.fixed()) for an in anchors]
    return A, fixed, phases, anchors_f


def run(fixed, phases, anchors, **overrides):
    A = {**fixed, **{k: fixed[k].fixed(v) for k, v in overrides.items()}}
    base_st = np.full((1, len(YEARS)), 140e6)
    return impact.simulate(A, phases, anchors, YEARS, 1, np.random.default_rng(0), base_st)


def test_input_files_are_complete_and_valid(inputs):
    A, _, phases, anchors = inputs
    assert set(phases) == {"R1", "R2", "R3", "R4"}
    assert {a.status for a in A.values()} <= {"official", "proposal", "assumption"}
    assert all(a.source for a in A.values())  # every number has a source line
    assert all(len(a.label) <= 45 for a in A.values())  # short enough for one chart line
    assert len(anchors) >= 4


def test_break_even_ignores_pre_program_zeros():
    yrs = np.arange(2026, 2031)
    assert impact.break_even_year(np.array([0.0, -5, -3, 1, 4]), yrs) == 2029
    assert impact.break_even_year(np.array([0.0, -5, -6, -7, -8]), yrs) is None


def test_ramp():
    assert np.allclose(impact.ramp(np.arange(2026, 2031), 2027, 2029), [0, 1 / 3, 2 / 3, 1, 1])


def test_stock_with_attrition():
    s = impact._stock(np.array([[10.0, 10.0, 0.0]]), np.array([[0.5]]))
    assert np.allclose(s, [[10, 15, 7.5]])


def test_nothing_happens_before_programs_start(inputs):
    _, fixed, phases, anchors = inputs
    res = run(fixed, phases, anchors)
    assert res.gross()[0, 0] == 0 and res.net()[0, 0] == 0  # FY2026: no program yet


def test_zero_uptake_means_no_stay1_revenue(inputs):
    _, fixed, phases, anchors = inputs
    res = run(fixed, phases, anchors, stay1_uptake=0.0)
    assert res.gross("R2").sum() == 0


def test_additionality_scales_linearly(inputs):
    _, fixed, phases, anchors = inputs
    full = run(fixed, phases, anchors, r2_additionality=1.0).gross("R2", "tot")
    half = run(fixed, phases, anchors, r2_additionality=0.5).gross("R2", "tot")
    assert np.allclose(half, full / 2)


def test_synergy_requires_r1_workforce_and_active_r4(inputs):
    _, fixed, phases, anchors = inputs
    none = run(fixed, phases, anchors, r1_to_r4_synergy=0.0)
    assert none.gross("SYN").sum() == 0
    some = run(fixed, phases, anchors, r1_to_r4_synergy=1.0)
    r4_start = phases["R4"][0]
    assert some.local_workers["SYN"][0, YEARS < r4_start].sum() == 0
    assert some.local_workers["SYN"][0, -1] > 0


def test_residency_creates_property_tax_only_from_worker_programs(inputs):
    _, fixed, phases, anchors = inputs
    res = run(fixed, phases, anchors)
    assert res.gross("R1", "property_tax").sum() > 0
    assert res.gross("R2", "property_tax").sum() == 0


def test_investment_leverage_handles_modeled_and_unmodeled(inputs):
    _, fixed, phases, anchors = inputs
    res = run(fixed, phases, anchors)
    invs = [
        {
            "investment": "ONT",
            "recommendations": "R2",
            "dashboard_kpi": "",
            "modeled_as": f"anchor:{anchors[0].name};rec:R4",
        },
        {
            "investment": "WVC",
            "recommendations": "R2",
            "dashboard_kpi": "",
            "modeled_as": "not_modeled:enabling",
        },
    ]
    out = impact.investment_leverage(res, invs, 2030, 2036)
    expect = impact.window_sum(res.by_anchor[anchors[0].name] + res.gross("R4"), YEARS, 2030, 2036)[0]
    assert out[0]["p50"] == pytest.approx(expect)
    assert out[1]["p50"] is None and out[1]["note"] == "enabling"


def test_benefit_cost_and_breakeven(inputs):
    _, fixed, phases, anchors = inputs
    res = run(fixed, phases, anchors)
    rows = {r["group"]: r for r in impact.benefit_cost(res, 2030, 2036)}
    assert set(rows) == set(impact.ROI_GROUPS)
    assert not any(r["present_value"] for r in rows.values())
    r2 = rows["R2 Connected Destination (Stay +1)"]
    gross = impact.window_sum(res.gross("R2"), YEARS, 2030, 2036)[0]
    cost = impact.window_sum(res.cost["R2"], YEARS, 2030, 2036)[0]
    assert r2["bcr_p50"] == pytest.approx(gross / cost)
    assert r2["breakeven_annual_cost_p50"] == pytest.approx(gross / 7)  # active all 7 years
    assert r2["prob_pays_for_itself"] in (0.0, 1.0)  # one deterministic simulation
    yr1 = impact.first_year_city_cost(res, 2027)
    assert yr1[1] == pytest.approx(fixed["cost_R1"].mode + fixed["cost_R2"].mode)  # R3/R4 start later


def test_tornado_sorted_by_swing(inputs):
    A, _, phases, anchors = inputs
    rows = impact.tornado(A, phases, anchors, YEARS, np.full((1, len(YEARS)), 140e6), 2030, 2036)
    swings = [abs(hi - lo) for _, lo, hi, _ in rows]
    assert swings == sorted(swings, reverse=True)


def test_airport_counts_each_traveler_once(inputs):
    # ONT reports enplaned + deplaned passengers: only the arriving half can add a night.
    _, fixed, phases, anchors = inputs
    ont = next(an for an in anchors if "Airport" in an.name)
    assert ont.arrival_share == 0.5
    full = [replace(an, arrival_share=1.0) if an is ont else an for an in anchors]
    halved = run(fixed, phases, anchors).by_anchor[ont.name]
    assert np.allclose(halved, run(fixed, phases, full).by_anchor[ont.name] / 2)


def test_in_person_spending_earns_measure_q_but_business_sales_do_not(inputs):
    _, fixed, phases, anchors = inputs
    with_q, without_q = run(fixed, phases, anchors), run(fixed, phases, anchors, measure_q_rate=0.0)
    for rec in ("R2", "R3"):  # visitor and district spending: 1% + 1%
        assert np.allclose(with_q.gross(rec, "sales_tax"), 2 * without_q.gross(rec, "sales_tax"))
    assert np.allclose(with_q.gross("R2", "tot"), without_q.gross("R2", "tot"))
    # R4 mixes resident spending (2%) with business-to-business sales (1%): less than double
    r4, r4_no_q = with_q.gross("R4", "sales_tax")[0, -1], without_q.gross("R4", "sales_tax")[0, -1]
    assert r4_no_q < r4 < 2 * r4_no_q


def test_residents_who_would_live_here_anyway_add_only_their_spending_gain(inputs):
    _, fixed, phases, anchors = inputs
    kw = dict(retained_resident_share=0.0, r4_taxable_sales_per_job=0.0)
    none = run(fixed, phases, anchors, stayer_spending_gain=0.0, **kw)
    assert none.gross("R1").sum() == 0 and none.gross("R4").sum() == 0  # nothing new to tax
    assert none.workers()[0, -1] > 0  # ...but the live/work outcome is still counted
    all_new = run(fixed, phases, anchors, stayer_spending_gain=1.0, **kw)
    assert all_new.gross("R1", "sales_tax").sum() > 0


def test_present_value_lowers_late_dollars_and_keeps_launch_year(inputs):
    _, fixed, phases, anchors = inputs
    res = run(fixed, phases, anchors, discount_rate=0.05)
    pv = res.pv_factor(2027)[0]
    assert pv[YEARS <= 2027].tolist() == [1.0, 1.0]
    assert pv[-1] == pytest.approx(1.05**-9)
    flat = {r["group"]: r for r in impact.benefit_cost(res, 2027, 2036)}
    disc = {r["group"]: r for r in impact.benefit_cost(res, 2027, 2036, discount_from=2027)}
    # Stock-building programs earn late, so discounting lowers their return per dollar
    assert disc["R1 Career Pathways"]["bcr_p50"] < flat["R1 Career Pathways"]["bcr_p50"]
    assert all(r["present_value"] for r in disc.values())


def test_whole_program_return_includes_startup_years(inputs):
    # A late window alone flatters the return: start-up costs are left out.
    _, fixed, phases, anchors = inputs
    res = run(fixed, phases, anchors)
    late = {r["group"]: r for r in impact.benefit_cost(res, 2030, 2036)}
    whole = {r["group"]: r for r in impact.benefit_cost(res, 2027, 2036)}
    g = "R2 Connected Destination (Stay +1)"
    assert whole[g]["bcr_p50"] < late[g]["bcr_p50"]


def test_r1_r4_package_carries_both_costs(inputs):
    _, fixed, phases, anchors = inputs
    res = run(fixed, phases, anchors)
    rows = {r["group"]: r for r in impact.benefit_cost(res, 2027, 2036)}
    gross = sum(impact.window_sum(res.gross(r), YEARS, 2027, 2036)[0] for r in ("R1", "R4", "SYN"))
    cost = sum(impact.window_sum(res.cost[r], YEARS, 2027, 2036)[0] for r in ("R1", "R4"))
    pair = rows["R1 + R4 together (shared cost)"]["bcr_p50"]
    assert pair == pytest.approx(gross / cost)
    assert pair < rows["R4 Employers (+ R1→R4 link)"]["bcr_p50"]


def test_stay1_base_parties_matches_the_chain_at_mode(inputs):
    A, _, _, anchors = inputs
    expect = sum(an.visitors * an.arrival_share * an.overnight.mode for an in anchors)
    expect *= A["dedup_factor"].mode / A["persons_per_room"].mode
    assert impact.stay1_base_parties(A, anchors) == pytest.approx(expect)


def test_room_rate_is_tied_to_official_hotel_tax_and_room_supply(inputs):
    A, _, _, _ = inputs
    adr = impact.derive_adr(A, 16_671_971.0)
    revpar = 16_671_971.0 / A["tot_rate"].mode / (A["hotel_rooms"].mode * 365)
    assert adr.mode == pytest.approx(revpar / A["hotel_occupancy"].mode)
    assert adr.low < adr.mode < adr.high  # high occupancy -> low rate
    # the derived rate reproduces actual hotel tax: nights sold x rate x tax rate
    nights = A["hotel_rooms"].mode * 365 * A["hotel_occupancy"].mode
    assert nights * adr.mode * A["tot_rate"].mode == pytest.approx(16_671_971.0)
