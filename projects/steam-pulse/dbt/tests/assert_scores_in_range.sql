select * from {{ ref('mart_game_scores') }}
where composite_score not between 0 and 1 or review_bayes not between 0 and 1
   or (excluded and composite_score is not null) or (not excluded and composite_score is null)
