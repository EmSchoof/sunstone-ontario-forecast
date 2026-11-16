"""Build staging/marts from raw, run data checks, export marts.

python -m ontario_forecast.transform.run
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from ontario_forecast import config
from ontario_forecast.transform.checks import run_checks

SQL_DIR = Path(__file__).parent / "sql"
EXPORT_TABLES = (
    "ontario_fy_panel",
    "city_tax_fy",
    "sb_county_sector_cy",
    "acs_place_of_work",
    "acs_vintage_change",
    "msa_occupation_wages",
    "headline_metrics",
)


def param_table(con: duckdb.DuckDBPyConnection, name: str, columns: str, rows: list[list]) -> None:
    """Create staging.<name> from config values so SQL never hard-codes parameters."""
    con.execute(f"create or replace table staging.{name} ({columns})")
    if rows:
        placeholders = ", ".join("?" * len(rows[0]))
        con.executemany(f"insert into staging.{name} values ({placeholders})", rows)


# name -> (column DDL, rows from config). Add a parameter here, reference it in SQL.
PARAMS = {
    "covid_fys": ("fy integer", [[fy] for fy in config.COVID_SHOCK_FYS]),
    "acs_vintages": ("acs_year integer", [[y] for y in config.ACS_NONOVERLAPPING_VINTAGES]),
    "fred_series": (
        "series_id varchar, column_name varchar, description varchar",
        [[sid, col, desc] for sid, (col, desc) in config.FRED_SERIES.items()],
    ),
    # Proposal figures: FALLBACKS / comparison columns only (see marts.headline_metrics).
    "proposal_benchmarks": (
        "metric varchar, period integer, value double",
        [[m, p, v] for m, (p, v) in config.PROPOSAL_BENCHMARKS.items()],
    ),
    "proposal_wages": (
        "soc varchar, median_annual_wage double",
        [[s, w] for s, w in config.PROPOSAL_MEDIAN_WAGES.items()],
    ),
}


def build(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("create schema if not exists staging")
    for name, (columns, rows) in PARAMS.items():
        param_table(con, name, columns, rows)
    for path in sorted(SQL_DIR.glob("*.sql")):
        con.execute(path.read_text())


def export(con: duckdb.DuckDBPyConnection, out_dir: Path = config.PROCESSED_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for t in EXPORT_TABLES:
        for fmt in ("parquet", "csv"):  # parquet for code, csv for teammates/Excel
            dest = out_dir / f"{t}.{fmt}"
            con.execute(f"copy marts.{t} to '{dest}' (format {fmt})")
        print(f"  exported marts.{t}")


def main() -> int:
    with duckdb.connect(str(config.WAREHOUSE)) as con:
        build(con)
        failures = run_checks(con)
        errors = 0
        for chk, rows in failures:
            errors += chk.severity == "error"
            print(f"[{chk.severity.upper()}] {chk.name}: {len(rows)} row(s), e.g. {rows[:3]}")
        if errors:
            print(f"{errors} check(s) failed; marts not exported.")
            return 1
        export(con)
    print("Transform complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
