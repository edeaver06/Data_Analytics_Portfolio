-- One row per game in the tracked universe. owners_* columns are SteamSpy ESTIMATES (bucketed ranges).
with latest_reviews as (
    select * from {{ ref('stg_app_reviews') }}
    qualify row_number() over (partition by appid order by fetched_at desc) = 1
)
select
    s.appid,
    coalesce(a.store_name, s.name) as game_name,
    s.developer, s.publisher,
    a.app_type, a.is_free, a.release_date, a.primary_genre, a.genres, a.metacritic_score,
    coalesce(a.store_price_usd, s.price_usd) as price_usd,
    a.store_list_price_usd, a.store_discount_pct, a.is_on_sale,
    a.categories, t.tags, t.n_tags,
    a.developers, a.publishers, a.on_windows, a.on_mac, a.on_linux,
    coalesce(a.supported_languages, t.steamspy_languages) as languages,
    a.required_age, a.achievements_total, a.store_recommendations, a.coming_soon,
    list_contains(a.categories, 'Single-player')        as is_single_player,
    list_contains(a.categories, 'Online Co-op')         as has_online_coop,
    list_contains(a.categories, 'Shared/Split Screen Co-op') or list_contains(a.categories, 'Shared/Split Screen') as has_split_screen,
    (list_contains(a.categories, 'Shared/Split Screen Co-op') or list_contains(a.categories, 'LAN Co-op')) as has_local_coop,
    list_contains(a.categories, 'Online PvP') or list_contains(a.categories, 'PvP') as has_pvp,
    list_contains(a.categories, 'Remote Play Together') as has_remote_play_together,
    dk.deck_status, dk.deck_category,
    fs.first_seen_ts, cast(fs.first_seen_ts at time zone 'UTC' as date) as first_seen_date_utc,
    list_contains(a.categories, 'Full controller support')   as full_controller_support,
    list_contains(a.categories, 'Steam Workshop')       as has_workshop,
    list_contains(a.categories, 'Steam Achievements')   as has_achievements,
    t.median_playtime_forever_min, t.avg_playtime_forever_min,
    s.owners_estimate_range, s.owners_estimate_low, s.owners_estimate_high,
    r.review_score_desc, r.total_reviews, r.total_positive as total_positive_reviews, r.total_negative as total_negative_reviews, r.positive_share as store_positive_share,
    s.positive_review_share as steamspy_positive_share,
    a.appid is not null as has_store_details,
    t.appid is not null as has_tags,
    r.appid is not null as has_reviews
from {{ ref('stg_steamspy_owners') }} s
left join {{ ref('stg_appdetails') }} a using (appid)
left join {{ ref('stg_steamspy_tags') }} t using (appid)
left join latest_reviews r using (appid)
left join {{ ref('stg_deck_compat') }} dk using (appid)
left join (select appid, min(snapshot_ts) as first_seen_ts from {{ source('raw', 'player_counts') }} group by 1) fs using (appid)
