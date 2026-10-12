-- Grain: one row per (appid, attribute_type, attribute). attribute_type in ('genre','category','tag').
-- Use for multi-filter: e.g. games having BOTH category 'Online Co-op' AND tag 'Roguelike'.
with g as (select appid, unnest(genres) as attribute from {{ ref('stg_appdetails') }}),
     c as (select appid, unnest(categories) as attribute from {{ ref('stg_appdetails') }}),
     t as (select appid, unnest(tags) as attribute, tag_votes from {{ ref('stg_steamspy_tags') }})
select distinct * from (
select appid, 'genre' as attribute_type, attribute, null::bigint as tag_votes from g
union all
select appid, 'category', attribute, null from c
union all
select appid, 'tag', attribute, cast(json_extract(tag_votes, '$."' || replace(attribute, '"', '\\"') || '"') as bigint) from t
) u
