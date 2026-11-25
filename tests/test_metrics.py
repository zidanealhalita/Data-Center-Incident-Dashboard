"""Cross-check dashboard metrics against independent plain-pandas calculations."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import metrics as M  # noqa: E402
from src.data import DATA_PATH, PART_ORDER, prepare  # noqa: E402


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


@pytest.fixture(scope="module")
def df(raw) -> pd.DataFrame:
    return prepare(raw)


def test_row_count_and_unique_ids(raw, df):
    assert len(df) == len(raw) == 2600
    assert df["ticket_id"].is_unique


def test_open_tickets(raw, df):
    assert int(df["is_open"].sum()) == int((raw["status"] != "Resolved").sum()) == 3
    # every open ticket lacks a resolution time and nothing else does
    assert df["resolved_at"].isna().sum() == 3
    assert df.loc[df["is_open"], "resolved_at"].isna().all()


def test_headline_kpis(raw, df):
    k = M.kpis(df)
    assert k["total"] == 2600
    assert k["mtta_mean"] == pytest.approx(raw["mtta_min"].mean())
    assert k["mttr_mean"] == pytest.approx(raw["time_to_resolve_min"].dropna().mean())
    assert k["ack_breaches"] == int(raw["ack_sla_breached"].sum()) == 110
    assert k["ack_compliance"] == pytest.approx(1 - 110 / 2600)
    resolved = raw[raw["resolved_at"].notna()]
    assert k["res_breaches"] == int(resolved["resolve_sla_breached"].sum()) == 42
    assert k["res_compliance"] == pytest.approx(1 - 42 / len(resolved))


def test_group_summary_matches_total(df):
    by_sev = M.group_summary(df, "severity")
    assert by_sev["tickets"].sum() == len(df)
    assert by_sev["ack_breaches"].sum() == df["ack_sla_breached"].sum()
    assert by_sev["resolve_breaches"].sum() == df.loc[df["resolved"], "resolve_sla_breached"].sum()


def test_part_status_covers_all_rows(df):
    assert set(df["part_status"]) == set(PART_ORDER)
    assert (df["part_status"] == PART_ORDER[0]).sum() == int((~df["spare_part_required"]).sum())


def test_pareto_shares(df):
    inc = df[df["ticket_type"] == "Incident"]
    p = M.pareto(inc, "component")
    assert p["value"].sum() == len(inc)
    assert p["cum_share"].iloc[-1] == pytest.approx(1.0)
    assert bool(p["vital_few"].iloc[0]) is True
    # the first item *beyond* the threshold is included, the next one is not
    n = int(p["vital_few"].sum())
    assert p["cum_share"].iloc[n - 1] >= 0.8 > p["cum_share"].iloc[n - 2]


def test_july_split_counts(df):
    before = df[df["created_at"] < "2026-07-01"]
    after = df[df["created_at"] >= "2026-07-01"]
    assert len(before) + len(after) == len(df)
    b, a = M.before_after_summary(before), M.before_after_summary(after)
    assert b["unavail_rate"] > a["unavail_rate"]


def test_mttr_decomposition_is_exact(df):
    before = df[df["created_at"] < "2026-07-01"]
    after = df[df["created_at"] >= "2026-07-01"]
    dec = M.mttr_decomposition(before, after)
    actual = (after.loc[after["resolved"], "time_to_resolve_min"].mean()
              - before.loc[before["resolved"], "time_to_resolve_min"].mean())
    assert dec["total"] == pytest.approx(actual)
    assert dec["mix"] + dec["within"] == pytest.approx(actual)


def test_two_proportion_pvalue():
    assert M.two_proportion_pvalue(50, 100, 50, 100) == pytest.approx(1.0)
    assert M.two_proportion_pvalue(10, 100, 50, 100) < 0.001
    assert math.isnan(M.two_proportion_pvalue(1, 0, 1, 10))
