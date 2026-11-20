"""docs/04_sources.md is the register of every data and content source. These tests fail when
something is added to the code or the data folders without being listed there."""

import re

from fiscal_impact_model import config

DOC = (config.ROOT / "docs" / "04_sources.md").read_text(encoding="utf-8")
INGEST = (config.PROJECT_DIR / "src" / "fiscal_impact_model" / "ingest" / "sources.py").read_text(
    encoding="utf-8"
)


def test_every_downloaded_resource_is_listed():
    resources = re.findall(r'@dlt\.resource\(name="(\w+)"', INGEST)
    assert len(resources) >= 7
    assert [r for r in resources if f"`{r}`" not in DOC] == []


def test_every_bls_series_is_listed():
    assert [s for s in config.BLS_SERIES if s not in DOC] == []


def test_every_endpoint_and_dataset_id_is_listed():
    ids = [
        config.SCO_CITY_REVENUES,
        config.LAUS_MONTHLY_PACKAGE,
        config.BLS_API_URL,
        config.LODES_BASE,
        config.OEWS_MSA,
        config.ONTARIO_PLACE_FIPS,
        config.SB_COUNTY_FIPS,
        "data.bls.gov/cew",
        "api.census.gov",
        *config.ACS_GROUPS,
    ]
    assert [i for i in ids if i not in DOC] == []


def test_every_reference_and_assumptions_file_is_listed():
    files = [*config.REFERENCE_FILES, *config.IMPACT_INPUT_FILES]
    assert len(files) >= 6
    assert [f.name for f in files if f"`{f.name}`" not in DOC] == []


def test_hand_entered_official_inputs_cite_a_source_in_the_register():
    # Inputs marked "official" in the assumptions file must be traceable from the register.
    from fiscal_impact_model.modeling import impact

    A = impact.load_assumptions(config.IMPACT_ASSUMPTIONS)
    official = [k for k, a in A.items() if a.status == "official"]
    assert official
    assert [k for k in official if f"`{k}`" not in DOC] == []


def test_every_csv_in_data_is_either_loaded_or_a_model_input():
    # All input data lives in data/; a CSV in neither list would be silently ignored.
    known = {*config.REFERENCE_FILES, *config.IMPACT_INPUT_FILES}
    assert sorted(f.name for f in config.DATA_DIR.glob("*.csv") if f not in known) == []
    assert all(f.exists() for f in known)
