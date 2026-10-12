-- Grain: (appid, date). Mendeley doi:10.17632/ycy3sy3vj2.1 (CC BY 4.0), 2019-04-07..2020-08-12.
select appid, date, initial_price_usd, final_price_usd, discount_pct,
       'mendeley_ycy3sy3vj2' as source, 'CC BY 4.0' as license, fetched_at
from {{ source('raw', 'backfill_mendeley_price_daily') }}
