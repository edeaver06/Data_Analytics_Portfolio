-- Latest SteamSpy record per game. owners_* are SteamSpy ESTIMATES (bucketed ranges).
with ranked as (
    select *,
           row_number() over (partition by appid order by fetched_at desc) as rn
    from {{ source('raw', 'steamspy_owners') }}
)
select
    appid, name, developer, publisher, fetched_at,
    owners_estimate_range,
    cast(replace(split_part(owners_estimate_range, ' .. ', 1), ',', '') as bigint) as owners_estimate_low,
    cast(replace(split_part(owners_estimate_range, ' .. ', 2), ',', '') as bigint) as owners_estimate_high,
    positive, negative,
    case when positive + negative > 0 then positive / (positive + negative) end as positive_review_share,
    price_cents / 100.0 as price_usd
from ranked where rn = 1
