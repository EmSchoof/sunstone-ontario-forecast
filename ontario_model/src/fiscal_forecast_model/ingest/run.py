"""Load all sources into data/warehouse/ontario.duckdb (schema `raw`).

python -m fiscal_forecast_model.ingest.run --skip-lodes        # fast sources (~1 min)
python -m fiscal_forecast_model.ingest.run --lodes-years 2002-2024
python -m fiscal_forecast_model.ingest.run --only bls_observations
"""

from __future__ import annotations

import argparse
import logging

import dlt
import duckdb

from fiscal_forecast_model import config
from fiscal_forecast_model.ingest.sources import ontario_source


def _years(s: str) -> tuple[int, int]:
    a, _, b = s.partition("-")
    return int(a), int(b or a)


def drop_empty_placeholders(con: duckdb.DuckDBPyConnection | None = None) -> list[str]:
    """Drop empty raw.* tables that dlt did not create.

    The transform SQL creates empty placeholder tables for sources that have not been loaded
    yet (so the SQL stays valid). dlt cannot load into them: it would have to add its
    bookkeeping columns as NOT NULL, which DuckDB refuses on an existing table. Removing
    the placeholder lets dlt create the table properly. Tables holding rows are never touched.
    """
    own = con is None
    if own:
        if not config.WAREHOUSE.exists():
            return []
        con = duckdb.connect(str(config.WAREHOUSE))
    try:
        placeholders = con.execute(
            "select table_name from information_schema.tables t where table_schema = 'raw' "
            "and table_name not like '\\_dlt%' escape '\\' and not exists ("
            "  select 1 from information_schema.columns c where c.table_schema = 'raw' "
            "  and c.table_name = t.table_name and c.column_name = '_dlt_load_id') order by 1"
        ).fetchall()
        dropped = []
        for (name,) in placeholders:
            if con.execute(f'select count(*) from raw."{name}"').fetchone()[0] == 0:
                con.execute(f'drop table raw."{name}"')
                dropped.append(name)
        return dropped
    finally:
        if own:
            con.close()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--skip-lodes", action="store_true", help="skip the ~2 GB LODES stream")
    ap.add_argument("--lodes-years", default=f"{config.LODES_FIRST_YEAR}-2024")
    ap.add_argument("--refresh-lodes", action="store_true", help="re-aggregate years already loaded")
    ap.add_argument("--only", nargs="+", metavar="RESOURCE", help="load only these resources")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config.WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    first, last = _years(args.lodes_years)
    source = ontario_source(
        include_lodes=not args.skip_lodes,
        lodes_first_year=first,
        lodes_last_year=last,
        refresh_lodes=args.refresh_lodes,
    )
    if args.only:
        source = source.with_resources(*args.only)

    dropped = drop_empty_placeholders()
    if dropped:
        print(f"Removed empty placeholder table(s) so dlt can create them: {', '.join(dropped)}")

    pipeline = dlt.pipeline(
        pipeline_name="ontario_ingest",
        destination=dlt.destinations.duckdb(str(config.WAREHOUSE)),
        dataset_name="raw",
        pipelines_dir=str(config.PIPELINES_DIR),
    )
    print(pipeline.run(source))


if __name__ == "__main__":
    main()
