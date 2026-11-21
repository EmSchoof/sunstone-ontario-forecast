<a id="readme-top"></a>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![uv](https://img.shields.io/badge/env-uv-DE5FE9)
![dlt](https://img.shields.io/badge/ingest-dlt-1F6FEB)
![DuckDB](https://img.shields.io/badge/warehouse-DuckDB-FFF000?logo=duckdb&logoColor=black)
![Nx](https://img.shields.io/badge/orchestration-Nx-143055?logo=nx&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)

<br />
<div align="center">
  <h2 align="center">Connecting Ontario: Forecast &amp; Impact Model</h2>
  <p align="center">
    How our recommendations build on what the City of Ontario, CA already has (the airport, Sports Empire,
    Toyota Arena, Downtown, Ontario Ranch) to grow local jobs, visitor stays and the City's tax base.
    <br />
    <em>Sunstone Economic Development Challenge @ USC Price</em>
    <br /><br />
    <a href="docs/03_conclusions.md"><strong>Read the conclusions »</strong></a>
    ·
    <a href="outputs/docs/conclusions.pdf">Download them as a PDF</a>
    ·
    <a href="outputs/charts/">Browse the charts</a>
    ·
    <a href="#quick-start">Run it yourself</a>
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#the-recommendations">The recommendations</a></li>
    <li><a href="#1-the-problem">The problem</a></li>
    <li><a href="#2-how-we-approached-it">How we approached it</a></li>
    <li><a href="#3-how-the-model-works">How the model works</a></li>
    <li><a href="#4-what-we-found">What we found</a></li>
    <li><a href="#quick-start">Quick start</a> (technical)</li>
    <li><a href="#repository-layout">Repository layout</a> (technical)</li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

## The recommendations

| Code | Recommendation | In one sentence |
|---|---|---|
| **R1** | Ontario Career Pathways & Employer Consortium | A City-convened consortium of employers, colleges, school districts and workforce groups: education → paid internships → local careers → residents who stay |
| **R2** | A Connected Destination Economy | Joint City–ONT outreach (event calendars, restaurant and hotel packages, a QR-code visitor guide) plus a two-bus evening transit pilot linking Downtown, Capital City and Toyota Arena |
| **R3** | Clean, Safe & Green Entertainment Districts | A DOIA-led Downtown ambassador pilot, expanding to Capital City on results, with green improvements phased in |

[![What each recommendation must achieve to pay for itself](outputs/charts/impact_break_even.png)](docs/03_conclusions.md#2-what-each-recommendation-must-achieve-to-pay-for-itself)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 1. The problem

Ontario already has what many cities want: an international airport (7.1M passengers in 2024), Ontario Mills
(28M annual visitors), Toyota Arena (about 730K a year), the new Sports Empire, and one of Southern California's
biggest job centers.
But that activity doesn't stay local:

- **About 1 in 7 working residents works in Ontario** (14.8% in 2019, per the City's 2023 hazard mitigation plan,
  citing Census OnTheMap). Meanwhile about 116,000 people commute in from elsewhere.
- **Visitors come and go.** The major attractions are miles apart, and many trips end the same day.
- **Businesses worry** about homelessness, safety, rising costs, traffic and permitting.

Every extra hotel night and every purchase made in Ontario adds to the City's budget through hotel tax and sales
tax. So the question is: **can our recommendations keep more of that activity, and more of those paychecks, in Ontario?**

**Learn more:** [Background](docs/00_background.md) covers the challenge, the City's assets and each recommendation in full.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 2. How we approached it

- **Two separate questions.** First: what happens to Ontario's hotel tax, sales tax and local jobs *if nothing
  changes*? Then: what does each recommendation *add* on top of that?
- **Official numbers first.** Figures come from the State Controller, the Census Bureau and the Bureau of Labor
  Statistics. A number quoted in the proposal is used only when no official source exists, and it's clearly marked.
- **Cautious on purpose.** The model only counts results that wouldn't have happened anyway, subtracts what the
  City spends, and leaves out "ripple effects." If anything, it undersells the plan.
- **Simple, tested methods over flashy ones.** About 20 years of yearly data is too little for AI-style models,
  which would find patterns that aren't really there.

**Learn more:** [Decisions](docs/01_decisions.md) explains each choice and the alternatives we rejected.
[Sources](docs/04_sources.md) lists every data and content source and where it lives in the repo.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 3. How the model works

1. **Gather and check the data.** Public data downloads automatically and is checked for errors before use.
2. **Forecast "if nothing changes."** The model learns from 20+ years of Ontario's tax history. It's tested on
   years it hadn't seen, and only kept if it beats a simple "same as last year" guess. It gives a low, likely and high outcome.
3. **Add each recommendation, step by step.** For example, for R2's hotel packages: visitors who already come → the
   share who stay overnight → the share who add a night → extra hotel tax and spending. Every step is an estimate with a
   range and a written source.
4. **Run 20,000 "what-if" futures** to see the range of outcomes, and how much tax revenue comes back for each
   dollar the City spends.

**Learn more:** [Methods](docs/02_methods.md) has the full statistical and data-engineering detail, including the formula
for each recommendation.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 4. What we found

> **What's reported here.** Only results built from sourced data: the status-quo forecasts and the break-even
> targets. No projected return is reported for any recommendation yet, because each still depends on inputs that
> are team estimates; the [Conclusions](docs/03_conclusions.md#4-what-the-model-cant-estimate-yet-and-what-would-let-it)
> list them and who holds the data.

**Bottom line:** each recommendation has a clear test the City can measure, and the proposal's partner
cost-sharing is what keeps Year 1 City spending within the $500K cap.

| | Program cost per year (proposal) | Pays for itself in City tax when it adds… | Per $100K of City money |
|---|---|---|---|
| **R1** Career Pathways | $75K–$150K | Not a tax-revenue program: judge it on placements, wages and retention | — |
| **R2** Connected Destination Economy | $290K–$475K | $290K–$475K more hotel tax a year (1.7%–2.8% more than FY2025) | $100K of hotel tax |
| **R3** Clean, Safe & Green Entertainment Districts | $350K–$550K | $17.5M–$27.5M of net new Downtown taxable sales a year | $5M of new sales |

**Also worth knowing:**
- **Combined, the three recommendations cost $715K–$1.175M a year** against the $500K Year 1 City cap, so
  partners carry the difference and each recommendation is assessed on its own budget and measures.
- **The City is already studying a circulator.** A $120K Internal Circulator Planning Study is due December 2026;
  the proposal launches the evening transit pilot after it reports.
- **The City's FY27 hotel-tax budget ($18.5M) looks optimistic.** Without new programs, it's higher than 63% of the
  likely outcomes.
- **The sales-tax numbers reconcile.** The City's $216.3M includes Measure Q ($64.3M) and Prop 172; the State
  Controller's $139M is the original 1% only. The forecast for that part ($147.4M in FY27) is close to the City's
  budget ($148.8M).

**What the model adds to the proposal:**
1. **A break-even test for each recommendation** (the proposal's Figure 1.2), built only from official data and
   the proposal's own costs.
2. **The status-quo hotel-tax forecast** (the proposal's Figure 1.1) that R2's results will be measured against.
3. **Baselines for the proposal's measures** where data already exists, such as the 8.8% of Ontario jobs held by
   residents in 2019.
4. **A Phase 1 data list** that would let the model estimate returns once the pilots start reporting.

**Learn more:** [Conclusions](docs/03_conclusions.md) ([PDF](outputs/docs/conclusions.pdf)) has every chart and
number, how each recommendation's success would be measured, and what drives the result.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

*The sections below are for people running or changing the code.*

## Quick start

Everything that runs lives in `ontario_forecast_model/`; run commands from there.

**Prerequisites:** `brew install uv node pnpm`. Optional free API keys go in
`ontario_forecast_model/.dlt/secrets.toml` (`census_api_key`, `bls_api_key`); see
[Methods](docs/02_methods.md#a2-ingestion-srcfiscal_impact_modelingest).

```bash
cd ontario_forecast_model && uv sync --all-extras && pnpm install && uv run pre-commit install
```

| Goal | Command (from `ontario_forecast_model/`) |
|---|---|
| Lint + tests | `pnpm nx run-many -t lint test` |
| Rebuild every chart from data already loaded | `pnpm nx run ontario-forecast:report` |
| End to end: checks → fresh data → every chart | `pnpm nx run ontario-forecast:e2e` |
| Load commuting data (LODES, once) | `pnpm nx run ontario-forecast:ingest-lodes` |
| Add a new analysis step | `pnpm nx g @sunstone/pipeline-plugin:stage <name> --dependsOn=select` |
| See the pipeline graph | `pnpm nx graph` |

**PyCharm:** open `ontario_forecast_model/` as the project, use its `.venv/bin/python` as the interpreter and
mark `src` as Sources Root.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Repository layout

The top level is for readers; everything that runs is in one folder.

```
sunstone-ontario-forecast/
├── README.md                     start here
├── docs/                         00 background · 01 decisions · 02 methods · 03 conclusions · 04 sources
├── outputs/                      what the model produces
│   ├── charts/                   deliverable PNG · SVG · PDF
│   ├── tables/                   charted numbers + analysis-ready marts as CSV
│   ├── models/                   fitted model coefficients (JSON)
│   ├── docs/                     shareable PDFs of the docs (conclusions.pdf)
│   └── eda/                      exploratory figures (not tracked)
├── data/                         what goes in
│   ├── *.csv                     all input data: reference figures (loaded by dlt) + impact-model inputs
│   └── warehouse/                DuckDB built by the pipeline (not tracked)
└── ontario_forecast_model/       the model: code, pipeline steps and tooling
    ├── src/fiscal_impact_model/
    │   ├── config.py · db.py     settings (single source of truth) + DuckDB → numpy
    │   ├── ingest/               dlt sources, LODES aggregation
    │   ├── transform/            SQL staging → marts, data-quality checks
    │   ├── modeling/             stats · features · evaluation · model · scenarios · impact
    │   ├── reporting/            charts · export · pdf
    │   └── tests/                pytest
    ├── analysis/                 pipeline steps: 01_eda → 02 selection → 03 scenarios → 04 impact
    ├── tools/pipeline-plugin/    Nx generator for new analysis steps
    └── pyproject.toml · uv.lock · package.json · pnpm-*.yaml · nx.json · project.json
```

Tools and why each was chosen: [Decisions §5](docs/01_decisions.md#5-engineering-decisions).

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Roadmap

- [x] Public-data pipeline with data-quality checks
- [x] Status-quo forecasts and the recommendation impact model, including ROI
- [x] Nx orchestration + stage generator
- [ ] Source the highest-impact inputs (Downtown uplift and share, hotel package uptake, the City's share of each cost)
- [ ] Close the open items in the [source register](docs/04_sources.md#open-items) (airport traffic, original citations)
- [x] Add the City's adopted FY2026–27 budget to `data/`
- [ ] Load LODES and ACS for the live/work charts
- [x] Reconcile the proposal's $216.3M sales-tax figure with State Controller actuals (~$139M): Measure Q + Prop 172

## Contact

Danny Valencia · Haley Chavez · Emily Schoof · Nathaniel Gallardo
(USC Price, Sunstone Economic Development Challenge), for the City of Ontario Economic Development Agency.

## License

- **Code** (`ontario_forecast_model/`): [MIT](LICENSE), © 2026 Emily Schoof.
- **Written analysis and results** (`docs/`, `outputs/`, and the team-entered inputs in `data/`):
  [CC BY 4.0](LICENSE-docs.md), © 2026 Team Ontario (Danny Valencia, Haley Chavez, Emily Schoof, Nathaniel
  Gallardo). Reuse is welcome with credit.
- **Third-party data** (State Controller, BLS, Census, City of Ontario budget and others) stays under its sources'
  own terms; see [Sources](docs/04_sources.md).

## Acknowledgments

Data: [CA State Controller](https://bythenumbers.sco.ca.gov/), [CA EDD](https://data.ca.gov/),
[U.S. BLS](https://www.bls.gov/), [U.S. Census Bureau](https://lehd.ces.census.gov/).
README structure: [Best-README-Template](https://github.com/othneildrew/Best-README-Template).

<p align="right">(<a href="#readme-top">back to top</a>)</p>
