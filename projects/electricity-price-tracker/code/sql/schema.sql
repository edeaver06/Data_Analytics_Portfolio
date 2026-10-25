-- Tables in data/electricity.db. Grain of retail_sales_monthly: one row per state + month + sector.
DROP TABLE IF EXISTS retail_sales_monthly;
CREATE TABLE retail_sales_monthly (
    state                   TEXT NOT NULL,   -- two-letter code, 50 states + DC
    state_name              TEXT NOT NULL,
    sector                  TEXT NOT NULL,   -- RES residential, COM commercial, ALL all sectors
    sector_name             TEXT NOT NULL,
    month                   TEXT NOT NULL,   -- first day of month, YYYY-MM-DD
    price_cents_per_kwh     REAL,            -- average retail price
    sales_million_kwh       REAL,            -- electricity sold
    revenue_million_usd     REAL,            -- utility revenue
    customers               INTEGER,         -- NULL before 2008 (not collected) or when withheld
    customers_not_collected INTEGER NOT NULL,
    any_value_missing       INTEGER NOT NULL,
    PRIMARY KEY (state, month, sector)
);

DROP TABLE IF EXISTS state_region;
CREATE TABLE state_region (
    state          TEXT PRIMARY KEY,
    primary_region TEXT NOT NULL,   -- dominant ISO/RTO or regional grouping
    region_type    TEXT NOT NULL,   -- ISO/RTO, non-RTO, isolated
    other_regions  TEXT,            -- ;-separated, for states split across regions
    multi_region   INTEGER NOT NULL,
    note           TEXT
);

-- Convenience view: residential prices with the region tag joined on (1 row per state-month; no fan-out).
DROP VIEW IF EXISTS v_residential_price;
CREATE VIEW v_residential_price AS
SELECT s.state, s.state_name, r.primary_region, r.multi_region, s.month,
       s.price_cents_per_kwh, s.sales_million_kwh, s.customers
FROM retail_sales_monthly AS s
JOIN state_region AS r ON r.state = s.state
WHERE s.sector = 'RES';
