# Decisions

[← Background](background.md) · [README](../README.md) · Next: [Methods →](methods.md)

> **Key:** **R1** Career Pathways (students → paid internships → local jobs) ·
> **R2** Connected Destination / Stay +1 (turn existing visitors into extra hotel nights) ·
> **R3** Clean, Safe & Green Downtown (ambassadors + upgrades) ·
> **R4** International & employer attraction (ONT flights, trade zone) ·
> **R1→R4** Career Pathways workforce helping attract employers. Full descriptions: [Background](background.md#the-recommendations-being-tested).

This document records *why* the model is built the way it is: the approach, why each data source was
chosen, and how the team's pre-forecast research shaped what the model tests.

## 1. How the recommendations were investigated before forecasting

The proposal's recommendations came from diagnostic research documented in the proposal. Each finding
became something the model has to represent:

| Team finding (proposal) | Evidence the team used | What it became in the model |
|---|---|---|
| Residents and jobs are disconnected (~15.5% live and work in Ontario) | Census OnTheMap / LEHD commute flows | The **live/work share** is a headline metric; LODES is loaded to rebuild and forecast it |
| Higher-wage careers exist locally (industrial engineers ~$101.7K, logisticians ~$77.4K…) | Regional median wages by occupation | **R1/R4 wage inputs** come from BLS OEWS for the same occupations, which replace the quoted figures |
| Visitor assets are fragmented | Asset review: ONT, Mills, Arena, Sports Empire, Convention Center, Downtown | **R2 is modeled per venue** ("anchor"), so the payoff attaches to existing investments |
| Safety and homelessness weigh on business | City Business Outreach Survey | **R3** is a district sales effect plus explicit displacement; safety itself is a KPI, not a dollar value |
| The City has a direct fiscal stake (TOT, sales tax) | FY2026–27 General Fund | **Fiscal channels are TOT, sales and property tax**, measured net of City cost |
| A transit pilot costs ~$154 per vehicle-hour | Omnitrans FY2026 fixed-route plan | Folded into the **R2 City cost range** from the proposal budget |
| Programs should expand only on results | Phased plan (0–6, 6–18, 18–36 months, 3–10 years) | **Phase ramps**: each recommendation starts and reaches full scale in the years the proposal states |

## 2. Approach

**Two layers, kept separate on purpose:**

1. **Status-quo baseline:** what hotel tax, sales tax and the live/work share do *if nothing changes*. It's
   estimated only from historical data and validated on years the model didn't see.
2. **Recommendation impact:** what each recommendation *adds* to that baseline. It's built as an explicit chain of
   cause and effect (logic model), and every step is an input with a source.

Keeping them apart stops program assumptions from contaminating the statistical forecast. It also lets a
reviewer disagree with one impact input without discarding the baseline.

**Short term vs long term:** FY27–29 covers proposal Phases 1–3 (the first 36 months). FY30–36 covers Phase 4
(3–10 years).

## 3. Data decisions

### Official sources first

**Rule:** if a high-quality official source exists, its value is used. A number quoted in the proposal
is a labeled fallback only (`is_fallback` in `marts.headline_metrics`), and differences over 5% are flagged.

| Need | Chosen source | Why this source |
|---|---|---|
| Hotel tax, sales tax, population (Ontario + 10 peer cities) | **CA State Controller** city revenue data (FY2003+) | The official, audited, comparable record of what Ontario actually collected; 23 years |
| City labor force | **CA EDD LAUS** | The official city-level employment series |
| Regional jobs by sector, unemployment, inflation | **BLS API** (CES, LAUS, CPI) | The primary source. FRED republishes the same series and timed out, so we went to the origin |
| County industry pay | **BLS QCEW** | A near-census of employer payrolls; supports the career-ladder argument |
| Occupation wages | **BLS OEWS** | Official medians for the exact pathway occupations the proposal cites |
| Live/work flows | **Census LODES 8** | The data behind OnTheMap (the 15.5% figure), available yearly since 2002 |
| Commuting, education, income | **Census ACS 5-year** | Survey cross-check with margins of error |
| City budget, airport traffic, venue visitors, program inputs | **Team-entered CSVs** with a source column | No download API exists; each value carries a citation and a status |

### Data handling decisions

- **Fiscal years (July–June) everywhere,** because the City budgets that way. Monthly data is averaged per fiscal
  year, and partial years are dropped instead of being half-averaged.
- **Sales tax "triple flip" (FY2005–16)** is corrected by adding in-lieu payments back; otherwise the series has
  fake breaks. The **hotel-tax line rename (FY2017)** is joined so the series stays continuous.
- **Real dollars:** revenue is deflated with the LA-area CPI, so growth means activity, not inflation.
- **Per-capita ratios are descriptive only:** two per-capita variables share a denominator and correlate mechanically.

## 4. Modeling decisions

| Decision | Alternative rejected | Reason |
|---|---|---|
| Model **growth rates**, not levels | Regress levels on levels | Trending series correlate by coincidence (spurious regression) |
| **At most 1 predictor**, chosen from **6 named in advance** | Search many indicators | ~20 annual points; searching dozens of indicators always "finds" something |
| Predictors enter **with a one-year lag** | Same-year predictors | Same-year values aren't known when the forecast is made |
| Choose by **out-of-sample error vs "same as last year"** | In-sample R² or p-values | Only out-of-sample error shows forecasting skill |
| **COVID FYs (2020–23) excluded from fitting** | Fit through them | Two pandemic years would set the slope on their own |
| **Classical statistics** (statsmodels/scipy) + numpy simulation | Darts, XGBoost, neural networks | Far too few observations; flexible models would fit noise |
| **Ranges from real forecast errors** (bootstrap) | Textbook normal intervals | Uses how wrong the model actually was on unseen years |
| Impact counts only **additional, non-displaced** effects, net of **City cost**; **no multipliers** | Gross economic impact with multipliers | Conservative, defensible to a City finance reviewer |

## 5. Engineering decisions

| Decision | Why |
|---|---|
| **dlt** for ingestion | Retries, paging (RESTClient), schema inference, incremental state (LODES years load once) |
| **DuckDB** warehouse + SQL transforms | Fast and typed. The ~2 GB LODES files are aggregated in the database, never loaded into Python |
| **pandas used deliberately, not by default** | Only statsmodels needs it at analysis time; the deployed model is numpy + JSON |
| **Targeted imports** from statsmodels/scipy | Proven implementations without loading unused model families |
| **Single source of truth** (`config.py`, SQL parameter tables, `features.py`) | Every rule and ID is defined once and reused (DRY) |
| **uv** + **pnpm/Nx** | Locked environments; the pipeline runs as a graph with cached lint and tests |
| **pre-commit + ruff + pytest** | Style and correctness checked on every commit; 40 tests cover the math, SQL, impact and ROI logic |

Next: [Methods →](methods.md)
