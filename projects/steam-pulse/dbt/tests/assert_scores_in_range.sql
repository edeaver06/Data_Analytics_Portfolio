select * from {{ ref('mart_game_scores') }}
where composite_score not between 0 and 1 or bayes_review_score not between 0 and 1
