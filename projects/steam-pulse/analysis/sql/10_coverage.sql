select
 (select count(*) from a_game) games,
 (select count(*) from a_game where player_count is not null) games_with_players,
 (select count(*) from a_game where release_date is not null) games_with_store_details,
 (select count(distinct snapshot_ts) from a_players) n_snapshots,
 (select min(snapshot_ts)::varchar from a_players) first_snapshot,
 (select max(snapshot_ts)::varchar from a_players) last_snapshot,
 (select count(distinct d) from a_players) n_days,
 (select min(release_date)::varchar from a_game) min_release,
 (select max(release_date)::varchar from a_game) max_release,
 (select count(*) from a_game where release_date >= (select max(d) from a_players) - 30) released_last_30d;
