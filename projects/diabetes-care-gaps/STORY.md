# Diabetes care gaps: the story in plain English
**Which diabetic patients are missing recommended care, and how is the clinic doing on the quality measures health plans pay for? This tracker follows 7 HEDIS-style diabetes measures against targets and produces a prioritized outreach worklist for care coordinators.**


[Back to the project page](README.md) · [The code](code/README.md)

**The question:** health plans are graded on how well their members with diabetes are cared for. Are the right tests happening, and are blood sugar and blood pressure under control? When a patient is missing one of those, that is a "care gap." I wanted to measure the gaps and build the call list a care manager would actually use.

**The data:** real patient records are private, so I used Synthea, a free tool that generates realistic but fake patients. I generated 9,130 of them (fixed seed, so anyone can recreate the same people). 779 adults aged 18-75 with diabetes were in care in 2025.

> **Terms:** *HbA1c* is a blood test showing average blood sugar over about three months. *HEDIS* is the national scorecard health plans report. My measures copy its structure but are not the official certified version.

## 1. Most measures are behind
5 of 7 measures missed their targets in 2025. Only 44.0% had a diabetic eye exam, and only 48.5% had blood sugar under control (HbA1c under 8%). Blood pressure (70.3%) and kidney testing (55.2%) met their targets.

## 2. Not much changed over nine years
Rates were nearly flat from 2017 to 2025. Statin use (a cholesterol drug most adults with diabetes over 40 should be on) was the exception, rising from 42.1% to 49.3%. I can't separate that from the synthetic population getting older.

## 3. Age matters more than insurance
Statin use was 75.2% for ages 65-75 and 38.6% for 45-64. Differences between insurance types were smaller, and the Uninsured and Dual Eligible groups are too small to compare fairly.

## 4. The data problem that almost fooled me
My first run said 82.4% of patients had blood sugar under control. That looked too good. Many patients had HbA1c results below 4 (some as low as 2.1), which is not realistic for anyone, let alone someone with diabetes. That is a quirk of the generator. 264 of 779 patients had only those values. I count them as "tested" but not "controlled," which gives 48.5%. A real analyst would send those results back for a retest, so they show up on the worklist as "A1c retest."

## 5. Who to call first
The worklist scores every patient with an open gap in 2026 so far (672 people). The highest priority goes to anyone with no valid HbA1c or one over 9%, then uncontrolled blood pressure, then missing eye, kidney or statin care. When two patients have the same score, the one who has gone longest without a visit comes first, because they are the least likely to walk in on their own before the year ends.

## How I checked it
I wrote every measure twice, once in R and once in plain SQL, and compared all 770 numbers. They matched exactly. Tests cover the edge cases: someone turning 18 or 76, a test exactly at 8.0%, a blood pressure reading with only one half recorded.
