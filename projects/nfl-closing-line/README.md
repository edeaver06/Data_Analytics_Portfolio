# Can You Beat the NFL Closing Line?

### ▶️ [Try the live app](https://nfl-line-e.streamlit.app/)
No install needed; if the app has been idle it shows a short wake-up screen first.

**Do popular betting "systems" beat the sportsbook?** No: across 7,354 games (1999–2026), the closing line is a very good forecast, and none of 10 common angles beats the -110 vig in a statistically defensible way.

**[▶️ Live app](https://nfl-line-e.streamlit.app/) | [📖 Story](STORY.md) | [💻 Code](code/README.md)**

![Win rate of 10 betting strategies vs the 52.38% breakeven](images/03_strategy_win_rates.png)

## The problem
Sports-betting content is full of "systems": bet home underdogs, bet the over in primetime, bet unders when it's windy. At standard -110 odds a bettor needs to win 52.38% of bets just to break even. This project tests whether any popular angle clears that bar once it's tested properly.

## Key findings
- **The line is right on average:** closing spreads are unbiased (slope 1.04, 95% CI 0.99–1.09; a slope of 1 means the line tracks results one-for-one). Totals are slightly off (slope 0.93; games ran 0.71 points above the line), not enough to beat the fee, even though the typical game misses by 10.3 points.
- **The famous biases aren't there:** home underdogs covered 50.5% and primetime overs hit 48.7%, both below the 52.38% breakeven.
- **Simple strategies lose money:** betting every favorite lost 7.0% per bet (about −499 units over 7,122 bets).
- **One angle stands out but isn't proven profitable:** unders with 15+ mph wind went 57.0%, but the beat-the-vig test doesn't survive multiple-testing correction (p = 0.09).

## What I built
- A DuckDB SQL model of 7,354 games, every strategy's bets and their win rates and ROI.
- A Python statistics module: regression with robust errors, bookmaker-margin removal, calibration and Brier score, exact binomial tests with Holm correction.
- A walk-forward check: strategies chosen on seasons before 2015 and tested only on 2015+.
- Polished charts and a responsible-gambling takeaway.

## Tools
Python (pandas, statsmodels, SciPy) · SQL · DuckDB · matplotlib · Jupyter · pytest

## Go deeper
- [The story in plain English](STORY.md)
- [How it's built: architecture, design decisions, how to run](code/README.md)
- [Walkthrough notebook](code/notebooks/nfl_closing_line.ipynb)
- [SQL](code/sql/closing_line.sql) · [Stats code](code/src/clv.py) · [Data (nflverse)](https://github.com/nflverse/nfldata)
