# Run from the project folder: Rscript tests/test_leakage.R
a <- na.omit(read.csv("data/raw/audit_data.csv"))
stopifnot(nrow(a) == 775)
stopifnot(all((a$Audit_Risk > 1) == (a$Risk == 1)))                                     # label is a threshold on Audit_Risk
stopifnot(max(abs(a$Audit_Risk - a$Inherent_Risk * a$CONTROL_RISK * a$Detection_Risk)) < 1e-9)
stopifnot(abs(max(prop.table(table(a$Risk))) - 0.606) < 0.001)                           # majority-class baseline 60.6%
cat("leakage checks passed\n")
