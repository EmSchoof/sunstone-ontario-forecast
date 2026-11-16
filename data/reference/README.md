# Reference data (hand-entered source data)

Official figures that have no download API go here as small CSVs (tracked in git): one row
per fiscal year, plus a `source` column citing the document and page.

Every `*.csv` in this folder is loaded automatically as `raw.manual_<file stem>`, with all
columns as text (cast them in SQL). Header-only templates load nothing until rows are added.
Never type an estimate as if it were an observation: leave cells blank when unknown.
Estimates and program inputs belong in [`../assumptions/`](../assumptions/README.md).

| File | Columns | Source to use |
|---|---|---|
| `city_budget_revenue.csv` | fy, tot_budget, sales_tax_budget, source | City of Ontario adopted budget (document + page). Replaces the proposal's quoted FY27 figures everywhere. `sales_tax_budget` is the budget's "Sales Tax" total, which includes Prop 172 and Measure Q |
| `city_sales_tax_detail.csv` | fy, basis (actual / adopted / current), sales_use_tax, prop_172, measure_q, total_sales_tax, tot, source | Same budget book, revenue detail page. Splits "Sales Tax" into Bradley-Burns (the series the forecast uses), Prop 172 and Measure Q |
| `ont_airport_passengers.csv` | fy, passengers, source | ONT monthly traffic reports |

Also wanted: hotel occupancy / average room rate (STR or CoStar), if the City or the visitors bureau can share it.
