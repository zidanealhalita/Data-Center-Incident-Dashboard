"""Data loading, cleaning and filtering for the DC incident dashboard."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "dataset2_dc_hardware_incident_tickets.csv"
)

SEV_ORDER = ["Sev-1", "Sev-2", "Sev-3", "Sev-4"]
SHIFT_ORDER = ["Morning", "Afternoon", "Night"]
PART_ORDER = ["Tidak butuh part", "Part tersedia", "Part tidak tersedia"]
TYPE_ORDER = ["Incident", "Preventive Maintenance", "Change Request"]
DATE_COLS = ["created_at", "acknowledged_at", "resolved_at"]

REQUIRED_COLUMNS = [
    "ticket_id", "created_at", "acknowledged_at", "resolved_at", "ticket_type",
    "severity", "category", "component", "root_cause", "hall_id", "rack_id",
    "shift", "technician_id", "spare_part_required", "spare_part_available",
    "part_wait_min", "mtta_min", "time_to_resolve_min", "sla_ack_target_min",
    "sla_resolve_target_min", "ack_sla_breached", "resolve_sla_breached",
    "customer_impact", "repeat_incident", "escalated_to", "status",
]


def _part_status(row_required: bool, row_available) -> str:
    if not row_required:
        return PART_ORDER[0]
    return PART_ORDER[1] if bool(row_available) else PART_ORDER[2]


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    """Parse types and add derived columns used across the dashboard."""
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan di dataset: {missing}")

    df = raw.copy()
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], format="mixed")

    df["month"] = df["created_at"].dt.to_period("M").dt.to_timestamp()
    df["hour"] = df["created_at"].dt.hour
    df["resolved"] = df["resolved_at"].notna()
    df["is_open"] = df["status"].ne("Resolved")
    df["rack_no"] = df["rack_id"].str[-2:].astype(int)

    df["part_status"] = [
        _part_status(req, avail)
        for req, avail in zip(df["spare_part_required"], df["spare_part_available"])
    ]
    df["customer_impact"] = df["customer_impact"].fillna("Tidak ada")
    df["escalated_to"] = df["escalated_to"].fillna("Tidak dieskalasi")
    return df.sort_values("created_at").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_data(path: str = str(DATA_PATH)) -> pd.DataFrame:
    return prepare(pd.read_csv(path))


def snapshot_time(df: pd.DataFrame) -> pd.Timestamp:
    """Latest timestamp present in the data, used as the 'as of' moment."""
    return df[DATE_COLS].max().max()


def apply_filters(
    df: pd.DataFrame,
    start,
    end,
    ticket_types,
    severities,
    halls,
    categories,
) -> pd.DataFrame:
    mask = (
        (df["created_at"].dt.date >= start)
        & (df["created_at"].dt.date <= end)
        & df["ticket_type"].isin(ticket_types)
        & df["severity"].isin(severities)
        & df["hall_id"].isin(halls)
        & df["category"].isin(categories)
    )
    return df[mask]
