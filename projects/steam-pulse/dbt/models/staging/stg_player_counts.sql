-- Successful player-count observations only; one row per snapshot x game.
select
    snapshot_id,
    snapshot_ts,
    cast(snapshot_ts at time zone 'UTC' as date) as snapshot_date_utc,
    appid,
    player_count
from {{ source('raw', 'player_counts') }}
where ok and player_count is not null
