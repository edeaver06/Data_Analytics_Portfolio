{{ config(materialized='incremental', unique_key=['appid', 'snapshot_date_utc'],
          incremental_strategy='delete+insert') }}
-- One row per game per UTC day: aggregates however many snapshots were taken that day.
with daily as (
    select
        appid,
        snapshot_date_utc,
        count(*)            as n_snapshots,
        max(player_count)   as peak_players_sampled,
        avg(player_count)   as avg_players_sampled,
        min(player_count)   as min_players_sampled,
        arg_max(player_count, snapshot_ts) as last_players,
        max(snapshot_ts)    as last_snapshot_ts
    from {{ ref('stg_player_counts') }}
    {% if is_incremental() %}
    -- reprocess whole days touched since the last run so late snapshots are included
    where snapshot_date_utc >= (select coalesce(max(snapshot_date_utc), date '1900-01-01') from {{ this }})
    {% endif %}
    group by 1, 2
)
select
    *,
    peak_players_sampled - lag(peak_players_sampled) over (partition by appid order by snapshot_date_utc) as peak_change_vs_prev_day
from daily
