# Pure measure functions (no I/O) so testthat can exercise them on toy data.
# HEDIS-STYLE, not certified HEDIS. One row per patient per measurement year.
suppressPackageStartupMessages({library(dplyr); library(lubridate)})
A1C_PLAUSIBLE <- c(4, 20)

period_bounds <- function(my, data_end) {
  list(start = as.Date(sprintf("%d-01-01", my)),
       end   = min(as.Date(sprintf("%d-12-31", my)), as.Date(data_end)))
}

age_on <- function(birthdate, on) as.integer(floor(time_length(interval(birthdate, on), "years")))

# Denominator: diabetes dx on/before period end, age 18-75 on Dec 31 of the MY,
# alive at period end, and at least one encounter of any kind in the period.
denominator <- function(my, patients, dx, enc, data_end) {
  b <- period_bounds(my, data_end); dec31 <- as.Date(sprintf("%d-12-31", my))
  dm <- dx |> filter(code %in% DIABETES_CODES, start <= b$end) |> distinct(patient)
  seen <- enc |> filter(date >= b$start, date <= b$end) |> distinct(patient)
  patients |>
    semi_join(dm, by = "patient") |> semi_join(seen, by = "patient") |>
    mutate(age = age_on(birthdate, dec31)) |>
    filter(age >= 18, age <= 75, is.na(deathdate) | deathdate > b$end) |>
    transmute(patient, sex, age, my = my)
}

latest_in <- function(df, b) df |> filter(date >= b$start, date <= b$end) |>
  arrange(patient, desc(ts)) |> distinct(patient, .keep_all = TRUE)

# Most recent date-time with BOTH a systolic and a diastolic reading.
latest_bp <- function(obs, b) {
  s <- obs |> filter(test == "sbp") |> select(patient, ts, date, sbp = value)
  d <- obs |> filter(test == "dbp") |> select(patient, ts, dbp = value)
  inner_join(distinct(s, patient, ts, .keep_all = TRUE), distinct(d, patient, ts, .keep_all = TRUE), by = c("patient", "ts")) |> latest_in(b) |> select(patient, sbp, dbp, bp_date = date)
}

payer_at <- function(cover, on) cover |> filter(start <= on, is.na(end) | end >= on) |>
  arrange(patient, desc(start)) |> distinct(patient, .keep_all = TRUE) |> select(patient, payer_group)

member_measures <- function(my, patients, dx, enc, obs, eye, statins, cover, data_end) {
  b <- period_bounds(my, data_end)
  den <- denominator(my, patients, dx, enc, data_end)
  # Any HbA1c result counts as "tested"; control uses the latest PLAUSIBLE value (4-20%).
  # Synthea emits some values <4%, which are not clinically credible (see reports/data-problems).
  a1c_any <- obs |> filter(test == "a1c", date >= b$start, date <= b$end) |> distinct(patient) |> mutate(a1c_tested = TRUE)
  a1c <- obs |> filter(test == "a1c", value >= A1C_PLAUSIBLE[1], value <= A1C_PLAUSIBLE[2]) |>
    latest_in(b) |> select(patient, last_a1c = value, a1c_date = date)
  bp  <- latest_bp(obs, b)
  egfr <- obs |> filter(test == "egfr", date >= b$start, date <= b$end) |> distinct(patient) |> mutate(has_egfr = TRUE)
  uacr <- obs |> filter(test == "uacr", date >= b$start, date <= b$end) |> distinct(patient) |> mutate(has_uacr = TRUE)
  ey  <- eye |> filter(date >= b$start, date <= b$end) |> distinct(patient) |> mutate(has_eye = TRUE)
  st  <- statins |> filter(start <= b$end, is.na(stop) | stop >= b$start) |> distinct(patient) |> mutate(has_statin = TRUE)
  den |>
    left_join(a1c_any, by = "patient") |> left_join(a1c, by = "patient") |> left_join(bp, by = "patient") |>
    left_join(egfr, by = "patient") |> left_join(uacr, by = "patient") |>
    left_join(ey, by = "patient") |> left_join(st, by = "patient") |>
    left_join(payer_at(cover, b$end), by = "patient") |>
    mutate(
      across(c(has_egfr, has_uacr, has_eye, has_statin), ~ coalesce(.x, FALSE)),
      payer_group = coalesce(payer_group, "Uninsured"),
      age_band = cut(age, c(17, 44, 64, 75), labels = c("18-44", "45-64", "65-75")),
      a1c_tested  = coalesce(a1c_tested, FALSE),
      a1c_invalid_only = a1c_tested & is.na(last_a1c),
      a1c_lt8     = coalesce(last_a1c < 8, FALSE),
      a1c_gt9     = is.na(last_a1c) | last_a1c > 9,        # inverse measure: untested counts as poor
      bp_lt140_90 = coalesce(sbp < 140 & dbp < 90, FALSE),  # no reading = not controlled
      eye_exam    = has_eye,
      kidney_eval = has_egfr & has_uacr,
      statin_elig = age >= 40,
      statin_40_75 = ifelse(statin_elig, has_statin, NA)
    )
}

kpi_rates <- function(mm, group_var = NULL) {
  ms <- c("a1c_tested", "a1c_lt8", "a1c_gt9", "bp_lt140_90", "eye_exam", "kidney_eval", "statin_40_75")
  g <- if (is.null(group_var)) mm |> mutate(group = "All") else mm |> mutate(group = as.character(.data[[group_var]]))
  g |> select(my, group, all_of(ms)) |>
    tidyr::pivot_longer(all_of(ms), names_to = "measure", values_to = "met") |>
    filter(!is.na(met)) |>
    group_by(my, breakdown = group_var %||% "overall", group, measure) |>
    summarise(denominator = n(), numerator = sum(met), .groups = "drop") |>
    mutate(rate = numerator / denominator)
}

# Public, non-reversible display ID: first 8 hex chars of the Synthea UUID.
public_id <- function(patient) {
  id <- substr(gsub("-", "", patient), 1, 8)
  stopifnot(!anyDuplicated(id))  # must stay unique within the output
  id
}

# Latest encounter on or before as_of, per patient.
last_visit <- function(enc, as_of) {
  enc |> filter(date <= as_of) |> group_by(patient) |> summarise(last_visit = max(date), .groups = "drop")
}

# Open gaps + priority score for outreach. Higher score = call first.
# Ties: longest time since last visit first (least-engaged patients are least likely to
# come in on their own before year end), then public ID.
worklist <- function(mm, enc, as_of) {
  mm |> mutate(
    gap_a1c_test = !a1c_tested,
    gap_a1c_ctrl = a1c_tested & !a1c_lt8,
    gap_bp = !bp_lt140_90, gap_eye = !eye_exam, gap_kidney = !kidney_eval,
    gap_statin = coalesce(statin_elig & !has_statin, FALSE),
    open_gaps = gap_a1c_test + gap_a1c_ctrl + gap_bp + gap_eye + gap_kidney + gap_statin,
    priority = 3 * (is.na(last_a1c) | coalesce(last_a1c > 9, FALSE)) +
               2 * coalesce(last_a1c >= 8 & last_a1c <= 9, FALSE) +
               2 * gap_bp + gap_eye + gap_kidney + gap_statin
  ) |> filter(open_gaps > 0) |>
    left_join(last_visit(enc, as_of), by = "patient") |>
    mutate(days_since_visit = as.integer(as_of - last_visit), patient_id = public_id(patient)) |>
    arrange(desc(priority), desc(days_since_visit), patient_id)
}
