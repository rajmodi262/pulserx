# PulseRx data dictionary (Tableau marts)

All values are **synthetic**. Marts are written by `alteryx/run_pipeline.py`.

## `tableau_hcp_targeting_mart.csv` -- one row per prescriber

| Field | Type | Meaning | How it is made |
|---|---|---|---|
| `HCP_NPI` | string | 10-digit prescriber ID (synthetic, not a real NPI) | generator |
| `HCP_Name`, `Specialty`, `Practice_Setting` | string | Prescriber attributes | generator |
| `Payer_Formulary_Access`, `Digital_Affinity`, `Is_KOL` | string | Access context | generator |
| `Territory_ID`, `District`, `Region`, `State` | string | Alignment hierarchy | generator |
| `Latitude`, `Longitude` | real | Jittered around the territory centre | generator |
| `Annual_Market_TRx` | integer | Category prescriptions, 12 months | Summarize (sum of monthly `Market_TRx`) |
| `Annual_PulseRx_TRx`, `Annual_PulseRx_NRx` | integer | Brand total / new prescriptions | Summarize |
| `Annual_BioZenith_TRx`, `Annual_TheraMax_TRx` | integer | Competitor prescriptions | Summarize |
| `Annual_PulseRx_Sales_USD`, `Annual_Market_Sales_USD` | real | TRx x list price ($1,850 PulseRx) | Summarize |
| `PulseRx_Market_Share_Pct` | real | Brand TRx / market TRx x 100 | Formula |
| `PulseRx_NRx_Ratio_Pct` | real | Brand NRx / brand TRx x 100 | Formula |
| `Market_Decile` | integer 1-10 | Equal-record deciles on `Annual_Market_TRx`, ties broken by NPI; 10 = top 10% | Tile |
| `Total_Calls_2025`, `In_Person_Calls`, `Virtual_Calls` | integer | CRM calls received (0 if none) | Summarize + left join |
| `Targeting_Tier` | string | `Tier 1: Protect & Grow` (decile 8-10, share >= 22%), `Tier 2: High-Value Conversion` (decile 8-10, share < 22%), `Tier 3: Moderate Opportunity` (decile 5-7), `Tier 4: Omnichannel` (decile 1-4) | Formula |
| `Recommended_Annual_Calls` | integer | Plan: Tier 1 = 18, Tier 2 = 14, Tier 3 = 6, Tier 4 = 1 | Formula |
| `Call_Deficit` | integer | Recommended - received (negative = over plan) | Formula |
| `Call_Attainment_Pct` | real | Received / recommended x 100 | Formula |
| `Field_Engagement_Status` | string | `Severely Under-Called` (> 3 short), `Slight Deficit`, `On Target` (within 2 over), `Over-Called` | Formula |
| `Projected_Incremental_TRx_Lift`, `Projected_Incremental_Sales_USD` | real | **Scenario only**: shortfall x assumed TRx per call (3.2 deciles 8-10, 0.8 otherwise) x $1,850 | Formula |

## `tableau_territory_alignment_mart.csv` -- one row per territory

| Field | Type | Meaning |
|---|---|---|
| `Territory_ID`, `Region`, `District`, `State` | string | Alignment keys |
| `Total_HCPs`, `Tier_1_2_HCPs` | integer | Prescribers, and those in Tiers 1-2 |
| `Total_Market_TRx`, `Total_PulseRx_TRx`, `Total_PulseRx_Sales_USD` | number | Territory totals |
| `Total_Calls_Delivered` | integer | CRM calls logged |
| `Total_Calls_Required` | integer | Calls the tier plan needs |
| `High_Decile_HCPs`, `High_Decile_Reached` | integer | Deciles 8-10, and those with at least one call |
| `High_Decile_Coverage_Pct` | real | Reached / high-decile x 100 |
| `Rep_Count`, `Target_Call_Capacity` | integer | Reps, and reps x 720 calls |
| `Annual_Sales_Quota_USD`, `Quota_Attainment_Pct` | number | $2.4M per rep; sales / quota x 100 |
| `Target_Decile_Coverage_Goal_Pct` | real | 0.85 goal carried from the roster |
| `Workload_Utilization_Pct` | real | Required / capacity x 100 |
| `Sizing_Consulting_Action` | string | `Overburdened (Carve Out Territory)` > 115%, `Underutilized (Expand Reach)` < 80%, else `Optimally Sized` |

## `tableau_monthly_rx_timeseries_mart.csv` -- one row per prescriber-month

Raw monthly Rx columns (`Month_Date`, `Market_TRx`, `PulseRx_TRx`, `PulseRx_NRx`, `BioZenith_TRx`,
`TheraMax_TRx`, `PulseRx_Sales_USD`, `Total_Market_Sales_USD`) joined to `Specialty`, `Territory_ID`,
`Region`, `Market_Decile`, `Targeting_Tier`.
