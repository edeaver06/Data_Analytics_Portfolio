-- Inputs registered by Python: raw_polls, raw_mit, raw_markets, horizons(days_before INT).
-- Election day 2024-11-05. All probabilities are P(Republican candidate wins state); this is a coding convention only.
CREATE OR REPLACE TABLE outcomes AS
WITH v AS (
  SELECT state_po, party_simplified AS party, sum(candidatevotes) AS votes
  FROM raw_mit WHERE year = 2024 AND party_simplified IN ('DEMOCRAT','REPUBLICAN')
  GROUP BY ALL
)
SELECT state_po,
  max(votes) FILTER (WHERE party='REPUBLICAN') AS rep_votes,
  max(votes) FILTER (WHERE party='DEMOCRAT')   AS dem_votes,
  CASE WHEN rep_votes > dem_votes THEN 1 ELSE 0 END AS rep_won,
  100.0 * (rep_votes - dem_votes) / (rep_votes + dem_votes) AS actual_margin_2p
FROM v GROUP BY state_po;

CREATE OR REPLACE TABLE market_at_horizon AS
WITH px AS (
  SELECT source, state_po, to_timestamp(ts)::DATE AS d, p_rep FROM raw_markets
),
ranked AS (
  SELECT h.days_before, px.*,
    row_number() OVER (PARTITION BY h.days_before, source, state_po ORDER BY d DESC) AS rn
  FROM horizons h JOIN px ON px.d <= DATE '2024-11-05' - h.days_before::INT
                         AND px.d >  DATE '2024-11-05' - h.days_before::INT - 3   -- price must be <=3 days stale
)
SELECT days_before, source, state_po, d AS price_date, p_rep FROM ranked WHERE rn = 1;

CREATE OR REPLACE TABLE poll_avg AS
WITH pq AS (                        -- one row per poll question, Harris vs Trump two-way share
  SELECT question_id, pollster, state, strptime(end_date, '%m/%d/%y')::DATE AS end_d,
    max(pct) FILTER (WHERE answer='Trump')  AS trump,
    max(pct) FILTER (WHERE answer='Harris') AS harris
  FROM raw_polls
  WHERE state IS NOT NULL AND coalesce(hypothetical, false) = false AND stage = 'general'
  GROUP BY ALL
),
two AS (
  SELECT *, 100.0 * (trump - harris) / (trump + harris) AS margin_2p FROM pq
  WHERE trump IS NOT NULL AND harris IS NOT NULL
),
win AS (                            -- polls ending in the 21 days up to the horizon date
  SELECT h.days_before, t.*,
    dense_rank() OVER (PARTITION BY h.days_before, t.state, t.pollster ORDER BY end_d DESC) AS recency
  FROM horizons h JOIN two t ON t.end_d <= DATE '2024-11-05' - h.days_before::INT
                            AND t.end_d >  DATE '2024-11-05' - h.days_before::INT - 21
),
per_pollster AS (                   -- each pollster's latest poll(s) count once
  SELECT days_before, state, pollster, avg(margin_2p) AS m FROM win WHERE recency = 1 GROUP BY ALL
)
SELECT days_before, state, count(*) AS n_pollsters, avg(m) AS poll_margin_2p
FROM per_pollster GROUP BY ALL;
