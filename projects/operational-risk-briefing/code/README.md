# Audit Risk Model (target-leakage case study): code and engineering notes

Everything technical lives here. For the recruiter summary see the [project page](../README.md); for the plain-English walkthrough see [STORY.md](../STORY.md). Run every command below from this `code/` folder.

## How to run
```bash
# R with tidyverse, randomForest, rmarkdown
Rscript tests/test_leakage.R                        # verifies the leak and the baseline
cd notebooks && Rscript -e 'rmarkdown::render("target_leakage_case_study.Rmd", output_dir = "../reports")'
```

## What's in this folder (`code/`)
| Folder | What it's for |
|---|---|
| `data/` | `raw/audit_data.csv`, the 776-record audit dataset |
| `notebooks/` | R Markdown source of the case study (it embeds the original published chart from `../images/`) |
| `reports/` | Knitted HTML report |
| `tests/` | R check proving the leak and the 60.6% baseline |

## Data
`audit_data.csv`: an audit-risk dataset of 776 firm records (775 after dropping incomplete rows). Its source and license still need to be confirmed and cited before publishing.

## Architecture
```
data/raw/audit_data.csv ──► notebooks/target_leakage_case_study.Rmd (R: tidyverse, randomForest) ──► reports/*.html
                        └─► tests/test_leakage.R (proves the leak and the 60.6% baseline)
```

## Design decisions (and why)
1. **Check where the label comes from before modelling.** `Risk` turned out to be `Audit_Risk > 1`, a rule, not an observed outcome; tracing feature lineage exposed the leak.
2. **Prove the leak with tests, not just words.** `tests/test_leakage.R` asserts the label rule holds on all 775 rows and that `Audit_Risk` equals its formula.
3. **Rebuild on raw inputs only.** Every engineered score or sub-score was dropped, leaving the 7 measurements an auditor actually records.
4. **Compare against a majority-class baseline (60.6%).** Accuracy only means something next to the simplest possible guess.
5. **Say what high accuracy really means here.** The rebuilt model re-learns the scoring policy; it doesn't predict independent audit failures.
6. **Withdraw conclusions publicly.** The original tiering and 70%-allocation advice are withdrawn and the asset-exposure advice is reversed, with the original kept for comparison.
7. **Random Forest permutation importance, scaled 0–100**, so drivers can be compared on one simple scale.
