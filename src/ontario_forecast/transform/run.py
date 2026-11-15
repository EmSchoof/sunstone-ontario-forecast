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
EXPORT_TABLES = ("ontario_fy_panel", "city_tax_fy", "sb_county_sector_cy")


def build(con: duckdb.DuckDBPyConnection) -> None:
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
