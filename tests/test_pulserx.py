"""Checks that keep PulseRx honest: numbers match data, SQL/Alteryx/Python agree, and the
pipeline detects the misallocation the generator plants (rather than restating it)."""
import os
import re
import sys
import xml.dom.minidom

import duckdb
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, d) for d in ("alteryx", "data", "analysis", "tableau")]
os.chdir(ROOT)

import generate_data  # noqa: E402
import headline_metrics  # noqa: E402
import run_pipeline  # noqa: E402

MARTS, DATA = "output_marts", "data"


@pytest.fixture(scope="module")
def hcp():
    return pd.read_csv(os.path.join(MARTS, "tableau_hcp_targeting_mart.csv"), dtype={"HCP_NPI": str})


@pytest.fixture(scope="module")
def db():
    con = duckdb.connect()
    for name, path in [("raw_hcp_universe", f"{DATA}/raw_hcp_universe.csv"),
                       ("raw_monthly_rx_claims", f"{DATA}/raw_monthly_rx_claims.csv"),
                       ("raw_rep_call_logs", f"{DATA}/raw_rep_call_logs.csv"),
                       ("raw_territory_quotas", f"{DATA}/raw_territory_quotas.csv"),
                       ("tableau_hcp_targeting_mart", f"{MARTS}/tableau_hcp_targeting_mart.csv")]:
        types = ", types={'HCP_NPI': 'VARCHAR'}" if "HCP_NPI" in open(path, encoding="utf-8").readline() else ""
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv_auto('{path}'{types})")
    return con


def test_readme_numbers_come_from_the_data():
    readme = open("README.md", encoding="utf-8").read()
    block = readme[readme.index(headline_metrics.START):readme.index(headline_metrics.END) + len(headline_metrics.END)]
    assert block == headline_metrics.render(headline_metrics.compute()), \
        "README metrics are stale: run `python analysis/headline_metrics.py`"


def test_resume_kit_numbers_come_from_the_data():
    path = "private/RESUME_AND_INTERVIEW_KIT.md"   # local only, not in the public repo
    if not os.path.exists(path):
        pytest.skip("private resume kit not present")
    kit = open(path, encoding="utf-8").read()
    s, e = headline_metrics.RESUME_START, headline_metrics.RESUME_END
    assert kit[kit.index(s):kit.index(e) + len(e)] == headline_metrics.render_resume(headline_metrics.compute()), \
        "Resume kit numbers are stale: run `python analysis/headline_metrics.py`"


def test_tableau_columns_match_the_mart():
    import sync_twb_columns
    assert sync_twb_columns.declared_columns() == sync_twb_columns.expected_columns(), \
        "Workbook columns are stale: run `python tableau/sync_twb_columns.py`"


def test_alteryx_comparison_catches_dropped_uncalled_hcps(hcp, tmp_path, capsys):
    import compare_with_python
    # What the .yxmd as written would produce: inner join drops uncalled HCPs, decile named Tile_Num
    ax = hcp[hcp["Total_Calls_2025"] > 0].rename(columns={"Market_Decile": "Tile_Num"})
    ax.to_csv(tmp_path / "ax.csv", index=False)
    assert compare_with_python.main(str(tmp_path / "ax.csv")) == 1
    assert "have no calls" in capsys.readouterr().out
    hcp.to_csv(tmp_path / "same.csv", index=False)
    assert compare_with_python.main(str(tmp_path / "same.csv")) == 0


def test_marts_are_consistent_with_raw_data(hcp):
    raw_hcp = pd.read_csv(f"{DATA}/raw_hcp_universe.csv")
    assert raw_hcp["HCP_NPI"].is_unique
    assert len(hcp) == len(raw_hcp)
    assert hcp["Total_Calls_2025"].sum() == len(pd.read_csv(f"{DATA}/raw_rep_call_logs.csv"))
    monthly = pd.read_csv(f"{MARTS}/tableau_monthly_rx_timeseries_mart.csv")
    assert len(monthly) == len(pd.read_csv(f"{DATA}/raw_monthly_rx_claims.csv"))
    assert (hcp["Market_Decile"].value_counts() == len(hcp) // 10).all()


def test_sql_deciles_and_tiers_match_pipeline(db, hcp):
    sql = open("sql/01_hcp_deciling_and_pareto.sql", encoding="utf-8").read()
    out = db.execute(sql).df().rename(columns=str.lower).set_index("hcp_npi")
    mart = hcp.set_index("HCP_NPI")
    assert (out.loc[mart.index, "market_decile"].values == mart["Market_Decile"].values).all()
    assert (out.loc[mart.index, "targeting_tier"].values == mart["Targeting_Tier"].values).all()


def test_sql_territory_workload_matches_pipeline(db):
    sql = open("sql/02_territory_workload_and_capacity.sql", encoding="utf-8").read()
    out = db.execute(sql).df().rename(columns=str.lower).set_index("territory_id")
    terr = pd.read_csv(f"{MARTS}/tableau_territory_alignment_mart.csv").set_index("Territory_ID")
    got = out.loc[terr.index, "workload_utilization_pct"].values
    assert got == pytest.approx(terr["Workload_Utilization_Pct"].round(1).values, abs=0.05)


def test_alteryx_rules_match_python():
    path = "alteryx/PulseRx_ETL_Targeting.yxmd"
    doc = xml.dom.minidom.parse(path)                     # well-formed
    ids = {n.getAttribute("ToolID") for n in doc.getElementsByTagName("Node")}
    for tag in ("Origin", "Destination"):
        assert {e.getAttribute("ToolID") for e in doc.getElementsByTagName(tag)} <= ids
    exprs = " ".join(f.getAttribute("expression") for f in doc.getElementsByTagName("FormulaField"))
    tier = re.search(r"IF \[Tile_Num\] >= (\d+) AND \[PulseRx_Market_Share_Pct\] >= (\d+)", exprs)
    assert int(tier.group(1)) == run_pipeline.TIER_DECILE_MIN
    assert float(tier.group(2)) == run_pipeline.SHARE_THRESHOLD_PCT
    calls = dict(re.findall(r"'(Tier \d)'\) THEN (\d+)", exprs))
    calls["Tier 4"] = re.search(r"ELSE (\d+) ENDIF", exprs).group(1)
    assert {k: int(v) for k, v in calls.items()} == run_pipeline.CALLS_PER_TIER
    assert f"> {run_pipeline.OVERBURDENED_PCT}" in exprs and f"< {run_pipeline.UNDERUTILIZED_PCT}" in exprs


def test_decile_8_high_share_is_tier_1_not_digital():
    # Regression: Tier 1 used to start at decile 9 while Tier 2 started at 8,
    # so decile-8 prescribers with high share fell through to Tier 4.
    assert run_pipeline.assign_tier(8, 30.0).startswith("Tier 1")
    assert run_pipeline.assign_tier(8, 10.0).startswith("Tier 2")
    assert run_pipeline.assign_tier(4, 50.0).startswith("Tier 4")


def test_pipeline_detects_planted_misallocation(tmp_path):
    """The pipeline never reads the generator's alignment parameter; it has to find it."""
    def zero_call_share(alignment):
        d, m = tmp_path / f"data_{alignment}", tmp_path / f"marts_{alignment}"
        generate_data.generate(str(d), alignment=alignment, quiet=True)
        h, _ = run_pipeline.run(str(d), str(m), quiet=True)
        high = h["Market_Decile"] >= run_pipeline.TIER_DECILE_MIN
        return (high & (h["Total_Calls_2025"] == 0)).sum() / high.sum()

    access_driven, volume_driven = zero_call_share(0.0), zero_call_share(1.0)
    assert access_driven > 0.25          # access-driven lists skip many high-value HCPs
    assert volume_driven < 0.05          # volume-driven lists reach almost all of them
