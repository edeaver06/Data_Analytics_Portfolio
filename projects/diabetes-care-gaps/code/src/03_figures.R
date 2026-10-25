# Static PNG figures from the KPI marts (never from raw data). Titles are built from the numbers.
source("src/00_config.R"); suppressPackageStartupMessages(library(ggplot2))
con <- dbConnect(SQLite(), DB_PATH)
kpi <- dbReadTable(con, "kpi"); mm <- dbReadTable(con, "member_measures"); dbDisconnect(con)
OK <- c(blue = "#0072B2", orange = "#E69F00", gray = "#8C8C8C", verm = "#D55E00", green = "#009E73")
theme_set(theme_minimal(base_size = 12) + theme(panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
          plot.title = element_text(face = "bold"), plot.caption = element_text(color = "gray40", hjust = 0)))
cap <- "Source: Synthea synthetic patients (seed 20261025; 9,130 generated).\nHEDIS-style measures, not certified HEDIS. Targets are illustrative, not NCQA benchmarks."
pct <- function(x) sprintf("%.1f%%", 100 * x)
k25 <- kpi |> filter(breakdown == "overall", my == 2025) |> left_join(TARGETS, by = "measure") |>
  mutate(label = MEASURE_LABELS[measure], meets = ifelse(direction == "higher", rate >= target, rate <= target))
n_miss <- sum(!k25$meets)
dir.create("images", showWarnings = FALSE)

# 01: KPI vs target (sorted bar, target tick)
p1 <- ggplot(k25, aes(reorder(label, rate), rate)) +
  geom_col(aes(fill = meets), width = 0.65) +
  geom_errorbar(aes(ymin = target, ymax = target), width = 0.8, linewidth = 1, color = "black") +
  geom_text(aes(label = pct(rate)), hjust = -0.15, size = 3.6) +
  scale_fill_manual(values = c(`TRUE` = OK[["blue"]], `FALSE` = OK[["orange"]]), labels = c(`TRUE` = "Meets target", `FALSE` = "Misses target"), name = NULL) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1.05), expand = c(0, 0)) + coord_flip() +
  labs(title = sprintf("%d of 7 diabetes measures miss target in MY2025", n_miss),
       subtitle = sprintf("%d diabetic adults 18-75. Black tick = illustrative target.\nPoor control is an inverse measure: lower is better.", k25$denominator[k25$measure == "a1c_tested"]),
       x = NULL, y = "Rate", caption = cap) + theme(legend.position = "top")
ggsave("images/01_kpi_vs_target_2025.png", p1, width = 9, height = 5, dpi = 200, bg = "white")

# 02: trend lines MY2017-2025, direct labels
tr <- kpi |> filter(breakdown == "overall", my %in% MEASURE_YEARS, measure != "a1c_gt9") |> mutate(label = MEASURE_LABELS[measure])
first_last <- tr |> filter(my %in% range(MEASURE_YEARS)) |> select(measure, my, rate) |> tidyr::pivot_wider(names_from = my, values_from = rate)
st <- first_last |> filter(measure == "statin_40_75")
p2 <- ggplot(tr, aes(my, rate)) + geom_line(linewidth = 1, color = OK[["blue"]]) + geom_point(size = 1.3, color = OK[["blue"]]) +
  geom_text(data = filter(tr, my %in% range(MEASURE_YEARS)), aes(label = pct(rate)), vjust = -0.9, size = 3) +
  facet_wrap(~ label, ncol = 3) +
  scale_x_continuous(breaks = c(2017, 2021, 2025), expand = expansion(add = 1.2)) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1)) +
  labs(title = sprintf("Rates are flat 2017-2025 except statin use (%s to %s)", pct(st[["2017"]]), pct(st[["2025"]])),
       subtitle = "HEDIS-style measure rates by measurement year, diabetic adults 18-75", x = "Measurement year", y = "Rate", caption = cap) +
  theme(panel.grid.major.x = element_blank(), strip.text = element_text(face = "bold"))
ggsave("images/02_trend_2017_2025.png", p2, width = 10, height = 5.5, dpi = 200, bg = "white")

# 03: statin by age band (biggest breakdown gap), n labelled
sa_all <- kpi |> filter(my == 2025, measure == "statin_40_75", breakdown == "age_band")
k40 <- filter(sa_all, group == "18-44"); sa <- filter(sa_all, group != "18-44")
p3 <- ggplot(sa, aes(group, rate)) + geom_col(fill = OK[["blue"]], width = 0.55) +
  geom_text(aes(label = sprintf("%s (n=%d)", pct(rate), denominator)), vjust = -0.5, size = 3.8) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1), expand = c(0, 0)) +
  labs(title = sprintf("Statin use: %s at 65-75 vs %s at 45-64 (MY2025)", pct(sa$rate[sa$group == "65-75"]), pct(sa$rate[sa$group == "45-64"])),
       subtitle = sprintf("Diabetic adults with an active statin prescription. Ages 40-44: %s (n=%d), not shown.", pct(k40$rate), k40$denominator),
       x = "Age band", y = "Rate", caption = cap)
ggsave("images/03_statin_by_age_2025.png", p3, width = 8, height = 5, dpi = 200, bg = "white")

# 04: data problem - implausible A1c values change the control rate
m25 <- filter(mm, my == 2025)
raw_ctrl <- mean(m25$a1c_tested & (m25$a1c_invalid_only | coalesce(m25$a1c_lt8 == 1, FALSE)))
cmp <- tibble(rule = c("Implausible (<4%) values\ncounted as controlled", "Implausible values excluded\n(used in this project)"),
              rate = c(raw_ctrl, mean(m25$a1c_lt8 == 1)))
p4 <- ggplot(cmp, aes(rule, rate)) + geom_col(fill = c(OK[["gray"]], OK[["blue"]]), width = 0.5) +
  geom_text(aes(label = pct(rate)), vjust = -0.5, size = 4) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1), expand = c(0, 0)) +
  labs(title = sprintf("%d of %d MY2025 patients had only implausible A1c results", sum(m25$a1c_invalid_only == 1), nrow(m25)),
       subtitle = "HbA1c control (<8%) rate under two rules", x = NULL, y = "HbA1c <8% rate", caption = cap)
ggsave("images/04_a1c_data_problem.png", p4, width = 8, height = 5, dpi = 200, bg = "white")
writeLines(sprintf("raw_ctrl_2025=%.4f", raw_ctrl), "reports/figure_numbers.txt")
