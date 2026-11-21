"""Data-quality checks (dbt-style): each query returns the rows that VIOLATE the rule.

severity "error" stops the build; "warn" is printed for review.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class Check:
    name: str
    sql: str
    severity: str = "error"


CHECKS: tuple[Check, ...] = (
    Check(
        "city_tax_fy is unique on (city, fy)",
        "select city, fy, count(*) n from staging.city_tax_fy group by all having n > 1",
    ),
    Check(
        "tax revenue is non-negative",
        "select * from staging.city_tax_fy where tot_revenue < 0 or sales_tax_bradley_burns < 0",
    ),
    Check(
        "Ontario has TOT and sales tax every year",
        "select fy from marts.ontario_fy_panel where tot_revenue is null or sales_tax_total is null",
    ),
    Check(
        "Ontario fiscal years are contiguous (growth rates assume consecutive years)",
        "select fy from (select fy, fy - lag(fy) over (order by fy) d from marts.ontario_fy_panel) "
        "where d <> 1",
    ),
    Check(
        "no fiscal year has more than 12 months (duplicate months)",
        "select 'bls' src, series_id, fy, n_months from marts.bls_fy where n_months > 12 "
        "union all select 'laus', city, fy, n_months from marts.laus_city_fy where n_months > 12",
    ),
    Check(
        "LODES live-and-work never exceeds residents or jobs",
        "select * from staging.lodes_ontario_cy "
        "where live_and_work > employed_residents or live_and_work > jobs_in_ontario",
    ),
    Check(
        "LODES shares lie in [0, 1]",
        "select * from staging.lodes_ontario_cy where share_residents_work_local not between 0 and 1 "
        "or share_jobs_held_by_residents not between 0 and 1",
    ),
    Check(
        "real revenue has a deflator for every year",
        "select fy from marts.ontario_fy_panel where tot_revenue_real is null",
        severity="warn",
    ),
    Check(
        "annual real TOT growth within +/-60% (review outliers)",
        "select fy, dlog_tot_real from marts.ontario_fy_panel where abs(dlog_tot_real) > 0.47",
        severity="warn",
    ),
    Check(
        "ACS place-of-work share lies in [0, 1]",
        "select * from marts.acs_place_of_work where share not between 0 and 1",
    ),
    Check(
        "OEWS wages are positive",
        "select * from marts.msa_occupation_wages where median_annual_wage <= 0 or mean_annual_wage <= 0",
    ),
    Check(
        "ACS loaded but place-of-work labels not matched (check B08008 labels)",
        "select 1 from staging.acs_place where acs_group = 'B08008' "
        "and not exists (select 1 from marts.acs_place_of_work) limit 1",
        severity="warn",
    ),
    Check(
        "OEWS occupations with no published median (suppressed)",
        "select occupation from marts.msa_occupation_wages where median_annual_wage is null",
        severity="warn",
    ),
    Check(
        "headline metrics still using a proposal fallback (load the official source)",
        "select metric, value from marts.headline_metrics where is_fallback",
        severity="warn",
    ),
    Check(
        "official value differs from the proposal by >5% (update the proposal text)",
        "select metric, value, proposal_value, pct_diff_vs_proposal from marts.headline_metrics "
        "where abs(pct_diff_vs_proposal) > 0.05",
        severity="warn",
    ),
    Check(
        "Measure Q not found after FY2023: check the State Controller 'Other Taxes - Other' "
        "line matched in staging.city_tax_fy",
        "select fy from marts.ontario_fy_panel where fy >= 2024 and sales_tax_measure_q = 0",
        severity="warn",
    ),
    Check(
        "State Controller Measure Q differs from the City budget actual by >1% "
        "(the 'Other Taxes - Other' line may hold something else that year)",
        "select p.fy, p.sales_tax_measure_q, d.measure_q from marts.ontario_fy_panel p "
        "join staging.city_sales_tax_detail d on d.fy = p.fy and d.basis = 'actual' "
        "where abs(p.sales_tax_measure_q / nullif(d.measure_q, 0) - 1) > 0.01",
        severity="warn",
    ),
    Check(
        "City budget sales-tax parts do not add up to the stated total",
        "select fy, basis from staging.city_sales_tax_detail "
        "where abs(sales_use_tax + prop_172 + measure_q - total_sales_tax) > 1",
    ),
    Check(
        "LODES years missing the out-of-state (aux) file",
        "select cy from staging.lodes_ontario_cy where not includes_aux",
        severity="warn",
    ),
)


def run_checks(con: duckdb.DuckDBPyConnection) -> list[tuple[Check, list[tuple]]]:
    """Return [(check, violating_rows)] for every check that found violations."""
    failures = []
    for chk in CHECKS:
        rows = con.execute(chk.sql).fetchall()
        if rows:
            failures.append((chk, rows))
    return failures
