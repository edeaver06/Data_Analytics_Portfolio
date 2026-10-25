# Edge-case tests for the HEDIS-style measure logic, on hand-built toy patients.
library(testthat)
source(file.path(ROOT, "src/00_config.R")); source(file.path(ROOT, "src/measures.R"))
de <- as.Date("2026-10-25")
pt <- function(id, bd, sex = "F", dd = NA) tibble(patient = id, birthdate = as.Date(bd), deathdate = as.Date(dd), sex = sex)
patients <- bind_rows(
  pt("p_ok", "1970-06-01"), pt("p_17", "2008-01-02"), pt("p_18", "2007-12-31"),
  pt("p_75", "1950-01-01"), pt("p_76", "1949-12-31"), pt("p_dead", "1960-01-01", dd = "2025-06-01"),
  pt("p_pre", "1970-01-01"), pt("p_noenc", "1970-01-01"), pt("p_late", "1970-01-01"))
dx <- tibble(patient = c("p_ok","p_17","p_18","p_75","p_76","p_dead","p_noenc","p_late"),
             code = "44054006", description = "T2DM",
             start = as.Date(c(rep("2015-01-01", 7), "2026-01-05")), stop = as.Date(NA)) |>
  bind_rows(tibble(patient = "p_pre", code = "714628002", description = "Prediabetes", start = as.Date("2015-01-01"), stop = as.Date(NA)))
enc <- tibble(patient = setdiff(patients$patient, "p_noenc"), date = as.Date("2025-03-01"))
o <- function(id, test, date, value, ts = paste0(date, "T10:00:00Z")) tibble(patient = id, ts = ts, date = as.Date(date), test = test, value = value)
empty <- list(eye = tibble(patient = character(), date = as.Date(character())),
              statins = tibble(patient = character(), start = as.Date(character()), stop = as.Date(character())),
              cover = tibble(patient = character(), start = as.Date(character()), end = as.Date(character()), payer_group = character()))
run <- function(obs = o("x", "a1c", "2025-01-01", 6)[0, ], eye = empty$eye, statins = empty$statins, cover = empty$cover)
  member_measures(2025, patients, dx, enc, obs, eye, statins, cover, de)

test_that("denominator: age 18-75 on Dec 31, diabetes not prediabetes, alive, seen, dx before period end", {
  d <- denominator(2025, patients, dx, enc, de)
  expect_setequal(d$patient, c("p_ok", "p_18", "p_75"))
  expect_equal(d$age[d$patient == "p_18"], 18L)
  expect_equal(d$age[d$patient == "p_75"], 75L)
})

test_that("untested patient: A1c test gap, counts as poor control, not controlled", {
  m <- run() |> filter(patient == "p_ok")
  expect_false(m$a1c_tested); expect_false(m$a1c_lt8); expect_true(m$a1c_gt9)
})

test_that("most recent A1c in the year decides control, not the best", {
  obs <- bind_rows(o("p_ok", "a1c", "2025-02-01", 6.5), o("p_ok", "a1c", "2025-11-01", 9.4))
  m <- run(obs) |> filter(patient == "p_ok")
  expect_true(m$a1c_tested); expect_false(m$a1c_lt8); expect_true(m$a1c_gt9)
})

test_that("A1c boundaries: exactly 8.0 is not <8, exactly 9.0 is not >9", {
  m8 <- run(o("p_ok", "a1c", "2025-05-01", 8.0)) |> filter(patient == "p_ok")
  expect_false(m8$a1c_lt8); expect_false(m8$a1c_gt9)
  m9 <- run(o("p_ok", "a1c", "2025-05-01", 9.0)) |> filter(patient == "p_ok")
  expect_false(m9$a1c_gt9)
})

test_that("implausible A1c (<4%) counts as a test but not as control", {
  m <- run(o("p_ok", "a1c", "2025-05-01", 3.1)) |> filter(patient == "p_ok")
  expect_true(m$a1c_tested); expect_true(m$a1c_invalid_only); expect_false(m$a1c_lt8); expect_true(m$a1c_gt9)
})

test_that("A1c outside the measurement year is ignored", {
  m <- run(o("p_ok", "a1c", "2024-12-31", 6)) |> filter(patient == "p_ok")
  expect_false(m$a1c_tested)
})

test_that("BP: both readings must be <140/<90; 140 systolic fails; unpaired reading ignored", {
  bp <- function(s, d) bind_rows(o("p_ok", "sbp", "2025-06-01", s), o("p_ok", "dbp", "2025-06-01", d))
  expect_true(run(bp(139, 89)) |> filter(patient == "p_ok") |> pull(bp_lt140_90))
  expect_false(run(bp(140, 70)) |> filter(patient == "p_ok") |> pull(bp_lt140_90))
  expect_false(run(bp(120, 90)) |> filter(patient == "p_ok") |> pull(bp_lt140_90))
  lone <- bind_rows(bp(120, 70), o("p_ok", "sbp", "2025-09-01", 150))
  expect_true(run(lone) |> filter(patient == "p_ok") |> pull(bp_lt140_90))
})

test_that("kidney evaluation needs BOTH eGFR and uACR in the year", {
  expect_false(run(o("p_ok", "egfr", "2025-03-01", 70)) |> filter(patient == "p_ok") |> pull(kidney_eval))
  both <- bind_rows(o("p_ok", "egfr", "2025-03-01", 70), o("p_ok", "uacr", "2025-08-01", 12))
  expect_true(run(both) |> filter(patient == "p_ok") |> pull(kidney_eval))
})

test_that("statin measure only applies to ages 40+ and needs a script overlapping the year", {
  st <- tibble(patient = c("p_ok", "p_18"), start = as.Date("2020-01-01"), stop = as.Date(c(NA, NA)))
  m <- run(statins = st)
  expect_true(m$statin_40_75[m$patient == "p_ok"]); expect_true(is.na(m$statin_40_75[m$patient == "p_18"]))
  ended <- tibble(patient = "p_ok", start = as.Date("2020-01-01"), stop = as.Date("2024-12-31"))
  expect_false(run(statins = ended) |> filter(patient == "p_ok") |> pull(statin_40_75))
})

test_that("rates ignore NA (ineligible) rows in the denominator", {
  m <- run(statins = tibble(patient = "p_ok", start = as.Date("2020-01-01"), stop = as.Date(NA)))
  k <- kpi_rates(m) |> filter(measure == "statin_40_75")
  expect_equal(k$denominator, 2); expect_equal(k$numerator, 1)
})

test_that("worklist ranks untested/poor-control patients first and drops patients with no gaps", {
  m <- run(bind_rows(o("p_18", "a1c", "2025-05-01", 6)))
  w <- worklist(m, enc, as.Date("2025-12-31"))
  expect_true(all(w$open_gaps > 0)); expect_true(w$priority[1] >= max(w$priority))
})

test_that("worklist tie-break: equal priority -> longest since last visit first, then ID", {
  mm <- tibble(patient = c("cccccccc-1", "aaaaaaaa-2", "bbbbbbbb-3"), a1c_tested = TRUE, a1c_lt8 = TRUE, last_a1c = 7,
               bp_lt140_90 = FALSE, eye_exam = TRUE, kidney_eval = TRUE, statin_elig = FALSE, has_statin = FALSE)
  e <- tibble(patient = mm$patient, date = as.Date(c("2025-06-01", "2025-11-01", "2025-06-01")))
  w <- worklist(mm, e, as.Date("2025-12-31"))
  expect_equal(w$patient_id, c("bbbbbbbb", "cccccccc", "aaaaaaaa"))
  expect_equal(w$days_since_visit, c(213L, 213L, 60L))
})

test_that("public_id truncates UUIDs to 8 chars and refuses collisions", {
  expect_equal(public_id("deadbeef-0000-4000-8000-000000000000"), "deadbeef")
  expect_error(public_id(c("abcdefgh-1", "abcdefgh-2")))
})
