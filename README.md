# Evan Deaver: Data Analyst Portfolio

### 📄 [View my Resume (PDF)](https://github.com/edeaver06/Data_Analytics_Portfolio/raw/main/resume/evan-deaver-resume-public.pdf)

[![CI](https://github.com/edeaver06/Data_Analytics_Portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/edeaver06/Data_Analytics_Portfolio/actions/workflows/ci.yml)

## Overview
I'm Evan, a Google-certified data analyst (SQL, Python, R, Excel, Tableau) moving into **data analyst and data engineer roles** (Remote, worldwide or US). I build tested SQL pipelines, publish dashboards, check models and data for flaws, and do data QA on AI model outputs.

**What's here:** Nine projects in [`projects/`](projects). Each one opens with a one-page summary (the question, the answer, key findings, what I built), a plain-English **Story**, and a `code/` folder with everything technical. Start with **Steam Pulse**. It runs in your browser with no install: [▶️ live app](https://steam-pulse-e.streamlit.app/).

## Portfolio Projects
| Project | Result | Role type | Links |
|---|---|---|---|
| **[Steam Pulse: What keeps a video game alive?](projects/steam-pulse)** | Which games keep players after launch? For publishers planning updates and sales: the top 10 held 40.1% of 6.22M players (Oct 12, 2026), and games have about 44% fewer players a month after launch month. | Data engineer (pipeline, warehouse, dbt, app) | **[▶️ Live app](https://steam-pulse-e.streamlit.app/)** · [Story](projects/steam-pulse/STORY.md) · [Code](projects/steam-pulse/code/README.md) |
| **[Markets vs Polls: Who Called the 2024 Election Better?](projects/markets-vs-polls)** | Did betting markets beat polls in 2024? For forecasters and newsrooms: one day out, markets were slightly more accurate (Brier score, lower is better: 0.042 Polymarket, 0.043 Kalshi vs 0.053 polls), in one election. | Data analyst (APIs, forecasting) | **[▶️ Live app](https://markets-polls-e.streamlit.app/)** · [Story](projects/markets-vs-polls/STORY.md) · [Code](projects/markets-vs-polls/code/README.md) |
| **[Olist: When the Parcel Is Late, the Stars Fall](projects/olist-ecommerce)** | How much does a late delivery cost in reviews? For marketplace operations teams: late orders average 3.78★ vs 4.29★ on time. | Data analyst / BI (SQL) | **[▶️ Live app](https://olist-e.streamlit.app/)** · [Tableau](https://public.tableau.com/app/profile/evan.deaver/viz/OlistLateDeliveries/OlistLateDeliveries) · [Story](projects/olist-ecommerce/STORY.md) · [Code](projects/olist-ecommerce/code/README.md) |
| **[Aircraft Readiness: What Grounds Airplanes, and How Fast Is It Reported?](projects/aircraft-readiness)** | Which aircraft systems disrupt flights? For airline maintenance planners: of 34,350 FAA reports, 2,521 disrupted a flight, mostly air conditioning, landing gear and engines; 7.1% of in-flight problems came back within 30 days. | Data analyst / BI | **[▶️ Live app](https://aircraft-ready-e.streamlit.app/)** · [Tableau](https://public.tableau.com/app/profile/evan.deaver/viz/AircraftReliability/AircraftReliability) · [Story](projects/aircraft-readiness/STORY.md) · [Code](projects/aircraft-readiness/code/README.md) |
| **[Google Fiber: Why Do Customers Call Back?](projects/google-fiber-fcr)** | Why do customers call back? For support operations managers: two problem types drive 80.2% of repeat calls, and Billing in market 3 averages ~1.97 repeat calls per first call. | Data analyst / BI (operations) | **[▶️ Live app](https://fiber-e.streamlit.app/)** · [Tableau](https://public.tableau.com/app/profile/evan.deaver/viz/GoogleFiberRepeatCallsFCR/GoogleFiberRepeatCalls) · [Story](projects/google-fiber-fcr/STORY.md) · [Code](projects/google-fiber-fcr/code/README.md) |
| **[NFL: Is the Market's Closing Price an Accurate Forecast?](projects/nfl-closing-line)** | Can anyone beat the betting market's final NFL forecast? For judging market efficiency: across 7,354 games, no common strategy beat it once the bookmaker's cut is counted (52.38% wins needed to break even). | Data analyst (statistics) | **[▶️ Live app](https://nfl-line-e.streamlit.app/)** · [Story](projects/nfl-closing-line/STORY.md) · [Code](projects/nfl-closing-line/code/README.md) |
| **[US Electricity Prices: Where Did Power Bills Rise Most?](projects/electricity-price-tracker)** | Where have home power bills risen most? For households and energy analysts: the US average rose from 8.58 to 18.02 cents per kWh since 2001 (+110%, about +13% after inflation), from 12.32¢ (North Dakota) to 43.51¢ (Hawaii). | Data analyst (API pipeline, SQLite, Google Sheets) | [📊 Google Sheet](https://docs.google.com/spreadsheets/d/1bRhtVTY08znmxWk9Amkb7G1pA-VjqgMjEWuWZTzX9so/edit) · [Story](projects/electricity-price-tracker/STORY.md) · [Code](projects/electricity-price-tracker/code/README.md) |
| **[Rural Hospital Financial Warning Signs](projects/rural-hospital-warning-signs)** | Which rural hospitals show financial strain? For state rural-health offices and hospital finance teams: 6.6% of 485 hospitals in SD, ND, MN, NE, MT, WY, IA show many warning signs vs 14.0% elsewhere (CMS FY2023); Wyoming is the outlier (46% lost money). | Data analyst (Python, SQLite, Google Sheets) | [📊 Google Sheet](https://docs.google.com/spreadsheets/d/1QoG2l-5s70JOvz15ZmdtHULTPSygrQUXWIPyah5qBbo/edit) · [Story](projects/rural-hospital-warning-signs/STORY.md) · [Code](projects/rural-hospital-warning-signs/code/README.md) |
| **[Diabetes Care Gaps: Which Patients Are Missing Recommended Care?](projects/diabetes-care-gaps)** | Which diabetic patients are missing recommended care? For care coordinators and quality teams: among 779 synthetic diabetic adults (MY2025), 5 of 7 HEDIS-style measures missed target, with A1c control at 48.5% vs a 60% target, and 672 patients have open gaps in 2026. | Data analyst (R, SQL, healthcare KPIs) | [📊 Dashboard](https://htmlpreview.github.io/?https://github.com/edeaver06/Data_Analytics_Portfolio/blob/main/projects/diabetes-care-gaps/code/app/dashboard.html) · [Story](projects/diabetes-care-gaps/STORY.md) · [Code](projects/diabetes-care-gaps/code/README.md) |

## Table of Contents
- [Overview](#overview)
- [Portfolio Projects](#portfolio-projects)
- [Skills](#skills)
- [Experience](#experience)
- [Education](#education)
- [Certificates](#certificates)
- [Contact](#contact)

To run a project: `cd projects/<name>/code && pip install -r requirements.txt && pytest -q` (or `make test` from the root). Each `code/README.md` has the full steps.

## Skills
- **Languages & querying:** SQL (DuckDB, Google BigQuery, PostgreSQL), Python (pandas), R (tidyverse, ggplot2, caret), dbt, Advanced Excel (pivot tables, Power Query, XLOOKUP)
- **BI & visualization:** Tableau (Tableau Public), dashboards, metric reporting
- **Data quality & AI operations:** data validation and reconciliation, anomaly detection, automated testing, human-in-the-loop (HITL) model evaluation, multimodal data annotation

## Experience
- **AI Data Annotator & Model Evaluator**, Outlier.ai (2025–present): QA on LLM outputs for factual accuracy, safety and instruction-following; defect classification with an error taxonomy; multimodal text and vision annotation.
- **E-Commerce & Digital Storefront Operations**, self-employed (2003–present): multi-channel sales, catalog, pricing and fulfillment; tracking inventory turnover across 200+ active listings in Excel.

## Education
- **Bachelor of General Studies** (emphases: Business, Sociology, Education), Black Hills State University (2015)

## Certificates
- **Google Professional Certificates:** [Data Analytics](https://www.coursera.org/account/accomplishments/specialization/3JJSOM5SNM00) (2025), Business Intelligence (2026), AI (2026)
- **Kaggle:** [Intro to Machine Learning](https://www.kaggle.com/learn/certification/evandeaver/intro-to-machine-learning) (2026), [Python](https://www.kaggle.com/learn/certification/evandeaver/python) (2026)

## Contact
- **Email:** edeaver06@gmail.com
- **LinkedIn:** [linkedin.com/in/evan-deaver-276152a5](https://www.linkedin.com/in/evan-deaver-276152a5/)
- **Tableau Public:** [evan.deaver](https://public.tableau.com/app/profile/evan.deaver/vizzes)
- **Kaggle:** [evandeaver](https://www.kaggle.com/evandeaver)
