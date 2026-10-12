SELECT sdr_id FROM mart.fct_discrepancy GROUP BY 1 HAVING count(*)>1
