# Ontario forecasting: Connecting Ontario (Sunstone @ USC Price)

Public-data pipeline and small-sample forecasting for the City of Ontario proposal:
hotel tax (TOT), sales tax, and the share of residents who work in Ontario.

## Stack

| Layer | Tool | Why |
|---|---|---|
| Extract & load | **dlt** -> DuckDB (`raw` schema) | schema inference, retries, incremental state |
| Transform | **DuckDB SQL** (`staging` -> `marts`) | fast, typed, testable; LODES (~2 GB) streamed and aggregated in-engine |
| Analysis | numpy + matplotlib (+ statsmodels for unit-root tests only) | |
| Deployed model | **numpy + json only** (`src/ontario_forecast/model.py`) | no pandas, tiny footprint |

pandas is not used anywhere in the project's code. statsmodels imports it internally, so
statsmodels is an *analysis* extra only and is never imported by the pipeline or model.

## Layout

```
src/ontario_forecast/
  config.py               paths, geography, source IDs, COVID years, proposal benchmarks
  ingest/sources.py       dlt resources (SCO, EDD LAUS, FRED, BLS QCEW, Census LODES)
  ingest/lodes.py         DuckDB aggregation of LODES origin-destination files
  ingest/run.py           CLI: load raw.*
  transform/sql/*.sql     staging + marts (fiscal-year aligned panel)
  transform/checks.py     data-quality checks (error / warn)
  transform/run.py        CLI: build, check, export to data/processed/
  db.py                   SQL -> numpy arrays
  stats.py                OLS, VIF, correlations w/ CIs, rolling-origin backtest, conformal intervals
  model.py                deployable GrowthForecaster (numpy/json)
analysis/
  01_eda.py               EDA (# %% cells)
  02_variable_selection.py
tests/                    pytest: stats, SQL transforms, LODES aggregation
data/manual/              hand-entered sources (tracked)
data/warehouse/, data/processed/, reports/figures/   generated (git-ignored)
```

## Setup in PyCharm

1. Open the `sunstone` folder.
2. Settings -> Project -> Python Interpreter -> Add -> Virtualenv -> **New**, location `.venv`.
3. In the PyCharm terminal: `pip install -e ".[analysis,dev]"`
4. Mark `src` as *Sources Root* (right-click -> Mark Directory as) so imports resolve.

## Run order

```bash
python -m ontario_forecast.ingest.run --skip-lodes   # SCO, LAUS, FRED, QCEW (~1-2 min)
python -m ontario_forecast.ingest.run --only lodes_ontario_flows   # ~2 GB streamed, incremental
python -m ontario_forecast.transform.run              # build marts, run checks, export
python analysis/01_eda.py
python analysis/02_variable_selection.py
pytest
```

## Data sources

| Source | Table | Grain | Coverage |
|---|---|---|---|
| CA State Controller, City Revenues | `raw.sco_city_revenue_lines` | city x FY x line item | FY2003+ (Ontario + 10 peers) |
| CA EDD LAUS (data.ca.gov) | `raw.laus_city_monthly` | city x month | ~2010+ |
| FRED (BLS CES, CPI) | `raw.fred_observations` | series x month | 1990+ |
| BLS QCEW, San Bernardino County | `raw.qcew_county_annual` | sector x year | 2014+ |
| Census LODES 8 OD (main + aux) | `raw.lodes_ontario_flows` | year (aggregated) | 2002+ |

Not available as downloads (see `data/manual/README.md`): ONT airport passengers,
hotel occupancy/ADR, visitor counts, City budget figures.

## Methodology guardrails

- **Fiscal-year alignment**: monthly series averaged July-June; partial years dropped.
- **Definitional breaks**: TOT line rename (FY2017) and sales-tax triple flip (FY2005-16) corrected in SQL.
- **Real dollars**: CPI-LA deflated, base = latest FY.
- **Stationarity**: models use log growth; levels are only described.
- **Curse of dimensionality**: ~20 annual observations means at most about 1 predictor per model, chosen from 6 pre-specified candidates.
- **No look-ahead**: drivers enter at lag 1; same-year correlations are labeled "nowcast".
- **Validation**: expanding-window rolling-origin backtest, same test years for every model,
  MAE/RMSE in dollars (no MAPE), must beat naive and drift baselines.
- **COVID**: FY2020-22 (and the FY2023 row with a COVID-year lagged driver) are excluded from fitting
  and reported separately in scoring.
- **Uncertainty**: 80% split-conformal intervals from out-of-sample errors.
- **Multiple comparisons**: screening correlations Bonferroni-adjusted and used descriptively only.

Why not Darts/XGBoost/neural models: they need far more observations than ~20 annual
points. Here, extra flexibility just fits noise.

Retraining cadence: annually, when the State Controller publishes a new fiscal year.
Monitor each new year's actual against the forecast interval.
