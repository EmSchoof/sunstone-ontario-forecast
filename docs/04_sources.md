# Sources

[← README](../README.md) · [Decisions](01_decisions.md) · [Methods](02_methods.md) · [Conclusions](03_conclusions.md)

Every number and every piece of content in this repository comes from one of the five groups below.
This page is the single register: where each one comes from, where it lives in the repo, and whether
the file itself is tracked in git or rebuilt by the pipeline.

`ontario_forecast_model/src/fiscal_impact_model/tests/test_sources_doc.py` fails if a download, a reference file, an assumptions file or a BLS series
is added to the code without being listed here.

**How to read "Tracked in git":**
- **Yes** means the file is committed, so a reader sees exactly what the team used.
- **Rebuilt** means the raw download isn't committed (it's large and public). The code that fetches it is
  committed, and `outputs/tables/source_snapshot.csv` records how many rows were loaded and when.

## 1. Downloaded public data

Fetched by `ontario_forecast_model/src/fiscal_impact_model/ingest/sources.py` into the `raw` schema of the local DuckDB warehouse.
Endpoints and IDs live only in `ontario_forecast_model/src/fiscal_impact_model/config.py`.

| Raw table | Publisher and dataset | Endpoint / ID | What we use | Tracked in git |
|---|---|---|---|---|
| `sco_city_revenue_lines` | California State Controller, *City - Revenues* (Local Government Financial Data) | `https://bythenumbers.sco.ca.gov/resource/rrtv-rsj9.json` | Hotel tax, sales tax (Bradley-Burns and in-lieu), Measure Q and population for Ontario and 10 peer cities, FY2003+. Measure Q has no line of its own: it sits under "Other Taxes – Other (Specify)", confirmed against the City budget for FY2025 ($61,594,662 in both) | Rebuilt |
| `laus_city_monthly` | California EDD, Local Area Unemployment Statistics (monthly) | data.ca.gov CKAN package `59218446-5760-4683-b52e-f6210021840a` | City labor force, employment and unemployment, not seasonally adjusted | Rebuilt |
| `bls_observations` | U.S. Bureau of Labor Statistics, public API v2 | `https://api.bls.gov/publicAPI/v2/timeseries/data/` | The six series listed below | Rebuilt |
| `qcew_county_annual` | BLS Quarterly Census of Employment and Wages, open data | `https://data.bls.gov/cew/data/api/{year}/a/area/06071.csv` | San Bernardino County employment and pay by sector, 2014+ | Rebuilt |
| `oews_msa_occupations` | BLS Occupational Employment and Wage Statistics, via the BLS API (OE series) | MSA code `0040140`; occupations in `config.OEWS_OCCUPATIONS` | Median and mean wages for the proposal's 14 pathway occupations | Rebuilt |
| `lodes_ontario_flows` | U.S. Census Bureau, LEHD LODES 8 origin-destination files (JT00, main + aux) and the CA block crosswalk | `https://lehd.ces.census.gov/data/lodes/LODES8/ca` | Residents, jobs and live-and-work counts for Ontario by year, 2002+ | Rebuilt |
| `acs_place` | U.S. Census Bureau, American Community Survey 5-year, via the Census API (free key) | `https://api.census.gov/data/{year}/acs/acs5` | Tables B08008, B08303, B15003, B19013 for Ontario city and San Bernardino County, 2010+ | Rebuilt |

**BLS series** (`config.BLS_SERIES`):

| Series ID | What it is |
|---|---|
| `SMU06401400000000001` | Total nonfarm jobs, Riverside-San Bernardino-Ontario MSA |
| `SMU06401407000000001` | Leisure and hospitality jobs, MSA |
| `SMU06401404300000001` | Transportation and warehousing jobs, MSA |
| `LAUMT064014000000003` | Unemployment rate, MSA |
| `CUURS49ASA0` | CPI-U, Los Angeles area, all items (the deflator) |
| `CUSR0000SEHB` | CPI-U, U.S., lodging away from home (hotel price proxy) |

All of these are U.S. or California government publications and are free to reuse. Geography codes:
Ontario place FIPS `0653896`, San Bernardino County FIPS `06071`.

## 2. Hand-entered official data (reference files in `data/`)

Official figures that have no download API. Each row has a `source` column citing the document and page.
Loaded as `raw.manual_<file>`. File layout and rules: [Methods A6](02_methods.md#a6-input-data-data).

**Source document:** City of Ontario, *Fiscal Year 2026-27 Adopted Annual Operating Budget* (506-page PDF),
from the City's [Budget and Financial Reports page](https://www.ontarioca.gov/government/financial-services/budget-and-financial-reports).
Page numbers below are PDF page numbers. **The PDF is 182 MB, over GitHub's 100 MB file limit, so it is not
committed**; the figures taken from it are.

| File | Source | Status | Tracked in git |
|---|---|---|---|
| `city_budget_revenue.csv` | Budget book, General Fund revenue detail, PDF p. 69 | Filled for FY2027: hotel tax $18,500,000; sales tax $216,255,543 (includes Prop 172 and Measure Q) | Yes |
| `city_sales_tax_detail.csv` | Same page | Filled: FY2025 actual, FY2026 adopted and current, FY2027 adopted, each split into Sales & Use (Bradley-Burns), Prop 172 and Measure Q | Yes |
| `ont_airport_passengers.csv` | Ontario International Airport monthly traffic reports (flyontario.com) | **Empty template** | Yes |

## 3. Model inputs (impact-model files in `data/`, see [Methods A6](02_methods.md#a6-input-data-data))

Every impact-model input, with a `status` (`official`, `published` for peer-reviewed or industry benchmarks,
`proposal` or `assumption`) and a `source` on each
row. The files are the register; `outputs/tables/impact_inputs_used.csv` is the copy the last run used.

| File | What it holds | Tracked in git |
|---|---|---|
| `impact_assumptions.csv` | Every numeric input as a low / likely / high range | Yes |
| `anchor_visitors.csv` | Visitors, overnight share and arrival share per venue | Yes |
| `impact_phases.csv` | Start and full-scale year per recommendation (proposal §5) | Yes |
| `city_investments.csv` | How each City investment maps to the model | Yes |

Rows marked `TEAM ASSUMPTION` have **no external source yet**. The row's source text names where a
sourced value should come from; they are placeholders, not citations.

**Official facts entered by hand in these files:**

| Input | Value | Source | Checked |
|---|---|---|---|
| `local_sales_tax_rate` | 1% | California Revenue and Taxation Code §7202 (Bradley-Burns local rate) | not re-checked |
| `measure_q_rate` | 1% | Budget book PDF p. 14 and p. 64: 1% transactions and use tax on destination-based taxable sales, effective April 1, 2023; the City receives 1% Bradley-Burns plus 1% Measure Q. Also <https://www.ontarioca.gov/MeasureQ> | 2026-11-16 |
| Airport `arrival_share` | 0.5 | ONT airport statistics, January 2024: 235,084 deplaned of 469,589 total passengers ([PDF](https://zh.flyontario.com/sites/default/files/2024-03/ont_airport_statistics_-_jan_2024_0.pdf)) | 2026-11-16 |
| Airport annual passengers | 7M+ | Proposal §3; consistent with ONT's 2024 total of 7,084,796 ([press release](https://prnewswire.com/news-releases/ontario-international-airport-passenger-count-soared-past-7-million-in-2024-302359212.html)) | 2026-11-16 |
| `pathway_wage` | OEWS range | Replaced at run time by BLS OEWS medians (section 1) | each run |
| `discount_rate` | 2–5% | Team assumption, anchored on OMB Circular A-4 (2% in the 2023 edition, 3% in 2003). Confirm the rate City Finance uses | not re-checked |
| `tot_rate` | 11.75% | Budget book PDF p. 66, citing Ontario Municipal Code §3-6.03 | 2026-11-16 |
| `hotel_rooms` | 5,670 rooms (52 hotels/motels) | Budget book PDF p. 66. About 2.07M room-nights of capacity a year | 2026-11-16 |
| `persons_per_household` | 3.37 (range 3.0–3.6) | U.S. Census Bureau [QuickFacts, Ontario city](https://census.gov/quickfacts/fact/table/ontariocitycalifornia/PST040223), ACS 2019–2023 | 2026-11-20 |
| Airport visitors (`anchor_visitors.csv`) | 7,084,796 passengers, CY2024 | Ontario International Airport Authority ([press release](https://prnewswire.com/news-releases/ontario-international-airport-passenger-count-soared-past-7-million-in-2024-302359212.html)); FAA [CY2024 enplanements](https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/arp-cy2024-commercial-service-enplanements.pdf): 3,494,554, confirming about half are departures | 2026-11-20 |
| `r1_conversion` (status `published`) | 30–63%, likely 46% | NACE Internship & Co-op Survey: [2025 report](https://naceweb.org/talent-acquisition/internships/intern-offer-and-conversion-rates-fall-acceptances-rise) (46% hybrid, 58.5% in-person, 2023-24 interns) and [2026 report](https://naceweb.org/talent-acquisition/internships/intern-conversion-rate-hits-highest-mark-in-five-years) (63.1%, 2024-25). National employer sample, so local and smaller employers are likely lower | 2026-11-20 |

**Program costs** (status `proposal`). The draft states each program's total cost but not how it splits between the
City and partners, so the model uses the stated **full program cost** and doesn't assume a split:

| Input | Range used | Source |
|---|---|---|
| `cost_R1` | $75K–$150K | Draft budget table: staffing and project management |
| `cost_R2_marketing` | $100K–$250K | Draft budget table: technology, data, marketing and outreach. For context, Economic Development's General Fund advertising budget is $900K in FY27 (budget book PDF p. 183) |
| `cost_R2_circulator` | $190K–$225K | Draft: 1,248 vehicle-hours at Omnitrans' $154 per vehicle revenue hour. The City's $120K Internal Circulator Planning Study, due December 2026 (PDF pp. 408, 487), should confirm cost and funding |
| `cost_R3` | $350K–$550K | Draft: small supervised Downtown pilot. DOIA already funds a maintenance ambassador program from its property assessment ([City page](https://ontarioca.gov/node/22583)); the City pays DOIA assessments on its own parcels (PDF p. 100) |

Reported results use only the low and high ends of these ranges. A midpoint is stored because the simulation needs
one, but no simulated result is reported while any input behind it is unsourced (see section 6).

**Safety baseline:** Ontario Police Department reports 380 encampments cleaned up and 105 cases of assistance
accepted by unhoused individuals (budget book PDF p. 319), about 28%, a usable baseline for the R3
service-acceptance measure.
| `adr` (room rate) | derived each run | Hotel tax (State Controller) ÷ `tot_rate` ÷ `hotel_rooms` ÷ 365 ÷ `hotel_occupancy`. Occupancy (60–75%) is a team assumption until STR or visitors-bureau data replaces it | each run |

## 4. The proposal and what it cites

The team's proposal, *Connecting Ontario: Building the Inland Empire's Next Generation Economy*, is the
content source for the recommendations, phases, budget and the figures in [Background](00_background.md).

> **Gap: the proposal document is not in this repository.** Add it (for example `docs/reference/proposal.pdf`)
> or record where the authoritative copy lives, so the section references below can be checked.

Proposal figures used in the code live in `config.PROPOSAL_BENCHMARKS` and `config.PROPOSAL_MEDIAN_WAGES`.
They are fallbacks: `outputs/tables/headline_metrics.csv` shows, per metric, whether the official value
or the proposal fallback was used (`is_fallback`).

| Proposal content | Proposal section | Underlying source named by the proposal | In this repo |
|---|---|---|---|
| Live/work figures (15.5%, 12,377 of 79,826; 123,552 inbound) | §1, §3 | Census OnTheMap / LEHD | Rebuilt from LODES (section 1) once loaded |
| Regional median wages by occupation | §3 | not recorded here | Replaced by BLS OEWS |
| Venue visitors (ONT, Mills, Toyota Arena, Sports Empire) | §3 | Sports Empire is a City projection; others not recorded here | `anchor_visitors.csv`, status `proposal` |
| ONT economic output (~$4.8B, ~24,300 jobs, 2024) | §3 | not recorded here | Quoted in Background only; not a model input |
| Average visitor stay (~2.6 days) | §3 | not recorded here | Quoted as a KPI only; not a model input |
| Business concerns (homelessness ~38%, safety ~36%, costs ~31%) | §3 | City of Ontario Business Outreach Survey | Quoted in Background only |
| FY2026–27 General Fund: ~$216.3M sales tax, ~$18.5M hotel tax | §1 | City of Ontario FY2026–27 budget | **Confirmed** against the budget book (`city_budget_revenue.csv`): $216,255,543 and $18,500,000 |
| Transit pilot cost (~$154 per vehicle-hour) | §6 | Omnitrans FY2026 fixed-route plan | Total for `cost_R2_circulator` |
| City cost per recommendation; $500K Year 1 cap | §6 | Proposal budget | `impact_assumptions.csv`, status `proposal` |
| Phases (0–6, 6–18, 18–36 months, 3–10 years) | §5 | Proposal | `impact_phases.csv` |

"Not recorded here" means the proposal quotes the figure but this repository doesn't hold the original
citation. Fill these in from the proposal's own reference list.

## 5. Outputs, documents and tools

| Item | Where | How it's produced | Tracked in git |
|---|---|---|---|
| Charts | `outputs/charts/` | `ontario_forecast_model/analysis/03_scenarios.py` and `04_impact.py` | Yes |
| Tables behind every chart, plus the analysis-ready marts | `outputs/tables/` | Same scripts and `transform/run.py` | Yes |
| What was loaded and when | `outputs/tables/source_snapshot.csv` | `transform/run.py` | Yes |
| Fitted forecast models | `outputs/models/` | `ontario_forecast_model/analysis/02_variable_selection.py` | Yes |
| Shareable PDFs of the docs | `outputs/docs/` | `reporting/pdf.py` from `docs/*.md` | Yes |
| Exploratory figures | `outputs/eda/` | `ontario_forecast_model/analysis/01_eda.py` | No (rebuilt) |
| Raw downloads and the warehouse | `data/warehouse/` | `ingest/run.py` | No (rebuilt) |
| API keys | `ontario_forecast_model/.dlt/secrets.toml` | Entered by each user | No (never commit) |

Written content in `docs/` and the README is the team's own. The README layout follows
[Best-README-Template](https://github.com/othneildrew/Best-README-Template). Software dependencies and
their exact versions are in `ontario_forecast_model/` (`pyproject.toml`, `uv.lock`, `package.json`, `pnpm-lock.yaml`).

## 6. What is reported, and what isn't

The model reports a result only when every input behind it has a source (`official`, `published` or `proposal`).

- **Reported:** the status-quo forecasts (fitted to State Controller data and tested on years the model hadn't
  seen) and the **break-even targets** in `outputs/tables/impact_break_even_targets.csv`, which use only official
  tax rates, actual tax revenue and the proposal's stated costs.
- **Not reported:** projected returns per dollar, net fiscal impact, residents added and similar simulated
  results. Each depends on inputs that are still team estimates. `outputs/tables/impact_evidence_gaps.csv` lists
  every one, by recommendation, with where to source it. Once a recommendation's list is empty, the model reports
  its projected return automatically.

## Open items

1. Add the proposal document, or a pointer to it (section 4).
2. Fill `ont_airport_passengers.csv` (section 2).
3. Record where the team keeps the budget book PDF, since it's too large to commit (section 2).
4. Replace the `TEAM ASSUMPTION` rows, starting with the ones at the top of the sensitivity chart.
5. Record the original citations for the proposal figures marked "not recorded here" (section 4).
