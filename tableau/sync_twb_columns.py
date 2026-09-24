"""Rewrite the <columns> block of the .twb data source from the HCP mart's actual header.

The workbook declares each CSV column with a position (ordinal) and type. If the mart's
columns change and the workbook is not updated, Tableau can map fields to the wrong
columns. Run this after the pipeline; tests/test_pulserx.py fails if they disagree.
"""
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TWB = os.path.join(ROOT, "tableau", "PulseRx_Executive_Dashboard.twb")
MART = os.path.join(ROOT, "output_marts", "tableau_hcp_targeting_mart.csv")
TYPES = {"i": "integer", "f": "real", "O": "string", "b": "boolean"}


def expected_columns():
    df = pd.read_csv(MART, nrows=200, dtype={"HCP_NPI": str})
    return [(c, TYPES[df[c].dtype.kind]) for c in df.columns]


def declared_columns(text=None):
    text = text if text is not None else open(TWB, encoding="utf-8").read()
    block = re.search(r"<columns character-set=.*?</columns>", text, re.S).group(0)
    return [(n, t) for t, n, _ in re.findall(r"<column datatype='(\w+)' name='([^']+)' ordinal='(\d+)' />", block)]


def sync():
    text = open(TWB, encoding="utf-8").read()
    cols = "\n".join(f"            <column datatype='{t}' name='{n}' ordinal='{i}' />"
                     for i, (n, t) in enumerate(expected_columns()))
    text = re.sub(r"(<columns character-set=[^>]*>\n).*?(\n\s*</columns>)", lambda m: m.group(1) + cols + m.group(2),
                  text, count=1, flags=re.S)
    open(TWB, "w", encoding="utf-8").write(text)
    print(f"{len(expected_columns())} columns written to {os.path.relpath(TWB, ROOT)}")


if __name__ == "__main__":
    sync()
