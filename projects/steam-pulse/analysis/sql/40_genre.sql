select g genre, count(*) n, median(player_count) med_ccu, sum(player_count) total_ccu, median(pos_share) med_pos_share
from (select unnest(genres) g, player_count, pos_share from a_game where genres is not null and player_count is not null)
group by 1 having count(*)>=5 order by total_ccu desc;
