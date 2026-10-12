-- SteamSpy estimate ranges must parse to low <= high
select * from {{ ref('stg_steamspy_owners') }}
where owners_estimate_low > owners_estimate_high or owners_estimate_low is null
