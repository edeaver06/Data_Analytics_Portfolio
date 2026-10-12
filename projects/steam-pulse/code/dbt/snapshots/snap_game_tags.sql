{% snapshot snap_game_tags %}
{{ config(target_schema='snapshots', unique_key='appid', strategy='check',
          check_cols=['tags_key', 'genres_key']) }}
-- SCD2 history of SteamSpy user tags + store genres. Vote counts are ignored; only set membership changes.
select t.appid,
       array_to_string(t.tags, '|')    as tags_key,
       array_to_string(a.genres, '|')  as genres_key,
       t.tags, a.genres, t.fetched_at
from {{ ref('stg_steamspy_tags') }} t
left join {{ ref('stg_appdetails') }} a using (appid)
{% endsnapshot %}
