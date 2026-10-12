-- KPI marts. Each view states whether its KPI is REAL, APPROXIMATED or BENCHMARK (see docs/schema.md).

-- Approximated MTBF: mean flight hours between reporting days, per model (MTBR = mean time between reports)
CREATE OR REPLACE VIEW mart.kpi_mtbr_by_model AS
SELECT a.make, a.model, count(*) AS intervals, count(DISTINCT i.aircraft_key) AS tails,
       round(sum(i.hours_between)/count(*),1) AS mtbr_hours,
       round(median(i.hours_between),1) AS median_hours_between,
       round(sum(i.cycles_between)/nullif(count(i.cycles_between),0),1) AS mean_cycles_between,
       round(sum(i.hours_between)/nullif(sum(i.ends_in_interruption::INT),0),0) AS hours_per_operational_interruption
FROM mart.fct_tail_interval i JOIN mart.dim_aircraft a USING (aircraft_key)
WHERE i.is_valid GROUP BY 1,2 HAVING count(*) >= 20 ORDER BY mtbr_hours;

-- Repeat discrepancy rate (REAL, as reported): same tail + same ATA chapter within 30 days
CREATE OR REPLACE VIEW mart.kpi_repeat_by_ata AS
SELECT d.ata_chapter, d.ata_chapter_name, count(*) AS reports,
       sum(f.is_repeat_30d_any::INT) AS repeats_any, round(100.0*avg(f.is_repeat_30d_any::INT),1) AS repeat_rate_any_pct,
       sum(f.is_in_operation::INT) AS in_operation_reports,
       sum(f.is_repeat_30d::INT) AS operational_repeats,
       round(100.0*sum(f.is_repeat_30d::INT)/nullif(sum(f.is_in_operation::INT),0),1) AS operational_repeat_rate_pct,
       round(100.0*avg(f.is_operational_interruption::INT),1) AS interruption_rate_pct
FROM mart.fct_discrepancy f JOIN mart.dim_ata d USING (ata_key)
GROUP BY 1,2 HAVING count(*) >= 30 ORDER BY reports DESC;

-- Monthly trend (REAL): volume, interruptions, repeats, reporting lag
CREATE OR REPLACE VIEW mart.kpi_monthly AS
SELECT dd.year_month, count(*) AS reports, count(DISTINCT f.aircraft_key) AS tails_reporting,
       sum(f.is_operational_interruption::INT) AS operational_interruptions,
       round(100.0*sum(f.is_repeat_30d::INT)/nullif(sum(f.is_in_operation::INT),0),1) AS operational_repeat_rate_pct,
       median(f.report_lag_days) AS median_report_lag_days
FROM mart.fct_discrepancy f JOIN mart.dim_date dd ON dd.date_key = f.difficulty_date_key
GROUP BY 1 ORDER BY 1;

-- Reporting backlog (APPROXIMATION of a "backlog"): days from event to FAA submission
CREATE OR REPLACE VIEW mart.kpi_report_lag AS
SELECT o.operator_code, count(*) AS reports, median(f.report_lag_days) AS median_lag_days,
       quantile_cont(f.report_lag_days,0.9) AS p90_lag_days,
       round(100.0*avg((f.report_lag_days > 3)::INT),1) AS pct_over_3_days
FROM mart.fct_discrepancy f JOIN mart.dim_operator o USING (operator_key)
GROUP BY 1 HAVING count(*) >= 50 ORDER BY reports DESC;

-- Top failing parts (REAL demand signal; NOT a backlog)
CREATE OR REPLACE VIEW mart.kpi_top_parts AS
SELECT p.part_name, count(*) AS reports, count(DISTINCT f.aircraft_key) AS tails,
       mode(f.part_condition) AS most_common_condition,
       round(100.0*avg(f.is_operational_interruption::INT),1) AS interruption_rate_pct
FROM mart.fct_discrepancy f JOIN mart.dim_part p USING (part_key)
WHERE p.part_name NOT IN ('UNKNOWN','NONE','N/A') GROUP BY 1 ORDER BY reports DESC LIMIT 50;

-- Engine MTBF benchmark (REAL simulation data): NASA C-MAPSS cycles to failure
CREATE OR REPLACE VIEW mart.kpi_engine_mtbf AS
SELECT dataset, count(*) AS engines, round(avg(cycles_to_failure),1) AS mean_cycles_to_failure,
       min(cycles_to_failure) AS min_cycles, max(cycles_to_failure) AS max_cycles,
       round(stddev(cycles_to_failure)/avg(cycles_to_failure),3) AS coeff_variation
FROM mart.fct_engine_run GROUP BY 1 ORDER BY 1;
