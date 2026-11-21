"""Single source of truth for paths, geography and source identifiers."""

from __future__ import annotations

from pathlib import Path

# ---- Paths ---------------------------------------------------------------
# Repository layout: the reader-facing folders (README, docs/, data/, outputs/) sit at the
# repository root; the model's code and tooling live in ontario_model/.
PROJECT_DIR = Path(__file__).resolve().parents[2]  # ontario_model/ (pyproject, analysis/)
ROOT = PROJECT_DIR.parent  # repository root

# Inputs
DATA_DIR = ROOT / "data"  # every input CSV lives here (see "Input data" in docs/02_methods.md)
# Hand-entered official figures with no download API: loaded by dlt as raw.manual_<file stem>.
REFERENCE_FILES = (
    DATA_DIR / "city_budget_revenue.csv",
    DATA_DIR / "city_sales_tax_detail.csv",
    DATA_DIR / "ont_airport_passengers.csv",
)
WAREHOUSE = DATA_DIR / "warehouse" / "ontario.duckdb"  # dlt loads raw.*; SQL builds staging.*, marts.*
PIPELINES_DIR = ROOT / ".dlt_pipelines"  # dlt state (git-ignored)

# Outputs: everything the pipeline writes
OUTPUTS_DIR = ROOT / "outputs"
CHARTS_DIR = OUTPUTS_DIR / "charts"  # deliverable PNG / SVG / PDF (tracked)
TABLES_DIR = OUTPUTS_DIR / "tables"  # charted numbers + analysis-ready marts as CSV (tracked)
MODELS_DIR = OUTPUTS_DIR / "models"  # fitted model JSON (tracked)
EDA_DIR = OUTPUTS_DIR / "eda"  # exploratory figures (git-ignored)
DOCS_PDF_DIR = OUTPUTS_DIR / "docs"  # shareable PDFs of docs/*.md (tracked)

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
        "label": "hotel tax",
        "source": "CA State Controller city revenues (Transient Occupancy / Transient Lodging Tax).",
        "budget_metric": "tot_fy27_budget",
    },
    "sales_tax": {
        "growth": "dlog_sales_tax_real",
        "level_real": "sales_tax_total_real",
        "level": "sales_tax_total",
        "label": "sales tax, excluding Measure Q",
        "source": (
            "CA State Controller city revenues (Bradley-Burns sales tax incl. in-lieu payments, FY2005-16); "
            "excludes Measure Q and Prop 172."
        ),
        # Bradley-Burns part of the budget only: the forecast series excludes Measure Q / Prop 172
        "budget_metric": "sales_tax_bradley_burns_fy27_budget",
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

# Recommendation impact model (analysis/04_impact.py)
# Impact-model inputs: read directly by the model, never ingested.
IMPACT_ASSUMPTIONS = DATA_DIR / "impact_assumptions.csv"
IMPACT_PHASES = DATA_DIR / "impact_phases.csv"
ANCHOR_VISITORS = DATA_DIR / "anchor_visitors.csv"
CITY_INVESTMENTS = DATA_DIR / "city_investments.csv"
IMPACT_INPUT_FILES = (IMPACT_ASSUMPTIONS, IMPACT_PHASES, ANCHOR_VISITORS, CITY_INVESTMENTS)
IMPACT_HORIZON = 11  # FY2026-FY2036: 10 years after the FY2027 launch
IMPACT_WINDOWS = {"Short term (FY27-29)": (2027, 2029), "Long term (FY30-36)": (2030, 2036)}
# Headline return on investment: every year the City pays, start-up years included,
# in present value. The short/long windows above only show how returns mature.
IMPACT_ROI_WINDOW = ("Whole program (FY27-36)", (2027, 2036))
IMPACT_SIMS = 20_000
# Recommendations in the current proposal draft (headline and "All recommendations").
# R4 and the R1->R4 link are still simulated and reported separately as a possible later phase.
IMPACT_RECS = ("R1", "R2", "R3")

# What-if scenarios (analysis/04_impact.py): ONE unknown per recommendation, shown at round steps
# chosen to sit below, within and above its break-even range. These are scenarios, not predictions;
# everything else in each row is official data or the proposal's stated costs.
WHAT_IF_NAMES = ("Smaller", "Middle", "Larger")
WHAT_IF_LEVELS = {
    "R2": (0.01, 0.02, 0.03),  # rise in citywide hotel tax, share of the latest fiscal year
    "R3": (10e6, 20e6, 30e6),  # net new in-person Downtown taxable sales per year, USD
    "R1": (100, 250, 500),  # more Ontario residents working in Ontario
}

# Baseline model selection (analysis/02): a model replaces "same as last year" only if it
# cuts the out-of-sample error by at least this share, with AND without the COVID years.
# With ~8 test years and ~9 models tried, smaller edges are indistinguishable from luck.
SELECTION_MIN_GAIN = 0.10

# Fiscal years ending June 2020-2022 contain the pandemic collapse and rebound.
# Flagged so EDA/backtests can show results with and without them.
COVID_SHOCK_FYS = (2020, 2021, 2022)

# Figures quoted in the proposal text. FALLBACK ONLY: any metric with an official
# source (State Controller, Census, BLS, City adopted budget in data/) uses that
# value first; see marts.headline_metrics (is_fallback flags proposal-only values).
# metric -> (period, value); period None = not stated in the proposal.
# metric -> (period, value, source). The live/work figures are the ones the proposal cites
# (its reference 4), checked against the plan on 2026-11-20; inflow = 126,883 jobs - 11,107.
LHMP_COMMUTE = "City of Ontario 2023 Local Hazard Mitigation Plan, p. 20 (Census OnTheMap, 2019)"
PROPOSAL_BENCHMARKS = {
    "share_residents_work_local": (2019, 0.148, LHMP_COMMUTE),
    "share_jobs_held_by_residents": (2019, 0.088, LHMP_COMMUTE),
    "live_and_work_in_ontario": (2019, 11_107, LHMP_COMMUTE),
    "employed_residents": (2019, 75_283, LHMP_COMMUTE),
    "inflow_commuters": (2019, 115_776, LHMP_COMMUTE + "; 126,883 jobs minus 11,107 held by residents"),
    "tot_fy27_budget": (2027, 18_500_000, "Proposal budget figure"),
    "sales_tax_fy27_budget": (2027, 216_300_000, "Proposal budget figure"),
}
# The proposal's executive summary also quotes about 15.5% (12,377 of 79,826) with no source recorded.
# Not a model input: 01_eda.py only checks which LODES year it matches once LODES is loaded.
PROPOSAL_SUMMARY_LIVE_AND_WORK = 12_377
