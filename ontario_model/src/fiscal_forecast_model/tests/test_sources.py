"""Offline tests for dlt resource construction (no network)."""

from fiscal_forecast_model.ingest.sources import _census_num, _num, _snake, manual_csv_resources


def test_manual_csv_resources_build_and_skip_empty_templates(tmp_path):
    (tmp_path / "filled.csv").write_text("FY,Passengers,Source\n2025,7000000,ONT report p.3\n")
    (tmp_path / "template.csv").write_text("fy,passengers,source\n")
    files = [tmp_path / "filled.csv", tmp_path / "template.csv"]
    resources = {r.name: r for r in manual_csv_resources(files)}  # must not raise
    assert set(resources) == {"manual_filled", "manual_template"}
    assert list(resources["manual_filled"]) == [
        {"fy": "2025", "passengers": "7000000", "source": "ONT report p.3"}
    ]
    assert list(resources["manual_template"]) == []


def test_parsers():
    assert _num(".") is None and _num("1,234.5") == 1234.5
    assert _census_num("-666666666") is None
    assert _snake(chr(0xFEFF) + "Seasonally Adjusted(Y/N)") == "seasonally_adjusted"  # UTF-8 BOM
