-- Latest SteamSpy user tags per game (tag -> vote count). SteamSpy data is third-party and ESTIMATED.
with ranked as (
    select *, row_number() over (partition by appid order by fetched_at desc) as rn
    from {{ source('raw', 'steamspy_tags') }}
    where ok
)
select
    appid,
    fetched_at,
    owners_estimate_range,
    list_sort(json_keys(tags)) as tags,
    len(json_keys(tags))       as n_tags,
    tags                       as tag_votes,
    cast(payload->>'$.average_forever' as integer) as avg_playtime_forever_min,   -- SteamSpy ESTIMATE
    cast(payload->>'$.median_forever'  as integer) as median_playtime_forever_min, -- SteamSpy ESTIMATE
    payload->>'$.languages'                        as steamspy_languages,
    payload->>'$.genre'                            as steamspy_genre_text
from ranked where rn = 1
