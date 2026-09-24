# Tableau: `PulseRx_Executive_Dashboard.twb`

## Status -- read this first

The `.twb` is a hand-written **starter** file. It contains:

- a text-file data source on `output_marts/tableau_hcp_targeting_mart.csv` (column list kept in
  sync with the mart by `tableau/sync_twb_columns.py`, checked by the tests)
- 4 calculated fields: territory brand share as a FIXED LOD, decile 8-10 reach %, opportunity
  quadrant, TRx per call
- 2 worksheets: brand sales by region (bar), market TRx vs brand share by tier (scatter)

It has **no dashboard, no parameters, and has not been opened in Tableau yet**. Everything below is
the plan for building the rest in the free **Tableau Public** desktop app.

## Build plan

1. Open the `.twb` in Tableau Public. If the data source path breaks, reconnect to the three CSVs
   in `output_marts/` (HCP mart, territory mart, monthly mart).
2. Keep the two existing sheets. Add:
   - **Decile concentration**: `Market_Decile` on columns, `SUM(Annual_Market_TRx)` as a running
     total % of total (quick table calculation), sorted decile 10 -> 1.
   - **Territory workload**: territory mart, `Territory_ID` on rows, `Workload_Utilization_Pct` on
     columns, colour by `Sizing_Consulting_Action`, reference lines at 80 and 115.
   - **Uncalled high-value prescribers**: HCP mart filtered to `Market_Decile >= 8` and
     `Total_Calls_2025 = 0`; rows `Territory_ID`, `HCP_Name`, `Targeting_Tier`.
   - **Brand trend**: monthly mart, `Month_Date` by month, `SUM(PulseRx_TRx)` and
     `SUM(BioZenith_TRx)`.
3. Add two parameters and use them in calculated fields:
   - `Decile Cutoff` (integer 1-10, default 8), used in the reach % and quadrant fields.
   - `Calls per Rep` (integer 600-840, default 720): capacity = `[Rep_Count] * [Calls per Rep]`,
     utilization = `SUM([Total_Calls_Required]) / SUM(capacity)`.
4. Put the sheets on one dashboard with the parameter controls shown, and check the headline
   numbers (uncalled high-value prescribers, plan calls vs capacity) match the Results table in
   `README.md`.
5. Publish to Tableau Public, allow downloads, put the link in `README.md`, and commit the
   downloaded `.twbx`.

## The FIXED LOD, and why it's there

```
{ FIXED [Territory_ID] : SUM([Annual_PulseRx_TRx]) } / { FIXED [Territory_ID] : SUM([Annual_Market_TRx]) } * 100
```

A plain `SUM(brand) / SUM(market)` recomputes on whatever is filtered, so filtering to one
specialty would show that specialty's share, not the territory's. FIXED computes at territory
level before dimension filters apply (context filters still apply), so the territory's share stays
put while the view is sliced. Be ready to explain that difference -- it is the usual follow-up.
