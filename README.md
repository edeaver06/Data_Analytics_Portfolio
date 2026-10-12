# Evan Deaver: Data Analyst Portfolio

### About
Hi, I'm Evan, a data analyst based in Austin, Texas. I also spend a lot of time on my ranch in Pringle, SD. I enjoy nature, animals and "the simple life", and I've had a passion for data since I was a teenager. I work in Python, R, SQL and Tableau, turning raw data into clear, actionable business recommendations. I also dabble in app development, automation and machine learning.

I'm looking for **junior remote data analyst and data engineer roles**. This portfolio is a work in progress.

---

### Table of Contents
- [Portfolio Projects](#portfolio-projects)
- [In Progress](#in-progress)
- [Earlier Work](#earlier-work)
- [Tableau & Dashboards](#tableau--dashboards)
- [Technical Skills](#technical-skills)
- [Approach](#approach)
- [Certificates](#certificates)
- [Contact](#contact)

---

### Portfolio Projects

| Project | Business question | Tools | Link |
|---|---|---|---|
| **Olist: Late Deliveries Are the Review Killer** | How much do late deliveries hurt reviews, and who or where causes them? | DuckDB SQL, Python, pytest | [Repo](https://github.com/edeaver06/olist-ecommerce) |
| **Can You Beat the NFL Closing Line?** | Is the betting market efficient, and do popular angles beat the -110 vig? | DuckDB SQL, Python (statsmodels OLS, binomial tests), pytest | [Repo](https://github.com/edeaver06/nfl-closing-line) |
| **Markets vs Polls: Who Called It Better?** | Were 2024 Polymarket and Kalshi state prices better calibrated than a poll-average forecast? | Python (APIs), DuckDB SQL, pytest | [Repo](https://github.com/edeaver06/markets-vs-polls) |
| **Google Fiber: Repeat Calls & First-Contact Resolution** | Which support categories and markets drive 7-day repeat calls? | Python (pandas, matplotlib), DuckDB SQL, pytest, Plotly | [Repo](https://github.com/edeaver06/google-fiber-fcr) |
| **Operational Risk Briefing: Strategic Audit Prioritization** | Which operational units should auditors prioritize? | R, Random Forest, tidyverse, ggplot2 | [RPubs report](https://rpubs.com/slammerjammer/1422063) |
| **The Synthetic Predator: AI-Automation in 2025 Bitcoin Scams** | Does word-complexity variability separate scam lures from human text? | R, tidyverse, ggplot2 | [RPubs report](https://rpubs.com/slammerjammer/1423363) |

#### Olist: Late Deliveries Are the Review Killer (SQL + Python)
A SQL analysis of 99,441 orders from a Brazilian e-commerce marketplace.
- Only **6.8%** of orders arrive late, but a late order averages **2.27★ vs 4.29★** on time. **62.4%** of late orders get a 1–2★ review, compared with **9.3%** of on-time orders.
- It's dose-response: once an order is 8–14 days late, **80%** of reviews are 1–2★.
- The worst seller quartile is late **12.0%** of the time vs **1.7%** for the best. The worst lane, São Paulo → Alagoas, is late **24.0%** of the time.
- Growth is strong (**+138%** GMV, Jan–Aug 2018 vs 2017), but only **3.0%** of customers ever order twice.
- Layered DuckDB marts (window functions, `QUALIFY`, cohorts, Pareto), grain traps handled, and **43 pytest tests** pin every headline number.

#### Can You Beat the NFL Closing Line? (SQL + Python stats)
Covers 7,354 games from 1999 through early 2026.
- Closing spreads are unbiased (slope 1.04, 95% CI 0.99–1.09), but the typical miss is still 10.3 points per game.
- After removing the vig, moneylines are well calibrated (Brier 0.211 vs 0.250 for a coin flip).
- Famous angles fail. Home underdogs cover 50.5% and primetime overs hit 48.7%, both below the **52.38%** breakeven at -110.
- Wind 15+ mph unders went 57.0%, but they don't beat the vig after Holm correction (p = 0.09).
- Uses OLS with robust standard errors, Wilson CIs, Holm correction and a walk-forward check, and ends with a responsible-gambling takeaway.

#### Markets vs Polls: Who Called It Better? (APIs + SQL + forecast scoring)
Scores the 2024 US presidential race state by state, neutrally (accuracy only, no side taken).
- At 1 day out across 35 states, the Brier score (lower is better) was **0.042** for Polymarket, **0.043** for Kalshi and **0.053** for the poll average. Both markets beat the polls at every matched horizon from 21 days to 1 day out.
- Why: the polls missed in the same direction almost everywhere, with the actual margin on average **3.2 points** more Republican than the poll average. With n = 1 election, this is not evidence that markets beat polls in general.
- Data comes from the Polymarket and Kalshi public APIs, an archived 538 polls CSV and MIT Election Lab results. Uses a paired bootstrap, a σ sensitivity check and a test that no data after each cutoff is used.

#### Google Fiber: Repeat Calls & FCR (Python + SQL)
Google Data Analytics capstone scenario: 3 markets, 5 problem types, Q1 2022.
- **Wi-Fi & Internet + Technical Troubleshooting account for 80.2% of repeat calls.** The share varies by market (87.1%, 89.3%, 66.5%).
- Market_3 has the highest repeat rate (44.7%), and its Billing rows are flagged as a likely data-quality issue.
- Scheduling: 60.6% repeat rate (1,469 repeat calls).
- The metrics are built in both pandas and DuckDB SQL (CTEs, window functions), and a pytest confirms the two agree. Includes an interactive Plotly dashboard.

#### Operational Risk Briefing (R)
Trained a Random Forest model to rank risk drivers and grouped operational units into risk tiers, so field audit effort can go to the highest-risk clusters.

#### The Synthetic Predator (R)
A forensic text analysis comparing word length and its coefficient of variation in 2025 Bitcoin scam lures against a human baseline.

---

### In Progress
- **Steam Pulse** (Python, dbt, DuckDB): an end-to-end data pipeline built on Steam data. *In progress.*

---

### Earlier Work
- **Cyclistic Bike-Share: Casual vs. Annual Riders** (R, dplyr, ggplot2): Google Data Analytics capstone; usage-pattern EDA and conversion recommendations. [RPubs report](https://rpubs.com/slammerjammer/1371255)

---

### Tableau & Dashboards
- **Tableau Public:** [Evan Deaver on Tableau Public](https://public.tableau.com/app/profile/evan.deaver/vizzes)

---

### Technical Skills
- **Python:** pandas, NumPy, matplotlib, seaborn, Plotly, Jupyter, pytest, statistical testing
- **SQL:** CTEs, window functions, QUALIFY, cohorts, joins, aggregations (DuckDB)
- **Data engineering:** layered SQL marts, dbt (in progress), reproducible pipelines, data tests
- **R:** tidyverse, dplyr, ggplot2, randomForest, RMarkdown
- **Visualization / BI:** Tableau, Plotly
- **Spreadsheets:** Excel (pivot tables, lookups, formulas)
- **Methods:** EDA, data cleaning and validation, hypothesis testing, classification, feature importance

### Approach
- **Clear problem definition:** understand the business context before writing code.
- **Rigorous methodology:** use appropriate statistical methods and check the results.
- **Data-driven storytelling:** turn analysis into clear, actionable recommendations for decision-makers.

---

### Certificates
- **Google Data Analytics Professional Certificate:** Google / Coursera ([Verify](https://www.coursera.org/account/accomplishments/specialization/3JJSOM5SNM00))
- **Python:** Kaggle ([Verify](https://www.kaggle.com/learn/certification/evandeaver/python))
- **Intro to Machine Learning:** Kaggle ([Verify](https://www.kaggle.com/learn/certification/evandeaver/intro-to-machine-learning))

---

### Contact
- **Email:** edeaver06@gmail.com
- **GitHub:** [github.com/edeaver06](https://github.com/edeaver06)
- **LinkedIn:** [linkedin.com/in/evan-deaver-276152a5](https://www.linkedin.com/in/evan-deaver-276152a5/)
- **Kaggle:** [kaggle.com/evandeaver](https://www.kaggle.com/evandeaver)
- **RPubs:** [rpubs.com/slammerjammer](https://rpubs.com/slammerjammer)
