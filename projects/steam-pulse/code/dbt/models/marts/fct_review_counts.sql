{{ config(materialized='incremental', unique_key=['appid', 'fetched_date_utc'],
          incremental_strategy='delete+insert') }}
-- Daily review-count series per game (last fetch of the day). Diff gives new reviews per day.
with d as (
    select * from {{ ref('stg_app_reviews') }}
    {% if is_incremental() %}
    where fetched_date_utc >= (select coalesce(max(fetched_date_utc), date '1900-01-01') from {{ this }})
    {% endif %}
    qualify row_number() over (partition by appid, fetched_date_utc order by fetched_at desc) = 1
)
select appid, fetched_date_utc, fetched_at, review_score_desc, total_positive, total_negative, total_reviews, positive_share
from d
