-- Grain: (appid, month). Steam review histogram, English reviews only.
-- Source is already one row per (appid, month); n_buckets/rollup_type describe how sub-month buckets were rolled up.
select appid, month, reviews_up, reviews_down, n_buckets, rollup_type,
       'english' as language, 'steam_histogram' as source, fetched_at
from {{ source('raw', 'backfill_reviews_monthly') }}
