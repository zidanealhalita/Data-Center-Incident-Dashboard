"""Page 5 - Root Cause Analysis and repeat incidents."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import metrics as M
from src import theme as T


def render(df: pd.DataFrame, full: pd.DataFrame, snapshot: pd.Timestamp) -> None:
    T.page_header("🧭 Root Cause Analysis", "Root cause terbanyak dan insiden berulang", df)
    inc = df[df["ticket_type"] == "Incident"]
    if inc.empty:
        st.info("Tidak ada tiket bertipe Incident pada filter ini. Ubah filter 'Tipe tiket' di sidebar.")
        return
    st.caption("Halaman ini hanya memakai tiket bertipe **Incident**. Definisi `repeat_incident` mengikuti kolom pada dataset "
               "(tidak ada aturan pembentuknya di data, jadi diperlakukan apa adanya).")

    pending = inc[inc["root_cause"] == "Pending RCA"]
    repeat = inc[inc["repeat_incident"]]
    k = st.columns(4)
    k[0].metric("Insiden dianalisis", T.fmt_int(len(inc)), border=True)
    k[1].metric("Jenis root cause", T.fmt_int(inc["root_cause"].nunique()), border=True)
    k[2].metric("Insiden berulang", T.fmt_int(len(repeat)), border=True,
                help=f"{len(repeat) / len(inc):.1%} dari insiden.")
    k[3].metric("RCA belum selesai", T.fmt_int(len(pending)), border=True,
                help=f"Root cause = 'Pending RCA' · {len(pending) / len(inc):.1%} dari insiden.")

    # ------------------------------------------------------------------ Top root causes
    st.subheader("Root cause terbanyak")
    top_n = st.slider("Tampilkan top N root cause", 5, 30, 15)
    rc = inc["root_cause"].value_counts().head(top_n).reset_index()
    rc.columns = ["root_cause", "insiden"]
    rc["share"] = rc["insiden"] / len(inc)
    rc["Jenis"] = np.where(rc["root_cause"] == "Pending RCA", "Pending RCA (belum diketahui)", "Root cause teridentifikasi")
    fig = px.bar(rc, x="insiden", y="root_cause", orientation="h", color="Jenis", text="insiden",
                 color_discrete_map={"Root cause teridentifikasi": T.BLUE, "Pending RCA (belum diketahui)": T.NEUTRAL},
                 custom_data=["share"],
                 labels={"insiden": "Jumlah insiden", "root_cause": ""})
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="<b>%{y}</b><br>%{x} insiden (%{customdata[0]:.1%})<extra></extra>")
    T.order_hbar(fig, rc["root_cause"].tolist())
    T.pad_x(fig, rc["insiden"].max(), 1.1)
    T.show(T.style(fig, max(360, 26 * top_n + 90)))

    left, right = st.columns(2)
    with left:
        st.markdown("**Root cause per kategori**")
        tm = inc.groupby(["category", "root_cause"]).size().reset_index(name="insiden")
        fig = px.treemap(tm, path=["category", "root_cause"], values="insiden", color="category",
                         color_discrete_map=T.CATEGORY_COLORS)
        fig.update_traces(root_color="rgba(0,0,0,0)", textfont=dict(size=13),
                          hovertemplate="<b>%{label}</b><br>%{value} insiden<extra></extra>",
                          marker_line_color="white", marker_line_width=2)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        T.show(fig.update_layout(height=420, paper_bgcolor="rgba(0,0,0,0)"), key="rca_treemap")
    with right:
        st.markdown("**Root cause teratas per komponen**")
        comp = inc["component"].value_counts().head(8).index.tolist()
        pick = st.selectbox("Komponen", comp, index=0)
        sub = inc[inc["component"] == pick]["root_cause"].value_counts().head(8).reset_index()
        sub.columns = ["root_cause", "insiden"]
        fig = px.bar(sub, x="insiden", y="root_cause", orientation="h", text="insiden",
                     color_discrete_sequence=[T.BLUE], labels={"insiden": "Jumlah insiden", "root_cause": ""})
        fig.update_yaxes(autorange="reversed")
        fig.update_traces(textposition="outside", cliponaxis=False)
        T.show(T.style(fig, 340, legend=False), key="rca_component")

    st.divider()

    # ------------------------------------------------------------------ Repeat incidents
    st.subheader("Insiden berulang")
    left, right = st.columns(2)
    with left:
        st.markdown("**Tingkat berulang per root cause** (min. 20 insiden)")
        rr = inc.groupby("root_cause").agg(insiden=("ticket_id", "count"), berulang=("repeat_incident", "sum"))
        rr = rr[rr["insiden"] >= 20]
        rr["pct"] = rr["berulang"] / rr["insiden"] * 100
        rr = rr.sort_values("pct", ascending=False).head(12).reset_index()
        overall = len(repeat) / len(inc) * 100
        fig = px.bar(rr, x="pct", y="root_cause", orientation="h", text=rr["pct"].map("{:.1f}%".format),
                     custom_data=["berulang", "insiden"], color_discrete_sequence=[T.ORANGE],
                     labels={"pct": "% insiden berulang", "root_cause": ""})
        fig.update_traces(textposition="outside", cliponaxis=False,
                          hovertemplate="<b>%{y}</b><br>%{x:.1f}% (%{customdata[0]} dari %{customdata[1]})<extra></extra>")
        fig.update_yaxes(autorange="reversed")
        T.pad_x(fig, max(rr["pct"].max(), overall), 1.2)
        fig.add_shape(type="line", x0=overall, x1=overall, y0=0, y1=1, yref="paper",
                      line=dict(color=T.TEXT_2, width=1.5, dash="dot"))
        fig.add_annotation(x=overall, y=1, yref="paper", text=f"Rata-rata {overall:.1f}%", showarrow=False,
                           xanchor="left", yanchor="bottom", font=dict(size=12, color=T.TEXT_2))
        T.show(T.style(fig, 420, legend=False), key="rca_repeat_rate")
    with right:
        st.markdown("**Jumlah insiden berulang per root cause**")
        rc2 = repeat["root_cause"].value_counts().head(12).reset_index()
        rc2.columns = ["root_cause", "berulang"]
        fig = px.bar(rc2, x="berulang", y="root_cause", orientation="h", text="berulang",
                     color_discrete_sequence=[T.BLUE], labels={"berulang": "Insiden berulang", "root_cause": ""})
        fig.update_yaxes(autorange="reversed")
        fig.update_traces(textposition="outside", cliponaxis=False)
        T.show(T.style(fig, 420, legend=False), key="rca_repeat_count")
    st.caption("Tingkat berulang tinggi dengan jumlah kecil bisa kebetulan; cek kolom 'insiden' di tooltip sebelum menyimpulkan.")

    st.markdown("**Hotspot berulang: kombinasi rack × komponen dengan ≥ 2 insiden berulang**")
    hot = (repeat.groupby(["rack_id", "component"])
           .agg(berulang=("ticket_id", "count"),
                root_cause_utama=("root_cause", lambda s: s.value_counts().index[0]),
                terakhir=("created_at", "max"))
           .query("berulang >= 2").sort_values(["berulang", "terakhir"], ascending=False).reset_index())
    if hot.empty:
        st.info("Tidak ada kombinasi rack × komponen dengan ≥ 2 insiden berulang pada filter ini.")
    else:
        st.dataframe(hot, hide_index=True, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Insiden berulang per komponen**")
        cp = inc.groupby("component").agg(insiden=("ticket_id", "count"), berulang=("repeat_incident", "sum"))
        cp = cp[cp["insiden"] >= 20]
        cp["% berulang"] = (cp["berulang"] / cp["insiden"] * 100).round(1)
        st.dataframe(cp.sort_values("% berulang", ascending=False).head(10), width="stretch")
    with c2:
        st.markdown("**Berulang vs tidak berulang**")
        g = M.group_summary(inc.assign(jenis=np.where(inc["repeat_incident"], "Berulang", "Tidak berulang")), "jenis")
        st.dataframe(g[["tickets", "mtta_mean", "mttr_mean", "mttr_median"]].round(0).rename(
            columns={"tickets": "insiden", "mtta_mean": "MTTA rata2", "mttr_mean": "MTTR rata2",
                     "mttr_median": "MTTR median"}), width="stretch")

    st.divider()

    # ------------------------------------------------------------------ Pending RCA
    st.subheader("Tindak lanjut RCA (Pending RCA)")
    if pending.empty:
        st.success("Tidak ada insiden dengan status root cause 'Pending RCA' pada filter ini.")
        return
    left, right = st.columns(2)
    with left:
        pm = pending.groupby("month").size().reset_index(name="pending")
        fig = go.Figure(go.Bar(x=pm["month"], y=pm["pending"], marker_color=T.NEUTRAL,
                               hovertemplate="%{x|%b %Y}<br>%{y} insiden<extra></extra>"))
        fig.update_traces(marker_line_color="white", marker_line_width=1.5)
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_yaxes(title="Insiden Pending RCA")
        st.markdown("**Pending RCA per bulan**")
        T.show(T.style(fig, 300, legend=False), key="rca_pending_month")
    with right:
        st.markdown("**Pending RCA per severity dan komponen**")
        sv = pending["severity"].value_counts().sort_index()
        st.write(", ".join(f"{s}: {n}" for s, n in sv.items()))
        pc = pending["component"].value_counts().head(6).reset_index()
        pc.columns = ["komponen", "insiden"]
        st.dataframe(pc, hide_index=True, width="stretch")
