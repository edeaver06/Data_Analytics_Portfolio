-- Players vs years since release, single snapshot (survivorship-biased proxy, not a decay curve).
select floor(date_diff('day', release_date, snapshot_date)/365.25)::int bucket_years, count(*) n,
  median(player_count) med_ccu
from a_game where release_date is not null and player_count is not null group by 1 order by 1;
