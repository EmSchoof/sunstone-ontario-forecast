"""dlt resources: one per public source. Raw data lands in the `raw` schema unchanged
except for type coercion (strings -> numbers/dates) and snake_case keys.

No pandas: CSVs are parsed with the stdlib `csv` module (streamed where large),
LODES is aggregated inside DuckDB.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import dlt
import duckdb
from dlt.sources.helpers import requests  # requests with retries/backoff
from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.paginators import OffsetPaginator
from requests.exceptions import HTTPError

from ontario_forecast import config
from ontario_forecast.ingest.lodes import aggregate_flows, load_ontario_blocks


def _num(x: str | None) -> float | None:
    """Parse numbers; '.', '-' and '' mean missing; BLS suppression codes ('*', '#') -> None."""
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
    k = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")  # also drops a UTF-8 BOM
    return k.removesuffix("_y_n")  # "Seasonally Adjusted(Y/N)"


log = logging.getLogger(__name__)


def _secret(name: str) -> str | None:
    """API key from env var (CENSUS_API_KEY) or .dlt/secrets.toml (census_api_key = "...")."""
    if v := os.environ.get(name.upper()):
        return v
    try:
        return dlt.secrets[name.lower()]
    except Exception:  # noqa: BLE001  dlt raises a KeyError subclass when the key is absent
        return None


def _census_num(x: str | None) -> float | None:
    """Census uses large negative sentinels (e.g. -666666666) for 'not available'."""
    v = _num(x)
    return None if v is None or v <= -1e8 else v


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
    cities: tuple[str, ...] = config.ALL_CITIES, page_size: int = 50_000
) -> Iterator[list[dict]]:
    names = ",".join("'" + c.replace("'", "''") + "'" for c in cities)
    # Socrata pages with $limit/$offset and returns a bare JSON list (no total count),
    # so paging stops at the first empty page. $order makes paging deterministic.
    client = RESTClient(
        base_url=config.SCO_BASE_URL,
        paginator=OffsetPaginator(
            limit=page_size,
            offset_param="$offset",
            limit_param="$limit",
            total_path=None,
            stop_after_empty_page=True,
        ),
    )
    for page in client.paginate(
        config.SCO_CITY_REVENUES, params={"$where": f"entity_name in({names})", "$order": ":id"}
    ):
        for row in page:
            row["fiscal_year"] = int(row["fiscal_year"])
            row["value"] = _num(row.get("value"))
            pop = _num(row.get("estimated_population"))
            row["estimated_population"] = int(pop) if pop is not None else None
        yield page


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
def laus_city_monthly(cities: tuple[str, ...] = config.ALL_CITIES) -> Iterator[list[dict]]:
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
# BLS API (shared by monthly series and OEWS)
# ---------------------------------------------------------------------------
def _bls_series(series_ids: list[str], **params) -> list[dict]:
    """POST to the BLS API in chunks; returns the Results.series list.

    Limits: 25 series and 10 years per request without a key; 50 and 20 with
    BLS_API_KEY (which also raises the daily cap from 25 to 500 requests).
    """
    key = _secret("bls_api_key")
    chunk = 50 if key else 25
    out = []
    for i in range(0, len(series_ids), chunk):
        payload = {"seriesid": series_ids[i : i + chunk], **params}
        if key:
            payload["registrationkey"] = key
        resp = requests.post(config.BLS_API_URL, json=payload, timeout=120).json()
        if resp.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS API: {resp.get('message')}")
        for msg in resp.get("message", []):
            # "No Data Available for Series X Year: Y" is routine (gaps by year, esp. OEWS);
            # anything else (unknown series, daily limit) is a real warning.
            (log.info if msg.startswith("No Data Available") else log.warning)("BLS API: %s", msg)
        out += resp["Results"]["series"]
    return out


# ---------------------------------------------------------------------------
# BLS monthly series: MSA employment (CES), unemployment (LAUS), CPI - long format
# ---------------------------------------------------------------------------
@dlt.resource(name="bls_observations", write_disposition="replace")
def bls_observations(
    series: tuple[str, ...] = tuple(config.BLS_SERIES),
    first_year: int = config.BLS_FIRST_YEAR,
    last_year: int = date.today().year,
) -> Iterator[list[dict]]:
    span = 20 if _secret("bls_api_key") else 10  # years per request allowed by BLS
    for start in range(first_year, last_year + 1, span):
        end = min(start + span - 1, last_year)
        for s in _bls_series(list(series), startyear=str(start), endyear=str(end)):
            yield [
                {
                    "series_id": s["seriesID"],
                    "obs_date": date(int(d["year"]), int(d["period"][1:]), 1),
                    "value": _num(d["value"]),
                    "preliminary": any(f.get("code") == "P" for f in d.get("footnotes", []) if f),
                }
                for d in s["data"]
                if d["period"].startswith("M") and d["period"] != "M13"  # M13 = annual average
            ]


# ---------------------------------------------------------------------------
# BLS QCEW - San Bernardino County employment and pay by NAICS sector (annual)
# ---------------------------------------------------------------------------
_QCEW_NUM = ("annual_avg_estabs", "annual_avg_emplvl", "total_annual_wages", "avg_annual_pay")


@dlt.resource(name="qcew_county_annual", write_disposition="replace")
def qcew_county_annual(
    first_year: int = config.QCEW_FIRST_YEAR, last_year: int = date.today().year
) -> Iterator[list[dict]]:
    for yr in range(first_year, last_year + 1):
        try:
            r = requests.get(config.QCEW_AREA_URL.format(year=yr, area=config.SB_COUNTY_FIPS), timeout=180)
        except HTTPError:
            continue  # year not yet published
        # Guard even if the client doesn't raise: an HTML error page must not be parsed as CSV.
        if r.status_code != 200 or not r.text.startswith('"area_fips"'):
            continue
        text = r.text
        rows = []
        for row in csv.DictReader(io.StringIO(text)):
            # 70 county total, 71 county by ownership, 74 county by NAICS sector x ownership
            if row["agglvl_code"] in ("70", "71", "74") and row["own_code"] in ("0", "5"):
                rec = {
                    k: row[k] for k in ("year", "own_code", "industry_code", "agglvl_code", "disclosure_code")
                }
                rec["year"] = int(rec["year"])
                rec.update({k: _num(row[k]) for k in _QCEW_NUM})
                rows.append(rec)
        yield rows


# ---------------------------------------------------------------------------
# Census LODES - Ontario live/work flows, one aggregated row per year
# ---------------------------------------------------------------------------
@dlt.resource(name="lodes_ontario_flows", write_disposition="merge", primary_key="year")
def lodes_ontario_flows(
    first_year: int = config.LODES_FIRST_YEAR, last_year: int = date.today().year, refresh: bool = False
) -> Iterator[dict]:
    """Incremental: years already loaded are skipped (tracked in dlt state)."""
    state = dlt.current.resource_state()
    done = set(state.setdefault("years_loaded", []))
    con = duckdb.connect()  # scratch in-memory engine
    con.execute("install httpfs; load httpfs;")  # lets DuckDB stream https files
    n_blocks = load_ontario_blocks(con, f"{config.LODES_BASE}/ca_xwalk.csv.gz", config.ONTARIO_PLACE_FIPS)
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


# ---------------------------------------------------------------------------
# Census ACS 5-year - Ontario city + San Bernardino County, selected tables (long)
# ---------------------------------------------------------------------------
_ACS_VAR = re.compile(r"^B\d{5}_\d{3}[EM]$")


@dlt.resource(name="acs_place", write_disposition="replace")
def acs_place(
    first_year: int = config.ACS_FIRST_YEAR, last_year: int = date.today().year - 1
) -> Iterator[list[dict]]:
    key = _secret("census_api_key")
    if not key:
        log.warning("acs_place skipped: set CENSUS_API_KEY (free at api.census.gov/data/key_signup.html)")
        return
    geos = {
        "Ontario city": {"for": f"place:{config.ONTARIO_PLACE_FIPS[2:]}", "in": "state:06"},
        "San Bernardino County": {"for": f"county:{config.SB_COUNTY_FIPS[2:]}", "in": "state:06"},
    }
    for yr in range(first_year, last_year + 1):
        base = config.ACS_URL.format(year=yr)
        for group in config.ACS_GROUPS:
            try:
                labels = requests.get(f"{base}/groups/{group}.json", timeout=120).json()["variables"]
            except (HTTPError, ValueError, KeyError):
                continue  # vintage/table not published
            for geo, params in geos.items():
                try:
                    header, *rows = requests.get(
                        base, params={"get": f"group({group})", **params, "key": key}, timeout=120
                    ).json()
                except (HTTPError, ValueError):
                    continue
                for vals in rows:
                    out: dict[str, dict] = {}
                    for var, val in zip(header, vals, strict=True):
                        if not _ACS_VAR.match(var):
                            continue  # skip annotations, GEO_ID, NAME
                        v = var[:-1]
                        rec = out.setdefault(
                            v,
                            {
                                "year": yr,
                                "geo": geo,
                                "acs_group": group,
                                "variable": v,
                                "label": labels.get(v + "E", {}).get("label"),
                                "estimate": None,
                                "moe": None,
                            },
                        )
                        rec["estimate" if var.endswith("E") else "moe"] = _census_num(val)
                    yield list(out.values())


# ---------------------------------------------------------------------------
# BLS OEWS - MSA wages for the proposal's pathway occupations
# ---------------------------------------------------------------------------
@dlt.resource(name="oews_msa_occupations", write_disposition="replace")
def oews_msa_occupations() -> Iterator[list[dict]]:
    ids = {
        f"OEUM{config.OEWS_MSA}000000{soc}{dt}": (soc, dt)
        for soc in config.OEWS_OCCUPATIONS
        for dt in config.OEWS_DATATYPES
    }
    rows = []
    for s in _bls_series(list(ids)):
        soc, dt = ids[s["seriesID"]]
        title, pathway = config.OEWS_OCCUPATIONS[soc]
        rows += [
            {
                "series_id": s["seriesID"],
                "soc": f"{soc[:2]}-{soc[2:]}",
                "occupation": title,
                "pathway": pathway,
                "measure": config.OEWS_DATATYPES[dt],
                "year": int(d["year"]),
                "value": _num(d["value"]),
            }  # '*'/'#' suppressed -> None
            for d in s["data"]
        ]
    yield rows


# ---------------------------------------------------------------------------
# Hand-entered source data in data/reference/ -> raw.manual_<file stem>
# (data/assumptions/ is deliberately NOT ingested: those are model inputs, not data)
# ---------------------------------------------------------------------------
def _read_manual_csv(path: Path) -> Iterator[list[dict]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        data = [{_snake(k): v for k, v in r.items()} for r in csv.DictReader(f)]
    if data:  # header-only templates load nothing
        yield data


def manual_csv_resources(folder: Path = config.REFERENCE_DIR):
    # Pass a generator OBJECT, not a function: dlt turns a function's arguments into
    # config fields, and Path is not a supported config type.
    for path in sorted(folder.glob("*.csv")):
        yield dlt.resource(_read_manual_csv(path), name=f"manual_{path.stem}", write_disposition="replace")


@dlt.source(name="ontario")
def ontario_source(
    include_lodes: bool = True,
    lodes_first_year: int = config.LODES_FIRST_YEAR,
    lodes_last_year: int = date.today().year,
    refresh_lodes: bool = False,
):
    resources = [
        sco_city_revenue_lines(),
        laus_city_monthly(),
        bls_observations(),
        qcew_county_annual(),
        acs_place(),
        oews_msa_occupations(),
        *manual_csv_resources(),
    ]
    if include_lodes:
        resources.append(lodes_ontario_flows(lodes_first_year, lodes_last_year, refresh_lodes))
    return resources
