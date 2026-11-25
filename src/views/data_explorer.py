"""Extra page - raw ticket explorer with CSV download."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import theme as T

DEFAULT_COLS = [
    "ticket_id", "created_at", "ticket_type", "severity", "category", "component", "root_cause",
    "hall_id", "rack_id", "shift", "part_status", "mtta_min", "time_to_resolve_min",
    "ack_sla_breached", "resolve_sla_breached", "customer_impact", "repeat_incident", "status",
]


def render(df: pd.DataFrame, full: pd.DataFrame, snapshot: pd.Timestamp) -> None:
    T.page_header("🗂️ Data Explorer", "Telusuri tiket mentah sesuai filter sidebar", df)
    query = st.text_input("Cari (ticket ID, komponen, root cause, rack, teknisi)", "")
    view = df
    if query.strip():
        q = query.strip().lower()
        hay = (df["ticket_id"] + " " + df["component"] + " " + df["root_cause"] + " " + df["rack_id"]
               + " " + df["technician_id"]).str.lower()
        view = df[hay.str.contains(q, regex=False)]

    cols = st.multiselect("Kolom", [c for c in df.columns], default=[c for c in DEFAULT_COLS if c in df.columns])
    st.write(f"{len(view):,} tiket")
    st.dataframe(view[cols] if cols else view, hide_index=True, width="stretch", height=520)
    st.download_button("⬇️ Unduh hasil filter (CSV)", (view[cols] if cols else view).to_csv(index=False).encode("utf-8"),
                       file_name="dc_incident_tickets_filtered.csv", mime="text/csv")
