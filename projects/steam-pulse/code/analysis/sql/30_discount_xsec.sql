-- Cross-sectional only (one snapshot): on-sale vs not, within paid games. NOT an elasticity estimate.
select case when discount_pct>0 then 'on_sale' else 'full_price' end segment, count(*) n,
  median(player_count) med_ccu, median(player_count/nullif(positive+negative,0)) med_ccu_per_review
from a_game where not f2p_steamspy and player_count is not null group by 1 order by 1;
