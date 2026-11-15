"""Run the real SQL against tiny hand-made raw tables in an in-memory DuckDB."""
import duckdb
import pytest

from ontario_forecast.transform.checks import run_checks
from ontario_forecast.transform.run import build


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
    c.execute("""create table raw.fred_observations as
        select 'CUURS49ASA0' series_id, d::date obs_date, 100.0 value
        from range(date '2014-07-01', date '2017-07-01', interval 1 month) r(d)""")
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


def test_checks_pass_on_clean_data(con):
    assert [c.name for c, _ in run_checks(con) if c.severity == "error"] == []
