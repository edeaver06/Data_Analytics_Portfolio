SELECT f.* FROM mart.fct_discrepancy f LEFT JOIN mart.dim_aircraft d USING (aircraft_key) WHERE d.aircraft_key IS NULL
