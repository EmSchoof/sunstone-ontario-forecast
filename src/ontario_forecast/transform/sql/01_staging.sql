-- STAGING: one cleaned, typed table per source. No joins across sources here.
create schema if not exists raw;
create schema if not exists staging;
create schema if not exists marts;

-- Fiscal year convention used everywhere: FY t = July (t-1) through June t.
-- (The State Controller's fiscal_year is the ending year: FY2025 = Jul 2024-Jun 2025.)
create or replace macro fiscal_year(d) as year(d) + case when month(d) >= 7 then 1 else 0 end;

-- LODES may be skipped on a run; keep downstream SQL valid with an empty table.
create table if not exists raw.lodes_ontario_flows (
    year bigint, jobs_in_ontario bigint, employed_residents bigint, live_and_work bigint,
    jobs_high_wage bigint, residents_high_wage bigint, live_and_work_high_wage bigint,
    includes_aux boolean, ontario_blocks bigint
);

-- State Controller: city tax revenue by fiscal year ------------------------
-- * TOT line was renamed in FY2017 ("Transient Lodging" -> "Transient Occupancy").
-- * FY2005-FY2016 "triple flip": part of the 1% Bradley-Burns sales tax was paid to
--   cities as "In-Lieu Local Sales and Use Taxes". Adding it back removes a false
--   level break in 2005 and 2016.
-- * Only "_General Revenues" lines; "_Functional Revenues" duplicates are excluded.
create or replace table staging.city_tax_fy as
select
    entity_name                                                                 as city,
    fiscal_year::integer                                                        as fy,
    sum(value) filter (where regexp_matches(line_description,
        '^Transient (Lodging|Occupancy) Taxes_General Revenues$'))              as tot_revenue,
    sum(value) filter (where line_description = 'Sales and Use Taxes_General Revenues')
                                                                                as sales_tax_bradley_burns,
    coalesce(sum(value) filter (where line_description =
        'In-Lieu Local Sales and Use Taxes_General Revenues'), 0)               as sales_tax_in_lieu,
    max(estimated_population)                                                   as population
from raw.sco_city_revenue_lines
group by all;

-- EDD LAUS: city labor force, not seasonally adjusted (consistent across cities) --
create or replace table staging.laus_city_month as
select
    regexp_replace(area_name, ' city$', '')                                     as city,
    strptime(year::varchar || ' ' || month || ' 1', '%Y %B %d')::date           as month_start,
    labor_force, employment, unemployment,
    unemployment / nullif(labor_force, 0) * 100                                 as unemployment_rate,
    status
from raw.laus_city_monthly
where seasonally_adjusted = 'N'
  and month in ('January','February','March','April','May','June','July',
                'August','September','October','November','December');

-- FRED: long monthly ----------------------------------------------------------
create or replace table staging.fred_month as
select series_id, obs_date::date as month_start, value
from raw.fred_observations
where value is not null;

-- QCEW: county x NAICS sector, calendar year ---------------------------------
create or replace table staging.qcew_county_sector_cy as
with titles(industry_code, sector) as (values
    ('10','Total, all industries'), ('11','Agriculture'), ('21','Mining'), ('22','Utilities'),
    ('23','Construction'), ('31-33','Manufacturing'), ('42','Wholesale trade'),
    ('44-45','Retail trade'), ('48-49','Transportation & warehousing'), ('51','Information'),
    ('52','Finance & insurance'), ('53','Real estate'), ('54','Professional & technical services'),
    ('55','Management of companies'), ('56','Administrative & waste services'),
    ('61','Educational services'), ('62','Health care & social assistance'),
    ('71','Arts, entertainment & recreation'), ('72','Accommodation & food services'),
    ('81','Other services'), ('92','Public administration'), ('99','Unclassified'))
select q.year::integer as cy, q.own_code, q.industry_code, t.sector,
       q.annual_avg_emplvl as employment, q.avg_annual_pay, q.annual_avg_estabs as establishments,
       q.disclosure_code
from raw.qcew_county_annual q left join titles t using (industry_code);

-- LODES: Ontario live/work flows, calendar year -------------------------------
-- LODES counts primary jobs held around Q2 of year t, which falls inside FY t.
create or replace table staging.lodes_ontario_cy as
select
    year::integer                                                          as cy,
    employed_residents, jobs_in_ontario, live_and_work,
    jobs_in_ontario - live_and_work                                        as inflow_commuters,
    employed_residents - live_and_work                                     as outflow_commuters,
    live_and_work / nullif(employed_residents, 0)                          as share_residents_work_local,
    live_and_work / nullif(jobs_in_ontario, 0)                             as share_jobs_held_by_residents,
    residents_high_wage, jobs_high_wage, live_and_work_high_wage,
    live_and_work_high_wage / nullif(residents_high_wage, 0)               as share_high_wage_residents_work_local,
    includes_aux
from raw.lodes_ontario_flows;
