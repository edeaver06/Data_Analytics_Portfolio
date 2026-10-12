SELECT f.* FROM mart.fct_discrepancy f LEFT JOIN mart.dim_date d ON d.date_key=f.difficulty_date_key WHERE d.date_key IS NULL
