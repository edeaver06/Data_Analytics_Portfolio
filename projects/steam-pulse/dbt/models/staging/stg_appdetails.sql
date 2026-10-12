-- Latest successful store record per game, flattened.
with ranked as (
    select *, row_number() over (partition by appid order by fetched_at desc) as rn
    from {{ source('raw', 'appdetails') }}
    where success
)
select
    appid,
    fetched_at,
    payload->>'$.name'                                   as store_name,
    payload->>'$.type'                                   as app_type,
    cast(payload->>'$.is_free' as boolean)               as is_free,
    payload->>'$.release_date.date'                      as release_date_text,
    try_strptime(payload->>'$.release_date.date', ['%d %b, %Y', '%b %d, %Y', '%b %Y']) ::date as release_date,
    payload->>'$.price_overview.currency'                as price_currency,
    cast(payload->>'$.price_overview.final' as integer) / 100.0 as store_price_usd,
    cast(payload->>'$.price_overview.initial' as integer) / 100.0 as store_list_price_usd,
    cast(payload->>'$.price_overview.discount_percent' as integer) as store_discount_pct,
    coalesce(cast(payload->>'$.price_overview.discount_percent' as integer), 0) > 0 as is_on_sale,
    list_sort(cast(json_extract_string(payload, '$.genres[*].description') as varchar[]))     as genres,
    list_sort(cast(json_extract_string(payload, '$.categories[*].description') as varchar[])) as categories,
    cast(payload->>'$.metacritic.score' as integer)      as metacritic_score,
    payload->>'$.genres[0].description'                  as primary_genre,
    cast(json_extract_string(payload, '$.developers[*]') as varchar[]) as developers,
    cast(json_extract_string(payload, '$.publishers[*]') as varchar[]) as publishers,
    cast(payload->>'$.platforms.windows' as boolean)     as on_windows,
    cast(payload->>'$.platforms.mac' as boolean)         as on_mac,
    cast(payload->>'$.platforms.linux' as boolean)       as on_linux,
    regexp_replace(payload->>'$.supported_languages', '<[^>]*>|\*', '', 'g') as supported_languages,
    cast(payload->>'$.required_age' as varchar)          as required_age,
    cast(payload->>'$.recommendations.total' as bigint)  as store_recommendations,
    cast(payload->>'$.achievements.total' as integer)    as achievements_total,
    cast(payload->>'$.release_date.coming_soon' as boolean) as coming_soon,
    payload                                              as raw_payload
from ranked where rn = 1
