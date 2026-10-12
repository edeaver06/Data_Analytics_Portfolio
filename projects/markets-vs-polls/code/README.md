# Markets vs Polls: code and engineering notes

Everything technical lives here. For the recruiter summary see the [project page](../README.md); for the plain-English walkthrough see [STORY.md](../STORY.md). Run every command below from this `code/` folder.

## How to run
```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python src/fetch_data.py     # downloads all raw data (~2 min); raw files are also committed
.venv/bin/python src/run_analysis.py           # prints scores, writes data/clean/ + ../images/
.venv/bin/python -m pytest -q tests        # 7 tests
```
Notebook: `notebooks/markets_vs_polls.ipynb`. Charts are written to `../images/`.

## Interactive dashboard
A Streamlit app in `app/` walks through the findings: a plain-English overview first, then interactive pages. It reads only the small extract in `app/data/`.
```bash
pip install -r app/requirements.txt
python app/make_extract.py   # refresh app/data after re-running the analysis
streamlit run app/streamlit_app.py
```
To deploy on Streamlit Community Cloud, set the main file to `projects/markets-vs-polls/code/app/streamlit_app.py`.

## What's in this folder (`code/`)
| Folder | What it's for |
|---|---|
| `data/` | `raw/` source downloads (market prices, 538 polls, MIT election results) and `clean/` scored outputs |
| `sql/` | DuckDB SQL that builds outcomes, market prices at each horizon and poll averages |
| `src/` | Python: data fetching (`fetch_data.py`), scoring (`forecast_scoring.py`) and the pipeline (`run_analysis.py`) |
| `notebooks/` | Walkthrough notebook |
| `tests/` | pytest checks, including that no data after a cutoff is used |

## Details
### Context
**Bottom line: in 2024, Polymarket and Kalshi state-level prices scored better than a simple poll-average forecast at every matched time point from 3 weeks to 1 day out. But this is one election with errors that were correlated across states, so it isn't evidence that markets beat polls in general.**

Every forecast is coded as P(Republican candidate wins the state). That's only a convention, and the same metrics apply to both sides. This project scores accuracy, not which side is right.

### Key findings
Brier score (lower is better; always guessing 50% scores 0.25), scored only on states where Polymarket, Kalshi and a poll average all exist at the same date:

| Days before Nov 5 | States | Polymarket | Kalshi | Polls (σ=5) | States called right (P / K / Polls) |
|---|---|---|---|---|---|
| 21 | 23 | 0.059 | 0.062 | 0.074 | 22 / 22 / 19 |
| 14 | 26 | 0.038 | 0.043 | 0.061 | 26 / 26 / 23 |
| 7 | 34 | **0.029** | 0.034 | 0.047 | 34 / 33 / 31 |
| 1 | 35 | **0.042** | 0.043 | 0.053 | 33 / 33 / 31 |

1. **Both markets beat polls at every horizon.** Polymarket minus polls at 1 day out: -0.011 Brier (paired bootstrap 95% CI -0.023 to -0.002). Kalshi minus polls: -0.010 (CI -0.022 to +0.001, which just includes 0). At 7 and 14 days out, both CIs exclude 0.
2. **Why the markets won:** the polls missed in the same direction almost everywhere. At 1 day out, the actual two-party margin was on average **3.2 points more Republican** than the poll average (SD 3.0 across 35 states). The poll average narrowly had the wrong leader in MI, WI, PA and NV. The markets also had MI and WI wrong, but leaned the right way in PA and NV. Any forecaster that leaned toward the outcome in close states looks good in a cycle with a one-directional miss. A cycle where polls miss the other way could reverse this ranking.
3. **Polymarket edged out Kalshi.** The gap was small (-0.005 Brier at 7 and 14 days), but its CI excludes 0 there. At 1 day out they're tied (CI includes 0). Kalshi's safe-state prices sat at 5–10% instead of 1–2%, which costs a little Brier score. That probably reflects its order-book prices and fees rather than real uncertainty.
4. **The poll forecast's result doesn't depend on its one tuning setting.** Turning the poll average into a win probability takes an assumed error size σ. I fixed σ at 5 points before scoring. Any σ from 3 to 8 gives a Brier of 0.053–0.059 at 1 day out, still worse than both markets.
5. 28 days out, only 7 states overlap, because Kalshi's state markets launched Oct 5, 2024. Everyone did poorly on that small set of swing states (0.21–0.27). Read that row as anecdotal.

### Data sources and coverage
| Source | What | Coverage | Access |
|---|---|---|---|
| Polymarket Gamma API https://gamma-api.polymarket.com/events + CLOB price history https://clob.polymarket.com/prices-history | Daily price of "Will a Republican win <State>?" | 47 of 51 states plus DC (no event found for DE, DC, NM, NY under the standard slug), Oct 1–Nov 5, 2024 | public, no key |
| Kalshi public API https://api.elections.kalshi.com/trade-api/v2 (`/historical/markets/PRESPARTY<ST>-24-R/candlesticks`) | Daily close price, Republican-wins-state market | 51/51, from Oct 5, 2024 | public, no key |
| FiveThirtyEight 2024 president polls CSV, Internet Archive snapshot https://web.archive.org/web/2024id_/https://projects.fivethirtyeight.com/polls/data/president_polls.csv | State polls (Harris vs Trump), last poll ending Nov 4, 2024 | 18,095 rows; enough polls for 23–35 states depending on horizon | public (538 shut down in 2025; the live URL now redirects to ABC News) |
| MIT Election Data + Science Lab, *U.S. President 1976–2024*, Harvard Dataverse doi:10.7910/DVN/42MVDX | Certified state vote totals | all 51, 2024 | public |

### Method
- **Matched time points:** for 28, 21, 14, 7 and 1 days before Nov 5, 2024, I took each market's last daily price on or before that date (no more than 3 days stale). The poll average uses polls ending in the 21 days up to that date, counting each pollster's latest poll once. Nothing after the cutoff is used, and a test checks this.
- **Poll probability:** two-party margin (R-D) → Φ(margin/σ), with σ = 5 points fixed in advance. This is a deliberately simple baseline, not a full forecast model like 538's or Silver Bulletin's.
- **Scoring:** Brier score, log loss, states called correctly, and a paired bootstrap over states for differences in Brier score.
- **SQL (DuckDB, CTEs):** `sql/forecasts.sql` builds `outcomes`, `market_at_horizon` and `poll_avg`. **Python:** `src/forecast_scoring.py` reuses `ml_prob` from `nfl-closing-line/code/src/clv.py`, with the same calibration and Brier approach.

### Caveats and gaps
- **n = 1 election.** The state outcomes are correlated (one national swing), so the effective sample is far smaller than 35, and the bootstrap CIs, which treat states as independent, are too narrow.
- The comparison only covers states with polls. Safe states with no polling are left out, which favors close races.
- Market prices are daily trade or close prices, not volume-weighted, and they include each platform's fees and spreads. Kalshi state markets didn't exist before Oct 5, 2024.
- **The planned national and historical comparison is out of scope.** I didn't do multi-cycle calibration (2016/2020) because neither platform has comparable state markets for those years: Kalshi's US election contracts only became legal in late 2024. I didn't check whether Polymarket had 2020 state markets with price history; that's possible future work. I scaled the project down to 2024 state-level winner markets rather than mix in unlike data.
- I didn't search non-standard Polymarket slugs for the 4 missing states. All 4 are uncompetitive, so they would barely change the scores.

## Architecture
```
Polymarket + Kalshi APIs, 538 polls (archive), MIT results ──► src/fetch_data.py ──► data/raw/
        ──► sql/forecasts.sql (DuckDB: outcomes, market_at_horizon, poll_avg)
        ──► src/forecast_scoring.py (Brier, log loss, calibration, bootstrap) ──► src/run_analysis.py ──► data/clean/, ../images/
```

## Design decisions (and why)
1. **Score only matched states and dates.** Polymarket, Kalshi and the poll average are compared only where all three exist on the same day, so no forecaster gets an easier set of states.
2. **No look-ahead.** Each forecast uses only prices and polls available on or before the cutoff date; a test enforces it.
3. **Brier score plus calibration, not just 'called it right'.** Brier rewards confident correct forecasts and punishes confident wrong ones.
4. **A deliberately simple poll baseline with its one setting fixed in advance** (σ = 5 points), then checked for sensitivity (σ 3–8) so the result isn't tuned.
5. **Paired bootstrap for differences.** Compares forecasters state by state, and the README says plainly that these intervals are too narrow because states move together.
6. **Code reuse across projects.** The probability helper comes from the NFL project, so both use the same calibration logic.
7. **Raw data committed.** The 538 source is archived-only and market APIs change, so the analysis stays reproducible.
