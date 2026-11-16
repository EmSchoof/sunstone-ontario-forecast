"""Run the real SQL against tiny hand-made raw tables in an in-memory DuckDB."""

import duckdb
import pytest

from ontario_forecast.transform.checks import run_checks
from ontario_forecast.transform.run import build, source_snapshot


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("create schema raw")
    c.execute("""create table raw.sco_city_revenue_lines as select * from (values
        ('Ontario', 2015, 'Sales and Use Taxes_General Revenues', 100.0, 170000),
        ('Ontario', 2015, 'In-Lieu Local Sales and Use Taxes_General Revenues', 30.0, 170000),
        ('Ontario', 2015, 'Transient Lodging Taxes_General Revenues', 10.0, 170000),
        ('Ontario', 2015, 'Transient Lodging Taxes_Functional Revenues', 0.0, 170000),
        ('Ontario', 2016, 'Sales and Use Taxes_General Revenues', 140.0, 171000),
        ('Ontario', 2016, 'Transient Lodging Taxes_General Revenues', 11.0, 171000),
        ('Ontario', 2017, 'Sales and Use Taxes_General Revenues', 150.0, 172000),
        ('Ontario', 2017, 'Transient Occupancy Taxes_General Revenues', 12.0, 172000)
        ) t(entity_name, fiscal_year, line_description, value, estimated_population)""")
    # CPI flat at 100 for full fiscal years 2015-2017 (Jul 2014 .. Jun 2017)
    # Explicit AS: `value` is a keyword in DuckDB >= 1.5, so implicit aliases fail to parse.
    c.execute("""create table raw.bls_observations as
        select 'CUURS49ASA0' as series_id, d::date as obs_date, 100.0 as value
        from range(date '2014-07-01', date '2017-07-01', interval 1 month) as r(d)""")
    c.execute("""create table raw.laus_city_monthly as select * from (values
        ('Ontario city', 2015, 'June', 'N', 100.0, 95.0, 5.0, 5.0, 'Final'),
        ('Ontario city', 2015, 'July', 'N', 100.0, 95.0, 5.0, 5.0, 'Final')
        ) t(area_name, year, month, seasonally_adjusted, labor_force, employment,
            unemployment, unemployment_rate, status)""")
    c.execute("""create table raw.qcew_county_annual as select * from (values
        (2024, '5', '72', '74', '', 1.0, 100.0, 1.0, 30000.0)
        ) t(year, own_code, industry_code, agglvl_code, disclosure_code,
            annual_avg_estabs, annual_avg_emplvl, total_annual_wages, avg_annual_pay)""")
    build(c)
    yield c
    c.close()


def test_triple_flip_in_lieu_added_back(con):
    v = con.execute("select sales_tax_total from marts.city_tax_fy where fy = 2015").fetchone()[0]
    assert v == 130.0


def test_measure_q_is_kept_out_of_the_forecast_series_but_reported(con):
    # The State Controller files Measure Q under a catch-all line: read it only for Ontario, FY2024+
    con.execute("""insert into raw.sco_city_revenue_lines values
        ('Ontario', 2017, 'Other Taxes – Other (Specify)_General Revenues', 5.0, 172000),
        ('Ontario', 2024, 'Sales and Use Taxes_General Revenues', 150.0, 172000),
        ('Ontario', 2024, 'Transient Occupancy Taxes_General Revenues', 12.0, 172000),
        ('Ontario', 2024, 'Other Taxes – Other (Specify)_General Revenues', 90.0, 172000),
        ('Fontana', 2024, 'Other Taxes – Other (Specify)_General Revenues', 7.0, 210000)""")
    build(con)
    rows = con.execute(
        "select city, fy, sales_tax_total, sales_tax_measure_q from marts.city_tax_fy "
        "where fy in (2017, 2024) order by city, fy"
    ).fetchall()
    assert rows == [
        ("Fontana", 2024, None, 0.0),  # another city's catch-all line is not Measure Q
        ("Ontario", 2017, 150.0, 0.0),  # before Measure Q existed
        ("Ontario", 2024, 150.0, 90.0),  # the forecast target stays Bradley-Burns only
    ]
    v = con.execute(
        "select value from marts.headline_metrics where metric = 'sales_tax_incl_measure_q_actual'"
    ).fetchone()[0]
    assert v == 240.0


def test_city_budget_split_gives_a_like_for_like_sales_tax_marker(con):
    con.execute("""insert into raw.manual_city_sales_tax_detail values
        ('2027', 'adopted', '148,791,668', '3213875', '64250000', '216255543', '18500000', 'Budget p. 69')""")
    build(con)
    got = dict(
        con.execute(
            "select metric, value from marts.headline_metrics where metric like '%fy27_budget'"
        ).fetchall()
    )
    assert got["sales_tax_bradley_burns_fy27_budget"] == 148_791_668
    assert got["measure_q_fy27_budget"] == 64_250_000
    assert [c.name for c, _ in run_checks(con) if c.severity == "error"] == []


def test_tot_rename_is_continuous_and_functional_lines_excluded(con):
    rows = con.execute("select fy, tot_revenue from marts.ontario_fy_panel order by fy").fetchall()
    assert rows == [(2015, 10.0), (2016, 11.0), (2017, 12.0)]


def test_fiscal_year_boundary(con):
    # June 2015 -> FY2015, July 2015 -> FY2016
    rows = con.execute("select fy, n_months from marts.laus_city_fy order by fy").fetchall()
    assert rows == [(2015, 1), (2016, 1)]


def test_partial_fiscal_years_excluded_from_panel(con):
    # LAUS has 1 month per FY -> must not appear in the panel
    assert con.execute("select count(laus_employment) from marts.ontario_fy_panel").fetchone()[0] == 0


def test_bls_series_ids_come_from_config(con):
    # CPI is joined by column name via staging.bls_series, so the deflator resolves
    assert con.execute("select count(cpi_la) from marts.ontario_fy_panel").fetchone()[0] == 3


def test_headline_metrics_prefer_official_values(con):
    rows = dict(con.execute("select metric, is_fallback from marts.headline_metrics").fetchall())
    assert rows["tot_revenue_actual"] is False  # State Controller value used
    assert rows["tot_fy27_budget"] is True  # no City budget loaded -> labeled fallback


def test_checks_pass_on_clean_data(con):
    assert [c.name for c, _ in run_checks(con) if c.severity == "error"] == []


def test_source_snapshot_lists_every_raw_table_with_row_counts(con):
    snap = {r["raw_table"]: r for r in source_snapshot(con)}
    assert snap["sco_city_revenue_lines"]["rows"] == 8
    assert snap["manual_city_budget_revenue"]["rows"] == 0  # empty template is still listed
    assert snap["sco_city_revenue_lines"]["last_loaded_at"] == ""  # no dlt load log in this test


def test_ingest_drops_only_empty_placeholders_dlt_did_not_create(con):
    # build() made empty placeholders (e.g. the budget tables); dlt-loaded tables carry _dlt_load_id.
    from ontario_forecast.ingest.run import drop_empty_placeholders

    con.execute("create table raw.loaded_by_dlt (x integer, _dlt_load_id varchar)")
    dropped = drop_empty_placeholders(con)
    assert "manual_city_budget_revenue" in dropped and "manual_city_sales_tax_detail" in dropped
    assert "loaded_by_dlt" not in dropped  # dlt's own table, even though empty
    assert "sco_city_revenue_lines" not in dropped  # has rows: never touched
    assert con.execute("select count(*) from raw.sco_city_revenue_lines").fetchone()[0] == 8
