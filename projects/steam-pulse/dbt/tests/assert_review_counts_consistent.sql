-- positive + negative must equal total, all non-negative
select * from {{ ref('stg_app_reviews') }}
where total_positive + total_negative <> total_reviews or total_positive < 0 or total_negative < 0
