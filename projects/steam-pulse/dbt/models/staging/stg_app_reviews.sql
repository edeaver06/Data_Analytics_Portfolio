-- Store review summary counts (all languages, all purchase types). One row per successful fetch.
select
    appid,
    fetched_at,
    cast(fetched_at at time zone 'UTC' as date) as fetched_date_utc,
    review_score, review_score_desc,
    total_positive, total_negative, total_reviews,
    case when total_reviews > 0 then total_positive / total_reviews end as positive_share
from {{ source('raw', 'app_reviews') }}
where ok
