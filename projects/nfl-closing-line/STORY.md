# Is the Market's Closing Price an Accurate Forecast? The story in plain English

**▶️ [Try the live app](https://nfl-line-e.streamlit.app/)** · [Back to the project page](README.md) · [The code and how it's built](code/README.md)

**The setting:** before every NFL game, sportsbooks publish a *line*, their prediction of the result. The final line just before kickoff is the *closing line*.

**The question:** is the closing line a good forecast, and can any popular betting "system" beat it?

**The data:** 7,354 NFL games from 1999 to early in the 2026 season, with closing lines, from the public nflverse dataset.

> **Three terms:**
> - *Spread* = the predicted winning margin. "Home −3" means the home team is expected to win by 3. A bet on a team "covers" if it beats the spread.
> - *-110 odds* = you risk $110 to win $100. Because of that fee (the *vig*), you must win **52.38%** of bets just to break even.
> - *Moneyline* = a bet on who wins outright; its odds can be turned into a win probability.

## 1. Is the closing line accurate?

On average, yes. The actual home margin minus the spread averages +0.08 points: almost exactly zero. But single games miss a lot: the typical miss is 10.3 points.

![How far results land from the spread](code/figures/05_spread_error_hist.png)

**What this means:** the line doesn't lean toward either side; it's right on average, not game by game. Being "unlucky" by 10 points is normal.

## 2. Do the odds give honest win chances?

After removing the bookmaker's margin (about 2.7%), the odds' win chances match what actually happened. In the chart, every group of games sits close to the diagonal "perfect" line. Over 5,358 games the accuracy score (Brier score) is 0.211, better than a coin flip's 0.250 (lower is better).

![Odds-implied win chance vs how often teams actually won](images/01_moneyline_calibration.png)

**What this means:** the market's probabilities are trustworthy. The odds' win chances closely match how often teams actually won, in every probability band we checked.

## 3. Do home underdogs beat the spread?

This is one of the most famous betting beliefs. Home underdogs covered 50.5% of the time (2,417 bets), below the 52.38% needed to profit. Only the 7+ point home underdogs reached 55.9% (525 games), and that's one subgroup out of many, not a tested strategy.

![Home team cover rate by size of the spread](images/02_cover_rate_by_spread.png)

**What this means:** the "home dog" edge isn't there overall, and one lucky-looking slice isn't enough to bet on.

## 4. Do any of 10 popular strategies beat the breakeven?

I tested 10 common angles. Only unders in windy games (15+ mph) clearly differ from a coin flip: 57.0% over 674 bets. But after correcting for testing 10 strategies at once, the evidence that it beats the 52.38% bar isn't strong enough (p = 0.09). Out of sample (2015 onward), it went 56.4% over 225 bets.

![Win rate of 10 strategies with uncertainty ranges](images/03_strategy_win_rates.png)

**What this means:** when you test many ideas, some look good by luck. Wind is also measured at kickoff, which a bettor doesn't know when betting, and lines may already reflect forecast wind. The out-of-sample check is also small (225 bets).

## 5. What happens if you just follow a simple rule?

Betting 1 unit on every favorite lost about 499 units over 7,122 bets (−7.0% per bet). Betting every over lost about 406 units. Home underdogs and primetime overs each lost about 86.

![Running profit or loss of simple strategies over time](images/04_backtest_pnl.png)

**What this means:** the fee does its job. Over time, simple rules steadily lose money.

## Summary
1. The closing spread is an unbiased forecast, but single games miss by about 10 points. Totals are slightly off (slope 0.93, CI excludes 1; games ran 0.71 points above the line), not by enough to beat the fee.
2. Odds-based win chances are well calibrated.
3. Famous edges like home underdogs and primetime overs don't beat the breakeven.
4. Wind unders look good but aren't proven profitable.
5. **Treat betting as paid entertainment with a negative expected value, not as income.** If it stops being fun, get help: 1-800-GAMBLER (US).

## Limitations (in plain words)
- **These are consensus closing lines.** Real prices vary by sportsbook, and you can't usually bet the exact close.
- **Opening lines and line movement aren't in the data**, so "beating the close" itself can't be measured.
- **Weather is only available for some games**, and it's measured at kickoff.
- **The strategy list was chosen in advance.** Searching through hundreds of angles would turn up "winners" by pure chance.
- **The 2026 season is partial** (78 games, data pulled Oct 12, 2026).
