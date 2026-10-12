SELECT 1 WHERE (SELECT avg((ata_key = 'UNK')::INT) FROM mart.fct_discrepancy) > 0.02
