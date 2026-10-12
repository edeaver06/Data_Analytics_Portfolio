select case when f2p_steamspy then 'free' else 'paid' end segment, count(*) n,
  median(player_count) med_ccu, median(ccu_yesterday_peak) med_peak_yday,
  median(pos_share) med_pos_share, median(positive+negative) med_reviews
from a_game where player_count is not null group by 1 order by 1;
