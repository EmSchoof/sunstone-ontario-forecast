"""Build staging/marts from raw, run data checks, export marts.

python -m fiscal_forecast_model.transform.run
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import duckdb

from fiscal_forecast_model import config
from fiscal_forecast_model.transform.checks import run_checks

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
    "bls_series": (
        "series_id varchar, column_name varchar, description varchar",
        [[sid, col, desc] for sid, (col, desc) in config.BLS_SERIES.items()],
    ),
    # Proposal figures: FALLBACKS / comparison columns only (see marts.headline_metrics).
    "proposal_benchmarks": (
        "metric varchar, period integer, value double, source varchar",
        [[m, p, v, src] for m, (p, v, src) in config.PROPOSAL_BENCHMARKS.items()],
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


def source_snapshot(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """One row per raw table: how many rows were loaded and when dlt last loaded it.

    The raw downloads are not committed (large, public, rebuildable), so this small table
    is the tracked record of which data the committed charts and tables were built from.
    """

    def exists(table: str, column: str | None = None) -> bool:
        sql = "select count(*) from information_schema.{} where table_schema = 'raw' and table_name = ?"
        if column is None:
            return con.execute(sql.format("tables"), [table]).fetchone()[0] > 0
        return con.execute(sql.format("columns") + " and column_name = ?", [table, column]).fetchone()[0] > 0

    tables = con.execute(
        "select table_name from information_schema.tables where table_schema = 'raw' order by 1"
    ).fetchall()
    has_loads = exists("_dlt_loads")
    out = []
    for (t,) in tables:
        if t.startswith("_dlt"):
            continue
        n = con.execute(f'select count(*) from raw."{t}"').fetchone()[0]
        loaded = None
        if n and has_loads and exists(t, "_dlt_load_id"):
            loaded = con.execute(
                f'select max(l.inserted_at) from raw."{t}" t '
                "join raw._dlt_loads l on l.load_id = t._dlt_load_id"
            ).fetchone()[0]
        out.append({"raw_table": t, "rows": n, "last_loaded_at": "" if loaded is None else str(loaded)})
    return out


def export(con: duckdb.DuckDBPyConnection, out_dir: Path = config.TABLES_DIR) -> None:
    """Analysis-ready marts as CSV next to the other tables (for teammates and Excel)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for t in EXPORT_TABLES:
        con.execute(f"copy marts.{t} to '{out_dir / f'{t}.csv'}' (format csv)")
    with open(out_dir / "source_snapshot.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["raw_table", "rows", "last_loaded_at"])
        w.writeheader()
        w.writerows(source_snapshot(con))
    print(f"  exported {len(EXPORT_TABLES)} marts to {out_dir.relative_to(config.ROOT)}/")


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
