# Data problems hit (and what I did)
1. **Implausible HbA1c values.** Synthea emits 29,613 HbA1c results below 4% (as low as 2.1%). HbA1c below 4% is not clinically credible. Rule: values outside 4-20% count as "test done" but are ignored for control; a patient with only such values is "not controlled" and is listed as "A1c retest (implausible value)" on the worklist. Impact in MY2025: 264 of 779 patients; control is 48.5% instead of 82.4%.
2. **Prediabetes looks like diabetes in a text search.** "Prediabetes" (714628002) is the most common diabetes-related code (3,488 rows). It is excluded from the denominator, and a unit test locks that in (it caught a version of `denominator()` that trusted the staging filter instead of checking codes).
3. **Duplicate timestamps.** 7 systolic/diastolic readings and 10 coverage periods share a patient + timestamp. BP readings are de-duplicated before pairing; coverage uses the latest-starting period covering the date.
4. **Unpaired BP readings.** BP control uses the latest timestamp that has BOTH a systolic and a diastolic value.
5. **Partial year.** 2026 runs only to 2026-10-25, so MY2026 rates are year to date and lower by construction. Trends use 2017-2025 only; 2026 feeds the worklist.
6. **Ties in the worklist.** 86 patients share the top priority score (8). Ties are now broken by longest time since last visit, then ID.
7. **Small groups.** Uninsured (46) and Dual Eligible (51) in MY2025, and ages 40-44 for the statin measure (32), are too small for comparisons.
