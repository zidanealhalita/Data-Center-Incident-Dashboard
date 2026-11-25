"""Data Center Hardware Incident Dashboard.

Author: Muhammad Zidane Alhalita (Data Center Analyst)
Run:    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from src import theme as T
from src.data import (SEV_ORDER, TYPE_ORDER, apply_filters, load_data, snapshot_time)
from src.views import (customer_impact, data_explorer, failure_analysis, insights, ops_summary, rca,
                       sla_shift, spare_parts)

AUTHOR = "Muhammad Zidane Alhalita"

st.set_page_config(page_title="DC Incident Dashboard", page_icon="🖥️", layout="wide")
T.inject_css()

try:
    full = load_data()
except FileNotFoundError:
    st.error("File data tidak ditemukan. Pastikan `data/dataset2_dc_hardware_incident_tickets.csv` ada di repositori.")
    st.stop()
except ValueError as exc:
    st.error(str(exc))
    st.stop()

snapshot = snapshot_time(full)

# ------------------------------------------------------------------ Sidebar filters
with st.sidebar:
    st.markdown("### 🖥️ DC Incident Dashboard")
    st.caption(f"Analis: **{AUTHOR}**")
    st.markdown("#### Filter global")

    dmin, dmax = full["created_at"].min().date(), full["created_at"].max().date()
    date_range = st.date_input("Periode tiket dibuat", value=(dmin, dmax), min_value=dmin, max_value=dmax)
    ticket_types = st.multiselect("Tipe tiket", TYPE_ORDER, default=TYPE_ORDER)
    severities = st.multiselect("Severity", SEV_ORDER, default=SEV_ORDER)
    halls = st.multiselect("Data hall", sorted(full["hall_id"].unique()), default=sorted(full["hall_id"].unique()))
    categories = st.multiselect("Kategori", sorted(full["category"].unique()), default=sorted(full["category"].unique()))
    st.divider()
    st.caption(f"Data: {len(full):,} tiket · {dmin:%d %b %Y} – {dmax:%d %b %Y}")
    st.caption("Halaman *Insights* selalu memakai seluruh data.")

if not (isinstance(date_range, (tuple, list)) and len(date_range) == 2):
    st.info("Pilih tanggal akhir pada filter 'Periode tiket dibuat' di sidebar.")
    st.stop()

filtered = apply_filters(full, date_range[0], date_range[1], ticket_types, severities, halls, categories)


def _page(module):
    def run() -> None:
        if filtered.empty and module is not insights:
            st.warning("Tidak ada tiket yang cocok dengan filter saat ini. Longgarkan filter di sidebar.")
            return
        module.render(filtered, full, snapshot)
    return run


pages = [
    st.Page(_page(ops_summary), title="Ops Summary", icon="🖥️", url_path="ops-summary", default=True),
    st.Page(_page(failure_analysis), title="Failure Analysis", icon="🔧", url_path="failure-analysis"),
    st.Page(_page(sla_shift), title="SLA & Shift", icon="⏱️", url_path="sla-shift"),
    st.Page(_page(spare_parts), title="Spare Parts Impact", icon="📦", url_path="spare-parts"),
    st.Page(_page(rca), title="RCA", icon="🧭", url_path="rca"),
    st.Page(_page(customer_impact), title="Customer Impact", icon="🚨", url_path="customer-impact"),
    st.Page(_page(insights), title="Insights & Rekomendasi", icon="💡", url_path="insights"),
    st.Page(_page(data_explorer), title="Data Explorer", icon="🗂️", url_path="data-explorer"),
]
st.navigation(pages).run()
