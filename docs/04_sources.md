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
| Airport annual passengers | 7M+ | Proposal §3; consistent with ONT's 2024 total of 7,084,864 ([press release](https://prnewswire.com/news-releases/ontario-international-airport-passenger-count-soared-past-7-million-in-2024-302359212.html)) | 2026-11-16 |
| `pathway_wage` | OEWS range | Replaced at run time by BLS OEWS medians (section 1) | each run |
| `discount_rate` | 2–5% | Team assumption, anchored on OMB Circular A-4 (2% in the 2023 edition, 3% in 2003). Confirm the rate City Finance uses | not re-checked |
| `tot_rate` | 11.75% | Budget book PDF p. 66, citing Ontario Municipal Code §3-6.03 | 2026-11-16 |
| `hotel_rooms` | 5,670 rooms (52 hotels/motels) | Budget book PDF p. 66. About 2.07M room-nights of capacity a year | 2026-11-16 |
| `persons_per_household` | 3.37 (range 3.0–3.6) | U.S. Census Bureau [QuickFacts, Ontario city](https://census.gov/quickfacts/fact/table/ontariocitycalifornia/PST040223), ACS 2019–2023 | 2026-11-20 |
| Airport visitors (`anchor_visitors.csv`) | 7,084,864 passengers, 2024 (stated in the release's text, Jan. 23, 2025; its table shows 7,084,796, which doesn't match the release's own domestic + international totals) | Ontario International Airport Authority ([press release](https://prnewswire.com/news-releases/ontario-international-airport-passenger-count-soared-past-7-million-in-2024-302359212.html)); FAA [CY2024 enplanements](https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/arp-cy2024-commercial-service-enplanements.pdf): 3,494,554, confirming about half are departures | 2026-11-20 |
| `r1_conversion` (status `published`) | 30–63%, likely 46% | NACE Internship & Co-op Survey: [2025 report](https://naceweb.org/talent-acquisition/internships/intern-offer-and-conversion-rates-fall-acceptances-rise) (46% hybrid, 58.5% in-person, 2023-24 interns) and [2026 report](https://naceweb.org/talent-acquisition/internships/intern-conversion-rate-hits-highest-mark-in-five-years) (63.1%, 2024-25). National employer sample, so local and smaller employers are likely lower | 2026-11-20 |

**Program costs** (status `proposal`). The proposal states each program's total cost but not how it splits between the
City and partners, so the model uses the stated **full program cost** and doesn't assume a split:

| Input | Range used | Source |
|---|---|---|
| `cost_R1` | $75K–$150K | Draft budget table: staffing and project management |
| `cost_R2_marketing` | $100K–$250K | Draft budget table: technology, data, marketing and outreach. For context, Economic Development's General Fund advertising budget is $900K in FY27 (budget book PDF p. 183) |
| `cost_R2_circulator` | $190K–$225K | Draft: 1,248 vehicle-hours at about $154 per revenue hour. **Verified 2026-11-20:** Omnitrans *Service Plan FY2026* (May 7, 2025), Exhibit 10, PDF p. 13 projects FY2026 fixed-route operating costs of $95,293K over 620K revenue hours = $153.70 per revenue hour (calculated; the plan doesn't print a per-hour figure). The City's $120K Internal Circulator Planning Study, due December 2026 (PDF pp. 408, 487), should confirm cost and funding |
| `cost_R3` | $350K–$550K | Draft: small supervised Downtown pilot. DOIA administers the Downtown Ontario Community Benefit Improvement District, which it says is "funded entirely by the property and business owners of Downtown Ontario", with security and case-worker services among its planned improvements ([About DOIA](https://downtownontario.org/about-doia/), read 2026-11-20); the City pays DOIA assessments on its own parcels (budget book PDF p. 100) |

Reported results use only the low and high ends of these ranges. A midpoint is stored because the simulation needs
one, but no simulated result is reported while any input behind it is unsourced (see section 6).

**Safety baseline:** Ontario Police Department reports 380 encampments cleaned up and 105 cases of assistance
accepted by unhoused individuals (budget book PDF p. 319), about 28%, a usable baseline for the R3
service-acceptance measure.
| `adr` (room rate) | derived each run | Hotel tax (State Controller) ÷ `tot_rate` ÷ `hotel_rooms` ÷ 365 ÷ `hotel_occupancy`. Occupancy (60–75%) is a team assumption until STR or visitors-bureau data replaces it | each run |

## 4. The proposal and what it cites

The team's proposal, *Connecting Ontario: Building the Inland Empire's Next Generation Economy*, is the
content source for the recommendations, phases, budget and the figures in [Background](00_background.md).

> **The proposal document is kept out of this repository on purpose.** The team holds the submission; the
> repository records only the proposal figures the model uses, in the table below.

Proposal figures used in the code live in `config.PROPOSAL_BENCHMARKS` and `config.PROPOSAL_MEDIAN_WAGES`.
They are fallbacks: `outputs/tables/headline_metrics.csv` shows, per metric, whether the official value
or the proposal fallback was used (`is_fallback`).

Each proposal figure the repository uses or quotes, with the proposal reference it rests on and what that source
actually says (checked 2026-11-20). Reference numbers follow the proposal's reference list.

| Proposal content | Proposal ref. | Checked against the source | In this repo |
|---|---|---|---|
| Ontario Mills: 28 million annual visitors | 1. City of Ontario, *Hospitality and tourism* | **Confirmed** (undated page) | `anchor_visitors.csv`, status `official` |
| ONT: 6.4 million passengers in 2023 | 1 | **Confirmed** ("12% surge over 2022") | Model uses the newer 2024 total, 7,084,864 (airport press release, Jan. 23, 2025) |
| Toyota Arena: about 730K annual visitors | 1 | **Confirmed** ("Approximately 730K annual visitors & 200 events") | `anchor_visitors.csv`, status `official` |
| Ontario Mills ~12M, Toyota Arena ~1.2M (the proposal's context section) | none | **No source found.** The City's own figures are 28M (Mills) and 728K–730K (Toyota Arena): ref. 1, and the City's [*Hospitality & Tourism* one-pager](https://content.ontarioca.gov/sites/default/files/2024-05/ONE-PAGER%20HOSPITALITY%20%26%20TOURISM_0.pdf) (May 2024: "28M annual shoppers", "728K event attendees"). The one-pager's "1.2 million new visitors annually" refers to the new 200-acre sports complex, not Toyota Arena | The model uses 28M and 730K (ref. 1) |
| Ontario Sports Empire ~1.2M visitors | none | **Confirmed** in the City budget book, p. 453 (a projection for the Sports Empire and retail phase) | `anchor_visitors.csv`, status `official` |
| Hotel rooms | none | Ref. 1 lists 5,461; the FY2026–27 budget book (p. 66) lists 5,670 | Model uses the budget book (newer, official) |
| ONT output ~$4.8B, ~24,300 jobs (2024) | none | **Source found:** Ontario International Airport, [press release](https://flyontario.com/press/independent-study-validates-decade-local-control-ontario-international-airports-economic-0) (Aug. 11, 2026) on an Oxford Economics study: "Ontario International Airport generated $4.8 billion in annual economic output in 2024, supporting 24,300 jobs and contributing $3 billion in regional gross domestic product". The source attributes the figures to the airport's economic impact | Not a model input |
| Average visitor stay ~2.6 days | none | **No source found.** The closest: GOCAL's 2023–24 annual report, as reported in a [July 31, 2024 release](https://www.prnewswire.com/news-releases/ontario-international-airport-helps-greater-ontarios-hospitality-industry-reach-record-levels-302211662.html): "Domestic visitors stayed in the area for 2.5 days, on average"; international visitors 3.4 days | Not a model input |
| Live/work: 14.8% of employed residents work in Ontario; residents hold 8.8% of jobs (2019) | 4. City of Ontario, *Local Hazard Mitigation Plan* (2023, adopted Nov 21, 2023) | **Confirmed**, p. 20: "As of 2019, 75,283 Ontario residents are employed, with approximately 11,107 (14.8%) working within the city. This local workforce accounts for 8.8% of the entire workforce, approximately 126,883 employees" (citing Census OnTheMap). The link with `%2520` in it is correct | `config.PROPOSAL_BENCHMARKS` (2019 values); Census LODES replaces them once loaded |
| Live/work about 15.5% (executive summary; 12,377 of 79,826) | none | **No source found online.** Not in ref. 4 (2019: 11,107 of 75,283). Likely a later Census OnTheMap year: once LODES is loaded, `01_eda.py` reports which year's live-and-work count matches 12,377 | The model uses the cited 2019 figures (14.8%, 8.8%) |
| City's share of the ambassador pilot from the existing Homeless Services allocation (~$4.5M) | none (City budget) | **Confirmed**: $4,450,688 General Fund, Homeless Services (budget book p. 141) | Context only; the break-even target applies to whatever share the City pays |
| Business concerns (homelessness ~38%, safety ~36%, costs ~31%, traffic and permitting ~21%) | 7. City of Ontario, *Business Outreach Survey* | **Not checked**: the survey isn't published online | Quoted in Background only, labelled as reported in the proposal |
| UpSkill Houston and the $17M Bloomberg investment | 3. Alvarez, R. (2026, August 5), Greater Houston Partnership | **Partly**: the $17M went to Gulf Coast TradeUp Careers, led by Houston City College, not to UpSkill Houston; UpSkill marked its 10-year anniversary in 2024 | Not a model input |
| "A ready local workforce attracts outside investment" | 2. U.S. Chamber of Commerce Foundation (2018, May 8) | **Not supported**: the page profiles UpSkill Houston and doesn't make this claim | Not a model input |
| Rose Bowl event shuttles | 5. Foothill Transit (page dated Nov 19, 2026) | **Partly**: Foothill Transit runs a shuttle from the Parsons lot in Old Pasadena straight to the Rose Bowl for live events; "times and prices vary by event"; the page doesn't mention other venues | Not a model input |
| LYMMO circulator, Orlando | 6. LYNX (the page's publisher; "Solodev" is its web vendor) | **Partly**: a bus rapid transit service through downtown Orlando serving the Kia Center, Inter&Co Stadium and Dr. Phillips Center; the page doesn't say it's free | Not a model input |
| Regional median wages by occupation | none | **Confirmed**: all five match BLS OEWS 2025 exactly | Replaced by BLS OEWS |
| FY2026–27 General Fund: ~$216.3M sales tax, ~$18.5M hotel tax | none | **Confirmed** against the budget book (`city_budget_revenue.csv`): $216,255,543 and $18,500,000 | Model input (reference data) |
| Transit pilot cost (~$154 per vehicle revenue hour) | none (Omnitrans FY2026 plan) | **Confirmed** as a calculation: $95,293K ÷ 620K revenue hours = $153.70 (Service Plan FY2026, Exhibit 10, PDF p. 13) | Total for `cost_R2_circulator` |
| Program costs; $500K Year 1 cap | proposal budget | Proposal's own figures | `impact_assumptions.csv`, status `proposal` |
| Phases (0–3, 3–12, 12–24 months, long term) | proposal implementation plan | Proposal's own figures | `impact_phases.csv` |

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

1. Fill `ont_airport_passengers.csv` (section 2).
2. Record where the team keeps the budget book PDF, since it's too large to commit (section 2).
3. Replace the `TEAM ASSUMPTION` rows; `outputs/tables/impact_evidence_gaps.csv` lists them by recommendation.
4. Load Census LODES to update the 2019 live/work figures to the latest year.
5. Match the 15.5% live/work figure to its OnTheMap year by loading LODES (`ingest-lodes`); the 2.6-day stay and the
   12M / 1.2M venue figures have no source found (section 4).
