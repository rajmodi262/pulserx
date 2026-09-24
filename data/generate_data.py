"""Synthetic commercial data for PulseRx.

Everything this script writes is SYNTHETIC. The brands (PulseRx, BioZenith, TheraMax),
the prescribers, the reps and the calls are invented. The files are shaped like the
feeds a commercial analytics team works with -- prescriber master, monthly Rx audit,
CRM call log, territory roster -- so the pipeline can be exercised end to end.

THE STATUS-QUO CALL PATTERN IS A SCENARIO, NOT A FINDING
--------------------------------------------------------
Reps in this simulation build their call lists mostly on *access* (community clinics,
in-person-only doctors, habit) rather than on prescribing *volume*. How much volume
matters is one parameter, CALL_TARGETING_ALIGNMENT:

    0.0  call lists ignore volume entirely (pure access / habit)
    1.0  call lists are ranked purely on volume (what a decile plan would do)

The default, 0.25, plants a misallocation. The pipeline's job is to detect and size it,
and tests/test_pulserx.py checks that it does: the measured low-decile call share
falls as the alignment parameter rises. Nothing downstream reads this parameter.
"""
import argparse
import os
import random

import numpy as np
import pandas as pd

CALL_TARGETING_ALIGNMENT = 0.25   # 0 = access-driven call lists, 1 = volume-driven
CALL_LIST_SHARE = 0.60            # share of each territory's HCPs that reps call on at all
N_CALLS = 16_500                  # CRM calls logged in the year
CALLS_PER_REP_CAPACITY = 720      # annual call capacity per rep
MAX_CALLS_PER_HCP = 36            # no prescriber sees a rep more than ~3 times a month
MAX_VOLUME_FACTOR = 12.0
SEED = 42

TERRITORIES = [
    {"id": "TERR_NE_01", "region": "Northeast", "district": "Boston Metro", "state": "MA", "lat": 42.3601, "lon": -71.0589, "reps": 2},
    {"id": "TERR_NE_02", "region": "Northeast", "district": "NYC Metro", "state": "NY", "lat": 40.7128, "lon": -74.0060, "reps": 3},
    {"id": "TERR_NE_03", "region": "Northeast", "district": "Tri-State / NJ", "state": "NJ", "lat": 40.0583, "lon": -74.4057, "reps": 2},
    {"id": "TERR_MA_01", "region": "Mid-Atlantic", "district": "Philly Metro", "state": "PA", "lat": 39.9526, "lon": -75.1652, "reps": 2},
    {"id": "TERR_MA_02", "region": "Mid-Atlantic", "district": "Capital District", "state": "MD", "lat": 39.0458, "lon": -76.6413, "reps": 2},
    {"id": "TERR_SE_01", "region": "Southeast", "district": "Atlanta Metro", "state": "GA", "lat": 33.7490, "lon": -84.3880, "reps": 2},
    {"id": "TERR_SE_02", "region": "Southeast", "district": "Florida Central", "state": "FL", "lat": 28.5383, "lon": -81.3792, "reps": 2},
    {"id": "TERR_MW_01", "region": "Midwest", "district": "Chicago Metro", "state": "IL", "lat": 41.8781, "lon": -87.6298, "reps": 3},
    {"id": "TERR_MW_02", "region": "Midwest", "district": "Great Lakes", "state": "OH", "lat": 41.4993, "lon": -81.6944, "reps": 2},
    {"id": "TERR_TX_01", "region": "South Central", "district": "Houston Metro", "state": "TX", "lat": 29.7604, "lon": -95.3698, "reps": 2},
    {"id": "TERR_TX_02", "region": "South Central", "district": "Dallas Metro", "state": "TX", "lat": 32.7767, "lon": -96.7970, "reps": 2},
    {"id": "TERR_WC_01", "region": "West Coast", "district": "SoCal Metro", "state": "CA", "lat": 34.0522, "lon": -118.2437, "reps": 3},
    {"id": "TERR_WC_02", "region": "West Coast", "district": "NorCal Bay Area", "state": "CA", "lat": 37.7749, "lon": -122.4194, "reps": 2},
    {"id": "TERR_WC_03", "region": "West Coast", "district": "Pacific NW", "state": "WA", "lat": 47.6062, "lon": -122.3321, "reps": 2},
]

# How easy a doctor is for a rep to see. This drives the status-quo call list.
SETTING_ACCESS = {
    "Academic Comprehensive Cancer Center": 0.6,
    "Community Oncology Network": 1.3,
    "Integrated Delivery Network (IDN)": 0.9,
    "Private Oncology Clinic": 1.4,
}
AFFINITY_ACCESS = {"High Digital Receptivity": 0.8, "Moderate": 1.0, "Strictly In-Person Only": 1.3}


def generate(output_dir="data", alignment=CALL_TARGETING_ALIGNMENT, seed=SEED, quiet=False):
    np.random.seed(seed)
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)
    say = (lambda *a: None) if quiet else print

    # 1. HCP UNIVERSE (2,500 specialist prescribers)
    specialties = ["Medical Oncology", "Hematology-Oncology", "Surgical Oncology", "Gynecologic Oncology", "Immunology"]
    specialty_weights = [0.42, 0.28, 0.14, 0.08, 0.08]
    first_names = ["Robert", "Sarah", "Michael", "Emily", "David", "Jennifer", "James", "Jessica", "John", "Amanda", "Brian", "Rachel", "Andrew", "Lauren", "Daniel", "Megan", "William", "Stephanie", "Matthew", "Nicole", "Vikram", "Priya", "Arun", "Sunita", "Chen", "Wei", "Mei", "Carlos", "Elena", "Mateo", "Tariq", "Fatima", "Alex", "Zoe", "Kavita"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Patel", "Shah", "Gupta", "Deshmukh", "Zhang", "Wang", "Liu", "O'Connor", "Kelly", "Sullivan", "Cohen", "Goldberg", "Kowalski", "Novak", "Dubois", "Fontaine", "Santos", "Fernandez", "Rossi", "Mancini", "Al-Mansoor", "Kapoor", "Tanaka"]

    hcp_rows = []
    for i in range(1, 2501):
        terr = random.choice(TERRITORIES)
        hcp_rows.append({
            "HCP_NPI": 1000000000 + i * 97 + random.randint(0, 89),  # step > jitter, so NPIs are unique
            "HCP_Name": f"Dr. {random.choice(first_names)} {random.choice(last_names)}",
            "Specialty": np.random.choice(specialties, p=specialty_weights),
            "Practice_Setting": np.random.choice(list(SETTING_ACCESS), p=[0.24, 0.42, 0.22, 0.12]),
            "Payer_Formulary_Access": np.random.choice(
                ["Tier 1: Preferred Unrestricted", "Tier 2: Prior Authorization Required", "Tier 3: Step Therapy / Restricted"],
                p=[0.55, 0.35, 0.10]),
            "Digital_Affinity": np.random.choice(list(AFFINITY_ACCESS), p=[0.30, 0.50, 0.20]),
            "Is_KOL": "Yes" if random.random() < 0.075 else "No",
            "Territory_ID": terr["id"],
            "District": terr["district"],
            "Region": terr["region"],
            "State": terr["state"],
            "Latitude": round(terr["lat"] + np.random.normal(0, 0.18), 5),
            "Longitude": round(terr["lon"] + np.random.normal(0, 0.18), 5),
            # Prescribing potential: Pareto-distributed (volume concentrates in few HCPs), capped so
            # the largest prescriber writes a plausible ~7k TRx a year rather than an outlier tail
            "Volume_Factor": round(min(np.random.pareto(a=1.75) + 0.15, MAX_VOLUME_FACTOR), 4),
        })
    df_hcps = pd.DataFrame(hcp_rows)
    df_hcps.to_csv(os.path.join(output_dir, "raw_hcp_universe.csv"), index=False)
    say(f" -> [1/5] {len(df_hcps)} HCPs -> raw_hcp_universe.csv")

    # 2. MONTHLY Rx AUDIT (Jan-Dec 2025): PulseRx vs BioZenith vs TheraMax
    dates = pd.date_range(start="2025-01-01", end="2025-12-01", freq="MS")
    seasonality = {1: 0.96, 2: 0.94, 3: 1.02, 4: 1.03, 5: 1.05, 6: 1.01, 7: 0.92, 8: 0.98, 9: 1.06, 10: 1.08, 11: 1.10, 12: 0.93}
    rx_records = []
    for _, hcp in df_hcps.iterrows():
        base_volume = max(6, int(hcp["Volume_Factor"] * 48))
        archetype = np.random.choice([0, 1, 2], p=[0.45, 0.35, 0.20])  # 0 competitor loyalist, 1 balanced, 2 PulseRx champion
        for dt in dates:
            m = dt.month
            if archetype == 2:
                brand_share = 0.35 + m * 0.012 + np.random.normal(0, 0.02)
                comp1_share = 0.35 - m * 0.006
            elif archetype == 1:
                brand_share = 0.18 + m * 0.008 + np.random.normal(0, 0.02)
                comp1_share = 0.48 - m * 0.004
            else:
                brand_share = 0.08 + m * 0.004 + np.random.normal(0, 0.015)
                comp1_share = 0.62 - m * 0.003
            brand_share = max(0.04, min(0.68, brand_share))
            comp1_share = max(0.18, min(0.75, comp1_share))

            total_rx = max(2, int(round(np.random.poisson(base_volume) * seasonality[m])))
            pulserx_trx = int(round(total_rx * brand_share))
            biozenith_trx = int(round(total_rx * comp1_share))
            theramax_trx = max(0, total_rx - (pulserx_trx + biozenith_trx))
            rx_records.append({
                "HCP_NPI": hcp["HCP_NPI"],
                "Month_Date": dt.strftime("%Y-%m-%d"),
                "Market_TRx": total_rx,
                "PulseRx_TRx": pulserx_trx,
                "PulseRx_NRx": int(round(pulserx_trx * random.uniform(0.24, 0.38))),
                "BioZenith_TRx": biozenith_trx,
                "TheraMax_TRx": theramax_trx,
                "PulseRx_Sales_USD": pulserx_trx * 1850,
                "Total_Market_Sales_USD": pulserx_trx * 1850 + biozenith_trx * 1720 + theramax_trx * 1390,
            })
    df_rx = pd.DataFrame(rx_records)
    df_rx.to_csv(os.path.join(output_dir, "raw_monthly_rx_claims.csv"), index=False)
    say(f" -> [2/5] {len(df_rx)} monthly Rx rows -> raw_monthly_rx_claims.csv")

    # 3. REP ROSTER
    rep_list = []
    for terr in TERRITORIES:
        for r_idx in range(1, terr["reps"] + 1):
            letter = chr(64 + r_idx)
            rep_list.append({
                "Rep_ID": f"REP_{terr['id'][-5:]}_{letter}",
                "Territory_ID": terr["id"],
                "District": terr["district"],
                "Region": terr["region"],
                "Rep_Name": f"Field Rep {terr['id'][-5:]}-{letter}",
                "Annual_Call_Capacity": CALLS_PER_REP_CAPACITY,
            })
    df_reps = pd.DataFrame(rep_list)
    df_reps.to_csv(os.path.join(output_dir, "raw_sales_reps.csv"), index=False)
    say(f" -> [3/5] {len(df_reps)} reps -> raw_sales_reps.csv")

    # 4. CRM CALL LOG -- the status-quo call pattern (see module docstring)
    access = (df_hcps["Practice_Setting"].map(SETTING_ACCESS)
              * df_hcps["Digital_Affinity"].map(AFFINITY_ACCESS)
              * np.random.lognormal(0.0, 0.6, len(df_hcps)))            # rep habit / relationships
    access_rank = access.groupby(df_hcps["Territory_ID"]).rank(pct=True)
    volume_rank = df_hcps["Volume_Factor"].groupby(df_hcps["Territory_ID"]).rank(pct=True)
    list_score = (1 - alignment) * access_rank + alignment * volume_rank
    on_list = list_score.groupby(df_hcps["Territory_ID"]).rank(pct=True, ascending=False) <= CALL_LIST_SHARE

    # How often a listed doctor is seen follows the same blend of access and volume rank
    # (rank, not raw volume, so the largest prescriber does not absorb hundreds of calls).
    freq_weight = (1 - alignment) * access / access[on_list].mean() + alignment * 2 * volume_rank
    p = np.where(on_list, freq_weight, 0.0)
    call_hcp_idx = []
    counts = np.zeros(len(df_hcps), dtype=int)
    while len(call_hcp_idx) < N_CALLS:          # draw, then re-draw any call past the per-HCP cap
        open_p = np.where(counts < MAX_CALLS_PER_HCP, p, 0.0)
        for i in np.random.choice(len(df_hcps), size=N_CALLS - len(call_hcp_idx), p=open_p / open_p.sum()):
            if counts[i] < MAX_CALLS_PER_HCP:
                counts[i] += 1
                call_hcp_idx.append(i)

    reps_by_terr = df_reps.groupby("Territory_ID")["Rep_ID"].apply(list).to_dict()
    channels = ["In-Person Detailing", "Virtual Video Detailing", "Dinner Meeting / Medical Advisory", "Email Follow-up"]
    sentiments = ["Positive - Requested Trial Patient Starters", "Neutral - Comfortable with BioZenith",
                  "Positive - High Switch Potential for Next Line", "Hesitant - Payer Prior Auth Friction",
                  "Committed - Adding PulseRx to Hospital Formulary"]
    start_dt = pd.Timestamp("2025-01-05")
    call_logs = []
    for n, idx in enumerate(call_hcp_idx, start=1):
        hcp = df_hcps.iloc[idx]
        channel = np.random.choice(channels, p=[0.58, 0.26, 0.06, 0.10])
        call_logs.append({
            "Call_ID": f"CALL_{n:06d}",
            "HCP_NPI": hcp["HCP_NPI"],
            "Rep_ID": random.choice(reps_by_terr[hcp["Territory_ID"]]),
            "Territory_ID": hcp["Territory_ID"],
            "Call_Date": (start_dt + pd.Timedelta(days=random.randint(0, 350))).strftime("%Y-%m-%d"),
            "Channel": channel,
            "Detailing_Minutes": random.choice([5, 10, 15, 20, 30]),
            "Samples_Provided": random.choice([0, 2, 4, 6]) if channel == "In-Person Detailing" else 0,
            "Physician_Feedback": np.random.choice(sentiments, p=[0.32, 0.26, 0.22, 0.12, 0.08]),
        })
    df_calls = pd.DataFrame(call_logs)
    df_calls.to_csv(os.path.join(output_dir, "raw_rep_call_logs.csv"), index=False)
    say(f" -> [4/5] {len(df_calls)} CRM calls -> raw_rep_call_logs.csv (alignment={alignment})")

    # 5. TERRITORY ROSTER, CAPACITY AND QUOTA
    df_quotas = pd.DataFrame([{
        "Territory_ID": t["id"], "Region": t["region"], "District": t["district"], "State": t["state"],
        "Rep_Count": t["reps"],
        "Annual_Sales_Quota_USD": t["reps"] * 2_400_000,
        "Target_Call_Capacity": t["reps"] * CALLS_PER_REP_CAPACITY,
        "Target_Decile_Coverage_Goal_Pct": 0.85,
    } for t in TERRITORIES])
    df_quotas.to_csv(os.path.join(output_dir, "raw_territory_quotas.csv"), index=False)
    say(f" -> [5/5] {len(df_quotas)} territories -> raw_territory_quotas.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="data")
    ap.add_argument("--alignment", type=float, default=CALL_TARGETING_ALIGNMENT)
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    generate(a.out, a.alignment, a.seed)
