"""Python version of the PulseRx targeting pipeline.

This is the implementation that actually produces output_marts/. It follows the same
steps as alteryx/PulseRx_ETL_Targeting.yxmd (Summarize -> Formula -> Tile -> Join ->
Formula -> Summarize -> Join -> Formula). The .yxmd has not yet been run in Alteryx
Designer; see alteryx/ALTERYX_WORKFLOW_GUIDE.md for what to check when it is.

Columns the Python version adds beyond the .yxmd: Call_Attainment_Pct,
Field_Engagement_Status, Projected_Incremental_TRx_Lift, Projected_Incremental_Sales_USD,
High_Decile_Coverage_Pct and the monthly time-series mart.
"""
import argparse
import os

import numpy as np
import pandas as pd

# Targeting rules. Kept identical to the Formula tools in the .yxmd and to sql/01.
TIER_DECILE_MIN = 8          # deciles 8-10 are "high value"
SHARE_THRESHOLD_PCT = 22.0   # brand share splitting "protect" from "convert"
CALLS_PER_TIER = {"Tier 1": 18, "Tier 2": 14, "Tier 3": 6, "Tier 4": 1}
OVERBURDENED_PCT, UNDERUTILIZED_PCT = 115, 80

# SCENARIO ASSUMPTIONS -- not measured. The synthetic data contains no call-response
# signal, so the value of an extra call is assumed. Every $ figure built on these is a
# scenario, and headline_metrics.py reports it with a 0.5x-1.5x range.
ASSUMED_TRX_PER_EXTRA_CALL = {"high_decile": 3.2, "other": 0.8}
NET_REVENUE_PER_TRX_USD = 1850


def assign_tier(decile, share):
    if decile >= TIER_DECILE_MIN and share >= SHARE_THRESHOLD_PCT:
        return "Tier 1: Protect & Grow"
    if decile >= TIER_DECILE_MIN:
        return "Tier 2: High-Value Conversion"
    if decile >= 5:
        return "Tier 3: Moderate Opportunity"
    return "Tier 4: Omnichannel"


def run(data_dir="data", output_dir="output_marts", quiet=False):
    say = (lambda *a: None) if quiet else print
    os.makedirs(output_dir, exist_ok=True)

    # Tools 1-4: inputs
    df_hcp = pd.read_csv(os.path.join(data_dir, "raw_hcp_universe.csv"), dtype={"HCP_NPI": str})
    df_rx = pd.read_csv(os.path.join(data_dir, "raw_monthly_rx_claims.csv"), dtype={"HCP_NPI": str})
    df_calls = pd.read_csv(os.path.join(data_dir, "raw_rep_call_logs.csv"), dtype={"HCP_NPI": str})
    df_quotas = pd.read_csv(os.path.join(data_dir, "raw_territory_quotas.csv"))
    say(f"Inputs: {len(df_hcp)} HCPs, {len(df_rx)} monthly Rx rows, {len(df_calls)} calls")
    df_hcp = df_hcp.drop(columns=["Volume_Factor"])  # generator-only field; not a real-world input

    # Tool 5: Summarize 12 months of Rx by HCP
    rx = df_rx.groupby("HCP_NPI").agg(
        Annual_Market_TRx=("Market_TRx", "sum"),
        Annual_PulseRx_TRx=("PulseRx_TRx", "sum"),
        Annual_PulseRx_NRx=("PulseRx_NRx", "sum"),
        Annual_BioZenith_TRx=("BioZenith_TRx", "sum"),
        Annual_TheraMax_TRx=("TheraMax_TRx", "sum"),
        Annual_PulseRx_Sales_USD=("PulseRx_Sales_USD", "sum"),
        Annual_Market_Sales_USD=("Total_Market_Sales_USD", "sum"),
    ).reset_index()

    # Tool 6: Formula -- share metrics
    rx["PulseRx_Market_Share_Pct"] = rx["Annual_PulseRx_TRx"] / rx["Annual_Market_TRx"].replace(0, 1) * 100
    rx["PulseRx_NRx_Ratio_Pct"] = rx["Annual_PulseRx_NRx"] / rx["Annual_PulseRx_TRx"].replace(0, 1) * 100

    # Tool 7: Tile -- equal-records deciles on market volume (10 = top 10%)
    rx = rx.sort_values(["Annual_Market_TRx", "HCP_NPI"]).reset_index(drop=True)
    rx["Market_Decile"] = pd.qcut(np.arange(len(rx)), 10, labels=range(1, 11)).astype(int)

    # Tool 8: Summarize calls by HCP
    calls = df_calls.groupby("HCP_NPI").agg(
        Total_Calls_2025=("Call_ID", "count"),
        In_Person_Calls=("Channel", lambda x: (x == "In-Person Detailing").sum()),
        Virtual_Calls=("Channel", lambda x: (x == "Virtual Video Detailing").sum()),
    ).reset_index()

    # Tools 9-10: Join HCP master + deciles + calls (HCPs with no calls get 0)
    hcp = df_hcp.merge(rx, on="HCP_NPI", how="left").merge(calls, on="HCP_NPI", how="left")
    for c in ["Total_Calls_2025", "In_Person_Calls", "Virtual_Calls"]:
        hcp[c] = hcp[c].fillna(0).astype(int)

    # Tool 11: Formula -- tiers, planned frequency, deficit
    hcp["Targeting_Tier"] = [assign_tier(d, s) for d, s in zip(hcp["Market_Decile"], hcp["PulseRx_Market_Share_Pct"])]
    hcp["Recommended_Annual_Calls"] = hcp["Targeting_Tier"].str[:6].map(CALLS_PER_TIER)
    hcp["Call_Deficit"] = hcp["Recommended_Annual_Calls"] - hcp["Total_Calls_2025"]
    hcp["Call_Attainment_Pct"] = hcp["Total_Calls_2025"] / hcp["Recommended_Annual_Calls"] * 100
    hcp["Field_Engagement_Status"] = np.select(
        [hcp["Call_Deficit"] > 3, hcp["Call_Deficit"] > 0, hcp["Call_Deficit"] >= -2],
        ["Severely Under-Called", "Slight Deficit", "On Target"], "Over-Called")
    per_call = np.where(hcp["Market_Decile"] >= TIER_DECILE_MIN,
                        ASSUMED_TRX_PER_EXTRA_CALL["high_decile"], ASSUMED_TRX_PER_EXTRA_CALL["other"])
    hcp["Projected_Incremental_TRx_Lift"] = hcp["Call_Deficit"].clip(lower=0) * per_call
    hcp["Projected_Incremental_Sales_USD"] = hcp["Projected_Incremental_TRx_Lift"] * NET_REVENUE_PER_TRX_USD

    # Tools 13-15: territory workload vs capacity
    hcp["_high"] = hcp["Market_Decile"] >= TIER_DECILE_MIN
    hcp["_high_reached"] = hcp["_high"] & (hcp["Total_Calls_2025"] > 0)
    terr = hcp.groupby("Territory_ID").agg(
        Total_HCPs=("HCP_NPI", "count"),
        Tier_1_2_HCPs=("Targeting_Tier", lambda x: x.str.startswith(("Tier 1", "Tier 2")).sum()),
        Total_Market_TRx=("Annual_Market_TRx", "sum"),
        Total_PulseRx_TRx=("Annual_PulseRx_TRx", "sum"),
        Total_PulseRx_Sales_USD=("Annual_PulseRx_Sales_USD", "sum"),
        Total_Calls_Delivered=("Total_Calls_2025", "sum"),
        Total_Calls_Required=("Recommended_Annual_Calls", "sum"),
        High_Decile_HCPs=("_high", "sum"),
        High_Decile_Reached=("_high_reached", "sum"),
    ).reset_index().merge(df_quotas, on="Territory_ID", how="left")
    hcp = hcp.drop(columns=["_high", "_high_reached"])
    terr["Workload_Utilization_Pct"] = terr["Total_Calls_Required"] / terr["Target_Call_Capacity"] * 100
    terr["Quota_Attainment_Pct"] = terr["Total_PulseRx_Sales_USD"] / terr["Annual_Sales_Quota_USD"] * 100
    terr["High_Decile_Coverage_Pct"] = terr["High_Decile_Reached"] / terr["High_Decile_HCPs"] * 100
    terr["Sizing_Consulting_Action"] = np.select(
        [terr["Workload_Utilization_Pct"] > OVERBURDENED_PCT, terr["Workload_Utilization_Pct"] < UNDERUTILIZED_PCT],
        ["Overburdened (Carve Out Territory)", "Underutilized (Expand Reach)"], "Optimally Sized")

    # Monthly time-series mart
    monthly = df_rx.merge(hcp[["HCP_NPI", "Specialty", "Territory_ID", "Region", "Market_Decile", "Targeting_Tier"]],
                          on="HCP_NPI", how="inner")

    hcp.to_csv(os.path.join(output_dir, "tableau_hcp_targeting_mart.csv"), index=False)
    terr.to_csv(os.path.join(output_dir, "tableau_territory_alignment_mart.csv"), index=False)
    monthly.to_csv(os.path.join(output_dir, "tableau_monthly_rx_timeseries_mart.csv"), index=False)
    say(f"Marts: {len(hcp)} HCPs, {len(terr)} territories, {len(monthly)} monthly rows -> {output_dir}/")
    return hcp, terr


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the PulseRx Tableau marts")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="output_marts")
    a = ap.parse_args()
    run(a.data, a.out)
