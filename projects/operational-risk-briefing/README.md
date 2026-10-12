# Audit Risk Model: A Target-Leakage Case Study

## Overview
**What:** A correction of my own April 2026 audit-risk Random Forest, showing its 97.8% accuracy came from target leakage.

**Why:** A model that looks near-perfect usually isn't, so this audits the published result, rebuilds the model honestly and corrects the business advice.

**Key result:** **My April 2026 Random Forest predicted audit risk with 97.8% out-of-bag accuracy. That number was invalid: the label `Risk` is just `Audit_Risk > 1`, and `Audit_Risk` is computed from the model's top feature.**

![Drivers after removing leakage](images/revised_drivers_no_leakage.png)

## Key results
- **The leak:** `Risk == (Audit_Risk > 1)` in 100% of 775 rows, and `Audit_Risk = Inherent_Risk × CONTROL_RISK × Detection_Risk` (Detection_Risk is fixed at 0.5). The original "Systemic Risk Factor" *was* Inherent_Risk.
- **Rebuilt on the 7 raw inputs** an auditor actually records: 98.5% out-of-bag accuracy vs a 60.6% majority-class baseline. Accuracy stays high because the label is a deterministic scoring rule, so the model re-learns the policy rather than predicting independent failures.
- **The conclusions change:** the honest top drivers are District_Loss (100), Money_Value (88) and PARA_B (72). Asset exposure goes from "irrelevant" to the #2 driver, so the original "don't prioritise by asset value" advice is reversed and the published tier and 70%-allocation figures are withdrawn.

## Explore
[Report (HTML, download)](reports/target_leakage_case_study.html) · [R Markdown source](notebooks/target_leakage_case_study.Rmd) · [Original published version (RPubs)](https://rpubs.com/slammerjammer/1422063)

## How to run
```bash
# R with tidyverse, randomForest, rmarkdown
Rscript tests/test_leakage.R                        # verifies the leak and the baseline
cd notebooks && Rscript -e 'rmarkdown::render("target_leakage_case_study.Rmd", output_dir = "../reports")'
```

## What's in this folder
| Folder | What it's for |
|---|---|
| `data/` | `raw/audit_data.csv`, the 776-record audit dataset |
| `notebooks/` | R Markdown source of the case study (plus the original published chart it embeds) |
| `reports/` | Knitted HTML report |
| `images/` | Original vs revised driver charts |
| `tests/` | R check proving the leak and the 60.6% baseline |

## Data
`audit_data.csv`: an audit-risk dataset of 776 firm records (775 after dropping incomplete rows). Its source and license still need to be confirmed and cited before publishing.
