-- Grain: one row per game (current state). Rebuilt every snapshot.
-- Components are percentile ranks in [0,1] across tracked games; NULL when inputs are missing or history is too short.
{% set bayes_c_quantile = 0.5 %}
with g as (select * from {{ ref('dim_game') }}),
prior as (
    -- prior mean = review-count-weighted global positive share; prior strength C = median review count
    select sum(total_positive)::double / nullif(sum(total_reviews), 0) as m,
           quantile_cont(total_reviews, {{ bayes_c_quantile }})        as c
    from g where total_reviews > 0
),
days as (select max(snapshot_date_utc) as d_max from {{ ref('fct_daily_players') }}),
p as (
    select f.appid,
           count(distinct f.snapshot_date_utc) as days_of_history,
           avg(f.avg_players_sampled) filter (where f.snapshot_date_utc >  d.d_max - 7)  as avg_players_7d,
           avg(f.avg_players_sampled) filter (where f.snapshot_date_utc <= d.d_max - 7
                                                and f.snapshot_date_utc >  d.d_max - 14) as avg_players_prev_7d,
           avg(f.avg_players_sampled) filter (where f.snapshot_date_utc <= d.d_max - 21
                                                and f.snapshot_date_utc >  d.d_max - 28) as avg_players_4w_ago,
           min(f.snapshot_date_utc) as first_seen, max(f.snapshot_date_utc) as last_seen
    from {{ ref('fct_daily_players') }} f cross join days d
    group by 1
),
base as (
    select g.appid, g.game_name, g.is_free, g.price_usd, g.total_reviews, g.store_positive_share,
           (prior.c * prior.m + coalesce(g.total_positive_reviews, 0)) / (prior.c + coalesce(g.total_reviews, 0)) as bayes_review_score,
           p.days_of_history, p.avg_players_7d,
           case when p.days_of_history >= 28 and p.avg_players_4w_ago > 0
                then p.avg_players_7d / p.avg_players_4w_ago end                    as retention_4w_ratio,
           case when p.days_of_history >= 14 and p.avg_players_prev_7d > 0
                then p.avg_players_7d / p.avg_players_prev_7d - 1 end               as momentum_wow,
           case when not coalesce(g.is_free, false) and g.price_usd > 0 and g.median_playtime_forever_min > 0
                then (g.median_playtime_forever_min / 60.0) / g.price_usd end      as hours_per_dollar
    from g cross join prior left join p using (appid)
),
ranked as (
    select *,
        case when bayes_review_score is not null then percent_rank() over (order by bayes_review_score) end as pct_quality,
        case when avg_players_7d is not null then percent_rank() over (order by ln(1 + avg_players_7d)) end as pct_player_strength,
        case when retention_4w_ratio is not null then percent_rank() over (order by retention_4w_ratio) end as pct_retention,
        case when momentum_wow is not null then percent_rank() over (order by momentum_wow) end as pct_momentum,
        case when hours_per_dollar is not null then percent_rank() over (order by hours_per_dollar) end as pct_value
    from base
)
select *,
    -- Composite: weighted mean of AVAILABLE components, weights renormalised over non-null ones.
    -- quality .35, player strength .25, retention .15, momentum .10, value .15
    (  coalesce(.35*pct_quality,0) + coalesce(.25*pct_player_strength,0) + coalesce(.15*pct_retention,0)
     + coalesce(.10*pct_momentum,0) + coalesce(.15*pct_value,0))
    / nullif(  (pct_quality is not null)::int*.35 + (pct_player_strength is not null)::int*.25
             + (pct_retention is not null)::int*.15 + (pct_momentum is not null)::int*.10
             + (pct_value is not null)::int*.15, 0)                                   as composite_score,
    (pct_retention is not null) and (pct_momentum is not null)                         as composite_has_history
from ranked
