-- Staging: type-cast and clean the raw FAA / NASA / GAO loads.
CREATE SCHEMA IF NOT EXISTS stg;
CREATE OR REPLACE TABLE stg.sdr AS
SELECT DISTINCT ON (OperatorControlNumber)
  OperatorControlNumber                                   AS sdr_id,
  CAST(strptime(split_part(DifficultyDate,' ',1),'%m/%d/%Y') AS DATE) AS difficulty_date,
  CAST(strptime(split_part(SubmissionDate,' ',1),'%m/%d/%Y') AS DATE) AS submission_date,
  NULLIF(trim(OperatorDesignator),'nan')                  AS operator_code,
  NULLIF(trim(SubmitterTypeCode),'nan')                   AS submitter_type,
  NULLIF(trim(SDRType),'nan')                             AS sdr_type,
  lpad(NULLIF(trim(replace(JASCCode,'.0','')),'nan'),4,'0') AS jasc_code,
  NULLIF(NatureOfConditionA,'nan')                        AS nature_code,
  NULLIF(PrecautionaryProcedureA,'nan')                   AS precaution_code,
  NULLIF(StageOfOperationCode,'nan')                      AS stage_code,
  NULLIF(HowDiscoveredCode,'nan')                         AS discovered_code,
  upper(NULLIF(trim(RegistryNNumber),'nan'))              AS n_number,
  upper(NULLIF(trim(AircraftMake),'nan'))                 AS aircraft_make,
  upper(NULLIF(trim(AircraftModel),'nan'))                AS aircraft_model,
  NULLIF(trim(AircraftSerialNumber),'nan')                AS aircraft_serial,
  TRY_CAST(NULLIF(AircraftTotalTime,'nan') AS DOUBLE)     AS aircraft_total_hours,
  TRY_CAST(NULLIF(AircraftTotalCycles,'nan') AS DOUBLE)   AS aircraft_total_cycles,
  upper(NULLIF(trim(PartName),'nan'))                     AS part_name,
  upper(NULLIF(trim(PartNumber),'nan'))                   AS part_number,
  upper(NULLIF(trim(PartCondition),'nan'))                AS part_condition,
  NULLIF(Discrepancy,'nan')                               AS discrepancy_text
FROM raw.sdrs
WHERE OperatorControlNumber IS NOT NULL AND OperatorControlNumber <> 'nan'
ORDER BY OperatorControlNumber;

-- FAA registry: one row per currently registered N-number
CREATE OR REPLACE TABLE stg.registry AS
SELECT upper(trim("N-NUMBER")) AS n_number, trim("MFR MDL CODE") AS mfr_mdl_code,
       TRY_CAST(trim("YEAR MFR") AS INT) AS year_mfr, trim("TYPE REGISTRANT") AS registrant_type,
       trim("NAME") AS registrant_name, trim("STATE") AS registrant_state,
       TRY_CAST(try_strptime(trim("AIR WORTH DATE"),'%Y%m%d') AS DATE) AS airworthiness_date
FROM raw.registry_master;
CREATE OR REPLACE TABLE stg.acftref AS
SELECT trim(CODE) AS mfr_mdl_code, trim(MFR) AS ref_mfr, trim(MODEL) AS ref_model,
       TRY_CAST(trim("NO-ENG") AS INT) AS n_engines, TRY_CAST(trim("NO-SEATS") AS INT) AS n_seats,
       trim("AC-WEIGHT") AS weight_class
FROM raw.registry_acftref;
