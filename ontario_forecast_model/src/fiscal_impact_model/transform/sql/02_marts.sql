-- MARTS: analysis-ready tables. Everything aligned to the City's fiscal year.

-- Monthly -> fiscal-year averages. n_months lets the panel drop partial years
-- (averaging 7 months of a growing series would bias the FY level).
create or replace table marts.bls_fy as
select series_id, fiscal_year(month_start) as fy, avg(value) as value, count(*) as n_months
from staging.bls_month group by all;

create or replace table marts.laus_city_fy as
select city, fiscal_year(month_start) as fy,
       avg(labor_force) as labor_force, avg(employment) as employment,
       avg(unemployment) as unemployment,
       avg(unemployment) / nullif(avg(labor_force), 0) * 100 as unemployment_rate,
       count(*) as n_months
from staging.laus_city_month group by all;

-- Peer comparison: tax revenue for Ontario and neighbors -----------------------
create or replace table marts.city_tax_fy as
with cpi as (select fy, value as cpi from marts.bls_fy join staging.bls_series using (series_id)
             where column_name = 'cpi_la' and n_months = 12),
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
left join base b on true    -- not a cross join: an empty base must not drop every row
order by t.city, t.fy;      -- fixed order, so the exported CSV doesn't reshuffle on every run

-- Ontario modeling panel: one row per fiscal year ------------------------------
create or replace table marts.ontario_fy_panel as
-- BLS series IDs live only in config.BLS_SERIES (staging.bls_series); pivot by column name.
with bls as (
    select fy,
        max(value) filter (where column_name = 'msa_nonfarm_jobs_k')    as msa_nonfarm_jobs_k,
        max(value) filter (where column_name = 'msa_leisure_jobs_k')    as msa_leisure_jobs_k,
        max(value) filter (where column_name = 'msa_transport_jobs_k')  as msa_transport_jobs_k,
        max(value) filter (where column_name = 'msa_unemployment_rate') as msa_unemployment_rate,
        max(value) filter (where column_name = 'cpi_la')                as cpi_la,
        max(value) filter (where column_name = 'cpi_us_lodging')        as cpi_us_lodging
    from marts.bls_fy join staging.bls_series using (series_id)
    where n_months = 12 group by fy),
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
           t.sales_tax_total, t.tot_revenue_real, t.sales_tax_total_real, t.sales_tax_measure_q,
           f.* exclude (fy), l.* exclude (fy), o.* exclude (fy),
           t.fy in (select fy from staging.covid_fys) as covid_shock   -- from config.COVID_SHOCK_FYS
    from marts.city_tax_fy t
    left join bls f using (fy) left join laus l using (fy) left join lodes o using (fy)
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

-- ACS place-of-work share with Census proportion MOE ---------------------------
-- MOE_p = sqrt(MOE_num^2 - p^2 * MOE_den^2) / den  (Census ACS handbook; if the
-- radicand is negative use the ratio formula with +). Matched by label, not code.
create or replace table marts.acs_place_of_work as
with num as (select acs_year, geo, estimate n, moe n_moe from staging.acs_place
             where acs_group = 'B08008' and lower(label) like '%worked in place of residence'),
den as (select acs_year, geo, estimate d, moe d_moe from staging.acs_place
        where acs_group = 'B08008' and lower(label) like '% > living in a place')  -- not "Not living"
select acs_year, acs_year - 4 as window_start, geo, n as worked_in_place_of_residence,
       d as workers_living_in_place, n / d as share,
       case when n_moe^2 - (n/d)^2 * d_moe^2 >= 0
            then sqrt(n_moe^2 - (n/d)^2 * d_moe^2) / d
            else sqrt(n_moe^2 + (n/d)^2 * d_moe^2) / d end                 as share_moe90,
       acs_year in (select acs_year from staging.acs_vintages)              as non_overlapping_vintage
from num join den using (acs_year, geo)
order by geo, acs_year;

-- Change between NON-overlapping ACS vintages, with a 90% significance test.
-- (Comparing overlapping 5-year windows double-counts shared survey years.)
create or replace table marts.acs_vintage_change as
with v as (select * from staging.acs_place where acs_year in (select acs_year from staging.acs_vintages)
           and estimate is not null and moe is not null),
pairs as (select a.geo, a.acs_group, a.variable, a.label, a.acs_year as from_year,
                 b.acs_year as to_year, a.estimate as from_est, b.estimate as to_est,
                 a.moe as from_moe, b.moe as to_moe
          from v a join v b on a.geo = b.geo and a.variable = b.variable
                           and b.acs_year = a.acs_year + 5)
select *, to_est - from_est as change,
       sqrt(from_moe^2 + to_moe^2) as change_moe90,
       abs(to_est - from_est) > sqrt(from_moe^2 + to_moe^2) as significant_90
from pairs;

-- OEWS: latest year, wide, with ratio to the all-occupation median -------------
create or replace table marts.msa_occupation_wages as
with latest as (select max(year) y from staging.oews_msa),
w as (select soc, occupation, pathway,
             max(value) filter (where measure = 'employment')          as employment,
             max(value) filter (where measure = 'mean_annual_wage')    as mean_annual_wage,
             max(value) filter (where measure = 'median_annual_wage')  as median_annual_wage,
             max(year) as year
      from staging.oews_msa, latest where year = latest.y group by all)
select w.*, w.median_annual_wage / (select median_annual_wage from w where soc = '00-0000')
            as median_vs_all_occupations,
       p.median_annual_wage                                   as proposal_median_wage,
       w.median_annual_wage / p.median_annual_wage - 1         as pct_diff_vs_proposal
from w left join staging.proposal_wages p using (soc)
order by w.median_annual_wage desc nulls last;

-- HEADLINE METRICS: one value per metric, official source first --------------
-- Rule: State Controller / Census / BLS / City adopted budget win. A proposal figure
-- is used only when no official value exists, and is flagged is_fallback = true.
create or replace table marts.headline_metrics as
with lodes as (select * from staging.lodes_ontario_cy order by cy desc limit 1),
tax as (select * from marts.city_tax_fy where city = 'Ontario' order by fy desc limit 1),
official(metric, period, "value", source) as (   -- quoted: keyword in DuckDB >= 1.5
    select 'share_residents_work_local', cy, share_residents_work_local,
           'Census LODES 8, all jobs (JT00)' from lodes
    union all select 'share_jobs_held_by_residents', cy, share_jobs_held_by_residents,
           'Census LODES 8, all jobs (JT00)' from lodes
    union all select 'live_and_work_in_ontario', cy, live_and_work, 'Census LODES 8' from lodes
    union all select 'employed_residents', cy, employed_residents, 'Census LODES 8' from lodes
    union all select 'inflow_commuters', cy, inflow_commuters, 'Census LODES 8' from lodes
    union all select 'tot_revenue_actual', fy, tot_revenue, 'CA State Controller' from tax
    union all select 'sales_tax_actual', fy, sales_tax_total,
           'CA State Controller (Bradley-Burns + in-lieu)' from tax
    union all select 'sales_tax_incl_measure_q_actual', fy, sales_tax_total + sales_tax_measure_q,
           'CA State Controller (Bradley-Burns + Measure Q; excludes Prop 172)' from tax
           where sales_tax_measure_q > 0
    union all select 'sales_tax_bradley_burns_fy27_budget', fy, sales_use_tax, source
              from staging.city_sales_tax_detail where fy = 2027 and basis = 'adopted'
    union all select 'measure_q_fy27_budget', fy, measure_q, source
              from staging.city_sales_tax_detail where fy = 2027 and basis = 'adopted'
    union all select 'tot_fy27_budget', fy, tot_budget, source from staging.city_budget
              where fy = 2027 and tot_budget is not null
    union all select 'sales_tax_fy27_budget', fy, sales_tax_budget, source from staging.city_budget
              where fy = 2027 and sales_tax_budget is not null
)
select coalesce(o.metric, p.metric)                                         as metric,
       coalesce(o.value, p.value)                                           as value,
       coalesce(o.period, p.period)                                         as period,
       coalesce(o.source, 'Proposal text (fallback: no official source loaded)') as source,
       o.value is null                                                      as is_fallback,
       p.value                                                              as proposal_value,
       case when o.value is not null and p.value is not null
            then o.value / p.value - 1 end                                  as pct_diff_vs_proposal
from official o full join staging.proposal_benchmarks p on o.metric = p.metric
order by metric;

-- County industry structure (calendar year; context, not a model input) -------
create or replace table marts.sb_county_sector_cy as
select * from staging.qcew_county_sector_cy
where own_code = '5' and industry_code <> '10' and disclosure_code is distinct from 'N'
order by cy, industry_code;
