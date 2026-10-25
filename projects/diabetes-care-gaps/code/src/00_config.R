# Shared configuration. Run every script from the project root.
# All measures are HEDIS-STYLE approximations for a portfolio demo. They are NOT certified
# NCQA HEDIS measures (no licensed value sets, simplified exclusions).
suppressPackageStartupMessages({
  library(dplyr); library(readr); library(lubridate); library(DBI); library(RSQLite); library(tidyr)
})
RAW_DIR <- "data/raw/synthea_csv"
DB_PATH <- "data/clean/care_gaps.sqlite"

# SNOMED-CT codes that put a patient in the diabetes denominator.
# Prediabetes (714628002) is deliberately NOT included.
DIABETES_CODES <- c(
  "44054006",        # Diabetes mellitus type 2
  "427089005",       # Diabetes mellitus due to cystic fibrosis
  "127013003",       # Disorder of kidney due to diabetes mellitus
  "90781000119102",  # Microalbuminuria due to type 2 DM
  "157141000119108", # Proteinuria due to type 2 DM
  "368581000119106", # Neuropathy due to type 2 DM
  "1551000119108",   # Nonproliferative diabetic retinopathy due to T2DM
  "1501000119109",   # Proliferative diabetic retinopathy due to T2DM
  "97331000119101",  # Macular edema and retinopathy due to T2DM
  "60951000119105"   # Blindness due to type 2 DM
)
LOINC <- c(a1c = "4548-4", sbp = "8480-6", dbp = "8462-4", egfr = "33914-3", uacr = "14959-1")
EYE_EXAM_CODES <- c("722161008",  # Diabetic retinal eye exam
                    "700070005")  # Optical coherence tomography of retina
STATIN_PATTERN <- "statin"        # matched case-insensitively on RxNorm description

MEASURE_YEARS <- 2017:2025        # complete measurement years in the 10-year history window
YTD_YEAR <- 2026                  # partial year used for the outreach worklist

# Illustrative targets for the dashboard tiles. NOT NCQA benchmarks.
TARGETS <- tibble::tribble(
  ~measure,          ~target, ~direction,
  "a1c_tested",       0.90,   "higher",
  "a1c_lt8",          0.60,   "higher",
  "a1c_gt9",          0.30,   "lower",
  "bp_lt140_90",      0.70,   "higher",
  "eye_exam",         0.60,   "higher",
  "kidney_eval",      0.50,   "higher",
  "statin_40_75",     0.70,   "higher"
)
MEASURE_LABELS <- c(
  a1c_tested = "HbA1c test done", a1c_lt8 = "HbA1c control (<8%)",
  a1c_gt9 = "HbA1c poor control (>9% or untested)", bp_lt140_90 = "BP control (<140/90)",
  eye_exam = "Retinal eye exam", kidney_eval = "Kidney health eval (eGFR + uACR)",
  statin_40_75 = "Statin on file (ages 40-75)"
)
