"""LODES origin-destination aggregation, done inside DuckDB.

Each CA OD file is ~96 MB gzipped (tens of millions of rows). Routing that through
Python row by row would be slow, so DuckDB streams the remote .csv.gz, joins it to
Ontario's census blocks, and returns ONE aggregated row per year. Only those
aggregates are loaded into the warehouse by dlt.
"""
from __future__ import annotations

from collections.abc import Sequence

import duckdb

# SE03 = jobs paying more than $3,333/month (LODES' top earnings band).
_AGG_SQL = """
with od as (
    select w_geocode, h_geocode, S000, SE03
    from read_csv({files}, header = true,
                  types = {{'w_geocode': 'VARCHAR', 'h_geocode': 'VARCHAR'}})
)
select
    coalesce(sum(S000) filter (where w.block is not null), 0)                       as jobs_in_ontario,
    coalesce(sum(S000) filter (where h.block is not null), 0)                       as employed_residents,
    coalesce(sum(S000) filter (where w.block is not null and h.block is not null), 0) as live_and_work,
    coalesce(sum(SE03) filter (where w.block is not null), 0)                       as jobs_high_wage,
    coalesce(sum(SE03) filter (where h.block is not null), 0)                       as residents_high_wage,
    coalesce(sum(SE03) filter (where w.block is not null and h.block is not null), 0) as live_and_work_high_wage
from od
left join ontario_blocks w on od.w_geocode = w.block
left join ontario_blocks h on od.h_geocode = h.block
"""


def load_ontario_blocks(con: duckdb.DuckDBPyConnection, xwalk_path: str, place_fips: str) -> int:
    """Create temp table ontario_blocks(block) from the LODES geography crosswalk."""
    con.execute(
        "create or replace temp table ontario_blocks as "
        "select tabblk2020 as block from read_csv(?, all_varchar = true) where stplc = ?",
        [xwalk_path, place_fips],
    )
    return con.execute("select count(*) from ontario_blocks").fetchone()[0]


def aggregate_flows(con: duckdb.DuckDBPyConnection, files: Sequence[str]) -> dict:
    """Aggregate one year's OD files (main = in-state residents, aux = out-of-state).

    Residents are counted from `main` only: in `aux` the home block is outside CA,
    so it can never match an Ontario block and the joins handle that naturally.
    Limitation: Ontario residents working outside CA appear only in other states'
    files and are not counted (a very small group).
    """
    file_list = "[" + ", ".join("'" + f.replace("'", "''") + "'" for f in files) + "]"
    cur = con.execute(_AGG_SQL.format(files=file_list))
    cols = [d[0] for d in cur.description]
    return {c: int(v) for c, v in zip(cols, cur.fetchone())}
