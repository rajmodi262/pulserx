"""Build web_dashboard/data.js from the marts and analysis/headline_metrics.py.

Everything the dashboard shows, including the what-if simulator, is computed from this
payload -- no numbers are typed into index.html or app.js.
"""
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "analysis"), os.path.join(ROOT, "alteryx")]
import headline_metrics  # noqa: E402
import run_pipeline  # noqa: E402


def build():
    marts = os.path.join(ROOT, "output_marts")
    hcp = pd.read_csv(os.path.join(marts, "tableau_hcp_targeting_mart.csv"))
    terr = pd.read_csv(os.path.join(marts, "tableau_territory_alignment_mart.csv"))
    monthly = pd.read_csv(os.path.join(marts, "tableau_monthly_rx_timeseries_mart.csv"))
    metrics = headline_metrics.compute(marts, os.path.join(ROOT, "data"))

    trend = monthly.groupby("Month_Date").agg(
        PulseRx_TRx=("PulseRx_TRx", "sum"), BioZenith_TRx=("BioZenith_TRx", "sum"),
        TheraMax_TRx=("TheraMax_TRx", "sum"), Market_TRx=("Market_TRx", "sum")).reset_index()
    for b in ("PulseRx", "BioZenith", "TheraMax"):
        trend[f"{b}_Share"] = trend[f"{b}_TRx"] / trend["Market_TRx"] * 100

    dec = hcp.groupby("Market_Decile").agg(HCP_Count=("HCP_NPI", "count"), Market_TRx=("Annual_Market_TRx", "sum"),
                                           PulseRx_TRx=("Annual_PulseRx_TRx", "sum"),
                                           Calls=("Total_Calls_2025", "sum")).reset_index()
    dec = dec.sort_values("Market_Decile", ascending=False)
    dec["Cum_HCP_Pct"] = dec["HCP_Count"].cumsum() / dec["HCP_Count"].sum() * 100
    dec["Cum_TRx_Pct"] = dec["Market_TRx"].cumsum() / dec["Market_TRx"].sum() * 100

    tier = hcp["Targeting_Tier"].str[:6]
    # Simulator inputs: tier counts per territory, and for Tier 1/2 a histogram of calls received,
    # so the shortfall at any planned frequency f is sum(count_c * max(0, f - c)) -- exact, no sampling.
    tier_by_terr = hcp.assign(T=tier).groupby(["Territory_ID", "T"]).size().unstack(fill_value=0)
    call_hist = {t: {int(c): int(n) for c, n in hcp.loc[tier == t, "Total_Calls_2025"].value_counts().items()}
                 for t in ("Tier 1", "Tier 2")}

    shown = hcp[hcp["Market_Decile"] >= run_pipeline.TIER_DECILE_MIN].sort_values("Annual_Market_TRx", ascending=False)
    cols = ["HCP_NPI", "HCP_Name", "Specialty", "Practice_Setting", "Payer_Formulary_Access", "Is_KOL", "Territory_ID",
            "District", "Region", "State", "Annual_Market_TRx", "Annual_PulseRx_TRx", "PulseRx_Market_Share_Pct",
            "Market_Decile", "Targeting_Tier", "Total_Calls_2025", "Recommended_Annual_Calls", "Call_Deficit"]

    a = metrics["arithmetic"]
    payload = {
        "metrics": metrics,
        "kpis": {
            "brand_sales_usd": a["brand_sales_usd"],
            "brand_share_pct": round(hcp["Annual_PulseRx_TRx"].sum() / hcp["Annual_Market_TRx"].sum() * 100, 1),
            "high_value_reach_pct": round(100 - a["high_value_hcps_with_zero_calls_pct"], 1),
            "plan_utilization_pct": a["plan_utilization_pct"],
            "tier1_2_call_shortfall": a["tier1_2_call_shortfall"],
        },
        "monthly_trend": trend.to_dict(orient="records"),
        "decile_summary": dec.sort_values("Market_Decile").to_dict(orient="records"),
        "territories": terr.to_dict(orient="records"),
        "sim": {
            "calls_per_tier": run_pipeline.CALLS_PER_TIER,
            "tier_by_territory": {t: {k: int(v) for k, v in row.items()} for t, row in tier_by_terr.iterrows()},
            "reps_by_territory": dict(zip(terr["Territory_ID"], terr["Rep_Count"].astype(int))),
            "calls_per_rep": a["calls_per_rep_capacity"],
            "tier1_2_call_histogram": call_hist,
            "assumed_trx_per_extra_call": run_pipeline.ASSUMED_TRX_PER_EXTRA_CALL["high_decile"],
            "net_revenue_per_trx_usd": run_pipeline.NET_REVENUE_PER_TRX_USD,
            "overburdened_pct": run_pipeline.OVERBURDENED_PCT,
        },
        "sample_hcps": shown[cols].to_dict(orient="records"),
    }
    out = os.path.join(ROOT, "web_dashboard", "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("const DASHBOARD_DATA = " + json.dumps(payload) + ";\n")
    print(f"data.js: {len(shown)} high-value HCPs, {len(terr)} territories")


if __name__ == "__main__":
    build()
