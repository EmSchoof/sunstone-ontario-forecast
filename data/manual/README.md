# Hand-entered data

Sources without a download API go here as small CSVs (tracked in git), with one
row per fiscal year and a `source` column citing the document and page.

Every `*.csv` here is loaded automatically as `raw.manual_<file stem>` (all columns
as text; cast them in SQL). Header-only templates load nothing until rows are added.
Never type an estimate as if it were an observation: leave cells blank when unknown.

Wanted:
- `ont_airport_passengers.csv`: fy, passengers, source (ONT monthly traffic reports)
- `city_budget_revenue.csv`: fy, tot_budget, sales_tax_budget, source (City of Ontario adopted budget,
  with document and page). Once filled, these replace the proposal's quoted FY27 figures everywhere.
- Hotel occupancy / ADR (STR/CoStar) if the City or CVB can share it
