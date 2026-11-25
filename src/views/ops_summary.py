"""Page 1 - Ops Summary."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import metrics as M
from src import theme as T
from src.data import SEV_ORDER, TYPE_ORDER


def render(df: pd.DataFrame, full: pd.DataFrame, snapshot: pd.Timestamp) -> None:
    T.page_header("🖥️ Ops Summary", "Gambaran kinerja operasional tiket hardware data center", df)
    k = M.kpis(df)

    r1 = st.columns(4)
    r1[0].metric("Total tiket", T.fmt_int(k["total"]), border=True,
                 help=f"{k['incidents']:,} bertipe Incident; sisanya Preventive Maintenance dan Change Request.")
    r1[1].metric("MTTA (rata-rata)", T.fmt_min(k["mtta_mean"]), border=True,
                 help="Mean Time To Acknowledge: created_at → acknowledged_at, semua tiket.")
    r1[2].metric("MTTR (rata-rata)", T.fmt_min(k["mttr_mean"]), border=True,
                 help="Mean Time To Resolve: created_at → resolved_at, hanya tiket yang sudah resolved.")
    r1[3].metric("Tiket masih terbuka", T.fmt_int(k["open"]), border=True,
                 help="Status bukan 'Resolved' (Pending Parts / In Progress).")

    r2 = st.columns(4)
    r2[0].metric("Kepatuhan SLA Acknowledge", T.fmt_pct(k["ack_compliance"]), border=True,
                 help=f"{k['ack_breaches']:,} tiket melewati target acknowledge.")
    r2[1].metric("Kepatuhan SLA Resolve", T.fmt_pct(k["res_compliance"]), border=True,
                 help=f"{k['res_breaches']:,} dari {k['resolved']:,} tiket resolved melewati target resolve. "
                      "Tiket terbuka tidak dihitung.")
    r2[2].metric("MTTA (median)", T.fmt_min(k["mtta_median"]), border=True,
                 help="Median lebih mewakili kondisi 'tipikal' karena distribusi waktu condong ke kanan.")
    r2[3].metric("MTTR (median)", T.fmt_min(k["mttr_median"]), border=True,
                 help="Rata-rata MTTR ditarik naik oleh sebagian kecil tiket yang menunggu spare part.")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Volume tiket per bulan")
        vol = df.groupby(["month", "ticket_type"]).size().reset_index(name="tickets")
        fig = px.bar(vol, x="month", y="tickets", color="ticket_type",
                     color_discrete_map=T.TYPE_COLORS, category_orders={"ticket_type": TYPE_ORDER},
                     labels={"month": "", "tickets": "Jumlah tiket", "ticket_type": ""})
        fig.update_traces(marker_line_color="white", marker_line_width=1.5)
        fig.update_xaxes(tickformat="%b %Y")
        T.show(T.style(fig, 360))

    monthly = M.group_summary(df, "month").reset_index()
    with right:
        st.subheader("MTTA dan MTTR per bulan (menit)")
        fig = go.Figure()
        fig.add_scatter(x=monthly["month"], y=monthly["mttr_mean"], name="MTTR", mode="lines+markers",
                        line=dict(color=T.BLUE, width=2), marker=dict(size=8, line=dict(color="white", width=2)),
                        hovertemplate="%{x|%b %Y}<br>MTTR %{y:,.0f} mnt<extra></extra>")
        fig.add_scatter(x=monthly["month"], y=monthly["mtta_mean"], name="MTTA", mode="lines+markers",
                        line=dict(color=T.ORANGE, width=2), marker=dict(size=8, line=dict(color="white", width=2)),
                        hovertemplate="%{x|%b %Y}<br>MTTA %{y:,.0f} mnt<extra></extra>")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_yaxes(title="Menit", rangemode="tozero")
        fig.update_layout(hovermode="x unified")
        T.show(T.style(fig, 360))

    left, right = st.columns(2)
    with left:
        st.subheader("Tingkat pelanggaran SLA per bulan")
        fig = go.Figure()
        fig.add_scatter(x=monthly["month"], y=monthly["ack_breach_rate"] * 100, name="Acknowledge",
                        mode="lines+markers", line=dict(color=T.BLUE, width=2),
                        marker=dict(size=8, line=dict(color="white", width=2)),
                        hovertemplate="%{x|%b %Y}<br>Ack breach %{y:.1f}%<extra></extra>")
        fig.add_scatter(x=monthly["month"], y=monthly["resolve_breach_rate"] * 100, name="Resolve",
                        mode="lines+markers", line=dict(color=T.ORANGE, width=2),
                        marker=dict(size=8, line=dict(color="white", width=2)),
                        hovertemplate="%{x|%b %Y}<br>Resolve breach %{y:.1f}%<extra></extra>")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_yaxes(title="% tiket melanggar SLA", rangemode="tozero")
        fig.update_layout(hovermode="x unified")
        T.show(T.style(fig, 340))

    with right:
        st.subheader("Komposisi tiket")
        tab_sev, tab_cat = st.tabs(["Per severity", "Per kategori"])
        with tab_sev:
            sev = df["severity"].value_counts().reindex(SEV_ORDER).fillna(0).reset_index()
            sev.columns = ["severity", "tickets"]
            fig = px.bar(sev, x="tickets", y="severity", orientation="h", text="tickets",
                         color="severity", color_discrete_map=T.SEV_COLORS,
                         labels={"tickets": "Jumlah tiket", "severity": ""})
            fig.update_yaxes(autorange="reversed")
            fig.update_traces(textposition="outside", cliponaxis=False)
            T.show(T.style(fig, 290, legend=False))
        with tab_cat:
            cat = df["category"].value_counts().reset_index()
            cat.columns = ["category", "tickets"]
            fig = px.bar(cat, x="tickets", y="category", orientation="h", text="tickets",
                         color="category", color_discrete_map=T.CATEGORY_COLORS,
                         labels={"tickets": "Jumlah tiket", "category": ""})
            fig.update_yaxes(autorange="reversed")
            fig.update_traces(textposition="outside", cliponaxis=False)
            T.show(T.style(fig, 290, legend=False))

    st.divider()
    st.subheader("Tiket yang masih terbuka")
    open_df = df[df["is_open"]].copy()
    if open_df.empty:
        st.success("Tidak ada tiket terbuka pada filter yang dipilih.")
        return
    open_df["usia_jam"] = ((snapshot - open_df["created_at"]).dt.total_seconds() / 3600).round(1)
    cols = ["ticket_id", "created_at", "severity", "category", "component", "rack_id", "status",
            "part_status", "part_wait_min", "usia_jam", "sla_resolve_target_min"]
    st.dataframe(
        open_df[cols].rename(columns={
            "part_status": "kondisi_part", "part_wait_min": "tunggu_part_mnt",
            "usia_jam": "usia_jam_saat_snapshot", "sla_resolve_target_min": "target_resolve_mnt"}),
        hide_index=True, width="stretch",
    )
    st.caption(f"Usia dihitung sampai snapshot data terakhir ({snapshot:%d %b %Y %H:%M}), "
               "bukan sampai hari ini. Tiket 'Pending Parts' menunggu spare part sehingga MTTR-nya belum terhitung.")
