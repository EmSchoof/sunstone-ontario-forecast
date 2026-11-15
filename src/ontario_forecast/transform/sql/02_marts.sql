-- MARTS: analysis-ready tables. Everything aligned to the City's fiscal year.

-- Monthly -> fiscal-year averages. n_months lets the panel drop partial years
-- (averaging 7 months of a growing series would bias the FY level).
create or replace table marts.fred_fy as
select series_id, fiscal_year(month_start) as fy, avg(value) as value, count(*) as n_months
from staging.fred_month group by all;

create or replace table marts.laus_city_fy as
select city, fiscal_year(month_start) as fy,
       avg(labor_force) as labor_force, avg(employment) as employment,
       avg(unemployment) as unemployment,
       avg(unemployment) / nullif(avg(labor_force), 0) * 100 as unemployment_rate,
       count(*) as n_months
from staging.laus_city_month group by all;

-- Peer comparison: tax revenue for Ontario and neighbors -----------------------
create or replace table marts.city_tax_fy as
with cpi as (select fy, value as cpi from marts.fred_fy
             where series_id = 'CUURS49ASA0' and n_months = 12),
base as (select cpi as cpi_base from cpi
         where fy = (select max(fy) from staging.city_tax_fy where fy in (select fy from cpi)))
select t.*,
       t.sales_tax_bradley_burns + t.sales_tax_in_lieu                     as sales_tax_total,
       t.tot_revenue * b.cpi_base / c.cpi                                   as tot_revenue_real,
       (t.sales_tax_bradley_burns + t.sales_tax_in_lieu) * b.cpi_base / c.cpi as sales_tax_total_real,
       t.tot_revenue / t.population                                         as tot_per_capita,
       (t.sales_tax_bradley_burns + t.sales_tax_in_lieu) / t.population     as sales_tax_per_capita
from staging.city_tax_fy t
left join cpi c using (fy)
left join base b on true;   -- not a cross join: an empty base must not drop every row

-- Ontario modeling panel: one row per fiscal year ------------------------------
create or replace table marts.ontario_fy_panel as
with fred as (
    select fy,
        max(value) filter (where series_id = 'RIVE106NA')            as msa_nonfarm_jobs_k,
        max(value) filter (where series_id = 'RIVE106LEIHN')         as msa_leisure_jobs_k,
        max(value) filter (where series_id = 'SMU06401404300000001') as msa_transport_jobs_k,
        max(value) filter (where series_id = 'RIVE106UR')            as msa_unemployment_rate,
        max(value) filter (where series_id = 'CUURS49ASA0')          as cpi_la,
        max(value) filter (where series_id = 'CUSR0000SEHB')         as cpi_us_lodging
    from marts.fred_fy where n_months = 12 group by fy),
laus as (
    select fy, labor_force as laus_labor_force, employment as laus_employment,
           unemployment_rate as laus_unemployment_rate
    from marts.laus_city_fy where city = 'Ontario' and n_months = 12),
lodes as (
    select cy as fy, employed_residents as lodes_employed_residents,
           jobs_in_ontario as lodes_jobs_in_ontario, live_and_work as lodes_live_and_work,
           share_residents_work_local as lodes_share_residents_work_local,
           share_jobs_held_by_residents as lodes_share_jobs_held_by_residents,
           share_high_wage_residents_work_local as lodes_share_high_wage_residents_work_local
    from staging.lodes_ontario_cy),
base as (
    select t.fy, t.population, t.tot_revenue, t.sales_tax_bradley_burns, t.sales_tax_in_lieu,
           t.sales_tax_total, t.tot_revenue_real, t.sales_tax_total_real,
           f.* exclude (fy), l.* exclude (fy), o.* exclude (fy),
           t.fy in (2020, 2021, 2022) as covid_shock      -- keep in sync with config.COVID_SHOCK_FYS
    from marts.city_tax_fy t
    left join fred f using (fy) left join laus l using (fy) left join lodes o using (fy)
    where t.city = 'Ontario')
select *,
    -- Growth rates (log differences). Levels of trending series are non-stationary;
    -- correlating them produces spurious relationships, so models use these.
    ln(tot_revenue_real)       - ln(lag(tot_revenue_real)       over w) as dlog_tot_real,
    ln(sales_tax_total_real)   - ln(lag(sales_tax_total_real)   over w) as dlog_sales_tax_real,
    ln(population)             - ln(lag(population)             over w) as dlog_population,
    ln(msa_nonfarm_jobs_k)     - ln(lag(msa_nonfarm_jobs_k)     over w) as dlog_msa_nonfarm_jobs,
    ln(msa_leisure_jobs_k)     - ln(lag(msa_leisure_jobs_k)     over w) as dlog_msa_leisure_jobs,
    ln(msa_transport_jobs_k)   - ln(lag(msa_transport_jobs_k)   over w) as dlog_msa_transport_jobs,
    ln(laus_employment)        - ln(lag(laus_employment)        over w) as dlog_laus_employment,
    ln(cpi_us_lodging)         - ln(lag(cpi_us_lodging)         over w) as dlog_cpi_lodging,
    msa_unemployment_rate      - lag(msa_unemployment_rate)     over w  as d_msa_unemployment_rate
from base
window w as (order by fy)
order by fy;

-- County industry structure (calendar year; context, not a model input) -------
create or replace table marts.sb_county_sector_cy as
select * from staging.qcew_county_sector_cy
where own_code = '5' and industry_code <> '10' and disclosure_code is distinct from 'N'
order by cy, industry_code;
