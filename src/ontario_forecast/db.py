"""Read marts straight into numpy arrays (no pandas)."""

from __future__ import annotations

import duckdb
import numpy as np

from ontario_forecast import config


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(config.WAREHOUSE), read_only=read_only)


def fetch(
    sql: str, params: list | None = None, con: duckdb.DuckDBPyConnection | None = None
) -> dict[str, np.ndarray]:
    """Run SQL and return {column: ndarray}.

    Integer columns stay integer unless they contain NULLs (then float with NaN).
    """
    own = con is None
    con = con or connect()
    try:
        cols = con.execute(sql, params or []).fetchnumpy()
    finally:
        if own:
            con.close()
    out = {}
    for k, v in cols.items():
        if np.ma.isMaskedArray(v):
            v = v.astype(float).filled(np.nan) if v.dtype.kind in "iuf" else v.filled(None)
        out[k] = np.asarray(v)
    return out


def load_panel(con: duckdb.DuckDBPyConnection | None = None) -> dict[str, np.ndarray]:
    """The Ontario fiscal-year modeling panel, chronologically ordered."""
    return fetch("select * from marts.ontario_fy_panel order by fy", con=con)
