-- Analysis-layer views. Read-only over Code Builder's DB (attached as sp).
-- Mirrors dim_game / fct_daily_players logic because the marts are not materialized yet.
create or replace view a_players as
select appid, cast(snapshot_ts at time zone 'UTC' as date) as d, snapshot_ts, player_count
from sp.raw.player_counts where ok and player_count is not null;

create or replace view a_owners as
select * exclude rn from (
  select *, row_number() over (partition by appid order by fetched_at desc) rn from sp.raw.steamspy_owners) where rn=1;

create or replace view a_store as
select appid,
  payload->>'$.type' app_type,
  cast(payload->>'$.is_free' as boolean) is_free,
  try_strptime(payload->>'$.release_date.date', ['%d %b, %Y','%b %d, %Y','%b %Y'])::date release_date,
  payload->>'$.genres[0].description' primary_genre,
  json_extract_string(payload, '$.genres[*].description') genres
from (select *, row_number() over (partition by appid order by fetched_at desc) rn
      from sp.raw.appdetails where success) where rn=1;

create or replace view a_game as
select o.appid, o.name, o.positive, o.negative,
  case when o.positive+o.negative>0 then o.positive/(o.positive+o.negative) end pos_share,
  o.price_cents/100.0 price_usd, o.initialprice_cents/100.0 list_price_usd, o.discount_pct,
  o.owners_estimate_range, o.ccu_yesterday_peak,
  (o.price_cents=0 and coalesce(o.initialprice_cents,0)=0) as f2p_steamspy,
  s.is_free, s.release_date, s.primary_genre, s.genres, s.app_type,
  p.player_count, p.d snapshot_date
from a_owners o left join a_store s using(appid) left join a_players p using(appid);

create or replace view a_store_cats as
select appid, json_extract_string(payload, '$.categories[*].description') categories
from (select *, row_number() over (partition by appid order by fetched_at desc) rn from sp.raw.appdetails where success) where rn=1;
