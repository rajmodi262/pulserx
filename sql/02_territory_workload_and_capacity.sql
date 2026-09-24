-- ============================================================================
-- PulseRx Commercial SFE Engine: Territory Workload & Sizing Optimization
-- Philosophy: "Retarget, Don't Hire"
-- ============================================================================

WITH hcp_call_demand AS (
    SELECT 
        h.territory_id,
        COUNT(DISTINCT h.hcp_npi) AS total_hcps,
        COUNT(DISTINCT CASE WHEN h.market_decile >= 8 THEN h.hcp_npi END) AS high_decile_hcps,
        -- Recommended Detailing Call Load per Tier
        SUM(
            CASE 
                WHEN h.targeting_tier LIKE 'Tier 1%' THEN 18
                WHEN h.targeting_tier LIKE 'Tier 2%' THEN 14
                WHEN h.targeting_tier LIKE 'Tier 3%' THEN 6
                ELSE 1
            END
        ) AS total_recommended_calls,
        SUM(h.annual_pulserx_sales_usd) AS actual_brand_revenue_usd
    FROM tableau_hcp_targeting_mart h
    GROUP BY h.territory_id
),
rep_actual_activity AS (
    SELECT 
        c.territory_id,
        COUNT(c.call_id) AS total_actual_calls_delivered,
        COUNT(DISTINCT CASE WHEN h.market_decile >= 8 AND c.call_id IS NOT NULL THEN c.hcp_npi END) AS high_decile_hcps_reached
    FROM raw_rep_call_logs c
    LEFT JOIN tableau_hcp_targeting_mart h ON c.hcp_npi = h.hcp_npi
    GROUP BY c.territory_id
)
SELECT 
    d.territory_id,
    q.region,
    q.district,
    q.rep_count,
    q.target_call_capacity AS max_rep_call_capacity,
    d.total_recommended_calls AS workload_call_demand,
    r.total_actual_calls_delivered,
    -- Utilization Ratio
    ROUND((d.total_recommended_calls::DOUBLE / q.target_call_capacity) * 100, 1) AS workload_utilization_pct,
    -- Target Reach Discipline
    ROUND((r.high_decile_hcps_reached::DOUBLE / NULLIF(d.high_decile_hcps, 0)) * 100, 1) AS high_decile_coverage_pct,
    -- Commercial Sizing Consulting Action
    CASE 
        WHEN (d.total_recommended_calls::DOUBLE / q.target_call_capacity) > 1.15 
            THEN 'Overburdened (Retarget & Carve Out Sub-Territory)'
        WHEN (d.total_recommended_calls::DOUBLE / q.target_call_capacity) < 0.80 
            THEN 'Underutilized (Expand Prescriber Universe)'
        ELSE 'Optimally Sized (Maintain)'
    END AS consulting_sizing_recommendation
FROM hcp_call_demand d
JOIN raw_territory_quotas q ON d.territory_id = q.territory_id
LEFT JOIN rep_actual_activity r ON d.territory_id = r.territory_id
ORDER BY workload_utilization_pct DESC;
