# Backfill sources, licenses, coverage

All files here were fetched 2026-10-12 (America/Guatemala). Raw responses are kept verbatim (gitignored, large); parsed tables are in `tables/`. Nothing is imputed.

| table | source | terms / license | granularity | coverage |
|---|---|---|---|---|
| `tables/steamcharts_monthly.parquet` | steamcharts.com/app/{appid} monthly table (avg + peak concurrent players) | No robots.txt (HTTP 404) and no terms page on 2026-10-12; the About page says the data comes from the Steam Web API. Fetched at 1 request / 1.5 s with an identifying User-Agent. Not redistributed beyond this portfolio; attribution: "Data: SteamCharts.com". | monthly | see README coverage table |
| `tables/reviews_monthly.parquet` | store.steampowered.com/appreviewhistogram/{appid} (public store endpoint behind the review graph). Steam returns `rollup_type` month (984 apps) or week (16 young apps: non-overlapping 7-day buckets); weekly buckets are SUMMED into their start month, one row per (appid, month) | Steam Subscriber Agreement / public web; 1 request / 1.2 s. English-language reviews only (`l=english`). | monthly up/down counts | 1,000/1,000 apps requested |
| `tables/mendeley_price_daily.parquet` | Vihanga et al., "Steam Games Dataset: Player count history, Price history and data about games", Mendeley Data v1, doi:10.17632/ycy3sy3vj2.1 | **CC BY 4.0** | daily price (initial, final, discount) | 1,512 paid apps, 2019-04-07 to 2020-08-12 |
| `tables/mendeley_players_daily.parquet` | same dataset, hourly player counts aggregated to daily mean/max | **CC BY 4.0** | hourly → daily | 2,000 apps, 2017-12-14 to 2020-08-12 |

## Considered and NOT used
- **SteamDB**: its terms forbid scraping, so it wasn't used.
- **IsThereAnyDeal API** (price history log): requires a registered app/API key. Its terms allow public non-competing use, but registration needs Evan's account. Not fetched. This is the recommended source for 2020-2026 price history once a key exists.
- **Kaggle** datasets: need an authenticated Kaggle account/API token; not used.
- **Steam appreviews API with per-review timestamps**: would give daily review history, but needs cursor paging (~100 reviews/request), which is millions of requests for the top 1,000. The monthly histogram endpoint was used instead.
- **SteamCharts chart-data.json**: monthly points plus hourly for the last ~30 days only; the HTML monthly table was used for consistency.

## Known gaps
- SteamCharts returned HTTP 500 for some appids (not tracked there). They're listed as empty files and counted in the README.
- SteamCharts history starts July 2012. Games released earlier have no launch month and are excluded from launch analyses.
- There is **no price history for 2020-08 → 2026-10**. The discount event study therefore uses the 2019-20 Mendeley panel (2,000 then-popular apps, not today's top 1,000).
- Review histograms are English-only.
