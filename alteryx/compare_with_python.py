"""Compare the HCP mart written by Alteryx Designer with the one written by run_pipeline.py.

Usage (after running PulseRx_ETL_Targeting.yxmd in Designer):
    python alteryx/compare_with_python.py path/to/alteryx_hcp_mart.csv

Checks row count, then decile, tier, planned calls, calls received and deficit per HCP.
Accepts the Tile tool's default field name (Tile_Num) if no Select tool renamed it.
"""
import sys

import pandas as pd

KEYS = ["Market_Decile", "Targeting_Tier", "Recommended_Annual_Calls", "Total_Calls_2025", "Call_Deficit"]


def main(alteryx_csv, python_csv="output_marts/tableau_hcp_targeting_mart.csv"):
    ax = pd.read_csv(alteryx_csv, dtype={"HCP_NPI": str}).rename(columns={"Tile_Num": "Market_Decile"})
    py = pd.read_csv(python_csv, dtype={"HCP_NPI": str})
    print(f"rows: Alteryx {len(ax):,} vs Python {len(py):,}")
    missing = set(py["HCP_NPI"]) - set(ax["HCP_NPI"])
    if missing:
        uncalled = py[py["HCP_NPI"].isin(missing) & (py["Total_Calls_2025"] == 0)]
        print(f"  {len(missing):,} HCPs missing from Alteryx output ({len(uncalled):,} of them have no calls --"
              " the Join tool's L output is probably not unioned back in)")
    m = py.merge(ax, on="HCP_NPI", suffixes=("_py", "_ax"))
    ok = True
    for k in KEYS:
        if f"{k}_ax" not in m:
            print(f"  {k}: not in Alteryx output")
            ok = False
            continue
        diff = (m[f"{k}_py"].astype(str) != m[f"{k}_ax"].astype(str)).sum()
        print(f"  {k}: {diff:,} of {len(m):,} rows differ")
        ok &= diff == 0
    ok &= not missing
    print("MATCH" if ok else "DIFFERENCES FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
