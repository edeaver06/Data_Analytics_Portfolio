# Audit Risk Model: A Target-Leakage Case Study

**Was my 97.8%-accurate audit-risk model real?** No. The label was computed from the model's own top feature, so I found the leak, rebuilt the model honestly and reversed the business advice.

**[📖 Story](STORY.md) | [💻 Code](code/README.md)**

![Drivers of audit risk after removing the leak](images/revised_drivers_no_leakage.png)

## The problem
Auditors have limited time and need to know which firms to check first. In April 2026 I published a Random Forest that seemed to predict audit risk almost perfectly and gave resource-allocation advice. A result that good on a real-world risk problem is a warning sign, so I audited my own work.

## Key findings
- **The label was a formula:** `Risk` equals `Audit_Risk > 1` in 100% of 775 rows, and `Audit_Risk` is calculated from the model's top feature, the "Systemic Risk Factor".
- **Rebuilt on the 7 raw inputs** an auditor actually records: 98.5% accuracy vs a 60.6% always-"Pass" baseline, because the model re-learns the scoring rule.
- **The honest top drivers** are district loss (100), money value (88) and discrepancy B (72).
- **Advice reversed:** asset exposure went from "irrelevant" to the #2 driver, so the original "don't prioritise by asset value" advice and its 70%-allocation figures are withdrawn.

## What I built
- A leak investigation that traced where every column comes from and proved the label is a threshold on a formula.
- Automated R tests that assert the leak and the 60.6% baseline.
- A rebuilt Random Forest on raw inputs only, with permutation importance.
- A corrected report that keeps the original for comparison and states what the model can and can't show.

## Tools
R · tidyverse · randomForest · R Markdown · ggplot2

## Go deeper
- [The story in plain English](STORY.md)
- [How it's built: design decisions, how to run](code/README.md)
- [Full report (HTML, download)](code/reports/target_leakage_case_study.html) · [R Markdown source](code/notebooks/target_leakage_case_study.Rmd)
- [Original published version (RPubs)](https://rpubs.com/slammerjammer/1422063)
