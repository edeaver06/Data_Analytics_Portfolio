CREATE INDEX IF NOT EXISTS ix_obs ON stg_obs (patient, test, date);
CREATE INDEX IF NOT EXISTS ix_obs_ts ON stg_obs (patient, ts, test);
CREATE INDEX IF NOT EXISTS ix_enc ON stg_enc (patient, date);
CREATE INDEX IF NOT EXISTS ix_eye ON stg_eye (patient, date);
CREATE INDEX IF NOT EXISTS ix_dx ON stg_dx (patient, start);
CREATE INDEX IF NOT EXISTS ix_statin ON stg_statins (patient);
CREATE INDEX IF NOT EXISTS ix_cover ON stg_cover (patient, start);
