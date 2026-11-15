"""Single source of truth for paths, geography and source identifiers."""
from __future__ import annotations

from pathlib import Path

# ---- Paths ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
WAREHOUSE = DATA_DIR / "warehouse" / "ontario.duckdb"   # dlt loads raw.*; SQL builds staging.*, marts.*
PROCESSED_DIR = DATA_DIR / "processed"                   # exported marts (parquet + csv) for sharing
MANUAL_DIR = DATA_DIR / "manual"                         # hand-entered data (airport, budget docs)
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
MODELS_DIR = ROOT / "models"
PIPELINES_DIR = ROOT / ".dlt_pipelines"                  # dlt state, kept inside the project

# ---- Geography -----------------------------------------------------------
CITY = "Ontario"
PEER_CITIES = (
    "Rancho Cucamonga", "Fontana", "Chino", "Chino Hills", "Upland",
    "Montclair", "Pomona", "Riverside", "San Bernardino", "Corona",
)
ONTARIO_PLACE_FIPS = "0653896"   # state 06 + Census place 53896
SB_COUNTY_FIPS = "06071"         # San Bernardino County

# ---- Sources -------------------------------------------------------------
SCO_CITY_REVENUES_URL = "https://bythenumbers.sco.ca.gov/resource/rrtv-rsj9.json"
CKAN_PACKAGE_SHOW = "https://data.ca.gov/api/3/action/package_show"
LAUS_MONTHLY_PACKAGE = "59218446-5760-4683-b52e-f6210021840a"   # EDD LAUS (monthly)
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
QCEW_AREA_URL = "https://data.bls.gov/cew/data/api/{year}/a/area/{area}.csv"
QCEW_FIRST_YEAR = 2014
LODES_BASE = "https://lehd.ces.census.gov/data/lodes/LODES8/ca"
LODES_FIRST_YEAR = 2002

FRED_SERIES = {
    "RIVE106NA": "Total nonfarm jobs, Riverside-San Bernardino-Ontario MSA (thousands, NSA)",
    "RIVE106LEIHN": "Leisure & hospitality jobs, MSA (thousands, NSA)",
    "SMU06401404300000001": "Transportation & warehousing jobs, MSA (thousands, NSA)",
    "RIVE106UR": "Unemployment rate, MSA (%, NSA)",
    "CUURS49ASA0": "CPI-U, Los Angeles area, all items (NSA) - deflator",
    "CUSR0000SEHB": "CPI-U, US, lodging away from home (SA) - hotel price proxy",
}

# Fiscal years ending June 2020-2022 contain the pandemic collapse and rebound.
# Flagged so EDA/backtests can show results with and without them.
COVID_SHOCK_FYS = (2020, 2021, 2022)

# Benchmarks quoted in the proposal, used to reconcile our derived numbers.
PROPOSAL_BENCHMARKS = {
    "live_and_work_in_ontario": 12_377,
    "employed_residents": 79_826,
    "inflow_commuters": 123_552,
    "tot_fy27_budget": 18_500_000,
    "sales_tax_fy27_budget": 216_300_000,
}
