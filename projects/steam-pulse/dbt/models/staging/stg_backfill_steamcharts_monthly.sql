-- Grain: (appid, month). SteamCharts monthly table; month = 1st of month.
select appid, month, avg_players, peak_players, 'steamcharts' as source, 'Data: SteamCharts.com (terms unpublished)' as attribution, fetched_at
from {{ source('raw', 'backfill_steamcharts_monthly') }}
