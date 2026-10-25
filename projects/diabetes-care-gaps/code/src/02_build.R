# Staging -> member-level measures, KPI marts and worklist (SQLite + CSV).
source("src/00_config.R"); source("src/measures.R")
con <- dbConnect(SQLite(), DB_PATH)
ld <- function(t) dbReadTable(con, t) |> mutate(across(any_of(c("birthdate","deathdate","start","stop","end","date")), as.Date))
patients <- ld("stg_patients"); dx <- ld("stg_dx"); enc <- ld("stg_enc"); obs <- ld("stg_obs")
eye <- ld("stg_eye"); statins <- ld("stg_statins"); cover <- ld("stg_cover")
data_end <- as.Date(dbGetQuery(con, "select value from meta where key='data_end'")$value)

mm <- bind_rows(lapply(c(MEASURE_YEARS, YTD_YEAR), member_measures, patients = patients, dx = dx, enc = enc,
                       obs = obs, eye = eye, statins = statins, cover = cover, data_end = data_end))
stopifnot(!anyDuplicated(mm[c("my", "patient")]))
message("member-years: ", nrow(mm)); print(count(mm, my))

kpi <- bind_rows(kpi_rates(mm), kpi_rates(mm, "age_band"), kpi_rates(mm, "sex"), kpi_rates(mm, "payer_group")) |>
  mutate(partial_year = my == YTD_YEAR)
wl <- worklist(filter(mm, my == YTD_YEAR), enc, data_end) |>
  transmute(rank = row_number(), patient_id, age, sex, payer_group,
            last_visit = as.character(last_visit), days_since_visit,
            last_a1c, a1c_date = as.character(a1c_date), sbp, dbp, open_gaps, priority,
            gaps = paste0(ifelse(gap_a1c_test, "A1c test; ", ""), ifelse(gap_a1c_ctrl & is.na(last_a1c), "A1c retest (implausible value); ", ifelse(gap_a1c_ctrl, "A1c >=8%; ", "")),
                          ifelse(gap_bp, "BP; ", ""), ifelse(gap_eye, "Eye exam; ", ""),
                          ifelse(gap_kidney, "Kidney eval; ", ""), ifelse(gap_statin, "Statin; ", "")) |> sub("; $", "", x = _))
mm_out <- mm |> mutate(across(where(is.Date), as.character), age_band = as.character(age_band))
dbWriteTable(con, "member_measures", mm_out, overwrite = TRUE)
dbWriteTable(con, "kpi", kpi, overwrite = TRUE)
dbWriteTable(con, "worklist_2026", wl, overwrite = TRUE)
dbWriteTable(con, "targets", TARGETS, overwrite = TRUE)
for (f in list.files("sql", "\\.sql$", full.names = TRUE)) for (s in strsplit(paste(readLines(f), collapse = "\n"), ";")[[1]])
  if (nzchar(trimws(s))) dbExecute(con, s)
dbDisconnect(con)
stopifnot(all(nchar(wl$patient_id) == 8), !any(grepl("-", wl$patient_id)))
write_csv(kpi, "data/clean/kpi.csv"); write_csv(wl, "data/clean/worklist_2026.csv")
write_csv(filter(kpi, breakdown == "overall") |> select(my, measure, denominator, numerator, rate), "data/clean/kpi_overall.csv")
