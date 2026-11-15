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
    Check("city_tax_fy is unique on (city, fy)",
          "select city, fy, count(*) n from staging.city_tax_fy group by all having n > 1"),
    Check("tax revenue is non-negative",
          "select * from staging.city_tax_fy where tot_revenue < 0 or sales_tax_bradley_burns < 0"),
    Check("Ontario has TOT and sales tax every year",
          "select fy from marts.ontario_fy_panel "
          "where tot_revenue is null or sales_tax_total is null"),
    Check("Ontario fiscal years are contiguous (growth rates assume consecutive years)",
          "select fy from (select fy, fy - lag(fy) over (order by fy) d from marts.ontario_fy_panel) "
          "where d <> 1"),
    Check("no fiscal year has more than 12 months (duplicate months)",
          "select 'fred' src, series_id, fy, n_months from marts.fred_fy where n_months > 12 "
          "union all select 'laus', city, fy, n_months from marts.laus_city_fy where n_months > 12"),
    Check("LODES live-and-work never exceeds residents or jobs",
          "select * from staging.lodes_ontario_cy "
          "where live_and_work > employed_residents or live_and_work > jobs_in_ontario"),
    Check("LODES shares lie in [0, 1]",
          "select * from staging.lodes_ontario_cy where share_residents_work_local not between 0 and 1 "
          "or share_jobs_held_by_residents not between 0 and 1"),
    Check("real revenue has a deflator for every year",
          "select fy from marts.ontario_fy_panel where tot_revenue_real is null", severity="warn"),
    Check("annual real TOT growth within +/-60% (review outliers)",
          "select fy, dlog_tot_real from marts.ontario_fy_panel where abs(dlog_tot_real) > 0.47",
          severity="warn"),
    Check("LODES years missing the out-of-state (aux) file",
          "select cy from staging.lodes_ontario_cy where not includes_aux", severity="warn"),
)


def run_checks(con: duckdb.DuckDBPyConnection) -> list[tuple[Check, list[tuple]]]:
    """Return [(check, violating_rows)] for every check that found violations."""
    failures = []
    for chk in CHECKS:
        rows = con.execute(chk.sql).fetchall()
        if rows:
            failures.append((chk, rows))
    return failures
