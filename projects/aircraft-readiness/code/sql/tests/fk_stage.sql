SELECT f.* FROM mart.fct_discrepancy f LEFT JOIN mart.dim_stage d USING (stage_code) WHERE d.stage_code IS NULL
