# Raw Synthea CSVs -> slim SQLite staging tables. Raw files are never modified.
# Drops all direct identifiers (names, SSN, addresses, phones): only IDs, dates, sex, codes, values.
source("src/00_config.R")
rd <- function(f, cols) read_csv(file.path(RAW_DIR, f), col_select = all_of(cols),
                                 col_types = cols(.default = col_character()), progress = FALSE)
log_n <- function(name, df) { message(sprintf("%-18s %9d rows", name, nrow(df))); df }

patients <- rd("patients.csv", c("Id", "BIRTHDATE", "DEATHDATE", "GENDER")) |>
  transmute(patient = Id, birthdate = as.Date(BIRTHDATE), deathdate = as.Date(DEATHDATE), sex = GENDER) |>
  log_n(name = "patients")
stopifnot(!anyDuplicated(patients$patient))

dx <- rd("conditions.csv", c("START", "STOP", "PATIENT", "CODE", "DESCRIPTION")) |>
  filter(CODE %in% DIABETES_CODES) |>
  transmute(patient = PATIENT, code = CODE, description = DESCRIPTION,
            start = as.Date(START), stop = as.Date(STOP)) |> log_n(name = "diabetes_dx")

enc <- rd("encounters.csv", c("Id", "START", "PATIENT", "ENCOUNTERCLASS")) |>
  transmute(encounter = Id, patient = PATIENT, date = as.Date(ymd_hms(START)), class = ENCOUNTERCLASS) |>
  log_n(name = "encounters")

obs <- rd("observations.csv", c("DATE", "PATIENT", "CODE", "VALUE")) |>
  filter(CODE %in% LOINC) |>
  transmute(patient = PATIENT, ts = DATE, date = as.Date(ymd_hms(DATE)),
            test = names(LOINC)[match(CODE, LOINC)], value = as.numeric(VALUE)) |>
  log_n(name = "labs_vitals")
message("non-numeric values dropped: ", sum(is.na(obs$value)))
obs <- filter(obs, !is.na(value))

eye <- rd("procedures.csv", c("START", "PATIENT", "CODE", "DESCRIPTION")) |>
  filter(CODE %in% EYE_EXAM_CODES) |>
  transmute(patient = PATIENT, date = as.Date(ymd_hms(START)), code = CODE, description = DESCRIPTION) |>
  log_n(name = "eye_exams")

statins <- rd("medications.csv", c("START", "STOP", "PATIENT", "CODE", "DESCRIPTION")) |>
  filter(grepl(STATIN_PATTERN, DESCRIPTION, ignore.case = TRUE)) |>
  transmute(patient = PATIENT, start = as.Date(ymd_hms(START)), stop = as.Date(ymd_hms(STOP)),
            code = CODE, description = DESCRIPTION) |> log_n(name = "statins")

payers <- rd("payers.csv", c("Id", "NAME")) |> transmute(payer = Id, payer_name = NAME)
cover <- rd("payer_transitions.csv", c("PATIENT", "START_DATE", "END_DATE", "PAYER")) |>
  transmute(patient = PATIENT, start = as.Date(ymd_hms(START_DATE)), end = as.Date(ymd_hms(END_DATE)), payer = PAYER) |>
  left_join(payers, by = "payer") |>
  mutate(payer_group = case_when(
    payer_name %in% c("Medicare", "Medicaid", "Dual Eligible") ~ payer_name,
    payer_name == "NO_INSURANCE" | is.na(payer_name) ~ "Uninsured",
    TRUE ~ "Commercial")) |> log_n(name = "payer_coverage")

data_end <- max(enc$date)
message("data end date: ", data_end)

dir.create("data/clean", showWarnings = FALSE)
if (file.exists(DB_PATH)) file.remove(DB_PATH)   # idempotent rebuild
con <- dbConnect(SQLite(), DB_PATH, extended_types = TRUE)
for (nm in c("patients", "dx", "enc", "obs", "eye", "statins", "cover")) {
  df <- get(nm) |> mutate(across(where(is.Date), as.character))
  dbWriteTable(con, paste0("stg_", nm), df)
}
dbWriteTable(con, "meta", tibble(key = c("data_end", "synthea_seed", "population"),
                                 value = c(as.character(data_end), "20261025", "8000")))
dbDisconnect(con)
