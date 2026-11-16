"""Load all sources into data/warehouse/ontario.duckdb (schema `raw`).

python -m ontario_forecast.ingest.run --skip-lodes        # fast sources (~1 min)
python -m ontario_forecast.ingest.run --lodes-years 2002-2024
python -m ontario_forecast.ingest.run --only fred_observations
"""

from __future__ import annotations

import argparse
import logging

import dlt

from ontario_forecast import config
from ontario_forecast.ingest.sources import ontario_source


def _years(s: str) -> tuple[int, int]:
    a, _, b = s.partition("-")
    return int(a), int(b or a)


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

    pipeline = dlt.pipeline(
        pipeline_name="ontario_ingest",
        destination=dlt.destinations.duckdb(str(config.WAREHOUSE)),
        dataset_name="raw",
        pipelines_dir=str(config.PIPELINES_DIR),
    )
    print(pipeline.run(source))


if __name__ == "__main__":
    main()
