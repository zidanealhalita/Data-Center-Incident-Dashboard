"""Page 4 - Spare Parts Impact, including before/after July 2026."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import metrics as M
from src import theme as T
from src.data import PART_ORDER

DEFAULT_CUTOFF = dt.date(2026, 7, 1)


def _delta(new: float, old: float, pct: bool = False, lower_is_better: bool = True) -> str | None:
    if np.isnan(new) or np.isnan(old):
        return None
    d = (new - old) * 100 if pct else new - old
    return f"{d:+,.1f}" + (" pp" if pct else "")


def render(df: pd.DataFrame, full: pd.DataFrame, snapshot: pd.Timestamp) -> None:
    T.page_header("📦 Spare Parts Impact", "Dampak ketersediaan spare part terhadap SLA dan waktu penyelesaian", df)

    need = df[df["spare_part_required"]]
    if need.empty:
        st.info("Tidak ada tiket yang membutuhkan spare part pada filter ini.")
        return
    res = df[df["resolved"]]
    unavail = need[need["part_status"] == PART_ORDER[2]]

    # ------------------------------------------------------------------ Headline
    k = st.columns(4)
    k[0].metric("Tiket butuh part", T.fmt_int(len(need)), border=True,
                help=f"{len(need) / len(df):.1%} dari seluruh tiket pada filter.")
    k[1].metric("Part tidak tersedia", T.fmt_int(len(unavail)), border=True,
                help="Jumlah tiket yang butuh part tetapi part belum ada di stok.")
    k[2].metric("% tidak tersedia", T.fmt_pct(len(unavail) / len(need)), border=True,
                help="Dari tiket yang membutuhkan part.")
    k[3].metric("Rata-rata tunggu part", T.fmt_hours(unavail["part_wait_min"].mean()), border=True,
                help="Hanya tiket dengan part tidak tersedia.")

    by_part = M.group_summary(df, "part_status").reindex(PART_ORDER)

    st.subheader("Part tersedia vs tidak tersedia")
    left, right = st.columns(2)
    with left:
        st.markdown("**MTTR per kondisi part (menit)**")
        s = by_part.dropna(subset=["mttr_mean"])
        fig = go.Figure()
        fig.add_bar(x=s.index, y=s["mttr_median"], name="Median", marker_color=T.BLUE)
        fig.add_bar(x=s.index, y=s["mttr_mean"], name="Rata-rata", marker_color=T.ORANGE)
        fig.update_traces(texttemplate="%{y:,.0f}", textposition="outside", cliponaxis=False,
                          marker_line_color="white", marker_line_width=1.5)
        fig.update_layout(barmode="group")
        fig.update_yaxes(title="Menit", rangemode="tozero")
        T.show(T.style(fig, 340))
    with right:
        st.markdown("**Tingkat pelanggaran SLA Resolve per kondisi part**")
        s = by_part.dropna(subset=["resolve_breach_rate"])
        fig = go.Figure(go.Bar(
            x=s.index, y=s["resolve_breach_rate"] * 100, marker_color=[T.PART_COLORS[i] for i in s.index],
            customdata=np.stack([s["resolve_breaches"], s["resolved"]], axis=-1),
            hovertemplate="%{x}<br>%{y:.1f}% (%{customdata[0]} dari %{customdata[1]})<extra></extra>",
            text=[f"{v:.1f}%" for v in s["resolve_breach_rate"] * 100], textposition="outside", cliponaxis=False))
        fig.update_yaxes(title="% tiket melanggar SLA Resolve", rangemode="tozero")
        T.show(T.style(fig, 340, legend=False))

    total_breach = int(res["resolve_sla_breached"].sum())
    breach_unavail = int(res.loc[res["part_status"] == PART_ORDER[2], "resolve_sla_breached"].sum())
    if total_breach:
        st.info(f"**{breach_unavail} dari {total_breach} pelanggaran SLA Resolve ({breach_unavail / total_breach:.0%})** "
                f"terjadi pada tiket dengan part tidak tersedia, padahal tiket tersebut hanya "
                f"{len(unavail) / len(df):.1%} dari seluruh tiket.")

    left, right = st.columns(2)
    with left:
        st.markdown("**Distribusi lama tunggu part (part tidak tersedia)**")
        if len(unavail):
            fig = px.histogram(unavail, x=unavail["part_wait_min"] / 60, nbins=25,
                               labels={"x": "Lama tunggu part (jam)"}, color_discrete_sequence=[T.ORANGE])
            fig.update_traces(marker_line_color="white", marker_line_width=1)
            fig.update_layout(yaxis_title="Jumlah tiket", xaxis_title="Lama tunggu part (jam)")
            T.show(T.style(fig, 320, legend=False))
    with right:
        st.markdown("**Komponen dengan % part tidak tersedia tertinggi** (min. 20 tiket butuh part)")
        comp = need.groupby("component").agg(
            butuh=("ticket_id", "count"),
            tidak_tersedia=("part_status", lambda s: int((s == PART_ORDER[2]).sum())))
        comp = comp[comp["butuh"] >= 20]
        comp["pct"] = comp["tidak_tersedia"] / comp["butuh"] * 100
        comp = comp.sort_values("pct", ascending=False).head(10).reset_index()
        fig = px.bar(comp, x="pct", y="component", orientation="h", text=comp["pct"].map("{:.1f}%".format),
                     custom_data=["tidak_tersedia", "butuh"], color_discrete_sequence=[T.ORANGE],
                     labels={"pct": "% tiket part tidak tersedia", "component": ""})
        fig.update_traces(textposition="outside", cliponaxis=False,
                          hovertemplate="<b>%{y}</b><br>%{x:.1f}% (%{customdata[0]} dari %{customdata[1]})<extra></extra>")
        fig.update_yaxes(autorange="reversed")
        T.pad_x(fig, comp["pct"].max(), 1.2)
        T.show(T.style(fig, 320, legend=False))

    st.divider()

    # ------------------------------------------------------------------ Before / after
    st.subheader("Sebelum vs sesudah Juli 2026")
    cutoff = st.date_input(
        "Tanggal pembatas (tiket dibuat sebelum tanggal ini = 'Sebelum')",
        value=DEFAULT_CUTOFF,
        help="Default 1 Juli 2026. Periode 'Sesudah' dimulai pada tanggal ini.",
    )
    cutoff_ts = pd.Timestamp(cutoff)
    before = df[df["created_at"] < cutoff_ts]
    after = df[df["created_at"] >= cutoff_ts]
    if before.empty or after.empty:
        st.warning("Salah satu periode kosong pada filter saat ini (cek filter tanggal di sidebar atau tanggal pembatas).")
        return

    b, a = M.before_after_summary(before), M.before_after_summary(after)
    months_b = before["month"].nunique()
    months_a = after["month"].nunique()
    st.caption(f"Sebelum: {before['created_at'].min():%d %b %Y} – {before['created_at'].max():%d %b %Y} "
               f"({months_b} bulan, {len(before):,} tiket) · Sesudah: {after['created_at'].min():%d %b %Y} – "
               f"{after['created_at'].max():%d %b %Y} ({months_a} bulan, {len(after):,} tiket). "
               "Periode tidak sama panjang, jadi bandingkan rasio/rata-rata, bukan jumlah mentah.")

    m = st.columns(5)
    m[0].metric("% part tidak tersedia", T.fmt_pct(a["unavail_rate"]), border=True,
                delta=_delta(a["unavail_rate"], b["unavail_rate"], pct=True), delta_color="inverse",
                help=f"Sebelum: {T.fmt_pct(b['unavail_rate'])}")
    m[1].metric("Tunggu part (rata2)", T.fmt_hours(a["avg_part_wait_unavail"]), border=True,
                delta=None if np.isnan(a["avg_part_wait_unavail"]) or np.isnan(b["avg_part_wait_unavail"])
                else f"{(a['avg_part_wait_unavail'] - b['avg_part_wait_unavail']) / 60:+,.1f} jam",
                delta_color="inverse", help=f"Rata-rata tunggu part pada tiket part tidak tersedia. Sebelum: {T.fmt_hours(b['avg_part_wait_unavail'])}")
    m[2].metric("MTTR rata-rata", T.fmt_min(a["mttr_mean"]), border=True,
                delta=_delta(a["mttr_mean"], b["mttr_mean"]) and f"{a['mttr_mean'] - b['mttr_mean']:+,.0f} mnt",
                delta_color="inverse", help=f"Sebelum: {T.fmt_min(b['mttr_mean'])}")
    m[3].metric("MTTR median", T.fmt_min(a["mttr_median"]), border=True,
                delta=f"{a['mttr_median'] - b['mttr_median']:+,.0f} mnt", delta_color="inverse",
                help=f"Sebelum: {T.fmt_min(b['mttr_median'])}")
    m[4].metric("% Resolve SLA breach", T.fmt_pct(a["res_breach_rate"], 2), border=True,
                delta=_delta(a["res_breach_rate"], b["res_breach_rate"], pct=True), delta_color="inverse",
                help=f"Sebelum: {T.fmt_pct(b['res_breach_rate'], 2)} "
                     f"({b['res_breaches']} breach) · Sesudah: {a['res_breaches']} breach")

    # significance
    p_unavail = M.two_proportion_pvalue(a["part_unavailable"], a["part_required"],
                                        b["part_unavailable"], b["part_required"])
    p_mttr = M.mann_whitney_pvalue(after.loc[after["resolved"], "time_to_resolve_min"],
                                   before.loc[before["resolved"], "time_to_resolve_min"])
    p_breach = M.two_proportion_pvalue(a["res_breaches"], a["resolved"], b["res_breaches"], b["resolved"])
    st.caption(f"Uji signifikansi — % part tidak tersedia: {T.pvalue_text(p_unavail)} · "
               f"MTTR: {T.pvalue_text(p_mttr)} (Mann-Whitney) · % Resolve breach: {T.pvalue_text(p_breach)}.")

    # monthly trends with cutoff marker
    monthly = df.groupby("month").apply(
        lambda g: pd.Series({
            "unavail_rate": ((g["part_status"] == PART_ORDER[2]).sum() / g["spare_part_required"].sum() * 100
                             if g["spare_part_required"].sum() else np.nan),
            "mttr": g.loc[g["resolved"], "time_to_resolve_min"].mean(),
            "res_breaches": int(g.loc[g["resolved"], "resolve_sla_breached"].sum()),
        }), include_groups=False).reset_index()

    left, right = st.columns(2)
    with left:
        st.markdown("**% tiket butuh-part yang partnya tidak tersedia, per bulan**")
        fig = go.Figure(go.Scatter(x=monthly["month"], y=monthly["unavail_rate"], mode="lines+markers",
                                   line=dict(color=T.ORANGE, width=2),
                                   marker=dict(size=9, line=dict(color="white", width=2)),
                                   hovertemplate="%{x|%b %Y}<br>%{y:.1f}%<extra></extra>"))
        T.vline(fig, cutoff_ts, "Batas")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_yaxes(title="%", rangemode="tozero")
        T.show(T.style(fig, 330, legend=False), key="ba_unavail")
    with right:
        st.markdown("**MTTR rata-rata per bulan (menit)**")
        fig = go.Figure(go.Scatter(x=monthly["month"], y=monthly["mttr"], mode="lines+markers",
                                   line=dict(color=T.BLUE, width=2),
                                   marker=dict(size=9, line=dict(color="white", width=2)),
                                   hovertemplate="%{x|%b %Y}<br>%{y:,.0f} mnt<extra></extra>"))
        T.vline(fig, cutoff_ts, "Batas")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_yaxes(title="Menit", rangemode="tozero")
        T.show(T.style(fig, 330, legend=False), key="ba_mttr")

    # decomposition
    st.markdown("#### Apa yang mendorong perbaikan MTTR?")
    dec = M.mttr_decomposition(before, after)
    c = st.columns(3)
    c[0].metric("Total perubahan MTTR", f"{dec['total']:+,.0f} mnt", border=True)
    c[1].metric("Efek ketersediaan part (mix)", f"{dec['mix']:+,.0f} mnt", border=True,
                help="Perubahan karena porsi tiket 'part tidak tersedia' berubah.")
    c[2].metric("Efek kecepatan kerja (within)", f"{dec['within']:+,.0f} mnt", border=True,
                help="Perubahan karena tiap kelompok tiket menjadi lebih cepat/lambat.")

    tbl = dec["table"].copy()
    tbl["Porsi tiket sebelum"] = (tbl["Porsi tiket sebelum"] * 100).round(1)
    tbl["Porsi tiket sesudah"] = (tbl["Porsi tiket sesudah"] * 100).round(1)
    tbl = tbl.rename(columns={"Porsi tiket sebelum": "% tiket sebelum", "Porsi tiket sesudah": "% tiket sesudah"}).round(0)
    tbl.index.name = "Kondisi part"
    st.dataframe(tbl, width="stretch")

    if dec["total"] < 0:
        share_mix = dec["mix"] / dec["total"]
        share_within = dec["within"] / dec["total"]
        st.success(f"Dari penurunan MTTR {abs(dec['total']):,.0f} mnt, sekitar **{share_mix:.0%}** berasal dari perubahan "
                   f"komposisi (lebih sedikit tiket dengan part tidak tersedia) dan **{share_within:.0%}** dari "
                   "perubahan kecepatan kerja di dalam tiap kelompok.")
    elif dec["total"] > 0:
        st.warning(f"MTTR justru naik {dec['total']:,.0f} mnt pada pembagian periode ini "
                   f"(efek komposisi {dec['mix']:+,.0f} mnt, efek kecepatan {dec['within']:+,.0f} mnt).")
    st.caption("Catatan: ini analisis observasional. Data tidak memuat penyebab perubahan (mis. penambahan stok atau "
               "perubahan kebijakan), sehingga hasil menunjukkan *korelasi waktu*, bukan bukti sebab-akibat.")
