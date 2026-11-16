"""Impact model tests: mechanics on the real input files, deterministic (all inputs at mode)."""

from dataclasses import replace

import numpy as np
import pytest

from ontario_forecast import config, impact

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
