"""Extra page - analyst insights & recommendations.

All numbers are computed from the *full* dataset (sidebar filters are ignored) so the
narrative always matches the data. Wording is written for the dataset's current patterns.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src import metrics as M
from src import theme as T
from src.data import PART_ORDER
from src.views.spare_parts import DEFAULT_CUTOFF


def _card(title: str, evidence: list[str], reco: str) -> None:
    bullets = "".join(f"<li>{html.escape(e)}</li>" for e in evidence)
    st.markdown(
        f'<div class="insight-card"><h4>{title}</h4><ul>{bullets}</ul>'
        f'<p class="reco">Rekomendasi: {html.escape(reco)}</p></div>',
        unsafe_allow_html=True,
    )


def render(df: pd.DataFrame, full: pd.DataFrame, snapshot: pd.Timestamp) -> None:
    st.title("💡 Insights & Rekomendasi")
    st.caption("Temuan utama dari sudut pandang analis data center. Angka di halaman ini dihitung dari "
               "**seluruh data** (filter sidebar tidak berlaku).")

    k = M.kpis(full)
    inc = full[full["ticket_type"] == "Incident"]
    res = full[full["resolved"]]

    # ---- 1. Overall health
    _card(
        "1. Kesehatan SLA secara umum baik, risikonya ada di ekor distribusi",
        [f"{k['total']:,} tiket ({full['created_at'].min():%b} – {full['created_at'].max():%b %Y}); "
         f"kepatuhan SLA acknowledge {T.fmt_pct(k['ack_compliance'])} dan resolve {T.fmt_pct(k['res_compliance'])}.",
         f"MTTR rata-rata {k['mttr_mean']:,.0f} mnt jauh di atas median {k['mttr_median']:,.0f} mnt: "
         "sebagian kecil tiket yang lama menarik rata-rata naik.",
         f"{k['open']} tiket masih terbuka pada snapshot terakhir."],
        "pantau median dan persentil atas (bukan hanya rata-rata) dan beri perhatian khusus pada tiket yang menunggu part.",
    )

    # ---- 2. Pareto
    p = M.pareto(inc, "component")
    n80 = int(p["vital_few"].sum())
    top3 = p.head(3)
    _card(
        "2. Sedikit komponen menghasilkan sebagian besar insiden",
        [f"{n80} dari {len(p)} komponen menyumbang 80% insiden.",
         "Tiga teratas: " + ", ".join(f"{i} ({r['share']:.0%})" for i, r in top3.iterrows()) + ".",
         f"{p.index[0]} sendiri menyumbang {p.iloc[0]['share']:.0%} dari seluruh insiden."],
        "prioritaskan pemantauan prediktif (SMART/DIMM ECC) dan penggantian proaktif untuk komponen teratas, "
        "serta jaga stok minimum part-nya.",
    )

    # ---- 3. Spare parts
    need = full[full["spare_part_required"]]
    unavail = need[need["part_status"] == PART_ORDER[2]]
    avail = res[res["part_status"] == PART_ORDER[1]]
    un_res = res[res["part_status"] == PART_ORDER[2]]
    total_breach = int(res["resolve_sla_breached"].sum())
    breach_un = int(un_res["resolve_sla_breached"].sum())
    _card(
        "3. Ketersediaan spare part adalah pendorong utama pelanggaran SLA Resolve",
        [f"{len(unavail)} tiket ({len(unavail) / len(need):.1%} dari tiket yang butuh part) partnya tidak tersedia.",
         f"MTTR tiket part tidak tersedia {un_res['time_to_resolve_min'].mean():,.0f} mnt vs "
         f"{avail['time_to_resolve_min'].mean():,.0f} mnt bila part tersedia "
         f"(≈{un_res['time_to_resolve_min'].mean() / avail['time_to_resolve_min'].mean():.1f}×).",
         f"{breach_un} dari {total_breach} pelanggaran SLA Resolve ({breach_un / total_breach:.0%}) terjadi pada tiket part tidak tersedia, "
         f"padahal tiket tersebut hanya {len(unavail) / len(full):.1%} dari seluruh tiket.",
         f"Rata-rata menunggu part {unavail['part_wait_min'].mean() / 60:,.1f} jam."],
        "tetapkan par-level stok untuk komponen dengan % part tidak tersedia tertinggi dan SLA vendor untuk part kritis.",
    )

    # ---- 4. Before/after July
    cutoff = pd.Timestamp(DEFAULT_CUTOFF)
    before, after = full[full["created_at"] < cutoff], full[full["created_at"] >= cutoff]
    b, a = M.before_after_summary(before), M.before_after_summary(after)
    dec = M.mttr_decomposition(before, after)
    p_mttr = M.mann_whitney_pvalue(after.loc[after["resolved"], "time_to_resolve_min"],
                                   before.loc[before["resolved"], "time_to_resolve_min"])
    _card(
        "4. Sejak Juli 2026 part tidak tersedia jauh berkurang dan MTTR turun",
        [f"% tiket butuh-part yang partnya tidak tersedia: {T.fmt_pct(b['unavail_rate'])} → {T.fmt_pct(a['unavail_rate'])}.",
         f"MTTR rata-rata {b['mttr_mean']:,.0f} → {a['mttr_mean']:,.0f} mnt ({(a['mttr_mean'] / b['mttr_mean'] - 1):+.0%}); "
         f"median {b['mttr_median']:,.0f} → {a['mttr_median']:,.0f} mnt; {T.pvalue_text(p_mttr)} (Mann-Whitney).",
         f"Pelanggaran SLA Resolve: {b['res_breaches']} → {a['res_breaches']} "
         f"(rate {T.fmt_pct(b['res_breach_rate'], 2)} → {T.fmt_pct(a['res_breach_rate'], 2)}).",
         f"Dekomposisi: {dec['mix'] / dec['total']:.0%} dari perubahan MTTR berasal dari komposisi (lebih sedikit tiket "
         f"part tidak tersedia), {dec['within'] / dec['total']:.0%} dari kecepatan kerja per kelompok."],
        "cari tahu apa yang berubah di Juli (stok, vendor, proses procurement) dan jadikan standar. "
        "Catatan: data observasional, sebab-akibat belum terbukti.",
    )

    # ---- 5. Night shift
    n, m = full[full["shift"] == "Night"], full[full["shift"] == "Morning"]
    p_ack = M.two_proportion_pvalue(int(n["ack_sla_breached"].sum()), len(n), int(m["ack_sla_breached"].sum()), len(m))
    p_mtta = M.mann_whitney_pvalue(n["mtta_min"], m["mtta_min"])
    _card(
        "5. Shift Night paling lambat merespons",
        [f"MTTA Night {n['mtta_min'].mean():,.0f} mnt vs Morning {m['mtta_min'].mean():,.0f} mnt ({T.pvalue_text(p_mtta)}).",
         f"Ack SLA breach Night {n['ack_sla_breached'].mean():.1%} vs Morning {m['ack_sla_breached'].mean():.1%} ({T.pvalue_text(p_ack)}).",
         f"Volume Night paling rendah ({len(n):,} tiket vs {len(m):,} di Morning), jadi bukan soal beban tiket semata."],
        "tinjau jumlah personel dan alur alert/on-call malam hari (mis. notifikasi otomatis untuk Sev-1/2 dan auto-escalation bila belum di-ack).",
    )

    # ---- 6. Sev-1
    s1 = res[res["severity"] == "Sev-1"]
    others = res[res["severity"] != "Sev-1"]
    _card(
        "6. Sev-1 punya tingkat pelanggaran SLA Resolve tertinggi",
        [f"{int(s1['resolve_sla_breached'].sum())} dari {len(s1)} tiket Sev-1 ({s1['resolve_sla_breached'].mean():.1%}) melewati target 240 menit, "
         f"vs {others['resolve_sla_breached'].mean():.1%} pada severity lain.",
         f"Dari {int((inc['customer_impact'] == 'Outage').sum())} insiden Outage, "
         + ", ".join(f"{int(v)} berasal dari {s}" for s, v in
                     inc.loc[inc["customer_impact"] == "Outage", "severity"].value_counts().sort_index().items())
         + ".",
         f"MTTR rata-rata Sev-1 {s1['time_to_resolve_min'].mean():,.0f} mnt, hanya sedikit di bawah target 240 mnt."],
        "buat runbook dan pre-staging part khusus untuk skenario Sev-1; margin terhadap target 4 jam sangat tipis.",
    )

    # ---- 7. Racks
    rk = inc.groupby(["hall_id", "rack_id"]).size()
    hall_rate = inc.groupby("hall_id").size() / inc.groupby("hall_id")["rack_id"].nunique()
    top_rack = rk.sort_values(ascending=False)
    _card(
        "7. Beban insiden tidak merata antar hall",
        [f"Insiden per rack: " + ", ".join(f"{h} {v:.0f}" for h, v in hall_rate.sort_values(ascending=False).items()) + ".",
         f"Rack teratas {top_rack.index[0][1]} ({top_rack.iloc[0]} insiden) = {top_rack.iloc[0] / rk.median():.1f}× median rack ({rk.median():.0f}).",
         f"{(top_rack.head(10).index.get_level_values(0) == hall_rate.idxmax()).sum()} dari 10 rack teratas berada di {hall_rate.idxmax()}."],
        f"audit lingkungan dan umur perangkat di {hall_rate.idxmax()} (suhu, daya, kabel) untuk mencari faktor bersama.",
    )

    # ---- 8. RCA
    pend = inc[inc["root_cause"] == "Pending RCA"]
    rep = inc.groupby("root_cause").agg(n=("ticket_id", "count"), r=("repeat_incident", "sum"))
    rep = rep[rep["n"] >= 20]
    rep["pct"] = rep["r"] / rep["n"]
    toprep = rep.sort_values("pct", ascending=False).head(3)
    _card(
        "8. Insiden berulang menandakan perbaikan yang belum permanen",
        [f"{inc['repeat_incident'].mean():.1%} insiden bertanda berulang ({int(inc['repeat_incident'].sum())} tiket).",
         "Root cause dengan tingkat berulang tertinggi (min. 20 insiden): " +
         ", ".join(f"{i} ({r['pct']:.0%}, n={int(r['n'])})" for i, r in toprep.iterrows()) + ".",
         f"{len(pend)} insiden ({len(pend) / len(inc):.1%}) masih 'Pending RCA' — seluruhnya Sev-3/Sev-4."],
        "wajibkan corrective action permanen untuk root cause berulang dan tetapkan batas waktu penyelesaian RCA.",
    )

    st.caption("Metodologi, definisi metrik dan batasan data ada di README repositori.")
