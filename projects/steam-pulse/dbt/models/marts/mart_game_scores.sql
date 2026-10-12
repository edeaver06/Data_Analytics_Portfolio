-- Grain: one row per game in dim_game (current state). Rebuilt every snapshot.
-- Composite = port of analysis/src/best_score.py (Data Analyst's validated formula); parity enforced by tests/test_score_parity.py.
--   review_bayes    = (pos + 1000*mu) / (pos + neg + 1000), mu = global pos/(pos+neg) over the scored set (SteamSpy counts)
--   player_strength = ln(1 + latest-day last_players)
--   value_per_dollar= review_bayes * ln(1 + players) / max(price_usd, $1)   (free games floored at $1)
--   composite_score = (0.45*pct(review_bayes) + 0.35*pct(player_strength) + 0.20*pct(value_per_dollar)) / 1.0
--   pct() = average-tie percentile rank in (0,1] among SCORED games (pandas rank(pct=True)).
--   retention / momentum: weight 0 until history exists; columns kept for information.
-- Scored set: players not null, pos+neg > 0, and NOT is_software.
{% set w_review, w_players, w_value, prior_n = 0.45, 0.35, 0.20, 1000 %}
with g as (select * from {{ ref('dim_game') }}),
ss as (select appid, positive, negative from {{ ref('stg_steamspy_owners') }}),
latest as (
    select appid, last_players as player_count, snapshot_date_utc
    from {{ ref('fct_daily_players') }}
    qualify row_number() over (partition by appid order by snapshot_date_utc desc) = 1
),
days as (select max(snapshot_date_utc) as d_max from {{ ref('fct_daily_players') }}),
hist as (
    select f.appid,
           count(distinct f.snapshot_date_utc) as days_of_history,
           avg(f.avg_players_sampled) filter (where f.snapshot_date_utc >  d.d_max - 7)  as avg_players_7d,
           avg(f.avg_players_sampled) filter (where f.snapshot_date_utc <= d.d_max - 7 and f.snapshot_date_utc > d.d_max - 14) as avg_players_prev_7d,
           avg(f.avg_players_sampled) filter (where f.snapshot_date_utc <= d.d_max - 21 and f.snapshot_date_utc > d.d_max - 28) as avg_players_4w_ago
    from {{ ref('fct_daily_players') }} f cross join days d group by 1
),
flagged as (
    select g.appid, g.game_name, g.app_type, g.genres_any, g.genres_source, g.tags, g.is_free, g.price_usd,
           ss.positive, ss.negative, l.player_count, l.snapshot_date_utc as players_date_utc,
           (x.appid is not null)
           or (len(list_intersect(coalesce(g.genres_any, []), ['Utilities','Software','Design & Illustration','Animation & Modeling',
                 'Audio Production','Video Production','Photo Editing','Web Publishing','Game Development','Education'])) > 0
               and len(list_intersect(coalesce(g.genres_any, []), ['Action','Adventure','RPG','Strategy','Simulation','Sports','Racing'])) = 0)
                                                                    as is_software,
           case when x.appid is not null then 'curated_list'
                when g.genres_any is not null then 'genre_rule' end as software_rule,
           h.days_of_history, h.avg_players_7d,
           case when h.days_of_history >= 28 and h.avg_players_4w_ago > 0 then h.avg_players_7d / h.avg_players_4w_ago end as retention_4w_ratio,
           case when h.days_of_history >= 14 and h.avg_players_prev_7d > 0 then h.avg_players_7d / h.avg_players_prev_7d - 1 end as momentum_wow,
           case when not coalesce(g.is_free, false) and g.price_usd > 0 and g.median_playtime_forever_min > 0
                then (g.median_playtime_forever_min / 60.0) / g.price_usd end as hours_per_dollar   -- informational, SteamSpy estimate
    from g
    left join ss using (appid)
    left join latest l using (appid)
    left join hist h using (appid)
    left join {{ ref('software_exclusions') }} x using (appid)
),
f2 as (
    select *, case when is_software then 'software'
                   when player_count is null then 'no_player_count'
                   when coalesce(positive, 0) + coalesce(negative, 0) = 0 then 'no_reviews' end as excluded_reason
    from flagged
),
scored as (select * from f2 where excluded_reason is null),
mu as (select sum(positive)::double / sum(positive + negative) as mu from scored),
comp as (
    select s.*,
           (s.positive + {{ prior_n }} * mu.mu) / (s.positive + s.negative + {{ prior_n }}) as review_bayes,
           ln(1 + s.player_count) as player_strength
    from scored s cross join mu
),
comp2 as (select *, review_bayes * player_strength / greatest(coalesce(price_usd, 0), 1.0) as value_per_dollar from comp),
ranked as (
    select appid, review_bayes, player_strength, value_per_dollar,
           ((rank() over (order by review_bayes) + (count(*) over (partition by review_bayes) - 1) / 2.0) / count(*) over ())     as pct_review_bayes,
           ((rank() over (order by player_strength) + (count(*) over (partition by player_strength) - 1) / 2.0) / count(*) over ())  as pct_player_strength,
           ((rank() over (order by value_per_dollar) + (count(*) over (partition by value_per_dollar) - 1) / 2.0) / count(*) over ()) as pct_value_per_dollar
    from comp2
)
select f2.*,
       r.review_bayes, r.player_strength, r.value_per_dollar,
       r.pct_review_bayes, r.pct_player_strength, r.pct_value_per_dollar,
       ({{ w_review }} * r.pct_review_bayes + {{ w_players }} * r.pct_player_strength + {{ w_value }} * r.pct_value_per_dollar)
         / ({{ w_review }} + {{ w_players }} + {{ w_value }})              as composite_score,
       rank() over (order by composite_score desc nulls last)             as composite_rank,
       excluded_reason is not null                                        as excluded,
       false                                                              as composite_has_history  -- retention/momentum weight 0 for now
from f2 left join ranked r using (appid)
