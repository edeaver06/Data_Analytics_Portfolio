# Markets vs Polls: Who Called the 2024 Election Better?

**Did betting markets forecast the 2024 presidential race better than polls?** Yes, state by state, at every matched date from 3 weeks to 1 day out. But it was one election, and the polls all missed in the same direction.

**[📖 Story](STORY.md) | [💻 Code](code/README.md)**

![Forecast accuracy (Brier score) of Polymarket, Kalshi and the poll average by days before the election](images/01_brier_by_horizon.png)

## The problem
Prediction markets such as Polymarket and Kalshi are often said to beat polls. Newsrooms, campaigns and investors who rely on forecasts need to know whether that's true, and why, before trusting either one. This project scores both on the same states and the same dates.

## Key findings
- **Markets scored better 1 day out:** Brier score (lower is better) Polymarket 0.042, Kalshi 0.043, poll average 0.053, across 35 states.
- **The polls missed in one direction:** actual results were on average 3.2 points more Republican than the poll average, and the miss went the same way in 31 of 35 states.
- **Close calls decided it:** the poll average had the wrong leader in 4 states (MI, WI, PA, NV); the markets missed 2.
- **The two markets were nearly tied:** Polymarket edged out Kalshi at 7 and 14 days out (−0.005 Brier) and they tied at 1 day.

## What I built
- A data pipeline pulling daily prices from the Polymarket and Kalshi public APIs, archived 538 polls and certified MIT election results.
- DuckDB SQL that lines up every forecast on matched dates with no look-ahead (enforced by a test).
- Scoring code: Brier score, log loss, calibration and paired bootstrap intervals.
- A sensitivity check showing the poll result doesn't depend on its one tuning setting.

## Tools
Python (pandas, SciPy) · SQL · DuckDB · REST APIs · matplotlib · Jupyter · pytest

## Go deeper
- [The story in plain English](STORY.md)
- [How it's built: architecture, design decisions, how to run](code/README.md)
- [Walkthrough notebook](code/notebooks/markets_vs_polls.ipynb)
- [SQL](code/sql/forecasts.sql) · [Scoring code](code/src/forecast_scoring.py)
