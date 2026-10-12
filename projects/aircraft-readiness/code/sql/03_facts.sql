-- fct_discrepancy: one row per Service Difficulty Report (grain = OperatorControlNumber)
CREATE OR REPLACE TABLE mart.fct_discrepancy AS
WITH base AS (
  SELECT s.*, a.aircraft_key, o.operator_key, p.part_key
  FROM stg.sdr s
  LEFT JOIN mart.dim_aircraft a USING (n_number)
  LEFT JOIN mart.dim_operator o USING (operator_code)
  LEFT JOIN mart.dim_part p USING (part_name)),
ev AS ( -- prior report on the same tail + same ATA chapter, on an earlier day (within 30 days)
  SELECT b.sdr_id, max(p.difficulty_date) AS prev_same_ata_date,
         -- operational repeat: both reports arose in operation (not found during a scheduled inspection)
         max(CASE WHEN coalesce(p.stage_code,'NR') NOT IN ('IN','NR','UK') AND coalesce(b.stage_code,'NR') NOT IN ('IN','NR','UK')
                  THEN p.difficulty_date END) AS prev_oper_same_ata_date
  FROM base b JOIN base p ON p.n_number = b.n_number AND substr(p.jasc_code,1,2) = substr(b.jasc_code,1,2)
       AND p.difficulty_date < b.difficulty_date AND p.difficulty_date >= b.difficulty_date - INTERVAL 30 DAY
  GROUP BY b.sdr_id)
SELECT b.sdr_id,
  CAST(strftime(b.difficulty_date,'%Y%m%d') AS INT) AS difficulty_date_key,
  CAST(strftime(b.submission_date,'%Y%m%d') AS INT) AS submission_date_key,
  coalesce(b.aircraft_key, -1) AS aircraft_key, coalesce(b.operator_key, -1) AS operator_key,
  coalesce(b.part_key, -1) AS part_key, coalesce(b.jasc_code, 'UNK') AS ata_key,
  b.difficulty_date, b.submission_date,
  CASE WHEN b.submission_date >= b.difficulty_date THEN date_diff('day', b.difficulty_date, b.submission_date) END AS report_lag_days,
  (b.submission_date < b.difficulty_date) AS is_date_anomaly,
  b.aircraft_total_hours, b.aircraft_total_cycles,
  coalesce(b.stage_code,'-1') AS stage_code, coalesce(b.precaution_code,'-1') AS precaution_code, b.nature_code, b.discovered_code, b.part_condition,
  (b.stage_code NOT IN ('IN','NR','UK') AND b.stage_code IS NOT NULL) AS is_in_operation,
  (b.precaution_code IS NOT NULL AND b.precaution_code NOT IN ('K','O')) AS is_operational_interruption,
  (ev.prev_same_ata_date IS NOT NULL) AS is_repeat_30d_any,
  (ev.prev_oper_same_ata_date IS NOT NULL) AS is_repeat_30d,
  date_diff('day', ev.prev_same_ata_date, b.difficulty_date) AS days_since_prev_same_ata,
  b.discrepancy_text,
  FALSE AS is_synthetic
FROM base b LEFT JOIN ev USING (sdr_id);

-- fct_tail_interval: hours/cycles flown between consecutive reporting days on the same tail
CREATE OR REPLACE TABLE mart.fct_tail_interval AS
WITH d AS (
  SELECT aircraft_key, difficulty_date, max(aircraft_total_hours) h, max(aircraft_total_cycles) c,
         bool_or(is_operational_interruption) interrupt
  FROM mart.fct_discrepancy WHERE aircraft_key <> -1 AND aircraft_total_hours > 0
  GROUP BY 1,2),
l AS (SELECT *, lag(h) OVER w ph, lag(c) OVER w pc, lag(difficulty_date) OVER w pd
      FROM d WINDOW w AS (PARTITION BY aircraft_key ORDER BY difficulty_date))
SELECT aircraft_key, pd AS from_date, difficulty_date AS to_date,
       CAST(strftime(difficulty_date,'%Y%m%d') AS INT) AS to_date_key,
       h - ph AS hours_between, c - pc AS cycles_between, date_diff('day', pd, difficulty_date) AS days_between,
       interrupt AS ends_in_interruption,
       -- valid: hours increase, and imply < 20 h/day utilization (filters typos / hours reset)
       (h - ph > 0 AND (h - ph) <= 20 * greatest(date_diff('day', pd, difficulty_date),1)) AS is_valid
FROM l WHERE ph IS NOT NULL;

-- NASA C-MAPSS: one row per simulated engine run-to-failure (train sets FD001-FD004)
CREATE OR REPLACE TABLE mart.fct_engine_run AS
SELECT dataset, unit, max(cycle) AS cycles_to_failure, FALSE AS is_synthetic_data_source
FROM raw.cmapss GROUP BY 1,2;

-- GAO mission-capable benchmark (real, fleet-level, annual)
CREATE OR REPLACE TABLE mart.fct_mc_rate_benchmark AS
UNPIVOT raw.ref_gao ON fy2015, fy2016, fy2017, fy2018, fy2019, fy2020, fy2021
INTO NAME fiscal_year_label VALUE mc_rate_pct;
CREATE OR REPLACE TABLE mart.fct_mc_rate_benchmark AS
SELECT aircraft, service, mc_goal_pct, CAST(substr(fiscal_year_label,3) AS INT) AS fiscal_year,
       mc_rate_pct, mc_rate_pct - mc_goal_pct AS gap_to_goal_pts, mc_rate_pct >= mc_goal_pct AS met_goal, source
FROM mart.fct_mc_rate_benchmark;
