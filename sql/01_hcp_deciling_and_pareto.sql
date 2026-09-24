-- ============================================================================
-- PulseRx Commercial SFE Engine: SQL Analytical Layer
-- Dialect: PostgreSQL / DuckDB (tests/test_pulserx.py runs it on DuckDB against the CSVs)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. HCP Volume Deciling & Cumulative 80/20 Lorenz Concentration
-- Computes true market potential deciles (1-10) and cumulative volume share.
-- ----------------------------------------------------------------------------
WITH hcp_annual_volume AS (
    SELECT 
        h.hcp_npi,
        h.hcp_name,
        h.specialty,
        h.practice_setting,
        h.territory_id,
        SUM(r.market_trx) AS annual_market_trx,
        SUM(r.pulserx_trx) AS annual_pulserx_trx,
        SUM(r.pulserx_nrx) AS annual_pulserx_nrx,
        SUM(r.biozenith_trx) AS annual_biozenith_trx,
        SUM(r.pulserx_sales_usd) AS annual_pulserx_sales_usd,
        SUM(r.pulserx_trx)::DOUBLE / NULLIF(SUM(r.market_trx), 0) * 100 AS pulserx_market_share_pct
    FROM raw_hcp_universe h
    INNER JOIN raw_monthly_rx_claims r 
        ON h.hcp_npi = r.hcp_npi
    GROUP BY 
        h.hcp_npi, h.hcp_name, h.specialty, h.practice_setting, h.territory_id
),
deciled_hcps AS (
    SELECT 
        *,
        -- 10 Percentile Decile Buckets: Decile 10 = Top 10% Prescribing Volume
        NTILE(10) OVER (ORDER BY annual_market_trx ASC, hcp_npi ASC) AS market_decile,
        -- Cumulative Distribution to verify the 80/20 Pareto Concentration Rule
        CUME_DIST() OVER (ORDER BY annual_market_trx DESC) AS prescriber_percentile,
        SUM(annual_market_trx) OVER () AS national_market_trx,
        SUM(annual_market_trx) OVER (ORDER BY annual_market_trx DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_trx_running
    FROM hcp_annual_volume
)
SELECT 
    hcp_npi,
    hcp_name,
    specialty,
    territory_id,
    annual_market_trx,
    annual_pulserx_trx,
    pulserx_market_share_pct,
    market_decile,
    ROUND(prescriber_percentile * 100, 1) AS top_percentile_hcp,
    ROUND((cumulative_trx_running / national_market_trx) * 100, 2) AS cumulative_category_share_pct,
    -- Strategic Tier Assignment (Consulting Rules)
    CASE 
        WHEN market_decile >= 8 AND pulserx_market_share_pct >= 22.0 THEN 'Tier 1: Protect & Grow'
        WHEN market_decile >= 8 THEN 'Tier 2: High-Value Conversion'
        WHEN market_decile >= 5 THEN 'Tier 3: Moderate Opportunity'
        ELSE 'Tier 4: Omnichannel'
    END AS targeting_tier
FROM deciled_hcps
ORDER BY annual_market_trx DESC;
