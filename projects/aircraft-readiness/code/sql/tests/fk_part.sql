SELECT f.* FROM mart.fct_discrepancy f LEFT JOIN mart.dim_part d USING (part_key) WHERE d.part_key IS NULL
