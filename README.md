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
    <a href="docs/conclusions.md"><strong>Read the conclusions »</strong></a>
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
    <li><a href="#the-four-recommendations">The four recommendations</a></li>
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

## The four recommendations

| Code | Recommendation | In one sentence |
|---|---|---|
| **R1** | Career Pathways & Employer Consortium | Connect students to paid internships with Ontario employers so more residents live *and* work here |
| **R2** | Connected Destination (Stay +1) | Turn visitors who already come for the airport, games and shopping into overnight guests |
| **R3** | Clean, Safe & Green Districts | Make Downtown feel safe and lively in the evening so people stay and spend |
| **R4** | International & employer attraction | Use ONT's Taiwan/Mexico flights and the trade zone to attract and keep employers |
| **R1→R4** | The link between them | A ready local workforce (R1) makes employers easier to attract (R4) |

[![How each recommendation builds Ontario's fiscal base](outputs/charts/impact_pathways.png)](docs/conclusions.md)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 1. The problem

Ontario already has what many cities want: an international airport (7M+ passengers a year), Ontario Mills
(about 12M visits), Toyota Arena, the new Sports Empire, and one of Southern California's biggest job centers.
But that activity doesn't stay local:

- **About 1 in 6 working residents works in Ontario (15.5%).** Meanwhile more than 120,000 people commute in from elsewhere.
- **Visitors come and go.** The major attractions are miles apart, and many trips end the same day.
- **Businesses worry** about homelessness, safety, rising costs, traffic and permitting.

Every extra hotel night and every purchase made in Ontario adds to the City's budget through hotel tax and sales
tax. So the question is: **can our recommendations keep more of that activity, and more of those paychecks, in Ontario?**

**Learn more:** [Background](docs/background.md) covers the challenge, the City's assets and each recommendation in full.

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

**Learn more:** [Decisions](docs/decisions.md) explains each choice and the alternatives we rejected.
[Sources](docs/sources.md) lists every data and content source and where it lives in the repo.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 3. How the model works

1. **Gather and check the data.** Public data downloads automatically and is checked for errors before use.
2. **Forecast "if nothing changes."** The model learns from 20+ years of Ontario's tax history. It's tested on
   years it hadn't seen, and only kept if it beats a simple "same as last year" guess. It gives a low, likely and high outcome.
3. **Add each recommendation, step by step.** For example, for Stay +1: visitors who already come → the share
   who stay overnight → the share who add a night → extra hotel tax and spending. Every step is an estimate with a
   range and a written source.
4. **Run 20,000 "what-if" futures** to see the range of outcomes, and how much tax revenue comes back for each
   dollar the City spends.

**Learn more:** [Methods](docs/methods.md) has the full statistical and data-engineering detail, including the formula
for each recommendation.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 4. What we found

> **Preliminary.** Many of the model's estimates are still team placeholders waiting for an official source.
> Which recommendations come out ahead is already meaningful; the exact dollar amounts will change.

**Bottom line:** the plan is affordable: about **$348K** of City money in Year 1, under the **$500K** cap. In
tax revenue alone it doesn't pay for itself: about **70¢ comes back for every $1** the City spends over the
whole program. Its strongest case is more residents in good local jobs, with partners sharing the cost.

| | What the model says | Tax revenue back per $1 (2027–36) | Chance it pays for itself |
|---|---|---|---|
| **R1** Career Pathways | Builds the workforce; brings in little tax directly | 13¢ | ~0% |
| **R2** Stay +1 | Returns about half its cost unless roughly twice as many visitors take the offer | 50¢ | 6% |
| **R3** Clean, Safe & Green | **Pays for itself** in the likely case, but rests on two unsourced Downtown estimates | **$1.36** | 68% |
| **R4** Employers (+ R1→R4) | About break-even; 38¢ once Career Pathways' cost is counted with it | 95¢ | 47% |
| **All together** | | 70¢ | 13% |

[![Tax revenue returned per $1 of City money](outputs/charts/impact_roi.png)](docs/conclusions.md#3-cost-and-return-on-investment)

**Also worth knowing:**
- **About 118 more residents working in Ontario by 2036**, and about 145 more people living here.
- **The airport is the most valuable venue** for Stay +1: it brings the most visitors who could stay another night.
- **The City's FY27 hotel-tax budget ($18.5M) looks optimistic.** Without new programs, it's higher than 70%
  of the likely outcomes.
- **The sales-tax numbers reconcile.** The City's $216.3M includes Measure Q ($64.3M) and Prop 172; the State
  Controller's $139M is the original 1% only. The model's FY27 estimate for that part ($147.4M) is close to the
  City's budget ($148.8M).

**What we recommend:**
1. **Lead with Downtown (R3)**, the strongest fiscal case, and **run Career Pathways (R1) lean** with employers
   funding most of it.
2. **Set a clear test for Stay +1:** expand it only if at least about 4% of overnight visitors add a night, or
   cut the City's share to about $112K a year. That's roughly where it pays for itself.
3. **Replace the team's estimates with real data first**, starting with Downtown sales and Stay +1 uptake.
   The Downtown result depends on them.

**Learn more:** [Conclusions](docs/conclusions.md) ([PDF](outputs/docs/conclusions.pdf)) has every chart and
number, how each recommendation's success would be measured, and what drives the result.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

*The sections below are for people running or changing the code.*

## Quick start

**Prerequisites:** `brew install uv node pnpm`. Optional free API keys go in `.dlt/secrets.toml`
(`census_api_key`, `bls_api_key`); see [Methods](docs/methods.md#a2-ingestion-srcontario_forecastingest).

```bash
uv sync --all-extras && pnpm install && uv run pre-commit install
```

| Goal | Command |
|---|---|
| Lint + tests (cached) | `pnpm nx run-many -t lint test` |
| Rebuild every chart from data already loaded | `pnpm nx run ontario-forecast:report` |
| End to end: checks → fresh data → every chart | `pnpm nx run ontario-forecast:e2e` |
| Load commuting data (LODES, once) | `pnpm nx run ontario-forecast:ingest-lodes` |
| Add a new analysis step | `pnpm nx g @sunstone/pipeline-plugin:stage <name> --dependsOn=select` |
| See the pipeline graph | `pnpm nx graph` |

**PyCharm:** use `.venv/bin/python` as the interpreter and mark `src` as Sources Root.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Repository layout

```
sunstone-ontario-forecast/
├── README.md
├── docs/                         background · decisions · methods · conclusions · sources
├── src/ontario_forecast/
│   ├── config.py · db.py         settings (single source of truth) + DuckDB → numpy
│   ├── ingest/                   dlt sources, LODES aggregation
│   ├── transform/                SQL staging → marts, data-quality checks
│   ├── modeling/                 stats · features · evaluation · model · scenarios · impact
│   └── reporting/                charts · export
├── analysis/                     pipeline steps: 01_eda → 02 selection → 03 scenarios → 04 impact
├── tests/                        pytest
├── data/
│   ├── reference/                hand-entered source data (budget, airport): loaded by dlt
│   └── assumptions/              impact-model inputs, each with a source and status
├── outputs/
│   ├── charts/                   deliverable PNG · SVG · PDF
│   ├── tables/                   charted numbers + analysis-ready marts as CSV
│   ├── models/                   fitted model coefficients (JSON)
│   ├── docs/                     shareable PDFs of the docs (conclusions.pdf)
│   └── eda/                      exploratory figures (not tracked)
├── tools/pipeline-plugin/        Nx generator for new analysis steps
└── pyproject.toml · uv.lock · package.json · pnpm-*.yaml · nx.json · project.json
```

Tools and why each was chosen: [Decisions §5](docs/decisions.md#5-engineering-decisions).

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Roadmap

- [x] Public-data pipeline with data-quality checks
- [x] Status-quo forecasts and the recommendation impact model, including ROI
- [x] Nx orchestration + stage generator
- [ ] Source the highest-impact inputs (Downtown uplift and share, Stay +1 uptake, R2 and R4 cost)
- [ ] Close the open items in the [source register](docs/sources.md#open-items) (proposal document, airport traffic)
- [x] Add the City's adopted FY2026–27 budget to `data/reference/`
- [ ] Load LODES and ACS for the live/work charts
- [x] Reconcile the proposal's $216.3M sales-tax figure with State Controller actuals (~$139M): Measure Q + Prop 172

## Contact

Danny Valencia · Haley Chavez · Emily Schoof · Nathaniel Gallardo
(USC Price, Sunstone Economic Development Challenge), for the City of Ontario Economic Development Agency.

No license has been chosen yet, so all rights are reserved. Choose one before making the repository public.

## Acknowledgments

Data: [CA State Controller](https://bythenumbers.sco.ca.gov/), [CA EDD](https://data.ca.gov/),
[U.S. BLS](https://www.bls.gov/), [U.S. Census Bureau](https://lehd.ces.census.gov/).
README structure: [Best-README-Template](https://github.com/othneildrew/Best-README-Template).

<p align="right">(<a href="#readme-top">back to top</a>)</p>
