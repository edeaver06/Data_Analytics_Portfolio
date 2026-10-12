-- Latest Steam Deck compatibility per game.
select appid, fetched_at, deck_category, deck_status
from {{ source('raw', 'deck_compat') }}
where ok
qualify row_number() over (partition by appid order by fetched_at desc) = 1
