# Google Fiber: Why Do Customers Call Back?

For a support operations manager: why do customers have to call back? Two problem types (Wi-Fi & Internet, Technical Troubleshooting) drive 80.2% of repeat calls, and Billing in market 3 averages ~1.97 repeat calls per first call. This measures FCR (first-contact resolution, meaning the problem is fixed on the first call).

### ▶️ [Try the live app](https://fiber-e.streamlit.app/)
No install needed; if the app has been idle it shows a short wake-up screen first.

**Where does first-contact support fail?** Two problem types, Wi-Fi & Internet and Technical Troubleshooting, drive 80.2% of all repeat calls, so that's where a fix pays off most.

**[▶️ Live app](https://fiber-e.streamlit.app/) | [📊 Tableau](https://public.tableau.com/app/profile/evan.deaver/viz/GoogleFiberRepeatCallsFCR/GoogleFiberRepeatCalls) | [📖 Story](STORY.md) | [💻 Code](code/README.md)**

![Share of repeat calls from Wi-Fi and technical problems, by market](images/wifi_tech_share_by_market.png)

## The problem
Every time a customer has to call support again about the same issue, it costs the company money and the customer patience. Google Fiber's support team wanted to know which problems and which markets cause the most repeat calls within 7 days, so it could focus on the fix that matters most.

## Key findings
- **Two problem types drive 80.2% of repeat calls:** Wi-Fi & Internet (50.7%) and Technical Troubleshooting (29.6%), across 20,240 repeat calls in Q1 2022.
- **Market_3 has the highest repeat rate, 44.7%** (36.7% without its Billing calls), against 27.9% in market_1 and 17.9% in market_2.
- **Market_3 Billing issues often aren't resolved on the first call:** market_3 logs 1,498 Billing repeats against 759 first calls, about 1.97 repeats per first call (one customer can call back several times). Without market_3, Billing's repeat rate drops from 67.5% to 32.3%, so this is a market_3 problem worth investigating.
- **Scheduling has the second-highest repeat rate, 60.6%** (1,469 repeat calls; 50.0% outside market_3), a candidate for appointment-status updates.

## What I built
- A Python analysis of 64,939 first calls and their 7-day repeats across 3 markets and 5 problem types.
- The same metrics in SQL (DuckDB, CTEs and window functions), with a test that SQL and Python agree.
- A market-by-market breakdown that isolated market_3's very high Billing repeat volume.
- Polished, colorblind-safe charts and an interactive Plotly dashboard.

## Tools
Python (pandas) · SQL · DuckDB · matplotlib · Plotly · Jupyter · pytest

## Go deeper
- [The story in plain English](STORY.md)
- [How it's built: architecture, design decisions, how to run](code/README.md)
- [Analysis notebook](code/notebooks/google_fiber_fcr.ipynb)
- [SQL](code/sql/fcr_metrics.sql)
