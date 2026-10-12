SELECT 1 WHERE (SELECT avg((aircraft_key = -1)::INT) FROM mart.fct_discrepancy) > 0.05
