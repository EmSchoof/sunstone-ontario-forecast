"""Single source of truth for paths, geography and source identifiers."""

from __future__ import annotations

from pathlib import Path

# ---- Paths ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
WAREHOUSE = DATA_DIR / "warehouse" / "ontario.duckdb"  # dlt loads raw.*; SQL builds staging.*, marts.*
PROCESSED_DIR = DATA_DIR / "processed"  # exported marts (parquet + csv) for sharing
MANUAL_DIR = DATA_DIR / "manual"  # hand-entered data (airport, budget docs)
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
MODELS_DIR = ROOT / "models"
PIPELINES_DIR = ROOT / ".dlt_pipelines"  # dlt state, kept inside the project

# ---- Geography -----------------------------------------------------------
CITY = "Ontario"
PEER_CITIES = (
    "Rancho Cucamonga",
    "Fontana",
    "Chino",
    "Chino Hills",
    "Upland",
    "Montclair",
    "Pomona",
    "Riverside",
    "San Bernardino",
    "Corona",
)
ALL_CITIES = (CITY, *PEER_CITIES)
ONTARIO_PLACE_FIPS = "0653896"  # state 06 + Census place 53896
SB_COUNTY_FIPS = "06071"  # San Bernardino County

# ---- Sources -------------------------------------------------------------
SCO_BASE_URL = "https://bythenumbers.sco.ca.gov/resource/"
SCO_CITY_REVENUES = "rrtv-rsj9.json"  # Socrata dataset: City - Revenues
CKAN_PACKAGE_SHOW = "https://data.ca.gov/api/3/action/package_show"
LAUS_MONTHLY_PACKAGE = "59218446-5760-4683-b52e-f6210021840a"  # EDD LAUS (monthly)
BLS_FIRST_YEAR = 1990  # monthly CES/LAUS/CPI history requested from the BLS API
QCEW_AREA_URL = "https://data.bls.gov/cew/data/api/{year}/a/area/{area}.csv"
QCEW_FIRST_YEAR = 2014
LODES_BASE = "https://lehd.ces.census.gov/data/lodes/LODES8/ca"
LODES_FIRST_YEAR = 2002

# BLS series_id -> (panel column name, description). The ONLY place series IDs live:
# transform/run.py loads this as staging.bls_series and the SQL pivots by column name.
# Requested from the BLS API directly (primary source; FRED only republishes these).
BLS_SERIES = {
    "SMU06401400000000001": (
        "msa_nonfarm_jobs_k",
        "CES total nonfarm jobs, Riverside-San Bernardino-Ontario MSA (thousands, NSA)",
    ),
    "SMU06401407000000001": ("msa_leisure_jobs_k", "CES leisure & hospitality jobs, MSA (thousands, NSA)"),
    "SMU06401404300000001": (
        "msa_transport_jobs_k",
        "CES transportation & warehousing jobs, MSA (thousands, NSA)",
    ),
    "LAUMT064014000000003": ("msa_unemployment_rate", "LAUS unemployment rate, MSA (%, NSA)"),
    "CUURS49ASA0": ("cpi_la", "CPI-U, Los Angeles area, all items (NSA) - deflator"),
    "CUSR0000SEHB": ("cpi_us_lodging", "CPI-U, US, lodging away from home (SA) - hotel price proxy"),
}

# Revenue forecast targets, shared by 02 (selection) and 03 (scenarios).
FORECAST_TARGETS = {
    "tot": {
        "growth": "dlog_tot_real",
        "level_real": "tot_revenue_real",
        "level": "tot_revenue",
        "label": "Transient Occupancy Tax (hotel tax)",
        "budget_metric": "tot_fy27_budget",
    },
    "sales_tax": {
        "growth": "dlog_sales_tax_real",
        "level_real": "sales_tax_total_real",
        "level": "sales_tax_total",
        "label": "Sales & use tax",
        "budget_metric": "sales_tax_fy27_budget",
    },
}

# Census ACS 5-year (needs a free key: CENSUS_API_KEY env var or .dlt/secrets.toml)
ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"
ACS_FIRST_YEAR = 2010
ACS_GROUPS = {
    "B08008": "Place of work: worked in place of residence (cross-checks LODES 15.5%)",
    "B08303": "Travel time to work",
    "B15003": "Educational attainment, population 25+ (Career Pathways baseline)",
    "B19013": "Median household income",
}
# 5-year estimates overlap (2019 = 2015-19). Only non-overlapping vintages are compared.
ACS_NONOVERLAPPING_VINTAGES = (2014, 2019, 2024)

# BLS OEWS, Riverside-San Bernardino-Ontario MSA wages by occupation (BLS API v2;
# optional BLS_API_KEY raises the daily limit). SOC code -> (title, proposal pathway)
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
OEWS_MSA = "0040140"
OEWS_DATATYPES = {"01": "employment", "04": "mean_annual_wage", "13": "median_annual_wage"}
OEWS_OCCUPATIONS = {
    "000000": ("All occupations", "benchmark"),
    "172112": ("Industrial engineers", "Engineering & infrastructure"),
    "172071": ("Electrical engineers", "Engineering & infrastructure"),
    "113071": ("Transportation, storage & distribution managers", "Logistics & operations"),
    "131081": ("Logisticians", "Logistics & operations"),
    "531047": ("First-line supervisors, transportation & material moving", "Logistics & operations"),
    "537062": ("Laborers & freight, stock & material movers", "Logistics entry"),
    "537065": ("Stockers & order fillers", "Logistics entry"),
    "472111": ("Electricians", "Green economy & trades"),
    "499021": ("HVAC mechanics & installers", "Green economy & trades"),
    "131121": ("Meeting, convention & event planners", "Visitor & entertainment"),
    "434081": ("Hotel, motel & resort desk clerks", "Visitor entry"),
    "353031": ("Waiters & waitresses", "Visitor entry"),
    "412031": ("Retail salespersons", "Visitor entry"),
}
# Proposal's quoted regional median wages. OEWS values take precedence (msa_occupation_wages).
PROPOSAL_MEDIAN_WAGES = {
    "17-2112": 101_700,
    "11-3071": 98_700,
    "13-1081": 77_370,
    "53-1047": 69_920,
    "13-1121": 63_850,
}

# Scenario export
SCENARIO_HORIZON = 5  # fiscal years ahead
SCENARIO_SIMS = 20_000
SCENARIO_SEED = 20261115  # fixed for reproducible charts
SCENARIO_QUANTILES = (0.10, 0.50, 0.90)
LODES_COVID_YEARS = (2020, 2021)  # calendar years (LODES); revenue uses COVID_SHOCK_FYS
FINAL_DIR = REPORTS_DIR / "final"

# Recommendation impact model (analysis/04_impact.py)
IMPACT_ASSUMPTIONS = MANUAL_DIR / "impact_assumptions.csv"
IMPACT_PHASES = MANUAL_DIR / "impact_phases.csv"
ANCHOR_VISITORS = MANUAL_DIR / "anchor_visitors.csv"
CITY_INVESTMENTS = MANUAL_DIR / "city_investments.csv"
IMPACT_HORIZON = 11  # FY2026-FY2036: 10 years after the FY2027 launch
IMPACT_WINDOWS = {"Short term (FY27-29)": (2027, 2029), "Long term (FY30-36)": (2030, 2036)}
IMPACT_SIMS = 20_000

# Fiscal years ending June 2020-2022 contain the pandemic collapse and rebound.
# Flagged so EDA/backtests can show results with and without them.
COVID_SHOCK_FYS = (2020, 2021, 2022)

# Figures quoted in the proposal text. FALLBACK ONLY: any metric with an official
# source (State Controller, Census, BLS, City adopted budget in data/manual/) uses that
# value first; see marts.headline_metrics (is_fallback flags proposal-only values).
# metric -> (period, value); period None = not stated in the proposal.
PROPOSAL_BENCHMARKS = {
    "share_residents_work_local": (None, 0.155),
    "share_jobs_held_by_residents": (None, 0.091),
    "live_and_work_in_ontario": (None, 12_377),
    "employed_residents": (None, 79_826),
    "inflow_commuters": (None, 123_552),
    "tot_fy27_budget": (2027, 18_500_000),
    "sales_tax_fy27_budget": (2027, 216_300_000),
}
