-- Independent SQL re-implementation of the HEDIS-STYLE measures (used for the audit),
-- plus reporting views over the R-built marts. Not certified HEDIS.
DROP VIEW IF EXISTS v_years;
CREATE VIEW v_years AS
WITH RECURSIVE y(my) AS (SELECT 2017 UNION ALL SELECT my + 1 FROM y WHERE my < 2026)
SELECT my,
       printf('%d-01-01', my) AS p_start,
       MIN(printf('%d-12-31', my), (SELECT value FROM meta WHERE key = 'data_end')) AS p_end,
       printf('%d-12-31', my) AS dec31
FROM y;

DROP VIEW IF EXISTS v_denominator;
CREATE VIEW v_denominator AS
WITH dm AS (
  SELECT DISTINCT y.my, d.patient FROM stg_dx AS d JOIN v_years AS y ON d.start <= y.p_end
), seen AS (
  SELECT DISTINCT y.my, e.patient FROM stg_enc AS e JOIN v_years AS y ON e.date BETWEEN y.p_start AND y.p_end
), aged AS (
  SELECT y.my, y.p_end, p.patient, p.sex, p.deathdate,
         (CAST(strftime('%Y', y.dec31) AS INT) - CAST(strftime('%Y', p.birthdate) AS INT)
          - (strftime('%m-%d', y.dec31) < strftime('%m-%d', p.birthdate))) AS age
  FROM stg_patients AS p CROSS JOIN v_years AS y
)
SELECT a.my, a.patient, a.sex, a.age
FROM aged AS a
JOIN dm   ON dm.my = a.my AND dm.patient = a.patient
JOIN seen ON seen.my = a.my AND seen.patient = a.patient
WHERE a.age BETWEEN 18 AND 75 AND (a.deathdate IS NULL OR a.deathdate > a.p_end);

DROP VIEW IF EXISTS v_sql_member;
CREATE VIEW v_sql_member AS
WITH win AS (
  SELECT d.my, d.patient, d.age, y.p_start, y.p_end FROM v_denominator AS d JOIN v_years AS y USING (my)
), a1c_ranked AS (
  SELECT w.my, w.patient, o.value,
         ROW_NUMBER() OVER (PARTITION BY w.my, w.patient ORDER BY o.ts DESC) AS rn
  FROM win AS w JOIN stg_obs AS o ON o.patient = w.patient AND o.test = 'a1c'
   AND o.date BETWEEN w.p_start AND w.p_end AND o.value BETWEEN 4 AND 20
), bp_ranked AS (
  SELECT w.my, w.patient, s.value AS sbp, d.value AS dbp,
         ROW_NUMBER() OVER (PARTITION BY w.my, w.patient ORDER BY s.ts DESC) AS rn
  FROM win AS w
  JOIN stg_obs AS s ON s.patient = w.patient AND s.test = 'sbp' AND s.date BETWEEN w.p_start AND w.p_end
  JOIN stg_obs AS d ON d.patient = s.patient AND d.ts = s.ts AND d.test = 'dbp'
)
SELECT w.my, w.patient, w.age,
  EXISTS (SELECT 1 FROM stg_obs o WHERE o.patient = w.patient AND o.test = 'a1c' AND o.date BETWEEN w.p_start AND w.p_end) AS a1c_tested,
  COALESCE((SELECT value < 8 FROM a1c_ranked r WHERE r.my = w.my AND r.patient = w.patient AND rn = 1), 0) AS a1c_lt8,
  COALESCE((SELECT value > 9 FROM a1c_ranked r WHERE r.my = w.my AND r.patient = w.patient AND rn = 1), 1) AS a1c_gt9,
  COALESCE((SELECT sbp < 140 AND dbp < 90 FROM bp_ranked b WHERE b.my = w.my AND b.patient = w.patient AND rn = 1), 0) AS bp_lt140_90,
  EXISTS (SELECT 1 FROM stg_eye e WHERE e.patient = w.patient AND e.date BETWEEN w.p_start AND w.p_end) AS eye_exam,
  (EXISTS (SELECT 1 FROM stg_obs o WHERE o.patient = w.patient AND o.test = 'egfr' AND o.date BETWEEN w.p_start AND w.p_end)
   AND EXISTS (SELECT 1 FROM stg_obs o WHERE o.patient = w.patient AND o.test = 'uacr' AND o.date BETWEEN w.p_start AND w.p_end)) AS kidney_eval,
  CASE WHEN w.age >= 40 THEN EXISTS (SELECT 1 FROM stg_statins s WHERE s.patient = w.patient
       AND s.start <= w.p_end AND (s.stop IS NULL OR s.stop >= w.p_start)) END AS statin_40_75
FROM win AS w;

-- Reporting views over the R marts
DROP VIEW IF EXISTS v_kpi_overall;
CREATE VIEW v_kpi_overall AS
SELECT k.my, k.measure, k.denominator, k.numerator, ROUND(100.0 * k.rate, 1) AS rate_pct, t.target, t.direction
FROM kpi AS k LEFT JOIN targets AS t USING (measure)
WHERE k.breakdown = 'overall';

DROP VIEW IF EXISTS v_worklist_top50;
CREATE VIEW v_worklist_top50 AS
SELECT rank, patient_id, age, sex, payer_group, last_visit, days_since_visit, last_a1c, sbp, dbp, open_gaps, priority, gaps
FROM worklist_2026 WHERE rank <= 50;
