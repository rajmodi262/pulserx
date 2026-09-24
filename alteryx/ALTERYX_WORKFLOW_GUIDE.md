# Alteryx workflow: `PulseRx_ETL_Targeting.yxmd`

## Status -- read this first

The `.yxmd` was written by hand as XML for Designer 2023.2. It is well-formed and its formulas
match the Python pipeline (`tests/test_pulserx.py::test_alteryx_rules_match_python`), but **it has
not been opened or run in Alteryx Designer yet**. The marts in `output_marts/` come from
`run_pipeline.py`. Until the checklist below is done, don't describe this as "built in Alteryx".

## The 16 tools

| # | Tool | Does |
|---|---|---|
| 1-4 | Input Data | HCP master, monthly Rx, CRM calls, territory roster (`..\data\*.csv`) |
| 5 | Summarize | Monthly Rx -> 12-month totals per `HCP_NPI` |
| 6 | Formula | `PulseRx_Market_Share_Pct`, `PulseRx_NRx_Ratio_Pct` |
| 7 | Tile | Equal Records, 10 tiles on `Annual_Market_TRx` -> `Tile_Num` |
| 8 | Summarize | Calls per `HCP_NPI` |
| 9 | Join | HCP master + deciles on `HCP_NPI` |
| 10 | Join | + call counts on `HCP_NPI` |
| 11 | Formula | Tier, planned calls, call deficit |
| 12 | Output Data | HCP mart |
| 13 | Summarize | Territory rollup of required and delivered calls |
| 14 | Join | + territory roster (capacity) |
| 15 | Formula | Utilization %, quota attainment, sizing action |
| 16 | Output Data | Territory mart |

Rules (same in Python, SQL and here): Tier 1 = decile >= 8 and share >= 22%; Tier 2 = decile >= 8
and share < 22%; Tier 3 = decile 5-7; Tier 4 = decile 1-4. Planned calls 18 / 14 / 6 / 1.
Overburdened > 115% of capacity, underutilized < 80%.

## Checklist for the first run in Designer

Install the free 30-day Designer trial, open the file, and work through these. Each one is a real
Alteryx skill worth being able to talk about.

1. **Input paths.** The inputs use `..\data\*.csv` relative to the workflow. If Designer can't find
   them, repoint the four Input Data tools.
2. **Uncalled prescribers are dropped (known bug).** Join #10 only passes its **J** (matched)
   output on to Formula #11. Prescribers with no calls come out of the **L** output and are lost --
   and those are exactly the high-value prescribers the analysis is about. Fix: add a **Union**
   of Join #10's J and L outputs, then a Formula setting `Total_Calls_2025` to 0 where it is null
   (`IIF(IsNull([Total_Calls_2025]), 0, [Total_Calls_2025])`), before Formula #11.
3. **Decile field name.** The Tile tool writes `Tile_Num`. Add a **Select** tool after it to rename
   it to `Market_Decile` so the output matches the Tableau workbook (update the tier formula to
   use the new name).
4. **Tie-breaking.** The Python and SQL versions sort by `Annual_Market_TRx` then `HCP_NPI`, so
   deciles are deterministic. Add a Sort tool before the Tile (volume, then NPI) to get the same
   deciles.
5. **Types.** CSV inputs arrive as strings. Check the Summarize tool can sum the TRx fields; add a
   Select tool to set numeric types if it can't.
6. **Compare with Python.** Write the HCP mart to CSV and run
   `python alteryx/compare_with_python.py <that csv>`. It checks row count and, per prescriber,
   decile, tier, planned calls, calls received and deficit. Aim for `MATCH`.
7. **Record it.** Screenshot the canvas and the Results window, save the fixed `.yxmd`, commit
   both, and update the Status section above.

## Interview notes (true only once the checklist is done)

- **Why Alteryx for this?** The steps are the same as the SQL, but a brand or sales-ops analyst
  can read the canvas, change a threshold in one Formula tool and re-run without code.
- **Equal Records vs Equal Sum in the Tile tool.** Equal Records puts the same number of
  prescribers in each decile (the usual market-decile convention, and what this uses). Equal Sum
  makes each decile hold the same share of volume, so decile 10 becomes a much smaller group of
  very large prescribers. This project uses Equal Records only.
- **What went wrong first time?** Answer with whatever actually happened on the checklist --
  item 2 is the likely one, and it is a good story because the bug would have hidden the finding.
