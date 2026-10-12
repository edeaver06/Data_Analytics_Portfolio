SELECT 1 WHERE (SELECT avg(is_date_anomaly::INT) FROM mart.fct_discrepancy) > 0.005 UNION ALL SELECT 1 FROM mart.fct_discrepancy WHERE report_lag_days < 0
