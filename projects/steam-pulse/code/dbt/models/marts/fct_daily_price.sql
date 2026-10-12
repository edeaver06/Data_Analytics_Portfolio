{{ config(materialized='incremental', unique_key=['appid', 'price_date_utc'], incremental_strategy='delete+insert') }}
-- Grain: one row per game per UTC day (last observation that day). Sources: every-run price_checks (all games)
-- plus full appdetails fetches. Games with no price_overview (free/unpriced) have NULL prices that day.
with obs as (
    select appid, fetched_at, final_cents / 100.0 as price_usd, initial_cents / 100.0 as initial_price_usd,
           discount_pct, null::boolean as is_free, 'price_check' as obs_source
    from {{ source('raw', 'price_checks') }} where ok
    union all
    select appid, fetched_at,
           cast(payload->>'$.price_overview.final' as integer) / 100.0,
           cast(payload->>'$.price_overview.initial' as integer) / 100.0,
           cast(payload->>'$.price_overview.discount_percent' as integer),
           cast(payload->>'$.is_free' as boolean), 'appdetails'
    from {{ source('raw', 'appdetails') }} where success
),
a as (select *, cast(fetched_at at time zone 'UTC' as date) as price_date_utc from obs)
select appid, price_date_utc, fetched_at, price_usd, initial_price_usd, discount_pct, is_free, obs_source
from a
{% if is_incremental() %} where price_date_utc >= (select coalesce(max(price_date_utc), date '1900-01-01') from {{ this }}) {% endif %}
qualify row_number() over (partition by appid, price_date_utc order by fetched_at desc) = 1
