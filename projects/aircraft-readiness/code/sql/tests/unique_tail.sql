SELECT n_number FROM mart.dim_aircraft GROUP BY 1 HAVING count(*)>1
