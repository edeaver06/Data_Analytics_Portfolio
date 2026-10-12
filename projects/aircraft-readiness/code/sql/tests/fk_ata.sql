SELECT f.* FROM mart.fct_discrepancy f LEFT JOIN mart.dim_ata d USING (ata_key) WHERE d.ata_key IS NULL
