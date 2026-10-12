{% snapshot snap_game_price %}
{{ config(target_schema='snapshots', unique_key='appid', strategy='check',
          check_cols=['store_price_usd', 'store_list_price_usd', 'store_discount_pct', 'is_free']) }}
-- SCD2 history of store price + sale discount (USD, cc=us). Checked EVERY run against the latest observation
-- (price_checks cover all tracked games each run); a new row appears only when price/discount changes.
-- Column names kept stable for downstream (analysis/sql/00_views.sql).
select appid,
       price_usd          as store_price_usd,
       initial_price_usd  as store_list_price_usd,
       discount_pct       as store_discount_pct,
       coalesce(discount_pct, 0) > 0 as is_on_sale,
       is_free,
       fetched_at
from {{ ref('fct_daily_price') }}
qualify row_number() over (partition by appid order by price_date_utc desc) = 1
{% endsnapshot %}
