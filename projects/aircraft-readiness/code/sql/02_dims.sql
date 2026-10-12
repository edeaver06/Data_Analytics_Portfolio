CREATE SCHEMA IF NOT EXISTS mart;
-- dim_date: every day covered by the facts
CREATE OR REPLACE TABLE mart.dim_date AS
SELECT CAST(strftime(d,'%Y%m%d') AS INT) AS date_key, CAST(d AS DATE) AS date,
       year(d) AS year, quarter(d) AS quarter, month(d) AS month, strftime(d,'%Y-%m') AS year_month,
       dayofweek(d) AS day_of_week, strftime(d,'%a') AS day_name,
       CASE WHEN month(d)>=10 THEN year(d)+1 ELSE year(d) END AS us_fiscal_year
FROM range((SELECT min(difficulty_date) FROM stg.sdr), (SELECT max(submission_date) FROM stg.sdr) + INTERVAL 1 DAY, INTERVAL 1 DAY) t(d);

-- dim_ata: JASC 4-digit code -> ATA chapter
CREATE OR REPLACE TABLE mart.dim_ata AS
SELECT jasc_code AS ata_key, jasc_description, ata_chapter, ata_chapter_name FROM raw.ref_jasc
UNION ALL
SELECT DISTINCT s.jasc_code, 'UNLISTED CODE', substr(s.jasc_code,1,2), coalesce(c.ata_chapter_name,'UNKNOWN')
FROM stg.sdr s LEFT JOIN (SELECT DISTINCT ata_chapter, ata_chapter_name FROM raw.ref_jasc) c ON c.ata_chapter = substr(s.jasc_code,1,2)
WHERE s.jasc_code IS NOT NULL AND s.jasc_code NOT IN (SELECT jasc_code FROM raw.ref_jasc)
UNION ALL SELECT 'UNK', 'UNKNOWN (no JASC code on report)', '--', 'UNKNOWN';

-- dim_aircraft: one row per tail (N-number) seen in SDRs, enriched from the FAA registry
CREATE OR REPLACE TABLE mart.dim_aircraft AS
WITH t AS (
  SELECT n_number, arg_max(aircraft_make, difficulty_date) AS sdr_make, arg_max(aircraft_model, difficulty_date) AS sdr_model,
         arg_max(aircraft_serial, difficulty_date) AS serial, max(aircraft_total_hours) AS max_reported_hours,
         max(aircraft_total_cycles) AS max_reported_cycles
  FROM stg.sdr WHERE n_number IS NOT NULL GROUP BY 1)
SELECT row_number() OVER (ORDER BY t.n_number) AS aircraft_key, t.n_number, t.sdr_make AS make, t.sdr_model AS model,
       CASE WHEN t.sdr_make IN ('BOEING','AIRBUS','CNDAIR','EMB','DOUG','BOMBDR','ATR','DEHAV','MD') THEN 'Transport category'
            ELSE 'Other / GA / rotorcraft' END AS fleet_class,
       t.serial, t.max_reported_hours, t.max_reported_cycles,
       r.year_mfr, a.ref_mfr, a.ref_model, a.n_engines, a.n_seats, a.weight_class,
       r.registrant_state, r.n_number IS NOT NULL AS in_current_registry
FROM t LEFT JOIN stg.registry r ON r.n_number = t.n_number
       LEFT JOIN stg.acftref a ON a.mfr_mdl_code = r.mfr_mdl_code
UNION ALL  -- Unknown member: reports with no N-number
SELECT -1, '<UNKNOWN>', '<UNKNOWN>', '<UNKNOWN>', 'Unknown', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, FALSE;

-- dim_operator: operator designator (SDRS does not publish operator names)
CREATE OR REPLACE TABLE mart.dim_operator AS
SELECT row_number() OVER (ORDER BY operator_code) AS operator_key, operator_code,
       count(*) AS sdr_count_total
FROM stg.sdr WHERE operator_code IS NOT NULL GROUP BY operator_code
UNION ALL SELECT -1, '<UNKNOWN>', (SELECT count(*) FROM stg.sdr WHERE operator_code IS NULL);

-- dim_part: normalized part name
CREATE OR REPLACE TABLE mart.dim_part AS
SELECT row_number() OVER (ORDER BY part_name) AS part_key, part_name FROM (SELECT DISTINCT part_name FROM stg.sdr WHERE part_name IS NOT NULL)
UNION ALL SELECT -1, '<UNKNOWN>';

-- Code lookups. dim_sdr_code is unique on code_key (= code_type:code); dim_stage / dim_precaution are
-- unique on their code and cover every code seen in the facts (unlabelled codes become 'Unknown').
CREATE OR REPLACE TABLE mart.dim_sdr_code AS
SELECT code_type || ':' || code AS code_key, code_type, code, label, label_basis FROM raw.ref_codes;
CREATE OR REPLACE TABLE mart.dim_stage AS
SELECT k.stage_code, coalesce(r.label, 'Unknown') AS stage_label, coalesce(r.label_basis, 'unverified (not in label table)') AS label_basis,
       coalesce(k.stage_code NOT IN ('IN','NR','UK','-1'), FALSE) AS is_in_operation
FROM (SELECT DISTINCT coalesce(stage_code,'-1') AS stage_code FROM stg.sdr) k
LEFT JOIN raw.ref_codes r ON r.code_type='stage' AND r.code=k.stage_code;
CREATE OR REPLACE TABLE mart.dim_precaution AS
SELECT k.precaution_code, coalesce(r.label, 'Unknown') AS precaution_label,
       coalesce(r.label_basis, 'unverified (not in label table)') AS label_basis,
       k.precaution_code NOT IN ('K','O','-1') AS is_operational_interruption
FROM (SELECT DISTINCT coalesce(precaution_code,'-1') AS precaution_code FROM stg.sdr) k
LEFT JOIN raw.ref_codes r ON r.code_type='precaution' AND r.code=k.precaution_code;
