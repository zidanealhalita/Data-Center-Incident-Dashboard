"""Extra page - Customer impact and escalation."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src import metrics as M
from src import theme as T
from src.data import SEV_ORDER


def render(df: pd.DataFrame, full: pd.DataFrame, snapshot: pd.Timestamp) -> None:
    T.page_header("🚨 Customer Impact & Eskalasi", "Insiden yang berdampak ke pelanggan dan ke mana eskalasinya", df)
    inc = df[df["ticket_type"] == "Incident"]
    if inc.empty:
        st.info("Tidak ada tiket bertipe Incident pada filter ini.")
        return

    outage = inc[inc["customer_impact"] == "Outage"]
    degraded = inc[inc["customer_impact"] == "Degraded"]
    esc = inc[inc["escalated_to"] != "Tidak dieskalasi"]

    k = st.columns(4)
    k[0].metric("Outage", T.fmt_int(len(outage)), border=True, help=f"{len(outage) / len(inc):.1%} dari insiden.")
    k[1].metric("Degraded", T.fmt_int(len(degraded)), border=True, help=f"{len(degraded) / len(inc):.1%} dari insiden.")
    k[2].metric("Insiden dieskalasi", T.fmt_int(len(esc)), border=True, help=f"{len(esc) / len(inc):.1%} dari insiden.")
    k[3].metric("MTTR Outage (rata2)", T.fmt_min(outage.loc[outage["resolved"], "time_to_resolve_min"].mean()), border=True,
                help="Hanya tiket Outage yang sudah resolved.")

    left, right = st.columns(2)
    with left:
        st.subheader("Dampak pelanggan per severity")
        imp = inc[inc["customer_impact"] != "Tidak ada"].groupby(["severity", "customer_impact"]).size().reset_index(name="insiden")
        fig = px.bar(imp, x="severity", y="insiden", color="customer_impact", text="insiden",
                     color_discrete_map=T.IMPACT_COLORS, category_orders={"severity": SEV_ORDER},
                     labels={"severity": "", "insiden": "Jumlah insiden", "customer_impact": ""})
        fig.update_traces(marker_line_color="white", marker_line_width=1.5)
        T.show(T.style(fig, 340))
    with right:
        st.subheader("Dampak pelanggan per bulan")
        mi = inc[inc["customer_impact"] != "Tidak ada"].groupby(["month", "customer_impact"]).size().reset_index(name="insiden")
        fig = px.bar(mi, x="month", y="insiden", color="customer_impact", color_discrete_map=T.IMPACT_COLORS,
                     labels={"month": "", "insiden": "Jumlah insiden", "customer_impact": ""})
        fig.update_traces(marker_line_color="white", marker_line_width=1.5)
        fig.update_xaxes(tickformat="%b %Y")
        T.show(T.style(fig, 340))

    left, right = st.columns(2)
    with left:
        st.subheader("Komponen penyebab Outage")
        oc = outage["component"].value_counts().head(10).reset_index()
        oc.columns = ["component", "outage"]
        if oc.empty:
            st.info("Tidak ada Outage pada filter ini.")
        else:
            fig = px.bar(oc, x="outage", y="component", orientation="h", text="outage",
                         color_discrete_sequence=[T.ORANGE], labels={"outage": "Jumlah Outage", "component": ""})
            fig.update_yaxes(autorange="reversed")
            fig.update_traces(textposition="outside", cliponaxis=False)
            T.show(T.style(fig, 340, legend=False))
    with right:
        st.subheader("Outage per data hall")
        oh = outage.groupby("hall_id").size().reindex(["DH1", "DH2", "DH3", "DH4"]).fillna(0).reset_index()
        oh.columns = ["hall_id", "outage"]
        fig = px.bar(oh, x="hall_id", y="outage", text="outage", color="hall_id", color_discrete_map=T.HALL_COLORS,
                     labels={"hall_id": "", "outage": "Jumlah Outage"})
        fig.update_traces(textposition="outside", cliponaxis=False)
        T.show(T.style(fig, 340, legend=False))

    st.divider()
    st.subheader("Eskalasi")
    if esc.empty:
        st.info("Tidak ada insiden yang dieskalasi pada filter ini.")
    else:
        left, right = st.columns([2, 3])
        with left:
            ec = esc.groupby(["escalated_to", "severity"]).size().reset_index(name="insiden")
            fig = px.bar(ec, x="insiden", y="escalated_to", color="severity", orientation="h",
                         color_discrete_map=T.SEV_COLORS, category_orders={"severity": SEV_ORDER},
                         labels={"insiden": "Jumlah insiden", "escalated_to": "", "severity": ""})
            fig.update_traces(marker_line_color="white", marker_line_width=1.5)
            T.show(T.style(fig, 300))
        with right:
            g = M.group_summary(esc, "escalated_to")
            tbl = g[["tickets", "mtta_mean", "mttr_mean", "mttr_median", "resolve_breaches"]].round(0).rename(
                columns={"tickets": "insiden", "mtta_mean": "MTTA", "mttr_mean": "MTTR", "mttr_median": "MTTR med",
                         "resolve_breaches": "breach"})
            tbl.index.name = "Tim"
            st.dataframe(tbl, width="stretch")
            st.caption("MTTA/MTTR dalam menit; breach = pelanggaran SLA Resolve.")
            st.caption("Eskalasi hanya terjadi pada Sev-1 dan Sev-2 di dataset ini.")

    st.subheader("Daftar insiden Outage")
    if not outage.empty:
        cols = ["ticket_id", "created_at", "severity", "hall_id", "rack_id", "component", "root_cause",
                "part_status", "time_to_resolve_min", "resolve_sla_breached", "escalated_to"]
        st.dataframe(outage.sort_values("created_at", ascending=False)[cols], hide_index=True, width="stretch")
