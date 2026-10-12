SELECT f.* FROM mart.fct_discrepancy f LEFT JOIN mart.dim_operator d USING (operator_key) WHERE d.operator_key IS NULL
