SELECT ata_key FROM mart.dim_ata GROUP BY 1 HAVING count(*)>1
