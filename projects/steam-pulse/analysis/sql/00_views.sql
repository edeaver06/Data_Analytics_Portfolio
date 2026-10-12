-- Analysis-layer views over Code Builder's marts (DB attached read-only as sp). No raw.* access.
create or replace view a_players as
select appid, snapshot_date_utc d, snapshot_ts, player_count from steam_pulse.staging.stg_player_counts;

create or replace view a_daily as select * from steam_pulse.marts.fct_daily_players;

create or replace view a_owners as
select appid, game_name as "name", developer, publisher, owners_estimate_range from steam_pulse.marts.dim_game;

create or replace view a_store as
select appid, app_type, is_free, release_date, primary_genre, genres_any genres from steam_pulse.marts.dim_game where has_store_details;

create or replace view a_store_cats as
select appid, categories from steam_pulse.marts.dim_game where has_store_details;

create or replace view a_game as
select d.appid, d.game_name as "name", s.positive, s.negative,
  case when s.positive+s.negative>0 then s.positive/(s.positive+s.negative) end pos_share,
  d.price_usd, d.store_list_price_usd list_price_usd, coalesce(pr.store_discount_pct, d.store_discount_pct) discount_pct,
  d.owners_estimate_range,
  (coalesce(d.is_free, d.price_usd = 0)) as f2p_steamspy,
  d.is_free, d.release_date, d.primary_genre, d.genres_any genres, d.app_type, d.deck_status,
  d.has_online_coop, d.has_local_coop, d.has_split_screen, d.full_controller_support, d.has_remote_play_together,
  p.last_players player_count, p.snapshot_date_utc snapshot_date
from steam_pulse.marts.dim_game d
left join steam_pulse.staging.stg_steamspy_owners s using(appid)
left join (select * from steam_pulse.snapshots.snap_game_price where dbt_valid_to is null) pr using(appid)
left join (select * from steam_pulse.marts.fct_daily_players qualify row_number() over (partition by appid order by snapshot_date_utc desc)=1) p using(appid);
