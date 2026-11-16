# Assumptions (impact-model inputs)

These files drive the recommendation impact model (`src/ontario_forecast/modeling/impact.py`,
`analysis/04_impact.py`). The model reads them directly; they are **not** loaded into the
warehouse, because they are inputs, not observed data.

| File | What it holds |
|---|---|
| `impact_assumptions.csv` | Every model input as a low / likely / high range, with unit, **status** (`official`, `proposal` or `assumption`) and **source** |
| `impact_phases.csv` | Start year and full-scale year of each recommendation (proposal §5 phases) |
| `anchor_visitors.csv` | Annual visitors and overnight share for each City venue Stay +1 builds on |
| `city_investments.csv` | How each City investment maps to the parts of the model that measure it |

**Rules:**
- Every row needs a source.
- Replace a `status = assumption` row with a sourced value as soon as one exists. The sensitivity
  chart (`outputs/charts/impact_sensitivity.png`) ranks which ones matter most.
- `tests/test_impact.py` checks these files on every test run: valid ranges, known statuses, and
  every row has a source.
