# Evan Deaver: Data Analyst Portfolio

[Resume (PDF)](https://github.com/edeaver06/Data_Analytics_Portfolio/raw/main/resume/evan-deaver-resume-public.pdf)

[![CI](https://github.com/edeaver06/Data_Analytics_Portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/edeaver06/Data_Analytics_Portfolio/actions/workflows/ci.yml)

## Overview
I'm Evan, a data analyst in the United States. After years running my own e-commerce business, I earned the Google Data Analytics and Google Business Intelligence certificates, and I'm now looking for data analyst and data engineer roles. I work in SQL, Python, R, Tableau, Google Sheets and Excel, and I write tests so the numbers in each project can be checked.

There are nine projects in [`projects/`](projects). Each folder has a one-page summary, a plain-English `STORY.md`, and a `code/` folder with the technical details. If you only open one, open Steam Pulse. The [live app](https://steam-pulse-e.streamlit.app/) runs in your browser with nothing to install.

## Portfolio Projects
| Project | Result | Role type | Links |
|---|---|---|---|
| **[Steam Pulse: What keeps a video game alive?](projects/steam-pulse)** | Across the ~1,000 most-owned games, the top 10 held 40.1% of 6.22M players (Oct 12, 2026). Games have about 44% fewer players a month after their launch month. | Data engineer (pipeline, DuckDB, dbt, app) | [Live app](https://steam-pulse-e.streamlit.app/) · [Story](projects/steam-pulse/STORY.md) · [Code](projects/steam-pulse/code/README.md) |
| **[Markets vs Polls: Who Called the 2024 Election Better?](projects/markets-vs-polls)** | One day out, across 35 state races scored, the markets were slightly more accurate than polls (Brier score, lower is better: 0.042 Polymarket, 0.043 Kalshi vs 0.053 polls), but this is one election. | Data analyst (APIs, forecasting) | [Live app](https://markets-polls-e.streamlit.app/) · [Story](projects/markets-vs-polls/STORY.md) · [Code](projects/markets-vs-polls/code/README.md) |
| **[Olist: When the Parcel Is Late, the Stars Fall](projects/olist-ecommerce)** | Late orders average 3.78★ vs 4.29★ on time. | Data analyst / BI (SQL) | [Live app](https://olist-e.streamlit.app/) · [Tableau](https://public.tableau.com/app/profile/evan.deaver/viz/OlistLateDeliveries/OlistLateDeliveries) · [Story](projects/olist-ecommerce/STORY.md) · [Code](projects/olist-ecommerce/code/README.md) |
| **[Aircraft Readiness: What Grounds Airplanes, and How Fast Is It Reported?](projects/aircraft-readiness)** | Of 34,350 FAA reports, 2,521 disrupted a flight, mostly air conditioning, landing gear and engines; 7.1% of in-flight problems came back within 30 days. | Data analyst / BI | [Live app](https://aircraft-ready-e.streamlit.app/) · [Tableau](https://public.tableau.com/app/profile/evan.deaver/viz/AircraftReliability/AircraftReliability) · [Story](projects/aircraft-readiness/STORY.md) · [Code](projects/aircraft-readiness/code/README.md) |
| **[Google Fiber: Why Do Customers Call Back?](projects/google-fiber-fcr)** | Two problem types account for 80.2% of repeat calls, and Billing in market 3 averages ~1.97 repeat calls per first call. | Data analyst / BI (operations) | [Live app](https://fiber-e.streamlit.app/) · [Tableau](https://public.tableau.com/app/profile/evan.deaver/viz/GoogleFiberRepeatCallsFCR/GoogleFiberRepeatCalls) · [Story](projects/google-fiber-fcr/STORY.md) · [Code](projects/google-fiber-fcr/code/README.md) |
| **[NFL: Is the Market's Closing Price an Accurate Forecast?](projects/nfl-closing-line)** | Across 7,354 games, closing spreads are unbiased and moneyline probabilities are well calibrated (Brier 0.211 vs 0.250 for a coin flip, on the 5,358 games with moneylines). None of 10 common strategies beat the market's forecast in a statistically defensible way. | Data analyst (statistics) | [Live app](https://nfl-line-e.streamlit.app/) · [Story](projects/nfl-closing-line/STORY.md) · [Code](projects/nfl-closing-line/code/README.md) |
| **[US Electricity Prices: Where Did Power Bills Rise Most?](projects/electricity-price-tracker)** | The US average home price rose from 8.58 to 18.02 cents per kWh since 2001 (+110%, about +13% after inflation, adjusted with CPI-U (FRED CPIAUCSL), 2001 average vs the latest 12 months). States range from 12.32¢ (North Dakota) to 43.51¢ (Hawaii). | Data analyst (API pipeline, SQLite, Google Sheets) | [Google Sheet](https://docs.google.com/spreadsheets/d/1bRhtVTY08znmxWk9Amkb7G1pA-VjqgMjEWuWZTzX9so/edit) · [Story](projects/electricity-price-tracker/STORY.md) · [Code](projects/electricity-price-tracker/code/README.md) |
| **[Rural Hospital Financial Warning Signs](projects/rural-hospital-warning-signs)** | 6.6% of 485 hospitals in SD, ND, MN, NE, MT, WY, IA show 4 or more of 6 warning signs vs 13.4% elsewhere (CMS FY2023); Wyoming is the outlier (46% lost money). | Data analyst (Python, SQLite, Google Sheets) | [Google Sheet](https://docs.google.com/spreadsheets/d/1QoG2l-5s70JOvz15ZmdtHULTPSygrQUXWIPyah5qBbo/edit) · [Story](projects/rural-hospital-warning-signs/STORY.md) · [Code](projects/rural-hospital-warning-signs/code/README.md) |
| **[Diabetes Care Gaps: Which Patients Are Missing Recommended Care?](projects/diabetes-care-gaps)** | Among 779 synthetic diabetic adults (MY2025), 5 of 7 HEDIS-style measures missed target, with A1c control at 48.5% vs a 60% target, and 672 patients have open gaps in 2026. | Data analyst (R, SQL, healthcare KPIs) | [Dashboard](https://htmlpreview.github.io/?https://github.com/edeaver06/Data_Analytics_Portfolio/blob/main/projects/diabetes-care-gaps/code/app/dashboard.html) · [Story](projects/diabetes-care-gaps/STORY.md) · [Code](projects/diabetes-care-gaps/code/README.md) |

## Table of Contents
- [Overview](#overview)
- [Portfolio Projects](#portfolio-projects)
- [Skills](#skills)
- [Experience](#experience)
- [Education](#education)
- [Certificates](#certificates)
- [Contact](#contact)

To run a project: `cd projects/<name>/code && pip install -r requirements.txt && pytest -q` (or `make test` from the root, which runs all eight Python projects and the Diabetes R tests). Each `code/README.md` has the full steps.

CI runs unit tests on small fixtures; checks against the full data run locally.

## Skills
- Languages and querying: SQL (DuckDB, SQLite), Python (pandas), R (tidyverse, ggplot2, testthat), dbt, Excel (pivot tables, formulas)
- BI and visualization: Tableau (Tableau Public), Google Sheets dashboards, Streamlit apps, metric reporting
- Data quality: data validation and reconciliation, anomaly detection, automated testing

## Experience
- **E-Commerce & Digital Storefront Operations**, self-employed (2003 to present). I sell across several channels, handle the catalog, pricing and shipping, and track inventory turnover for 200+ active listings in Excel.
- **Data Annotator**, Outlier.ai (2025 to present). I check large language model (LLM) outputs for factual accuracy, safety and instruction-following, and classify defects with an error taxonomy.

## Education
- **Bachelor of General Studies** (emphases: Business, Social Science, Education), Black Hills State University (2015)

## Certificates
- **Google Professional Certificates:** [Data Analytics](https://www.coursera.org/account/accomplishments/specialization/3JJSOM5SNM00) (2025), Business Intelligence (2026)

## Contact
- **Email:** edeaver06@gmail.com
- **LinkedIn:** [linkedin.com/in/evan-d-276152a5](https://www.linkedin.com/in/evan-d-276152a5/)
- **Tableau Public:** [evan.deaver](https://public.tableau.com/app/profile/evan.deaver/vizzes)
- **Kaggle:** [evandeaver](https://www.kaggle.com/evandeaver)
