"""dlt resources: one per public source. Raw data lands in the `raw` schema unchanged
except for type coercion (strings -> numbers/dates) and snake_case keys.

No pandas: CSVs are parsed with the stdlib `csv` module (streamed where large),
LODES is aggregated inside DuckDB.
"""
from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterator
from datetime import date

import dlt
import duckdb
from dlt.sources.helpers import requests  # requests with retries/backoff
from requests.exceptions import HTTPError

from ontario_forecast import config
from ontario_forecast.ingest.lodes import aggregate_flows, load_ontario_blocks


def _num(x: str | None) -> float | None:
    """Parse numbers; FRED uses '.', other sources use '' for missing."""
    if x is None:
        return None
    x = x.strip().replace(",", "")
    if x in ("", "."):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _snake(key: str) -> str:
    k = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")   # also drops a UTF-8 BOM
    return k.removesuffix("_y_n")                              # "Seasonally Adjusted(Y/N)"


def _exists(url: str) -> bool:
    try:
        return requests.head(url, timeout=60, allow_redirects=True).status_code == 200
    except HTTPError:
        return False


# ---------------------------------------------------------------------------
# CA State Controller - city revenue line items (TOT, sales tax, population)
# ---------------------------------------------------------------------------
@dlt.resource(name="sco_city_revenue_lines", write_disposition="replace")
def sco_city_revenue_lines(
    cities: tuple[str, ...] = (config.CITY, *config.PEER_CITIES), page_size: int = 50_000
) -> Iterator[list[dict]]:
    names = ",".join("'" + c.replace("'", "''") + "'" for c in cities)
    offset = 0
    while True:
        page = requests.get(
            config.SCO_CITY_REVENUES_URL,
            params={"$where": f"entity_name in({names})", "$order": ":id",
                    "$limit": page_size, "$offset": offset},
            timeout=300,
        ).json()
        if not page:
            break
        for row in page:
            row["fiscal_year"] = int(row["fiscal_year"])
            row["value"] = _num(row.get("value"))
            pop = _num(row.get("estimated_population"))
            row["estimated_population"] = int(pop) if pop is not None else None
        yield page
        if len(page) < page_size:
            break
        offset += page_size


# ---------------------------------------------------------------------------
# CA EDD LAUS - city labor force / employment (monthly)
# ---------------------------------------------------------------------------
def _ckan_csv_url(package_id: str, must_contain: str) -> str:
    meta = requests.get(config.CKAN_PACKAGE_SHOW, params={"id": package_id}, timeout=120).json()
    for res in meta["result"]["resources"]:
        if res.get("format", "").upper() == "CSV" and must_contain in res["url"]:
            return res["url"]
    raise LookupError(f"No CSV containing {must_contain!r} in CKAN package {package_id}")


@dlt.resource(name="laus_city_monthly", write_disposition="replace")
def laus_city_monthly(cities: tuple[str, ...] = (config.CITY, *config.PEER_CITIES)) -> Iterator[list[dict]]:
    places = {f"{c} city" for c in cities}
    url = _ckan_csv_url(config.LAUS_MONTHLY_PACKAGE, "laborforceandunemployment_monthly")
    with requests.get(url, stream=True, timeout=600) as r:
        r.encoding = "utf-8-sig"
        reader = csv.DictReader(r.iter_lines(decode_unicode=True))
        batch = []
        for raw in reader:
            row = {_snake(k): v for k, v in raw.items()}
            if row.get("area_type") != "Sub-County Place" or row.get("area_name") not in places:
                continue
            for k in ("labor_force", "employment", "unemployment", "unemployment_rate"):
                row[k] = _num(row.get(k))
            row["year"] = int(row["year"])
            batch.append(row)
        yield batch


# ---------------------------------------------------------------------------
# FRED - MSA employment and CPI (monthly), long format
# ---------------------------------------------------------------------------
@dlt.resource(name="fred_observations", write_disposition="replace")
def fred_observations(series: tuple[str, ...] = tuple(config.FRED_SERIES)) -> Iterator[list[dict]]:
    for sid in series:
        text = requests.get(config.FRED_CSV_URL, params={"id": sid}, timeout=180).text
        reader = csv.reader(io.StringIO(text))
        next(reader)  # header
        yield [{"series_id": sid, "obs_date": date.fromisoformat(d), "value": _num(v)} for d, v in reader]


# ---------------------------------------------------------------------------
# BLS QCEW - San Bernardino County employment and pay by NAICS sector (annual)
# ---------------------------------------------------------------------------
_QCEW_NUM = ("annual_avg_estabs", "annual_avg_emplvl", "total_annual_wages", "avg_annual_pay")


@dlt.resource(name="qcew_county_annual", write_disposition="replace")
def qcew_county_annual(first_year: int = config.QCEW_FIRST_YEAR,
                       last_year: int = date.today().year) -> Iterator[list[dict]]:
    for yr in range(first_year, last_year + 1):
        try:
            text = requests.get(config.QCEW_AREA_URL.format(year=yr, area=config.SB_COUNTY_FIPS),
                                timeout=180).text
        except HTTPError:
            continue  # year not yet published
        rows = []
        for row in csv.DictReader(io.StringIO(text)):
            # 70 county total, 71 county by ownership, 74 county by NAICS sector x ownership
            if row["agglvl_code"] in ("70", "71", "74") and row["own_code"] in ("0", "5"):
                rec = {k: row[k] for k in ("year", "own_code", "industry_code", "agglvl_code",
                                           "disclosure_code")}
                rec["year"] = int(rec["year"])
                rec.update({k: _num(row[k]) for k in _QCEW_NUM})
                rows.append(rec)
        yield rows


# ---------------------------------------------------------------------------
# Census LODES - Ontario live/work flows, one aggregated row per year
# ---------------------------------------------------------------------------
@dlt.resource(name="lodes_ontario_flows", write_disposition="merge", primary_key="year")
def lodes_ontario_flows(first_year: int = config.LODES_FIRST_YEAR,
                        last_year: int = date.today().year,
                        refresh: bool = False) -> Iterator[dict]:
    """Incremental: years already loaded are skipped (tracked in dlt state)."""
    state = dlt.current.resource_state()
    done = set(state.setdefault("years_loaded", []))
    con = duckdb.connect()                          # scratch in-memory engine
    con.execute("install httpfs; load httpfs;")      # lets DuckDB stream https files
    n_blocks = load_ontario_blocks(con, f"{config.LODES_BASE}/ca_xwalk.csv.gz",
                                   config.ONTARIO_PLACE_FIPS)
    if n_blocks == 0:
        raise ValueError("No Ontario blocks found in the LODES crosswalk")
    for yr in range(first_year, last_year + 1):
        if yr in done and not refresh:
            continue
        main = f"{config.LODES_BASE}/od/ca_od_main_JT00_{yr}.csv.gz"
        aux = f"{config.LODES_BASE}/od/ca_od_aux_JT00_{yr}.csv.gz"
        if not _exists(main):
            continue
        files = [main] + ([aux] if _exists(aux) else [])
        row = aggregate_flows(con, files)
        row.update(year=yr, includes_aux=len(files) == 2, ontario_blocks=n_blocks)
        yield row
        done.add(yr)
        state["years_loaded"] = sorted(done)


@dlt.source(name="ontario")
def ontario_source(include_lodes: bool = True, lodes_first_year: int = config.LODES_FIRST_YEAR,
                   lodes_last_year: int = date.today().year, refresh_lodes: bool = False):
    resources = [sco_city_revenue_lines(), laus_city_monthly(), fred_observations(),
                 qcew_county_annual()]
    if include_lodes:
        resources.append(lodes_ontario_flows(lodes_first_year, lodes_last_year, refresh_lodes))
    return resources
