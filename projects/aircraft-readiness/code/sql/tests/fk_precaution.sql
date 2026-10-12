SELECT f.* FROM mart.fct_discrepancy f LEFT JOIN mart.dim_precaution d USING (precaution_code) WHERE d.precaution_code IS NULL
