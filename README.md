# sunstone-ontario-forecast: Connecting Ontario (Sunstone @ USC Price)

Public-data pipeline and small-sample forecasting for the City of Ontario proposal:
hotel tax (TOT), sales tax, and the share of residents who work in Ontario.

## Stack

| Layer | Tool | Why |
|---|---|---|
| Environment | **uv** (`uv.lock`) | reproducible lockfile, fast installs |
| Extract & load | **dlt** (RESTClient, incremental state) -> DuckDB `raw` | retries, paging, schema inference |
| Transform | **DuckDB SQL** (`staging` -> `marts`) | fast, typed, testable; LODES (~2 GB) streamed in-engine |
| Statistics | **statsmodels + scipy**, targeted imports only | proven implementations; no `statsmodels.api` |
| Evaluation & scenarios | numpy | chronological backtest, conformal intervals, bootstrap |
| Charts | matplotlib | static PNG/SVG/PDF export |
| Deployed model | **numpy + json only** (`model.py`) | fit in analysis, serve coefficients |
| Quality | **pre-commit + ruff**, pytest | lint/format on every commit |

pandas is used deliberately, not by default. Heavy data work runs in DuckDB. statsmodels
brings pandas in at analysis time only, and the deployed model never imports it.

## Layout

```
src/ontario_forecast/
  config.py               paths, geography, source IDs, COVID years, proposal benchmarks
  ingest/sources.py       dlt resources (SCO, EDD LAUS, FRED, QCEW, LODES, ACS, OEWS, manual CSVs)
  ingest/lodes.py         DuckDB aggregation of LODES origin-destination files
  ingest/run.py           CLI: load raw.*
  transform/sql/*.sql     staging + marts (fiscal-year aligned panel)
  transform/checks.py     data-quality checks (error / warn)
  transform/run.py        CLI: build, check, export to data/processed/
  db.py                   SQL -> numpy arrays
  stats.py                statsmodels/scipy wrappers (OLS, VIF, ADF/KPSS, correlations, Holm)
  features.py             shared lag + COVID fit/score masks (one rule for 02 and 03)
  evaluation.py           rolling-origin backtest, MAE/RMSE, conformal half-width (numpy)
  model.py                deployable GrowthForecaster (numpy/json)
  scenarios.py            P10/P50/P90 bootstrap of out-of-sample errors (numpy)
  charts.py               final chart style (matplotlib)
analysis/
  01_eda.py               EDA (# %% cells)
  02_variable_selection.py
  03_scenarios.py         final export -> reports/final/
tests/                    pytest
data/manual/              hand-entered sources (tracked)
data/warehouse/, data/processed/, reports/figures/   generated (git-ignored)
```

## Single source of truth (DRY)

| Defined once in | Used by |
|---|---|
| `config.py`: cities, FRED series IDs + column names, COVID years, ACS vintages, forecast targets, proposal fallbacks | ingest, SQL (via `staging.*` parameter tables), analyses |
| `transform/run.py: PARAMS` | every SQL parameter. Add it here, then reference `staging.<name>` |
| `features.py` | lag + COVID fit/score rules for selection (02) and scenarios (03) |
| `db.load_panel()` | the one panel query |
| `marts.headline_metrics` | every headline number (official source first) |
| `scenarios.Fan.rows()/final()` | chart labels and the summary CSV |

## Setup

Install uv once (`brew install uv`), then from the project folder:

```bash
uv sync --all-extras          # creates .venv from uv.lock (writes the lock on first run)
uv run pre-commit install     # ruff + hygiene checks on every git commit
```

**PyCharm:** Settings -> Python Interpreter -> Add -> *Existing* -> `.venv/bin/python`
(recent versions also offer a "uv" interpreter type). Mark `src` as Sources Root.

## Run order

```bash
uv run python -m ontario_forecast.ingest.run --skip-lodes          # SCO, LAUS, FRED, QCEW, ACS, OEWS, manual
uv run python -m ontario_forecast.ingest.run --only lodes_ontario_flows   # ~2 GB streamed, incremental
uv run python -m ontario_forecast.transform.run                    # build marts, run checks, export
uv run python analysis/01_eda.py
uv run python analysis/02_variable_selection.py
uv run python analysis/03_scenarios.py                             # final charts -> reports/final/
uv run pytest
```

### API keys (optional, free)

Put them in env vars or `.dlt/secrets.toml` (git-ignored):

```toml
census_api_key = "..."   # https://api.census.gov/data/key_signup.html  (ACS; skipped if absent)
bls_api_key = "..."      # https://data.bls.gov/registrationEngine/     (raises OEWS daily limit)
```

## Data sources

| Source | Table | Grain | Coverage |
|---|---|---|---|
| CA State Controller, City Revenues | `raw.sco_city_revenue_lines` | city x FY x line item | FY2003+ (Ontario + 10 peers) |
| CA EDD LAUS (data.ca.gov) | `raw.laus_city_monthly` | city x month | ~2010+ |
| FRED (BLS CES, CPI) | `raw.fred_observations` | series x month | 1990+ |
| BLS QCEW, San Bernardino County | `raw.qcew_county_annual` | sector x year | 2014+ |
| Census LODES 8 OD (main + aux) | `raw.lodes_ontario_flows` | year (aggregated) | 2002+ |
| Census ACS 5-year (key) | `raw.acs_place` | geo x vintage x variable | 2010+ |
| BLS OEWS via API | `raw.oews_msa_occupations` | occupation x year | latest |
| Hand-entered CSVs | `raw.manual_<file>` | as entered | `data/manual/*.csv` |

ACS 5-year estimates overlap, so only non-overlapping vintages (2010-14, 2015-19, 2020-24)
are compared, and every change is tested against its 90% margin of error.

Not available as downloads (fill the templates in `data/manual/`): ONT airport passengers,
City budget figures, hotel occupancy/ADR, visitor counts.

## Methodology guardrails

- **Source priority**: official data first (CA State Controller, Census, BLS, the City's adopted
  budget in `data/manual/`). A figure quoted in the proposal is used only when no official value
  exists, and it is flagged `is_fallback` in `marts.headline_metrics`. Charts and EDA read from that table.
  Differences over 5% are raised as warnings so the proposal text can be corrected.
- **Fiscal-year alignment**: monthly series averaged July-June; partial years dropped.
- **Definitional breaks**: TOT line rename (FY2017) and sales-tax triple flip (FY2005-16) corrected in SQL.
- **Real dollars**: CPI-LA deflated, base = latest FY.
- **Stationarity**: models use log growth; ADF + KPSS (statsmodels) as supporting evidence.
- **Curse of dimensionality**: ~20 annual observations means at most about 1 predictor per model,
  chosen from 6 pre-specified candidates.
- **No look-ahead**: drivers enter at lag 1; same-year correlations are labeled "nowcast".
- **Validation**: expanding-window rolling-origin backtest, same test years for every model,
  MAE/RMSE in dollars (no MAPE), must beat naive and drift baselines.
- **COVID**: FY2020-22, and the FY2023 row whose lagged driver is a COVID year, are
  excluded from fitting and reported separately in scoring.
- **Multiple comparisons**: screening p-values Holm-adjusted; descriptive only.
- **Uncertainty**: 80% split-conformal intervals from out-of-sample errors. The selected
  model's backtest error is slightly optimistic (best of ~9 models on the same years).

Why not Darts/XGBoost/neural models: they need far more observations than ~20 annual
points. Here, extra flexibility just fits noise.

## Final deliverable: three statistically likely outcomes

`analysis/03_scenarios.py` exports, for hotel tax, sales tax and the live/work share:
**Downside (P10), Central (P50), Upside (P90)** for the next 5 fiscal years. The
simulation draws 20,000 paths by resampling the selected model's *out-of-sample* errors
(ex-COVID), with a fixed seed so the results are reproducible. These are status-quo baselines with no program effect,
which makes them the counterfactual the proposal's dashboard metrics are judged against. The hotel-tax chart
marks the City's FY27 budget figure and reports its percentile. Every charted number is
in `reports/final/scenarios_summary.csv`.

Retraining cadence: annually, when the State Controller publishes a new fiscal year.
Monitor each new year's actual against the forecast interval.
