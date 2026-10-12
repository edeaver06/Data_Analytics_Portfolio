-- Grain: (appid, date). Mendeley doi:10.17632/ycy3sy3vj2.1 (CC BY 4.0); hourly counts aggregated to daily.
select appid, date, avg_players, peak_players, n_hourly_obs,
       'mendeley_ycy3sy3vj2' as source, 'CC BY 4.0' as license, fetched_at
from {{ source('raw', 'backfill_mendeley_players_daily') }}
