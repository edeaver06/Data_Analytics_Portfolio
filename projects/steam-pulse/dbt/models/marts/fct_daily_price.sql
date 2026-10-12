{{ config(materialized='incremental', unique_key=['appid', 'price_date_utc'], incremental_strategy='delete+insert') }}
-- Grain: one row per game per UTC day on which store appdetails was fetched (last fetch that day).
-- Appdetails refresh is budgeted, so days are sparse per game; use snap_game_price for continuous validity ranges.
with a as (
    select appid, fetched_at, cast(fetched_at at time zone 'UTC' as date) as price_date_utc,
           cast(payload->>'$.price_overview.final' as integer) / 100.0   as price_usd,
           cast(payload->>'$.price_overview.initial' as integer) / 100.0 as initial_price_usd,
           cast(payload->>'$.price_overview.discount_percent' as integer) as discount_pct,
           cast(payload->>'$.is_free' as boolean) as is_free
    from {{ source('raw', 'appdetails') }} where success
)
select appid, price_date_utc, fetched_at, price_usd, initial_price_usd, discount_pct, is_free
from a
{% if is_incremental() %} where price_date_utc >= (select coalesce(max(price_date_utc), date '1900-01-01') from {{ this }}) {% endif %}
qualify row_number() over (partition by appid, price_date_utc order by fetched_at desc) = 1
