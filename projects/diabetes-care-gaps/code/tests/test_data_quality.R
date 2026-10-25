# Data-quality checks on the built database.
library(testthat); library(DBI)
con <- dbConnect(RSQLite::SQLite(), file.path(ROOT, "data/clean/care_gaps.sqlite"))
q <- function(s) dbGetQuery(con, s)
test_that("one member row per patient per year", expect_equal(q("select count(*) n from (select my, patient from member_measures group by 1,2 having count(*)>1)")$n, 0))
test_that("rates are in [0,1] and numerators <= denominators",
  expect_equal(q("select count(*) n from kpi where rate<0 or rate>1 or numerator>denominator")$n, 0))
test_that("breakdown denominators add up to the overall denominator", {
  x <- q("select my, measure, breakdown, sum(denominator) d from kpi group by 1,2,3")
  ov <- subset(x, breakdown == "overall"); for (b in c("age_band","sex","payer_group")) {
    s <- merge(ov, subset(x, breakdown == b), by = c("my","measure")); expect_equal(s$d.x, s$d.y) }
})
test_that("everyone in the denominator is 18-75", expect_equal(q("select count(*) n from member_measures where age<18 or age>75")$n, 0))
test_that("measurement years 2017-2026 present", expect_equal(q("select count(distinct my) n from member_measures")$n, 10))
test_that("no direct identifiers in staging", {
  expect_false(any(grepl("ADDRESS|SSN|FIRST|LAST|PHONE|LAT|LON", toupper(dbListFields(con, "stg_patients")))))
})
dbDisconnect(con)

test_that("public outputs carry only 8-char IDs, never full Synthea UUIDs", {
  uuid <- "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
  wl <- readr::read_csv(file.path(ROOT, "data/clean/worklist_2026.csv"), show_col_types = FALSE)
  expect_true(all(nchar(wl$patient_id) == 8))
  for (f in c("data/clean/worklist_2026.csv", "data/clean/kpi.csv", "data/clean/kpi_overall.csv",
              "app/dashboard.html", "README.md", "STORY.md"))
    if (file.exists(file.path(ROOT, f))) expect_false(any(grepl(uuid, readLines(file.path(ROOT, f), warn = FALSE))), info = f)
})
