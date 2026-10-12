select g genre, count(*) n, median(player_count) med_ccu, sum(player_count) total_ccu, median(pos_share) med_pos_share
from (select unnest(genres) g, player_count, pos_share from a_game where genres is not null and player_count is not null)
where g not in ('Utilities','Software','Design & Illustration','Animation & Modeling','Audio Production','Video Production','Photo Editing','Web Publishing','Game Development','Education')
group by 1 having count(*)>=5 order by total_ccu desc;
