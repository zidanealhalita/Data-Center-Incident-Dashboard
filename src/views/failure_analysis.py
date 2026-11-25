"""Page 2 - Failure Analysis (Pareto of components, problem racks)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import metrics as M
from src import theme as T


def _rack_heatmap(inc: pd.DataFrame) -> go.Figure:
    pivot = (inc.groupby(["hall_id", "rack_no"]).size().unstack(fill_value=0)
             .reindex(columns=range(1, 11), fill_value=0).sort_index())
    z = pivot.values
    zmax = max(z.max(), 1)
    fig = go.Figure(go.Heatmap(
        z=z, x=[f"R{c:02d}" for c in pivot.columns], y=pivot.index, colorscale=T.HEAT_SCALE,
        xgap=3, ygap=3, showscale=False,
        hovertemplate="%{y} · %{x}<br>%{z} insiden<extra></extra>"))
    for i, hall in enumerate(pivot.index):
        for j, rack in enumerate(pivot.columns):
            val = int(z[i, j])
            fig.add_annotation(x=f"R{rack:02d}", y=hall, text=str(val), showarrow=False,
                               font=dict(color="white" if val / zmax > 0.5 else T.TEXT, size=13))
    fig.update_yaxes(autorange="reversed")
    return fig


def render(df: pd.DataFrame, full: pd.DataFrame, snapshot: pd.Timestamp) -> None:
    T.page_header("🔧 Failure Analysis", "Komponen penyebab insiden dan rack yang sering bermasalah", df)
    inc = df[df["ticket_type"] == "Incident"]
    if inc.empty:
        st.info("Tidak ada tiket bertipe Incident pada filter ini. Ubah filter 'Tipe tiket' di sidebar.")
        return
    st.caption("Halaman ini hanya memakai tiket bertipe **Incident**. Preventive Maintenance dan Change Request "
               "adalah pekerjaan terjadwal, bukan kegagalan.")

    # ------------------------------------------------------------------ Pareto
    st.subheader("Pareto komponen penyebab insiden")
    mode = st.radio("Ukuran", ["Jumlah insiden", "Total jam penyelesaian"], horizontal=True,
                    help="'Total jam penyelesaian' menjumlahkan time_to_resolve tiap insiden resolved — "
                         "menunjukkan komponen yang paling banyak menyita waktu tim.")
    if mode == "Jumlah insiden":
        p = M.pareto(inc, "component")
        unit = "insiden"
    else:
        p = M.pareto(inc[inc["resolved"]], "component", "time_to_resolve_min", scale=1 / 60)
        unit = "jam"
    p = p.reset_index()
    p["Kelompok"] = p["vital_few"].map({True: "Penyumbang 80% teratas", False: "Sisanya"})
    n_vital = int(p["vital_few"].sum())

    fig = px.bar(p, x="value", y="component", orientation="h", color="Kelompok",
                 color_discrete_map={"Penyumbang 80% teratas": T.BLUE, "Sisanya": T.MUTED},
                 category_orders={"Kelompok": ["Penyumbang 80% teratas", "Sisanya"]},
                 custom_data=["share", "cum_share"],
                 labels={"value": mode, "component": ""})
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f} " + unit +
                      "<br>Porsi %{customdata[0]:.1%} · kumulatif %{customdata[1]:.1%}<extra></extra>")
    T.order_hbar(fig, p["component"].tolist())
    T.pad_x(fig, p["value"].max(), 1.05)
    T.show(T.style(fig, max(380, 24 * len(p) + 80)))
    top = p.iloc[0]
    st.info(f"**{n_vital} dari {len(p)} komponen** menyumbang 80% dari total ({mode.lower()}). "
            f"Teratas: **{top['component']}** ({top['share']:.1%}).")

    # ------------------------------------------------------------------ Components table
    with st.expander("Detail per komponen"):
        comp = M.group_summary(inc, "component")
        extra = inc.groupby("component").agg(
            outage=("customer_impact", lambda s: int((s == "Outage").sum())),
            repeat=("repeat_incident", "sum"),
            sev12=("severity", lambda s: int(s.isin(["Sev-1", "Sev-2"]).sum())),
        )
        tbl = comp.join(extra).sort_values("tickets", ascending=False)
        st.dataframe(
            tbl[["tickets", "sev12", "outage", "repeat", "mtta_mean", "mttr_mean", "mttr_median",
                 "ack_breaches", "resolve_breaches"]].rename(columns={
                "tickets": "insiden", "sev12": "Sev-1/2", "repeat": "berulang", "mtta_mean": "MTTA rata2",
                "mttr_mean": "MTTR rata2", "mttr_median": "MTTR median", "ack_breaches": "ack breach",
                "resolve_breaches": "resolve breach"}).round(0),
            width="stretch")

    st.divider()

    # ------------------------------------------------------------------ Racks
    st.subheader("Rack yang paling sering bermasalah")
    racks = inc.groupby(["rack_id", "hall_id"]).agg(
        insiden=("ticket_id", "count"),
        sev12=("severity", lambda s: int(s.isin(["Sev-1", "Sev-2"]).sum())),
        berulang=("repeat_incident", "sum"),
        outage=("customer_impact", lambda s: int((s == "Outage").sum())),
    ).reset_index().sort_values("insiden", ascending=False)

    left, right = st.columns([3, 2])
    with left:
        top_n = st.slider("Tampilkan top N rack", 5, 20, 10)
        top_racks = racks.head(top_n)
        fig = px.bar(top_racks, x="insiden", y="rack_id", orientation="h", color="hall_id",
                     color_discrete_map=T.HALL_COLORS, text="insiden",
                     category_orders={"hall_id": ["DH1", "DH2", "DH3", "DH4"]},
                     custom_data=["sev12", "berulang", "outage"],
                     labels={"insiden": "Jumlah insiden", "rack_id": "", "hall_id": "Hall"})
        fig.update_traces(textposition="outside", cliponaxis=False,
                          hovertemplate="<b>%{y}</b><br>%{x} insiden<br>Sev-1/2: %{customdata[0]}"
                                        "<br>Berulang: %{customdata[1]}<br>Outage: %{customdata[2]}<extra></extra>")
        T.order_hbar(fig, top_racks["rack_id"].tolist())
        T.pad_x(fig, top_racks["insiden"].max(), 1.12)
        T.show(T.style(fig, max(340, 30 * top_n + 80)))
    with right:
        st.markdown("**Peta panas insiden per hall dan rack**")
        T.show(T.style(_rack_heatmap(inc), 250, legend=False))
        med = racks["insiden"].median()
        mx = racks.iloc[0]
        st.caption(f"Median {med:.0f} insiden per rack; tertinggi {mx['rack_id']} dengan {mx['insiden']} "
                   f"({mx['insiden'] / med:.1f}× median).")

    hall = inc.groupby("hall_id").agg(
        insiden=("ticket_id", "count"), rack=("rack_id", "nunique"),
        sev12=("severity", lambda s: int(s.isin(["Sev-1", "Sev-2"]).sum())),
        berulang=("repeat_incident", "sum"),
        outage=("customer_impact", lambda s: int((s == "Outage").sum())))
    hall["insiden_per_rack"] = (hall["insiden"] / hall["rack"]).round(1)
    hall["% berulang"] = (hall["berulang"] / hall["insiden"] * 100).round(1)
    st.markdown("**Ringkasan per data hall**")
    st.dataframe(hall.rename(columns={"sev12": "Sev-1/2"}), width="stretch")

    st.markdown("**Drill-down rack**")
    pick = st.selectbox("Pilih rack", racks["rack_id"].tolist(), index=0)
    sub = inc[inc["rack_id"] == pick]
    c1, c2 = st.columns(2)
    for col, field, title in ((c1, "component", "Komponen"), (c2, "root_cause", "Root cause")):
        with col:
            vc = sub[field].value_counts().head(8).reset_index()
            vc.columns = [field, "insiden"]
            fig = px.bar(vc, x="insiden", y=field, orientation="h", text="insiden",
                         labels={"insiden": f"Insiden di {pick}", field: ""},
                         color_discrete_sequence=[T.BLUE])
            fig.update_yaxes(autorange="reversed")
            fig.update_traces(textposition="outside", cliponaxis=False)
            st.markdown(f"{title} teratas di **{pick}** ({len(sub)} insiden)")
            T.show(T.style(fig, 300, legend=False), key=f"drill_{field}")
