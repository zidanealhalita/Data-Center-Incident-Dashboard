"""Page 3 - SLA & Shift performance."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import metrics as M
from src import theme as T
from src.data import SEV_ORDER, SHIFT_ORDER


def _grouped_breach_chart(summary: pd.DataFrame, order: list[str], height: int = 340) -> go.Figure:
    s = summary.reindex(order)
    fig = go.Figure()
    fig.add_bar(x=s.index, y=s["ack_breach_rate"] * 100, name="Acknowledge", marker_color=T.BLUE,
                customdata=np.stack([s["ack_breaches"], s["tickets"]], axis=-1),
                hovertemplate="%{x}<br>Ack breach %{y:.1f}% (%{customdata[0]} dari %{customdata[1]})<extra></extra>")
    fig.add_bar(x=s.index, y=s["resolve_breach_rate"] * 100, name="Resolve", marker_color=T.ORANGE,
                customdata=np.stack([s["resolve_breaches"], s["resolved"]], axis=-1),
                hovertemplate="%{x}<br>Resolve breach %{y:.1f}% (%{customdata[0]} dari %{customdata[1]})<extra></extra>")
    fig.update_traces(texttemplate="%{y:.1f}%", textposition="outside", cliponaxis=False,
                      marker_line_color="white", marker_line_width=1.5)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="% tiket melanggar SLA", rangemode="tozero")
    return T.style(fig, height)


def _heatmap(pivot: pd.DataFrame, fmt: str, hover_label: str) -> go.Figure:
    z = pivot.values.astype(float)
    zmax = np.nanmax(z) if np.isfinite(z).any() and np.nanmax(z) > 0 else 1
    fig = go.Figure(go.Heatmap(z=z, x=pivot.columns, y=pivot.index, colorscale=T.HEAT_SCALE, showscale=False,
                               xgap=3, ygap=3, hovertemplate="%{y} · %{x}<br>" + hover_label + ": %{z}<extra></extra>"))
    for i, r in enumerate(pivot.index):
        for j, c in enumerate(pivot.columns):
            v = z[i, j]
            if np.isnan(v):
                continue
            fig.add_annotation(x=c, y=r, text=fmt.format(v), showarrow=False,
                               font=dict(color="white" if v / zmax > 0.5 else T.TEXT, size=13))
    fig.update_yaxes(autorange="reversed")
    return fig


def render(df: pd.DataFrame, full: pd.DataFrame, snapshot: pd.Timestamp) -> None:
    T.page_header("⏱️ SLA & Shift", "Performa SLA per shift dan per severity", df)
    st.caption("Shift ditentukan dari jam tiket dibuat: Morning 07–14, Afternoon 15–22, Night 23–06. "
               "Pelanggaran Ack = MTTA ≥ target; pelanggaran Resolve dihitung dari tiket resolved saja.")

    shifts = [s for s in SHIFT_ORDER if s in set(df["shift"])]
    sevs = [s for s in SEV_ORDER if s in set(df["severity"])]
    by_shift = M.group_summary(df, "shift")
    by_sev = M.group_summary(df, "severity")

    # ------------------------------------------------------------------ Shift
    st.subheader("Performa per shift")
    cols = st.columns(len(shifts))
    for c, sh in zip(cols, shifts):
        r = by_shift.loc[sh]
        c.metric(f"{sh}", f"MTTA {r['mtta_mean']:,.0f} mnt", border=True,
                 help=f"{int(r['tickets']):,} tiket · MTTR {r['mttr_mean']:,.0f} mnt · "
                      f"ack breach {r['ack_breach_rate']:.1%} · resolve breach {r['resolve_breach_rate']:.1%}")
        c.caption(f"{int(r['tickets']):,} tiket · MTTR {r['mttr_mean']:,.0f} mnt · "
                  f"ack breach {r['ack_breach_rate']:.1%}")

    left, right = st.columns(2)
    with left:
        st.markdown("**MTTA dan MTTR per shift (menit)**")
        s = by_shift.reindex(shifts)
        fig = go.Figure()
        fig.add_bar(x=s.index, y=s["mtta_mean"], name="MTTA", marker_color=T.BLUE)
        fig.add_bar(x=s.index, y=s["mttr_mean"], name="MTTR", marker_color=T.ORANGE)
        fig.update_traces(texttemplate="%{y:,.0f}", textposition="outside", cliponaxis=False,
                          marker_line_color="white", marker_line_width=1.5)
        fig.update_layout(barmode="group")
        fig.update_yaxes(title="Menit", rangemode="tozero")
        T.show(T.style(fig, 340))
    with right:
        st.markdown("**Tingkat pelanggaran SLA per shift**")
        T.show(_grouped_breach_chart(by_shift, shifts), key="breach_shift")

    # Night vs Morning statistical check
    if {"Night", "Morning"} <= set(shifts):
        n, m = df[df["shift"] == "Night"], df[df["shift"] == "Morning"]
        p_ack = M.two_proportion_pvalue(int(n["ack_sla_breached"].sum()), len(n),
                                        int(m["ack_sla_breached"].sum()), len(m))
        p_mtta = M.mann_whitney_pvalue(n["mtta_min"], m["mtta_min"])
        st.info(f"**Night vs Morning**: MTTA {n['mtta_min'].mean():,.0f} vs {m['mtta_min'].mean():,.0f} mnt "
                f"({T.pvalue_text(p_mtta)}, Mann-Whitney); ack breach {n['ack_sla_breached'].mean():.1%} vs "
                f"{m['ack_sla_breached'].mean():.1%} ({T.pvalue_text(p_ack)}, uji proporsi).")

    st.divider()

    # ------------------------------------------------------------------ Severity
    st.subheader("Performa per severity")
    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Tingkat pelanggaran SLA per severity**")
        T.show(_grouped_breach_chart(by_sev, sevs, 380), key="breach_sev")
    with right:
        st.markdown("**Target SLA vs realisasi**")
        tgt = df.groupby("severity").agg(target_ack=("sla_ack_target_min", "first"),
                                         target_resolve=("sla_resolve_target_min", "first"))
        t = by_sev.join(tgt).reindex(sevs)
        tbl = pd.DataFrame({
            "Tiket": t["tickets"],
            "Target Ack (mnt)": t["target_ack"],
            "MTTA median": t["mtta_median"].round(0),
            "Ack breach": t["ack_breaches"],
            "Target Resolve (mnt)": t["target_resolve"],
            "MTTR median": t["mttr_median"].round(0),
            "MTTR rata2": t["mttr_mean"].round(0),
            "Resolve breach": t["resolve_breaches"],
            "% Resolve breach": (t["resolve_breach_rate"] * 100).round(1),
        }).T
        tbl.index.name = None
        tbl.columns.name = None
        st.dataframe(tbl, width="stretch")
        s1 = by_sev.loc["Sev-1"] if "Sev-1" in by_sev.index else None
        if s1 is not None and s1["resolved"] > 0:
            st.caption(f"Sev-1: {int(s1['resolve_breaches'])} dari {int(s1['resolved'])} tiket resolved "
                       f"melewati target resolve ({s1['resolve_breach_rate']:.1%}). "
                       "Jumlah kejadian kecil, sehingga persentase mudah berayun.")

    st.divider()

    # ------------------------------------------------------------------ Shift x severity
    st.subheader("Shift × severity")
    left, right = st.columns(2)
    with left:
        st.markdown("**Ack breach rate (%)**")
        pv = df.pivot_table(index="shift", columns="severity", values="ack_sla_breached", aggfunc="mean")
        pv = pv.reindex(index=shifts, columns=sevs) * 100
        T.show(T.style(_heatmap(pv, "{:.1f}%", "Ack breach %"), 260, legend=False), key="hm_ack")
    with right:
        st.markdown("**Jumlah Resolve breach**")
        pv = df[df["resolved"]].pivot_table(index="shift", columns="severity", values="resolve_sla_breached",
                                            aggfunc="sum").reindex(index=shifts, columns=sevs)
        T.show(T.style(_heatmap(pv, "{:.0f}", "Resolve breach"), 260, legend=False), key="hm_res")

    st.markdown("**Volume tiket per jam pembuatan**")
    hourly = df.groupby(["hour", "shift"]).size().reset_index(name="tickets")
    fig = px.bar(hourly, x="hour", y="tickets", color="shift", color_discrete_map=T.SHIFT_COLORS,
                 category_orders={"shift": SHIFT_ORDER}, labels={"hour": "Jam (0–23)", "tickets": "Jumlah tiket", "shift": ""})
    fig.update_traces(marker_line_color="white", marker_line_width=1)
    fig.update_xaxes(dtick=1)
    T.show(T.style(fig, 300))

    # ------------------------------------------------------------------ Technician
    with st.expander("Performa per teknisi (konteks tambahan)"):
        tech = M.group_summary(df, "technician_id")
        view = tech[["tickets", "mtta_mean", "mttr_mean", "mttr_median", "ack_breaches", "resolve_breaches"]].round(0)
        view.columns = ["Tiket", "MTTA rata2", "MTTR rata2", "MTTR median", "Ack breach", "Resolve breach"]
        st.dataframe(view.sort_values("Tiket", ascending=False), width="stretch")
        st.caption("Perbandingan antar teknisi tidak 'apple-to-apple': campuran severity, komponen dan "
                   "ketersediaan part tiap teknisi berbeda. Gunakan untuk melihat beban kerja, bukan menilai individu.")
