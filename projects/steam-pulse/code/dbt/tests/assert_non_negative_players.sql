select * from {{ ref('fct_daily_players') }}
where min_players_sampled < 0 or peak_players_sampled < avg_players_sampled - 1e-9
