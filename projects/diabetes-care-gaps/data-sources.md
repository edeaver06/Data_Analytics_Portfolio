# Data sources

## Synthea synthetic patients (the only data source)
- **What:** Synthea, an open-source synthetic patient generator by The MITRE Corporation. https://github.com/synthetichealth/synthea
- **License:** Apache License 2.0. Generated data is synthetic and contains no real patient information (no PHI).
- **Version:** `synthea-with-dependencies.jar` from the GitHub release tag `master-branch-latest`, build `bd8a52b` (from `version.txt` inside the jar), downloaded 2026-10-25.
- **Command:**
  ```
  java -Xmx8g -jar synthea-with-dependencies.jar -s 20261025 -cs 20261025 -r 20261025 -p 8000 \
    --exporter.baseDirectory=./output --exporter.csv.export=true --exporter.fhir.export=false \
    --exporter.hospital.fhir.export=false --exporter.practitioner.fhir.export=false \
    --exporter.years_of_history=10 Massachusetts
  ```
  Seed 20261025, clinician seed 20261025, reference date 2026-10-25, 8,000 living patients requested (9,130 generated including 1,130 deceased), Massachusetts.
- **Output used:** CSV export (patients, conditions, encounters, observations, procedures, medications, payers, payer_transitions), about 6.1 GB, kept in `data/raw/` and not committed.
- **Rows staged:** 9,130 patients; 3,276 diabetes condition rows (1,340 patients ever diagnosed); 528,685 encounters; 439,490 lab/vital rows (HbA1c, BP, eGFR, uACR); 8,090 eye exams; 9,916 statin prescriptions; 388,780 coverage periods. Data runs through 2026-10-25.

## Code lists used (not NCQA value sets)
- Diabetes: SNOMED-CT 44054006, 427089005, 127013003, 90781000119102, 157141000119108, 368581000119106, 1551000119108, 1501000119109, 97331000119101, 60951000119105. Prediabetes 714628002 is excluded.
- LOINC: HbA1c 4548-4; systolic 8480-6; diastolic 8462-4; eGFR 33914-3; urine albumin/creatinine ratio 14959-1.
- Eye exam procedures: 722161008 (diabetic retinal eye exam), 700070005 (OCT of retina).
- Statins: any medication whose RxNorm description contains "statin".

## Not certified HEDIS
HEDIS® is a registered trademark of NCQA. These measures follow the structure of HEDIS Comprehensive Diabetes Care-family measures but are simplified approximations for a portfolio demo.
