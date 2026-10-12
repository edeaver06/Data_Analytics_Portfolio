{% snapshot snap_game_price %}
{{ config(target_schema='snapshots', unique_key='appid', strategy='check',
          check_cols=['store_price_usd', 'store_list_price_usd', 'store_discount_pct', 'is_free'],
          invalidate_hard_deletes=False) }}
-- SCD2 history of store price + sale discount (USD store, cc=us). A new row appears whenever any check col changes.
select appid, store_price_usd, store_list_price_usd, store_discount_pct, is_on_sale, is_free, fetched_at
from {{ ref('stg_appdetails') }}
{% endsnapshot %}
