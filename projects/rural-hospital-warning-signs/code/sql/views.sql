DROP VIEW IF EXISTS state_summary;
CREATE VIEW state_summary AS
SELECT state,
       COUNT(*) AS hospitals_scored,
       SUM(is_rural) AS rural,
       SUM(is_cah) AS cah,
       ROUND(AVG(total_margin < 0), 4) AS share_negative_total_margin,
       SUM(warning_tier = 'Many warning signs') AS many_warning_signs,
       ROUND(AVG(warning_tier = 'Many warning signs'), 4) AS share_many_warning_signs,
       ROUND(AVG(medicaid_share), 4) AS avg_medicaid_share
FROM hospitals WHERE analysis_ok = 1 GROUP BY state;
