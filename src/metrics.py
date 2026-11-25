"""Pure-pandas metric helpers (no Streamlit imports so they are unit-testable)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.data import PART_ORDER


def _mean(s: pd.Series) -> float:
    return float(s.mean()) if len(s) else float("nan")


def _median(s: pd.Series) -> float:
    return float(s.median()) if len(s) else float("nan")


def kpis(df: pd.DataFrame) -> dict:
    """Headline KPIs.

    * MTTA uses all tickets (every ticket has an acknowledgement time).
    * MTTR and resolve-SLA compliance use resolved tickets only; open tickets
      have no resolution time and have not been evaluated against the SLA yet.
    """
    res = df[df["resolved"]]
    n = len(df)
    return {
        "total": n,
        "incidents": int((df["ticket_type"] == "Incident").sum()),
        "resolved": len(res),
        "open": int(df["is_open"].sum()),
        "mtta_mean": _mean(df["mtta_min"]),
        "mtta_median": _median(df["mtta_min"]),
        "mttr_mean": _mean(res["time_to_resolve_min"]),
        "mttr_median": _median(res["time_to_resolve_min"]),
        "ack_breaches": int(df["ack_sla_breached"].sum()),
        "res_breaches": int(res["resolve_sla_breached"].sum()),
        "ack_compliance": 1 - df["ack_sla_breached"].mean() if n else float("nan"),
        "res_compliance": (
            1 - res["resolve_sla_breached"].mean() if len(res) else float("nan")
        ),
    }


def group_summary(df: pd.DataFrame, by) -> pd.DataFrame:
    """Per-group ticket count, MTTA/MTTR and SLA breach counts/rates."""
    out = df.groupby(by, observed=True).agg(
        tickets=("ticket_id", "count"),
        mtta_mean=("mtta_min", "mean"),
        mtta_median=("mtta_min", "median"),
        ack_breaches=("ack_sla_breached", "sum"),
    )
    res = (
        df[df["resolved"]]
        .groupby(by, observed=True)
        .agg(
            resolved=("ticket_id", "count"),
            mttr_mean=("time_to_resolve_min", "mean"),
            mttr_median=("time_to_resolve_min", "median"),
            resolve_breaches=("resolve_sla_breached", "sum"),
        )
    )
    out = out.join(res)
    for col in ("resolved", "resolve_breaches"):
        out[col] = out[col].fillna(0).astype(int)
    out["ack_breach_rate"] = out["ack_breaches"] / out["tickets"]
    out["resolve_breach_rate"] = np.where(
        out["resolved"] > 0, out["resolve_breaches"] / out["resolved"].replace(0, np.nan), np.nan
    )
    out["ack_compliance"] = 1 - out["ack_breach_rate"]
    out["resolve_compliance"] = 1 - out["resolve_breach_rate"]
    return out


def pareto(df: pd.DataFrame, col: str, value: str | None = None, scale: float = 1.0,
           threshold: float = 0.8) -> pd.DataFrame:
    """Sorted Pareto table. ``vital_few`` marks the items needed to reach ``threshold``."""
    if value is None:
        s = df.groupby(col).size()
    else:
        s = df.groupby(col)[value].sum() * scale
    out = s.sort_values(ascending=False).rename("value").to_frame()
    out["share"] = out["value"] / out["value"].sum()
    out["cum_share"] = out["share"].cumsum()
    out["vital_few"] = out["cum_share"].shift(fill_value=0.0) < threshold
    return out


def two_proportion_pvalue(x1: int, n1: int, x2: int, n2: int) -> float:
    """Two-sided z-test p-value for the difference between two proportions."""
    if min(n1, n2) == 0:
        return float("nan")
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return float("nan")
    z = (p1 - p2) / se
    return math.erfc(abs(z) / math.sqrt(2))


def mann_whitney_pvalue(a: pd.Series, b: pd.Series) -> float:
    """Two-sided Mann-Whitney U p-value (nan if scipy is missing or data is empty)."""
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    try:
        from scipy.stats import mannwhitneyu
    except ImportError:  # pragma: no cover
        return float("nan")
    return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)


def before_after_summary(df: pd.DataFrame) -> dict:
    """KPIs used in the spare-part before/after comparison."""
    res = df[df["resolved"]]
    need = df[df["spare_part_required"]]
    unavail = need[need["part_status"] == PART_ORDER[2]]
    return {
        "tickets": len(df),
        "part_required": len(need),
        "part_unavailable": len(unavail),
        "unavail_rate": len(unavail) / len(need) if len(need) else float("nan"),
        "avg_part_wait_unavail": _mean(unavail["part_wait_min"]),
        "mttr_mean": _mean(res["time_to_resolve_min"]),
        "mttr_median": _median(res["time_to_resolve_min"]),
        "resolved": len(res),
        "res_breaches": int(res["resolve_sla_breached"].sum()),
        "res_breach_rate": (
            float(res["resolve_sla_breached"].mean()) if len(res) else float("nan")
        ),
        "ack_breach_rate": float(df["ack_sla_breached"].mean()) if len(df) else float("nan"),
    }


def mttr_decomposition(before: pd.DataFrame, after: pd.DataFrame) -> dict:
    """Split the MTTR change into a *mix* effect and a *within-group* effect.

    Groups are the part statuses (no part needed / available / unavailable).

    * mix    = change caused by tickets moving between groups
               (e.g. fewer 'part unavailable' tickets)
    * within = change caused by a group getting faster or slower
    * total  = mix + within = MTTR(after) - MTTR(before)
    """
    b = before[before["resolved"]]
    a = after[after["resolved"]]
    w_b = b["part_status"].value_counts(normalize=True).reindex(PART_ORDER).fillna(0.0)
    w_a = a["part_status"].value_counts(normalize=True).reindex(PART_ORDER).fillna(0.0)
    m_b = b.groupby("part_status")["time_to_resolve_min"].mean().reindex(PART_ORDER)
    m_a = a.groupby("part_status")["time_to_resolve_min"].mean().reindex(PART_ORDER)
    # A group missing in one period has weight 0 there, so its fill value is irrelevant.
    m_b_f = m_b.fillna(m_a).fillna(0.0)
    m_a_f = m_a.fillna(m_b_f).fillna(0.0)

    mix = float(((w_a - w_b) * m_b_f).sum())
    within = float((w_a * (m_a_f - m_b_f)).sum())
    table = pd.DataFrame(
        {
            "Porsi tiket sebelum": w_b,
            "Porsi tiket sesudah": w_a,
            "MTTR sebelum (mnt)": m_b,
            "MTTR sesudah (mnt)": m_a,
        }
    )
    return {"mix": mix, "within": within, "total": mix + within, "table": table}
