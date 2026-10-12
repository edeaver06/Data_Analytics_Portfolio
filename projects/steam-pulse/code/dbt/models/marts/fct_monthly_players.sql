-- Grain: (appid, month, source). source in ('steamcharts', 'steam_pulse'). Not merged: definitions differ
-- (SteamCharts avg = mean of its hourly samples; steam_pulse = mean of our 6-hourly samples).
-- is_partial_month: current calendar month, or (steam_pulse) fewer days observed than the month has.
with sc as (
    select appid, month, avg_players, peak_players::double as peak_players, null::integer as days_observed, 'steamcharts' as source
    from {{ ref('stg_backfill_steamcharts_monthly') }}
),
sp as (
    select appid, date_trunc('month', snapshot_date_utc)::date as month,
           avg(avg_players_sampled) as avg_players, max(peak_players_sampled)::double as peak_players,
           count(*)::integer as days_observed, 'steam_pulse' as source
    from {{ ref('fct_daily_players') }} group by 1, 2
),
u as (select * from sc union all select * from sp)
select *,
    month = date_trunc('month', current_date)::date
      or (source = 'steam_pulse' and days_observed < extract(day from last_day(month))) as is_partial_month
from u
