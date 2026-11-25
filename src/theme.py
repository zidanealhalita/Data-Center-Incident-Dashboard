"""Colors, Plotly styling and small UI helpers shared by all pages."""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Categorical palette (fixed order, first slots are the best separated ones).
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17", "#6a4ce2", "#ec4647",
)
NEUTRAL = "#949494"      # "not applicable" / "before" / neutral series
MUTED = "#c4c4c4"        # de-emphasised bars
TEXT = "#191919"
TEXT_2 = "#666666"
GRID = "#e8e8e8"

SEV_COLORS = {"Sev-1": "#0e3d7e", "Sev-2": "#1b64be", "Sev-3": "#338ced", "Sev-4": "#84b9f3"}
SHIFT_COLORS = {"Morning": BLUE, "Afternoon": ORANGE, "Night": AQUA}
TYPE_COLORS = {"Incident": BLUE, "Preventive Maintenance": ORANGE, "Change Request": AQUA}
HALL_COLORS = {"DH1": BLUE, "DH2": ORANGE, "DH3": AQUA, "DH4": YELLOW}
PART_COLORS = {"Tidak butuh part": NEUTRAL, "Part tersedia": BLUE, "Part tidak tersedia": ORANGE}
IMPACT_COLORS = {"Degraded": BLUE, "Outage": ORANGE}
CATEGORY_COLORS = {
    "Server Hardware": BLUE, "Network": ORANGE, "Cooling": AQUA,
    "Power": YELLOW, "Physical Security": MAGENTA,
}
HEAT_SCALE = [[0.0, "#e8f1fd"], [0.5, "#338ced"], [1.0, "#0e3d7e"]]

CSS = """
<style>
  .block-container {padding-top: 2.2rem; padding-bottom: 3rem;}
  [data-testid="stMetricValue"] {font-size: 1.7rem;}
  h1 {letter-spacing: -0.01em;}
  .insight-card {border: 1px solid #e3e3e3; border-left: 5px solid #257de0;
                 border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;
                 background: #fafbfc;}
  .insight-card h4 {margin: 0 0 6px 0;}
  .insight-card p {margin: 4px 0;}
  .insight-card .reco {color: #1b64be; font-weight: 600;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str, df: pd.DataFrame) -> None:
    st.title(title)
    if len(df):
        st.caption(
            f"{subtitle} · {len(df):,} tiket dalam filter · "
            f"{df['created_at'].min():%d %b %Y} – {df['created_at'].max():%d %b %Y}"
        )
    else:
        st.caption(subtitle)


def style(fig: go.Figure, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="simple_white",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Inter, 'Segoe UI', Roboto, sans-serif", size=13, color=TEXT),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="outside", tickcolor=GRID, title_font_color=TEXT_2)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)", title_font_color=TEXT_2)
    return fig


def show(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "displayModeBar": False}, key=key)


def order_hbar(fig: go.Figure, order: list[str]) -> None:
    """Horizontal bars: first item of ``order`` at the top."""
    fig.update_yaxes(categoryorder="array", categoryarray=list(order), autorange="reversed")


def pad_x(fig: go.Figure, xmax: float, factor: float = 1.2) -> None:
    """Leave room on the right so 'outside' bar labels are not clipped."""
    fig.update_xaxes(range=[0, xmax * factor])


def vline(fig: go.Figure, x, label: str) -> None:
    """Vertical reference line on a datetime axis (avoids add_vline datetime quirks)."""
    fig.add_shape(type="line", x0=x, x1=x, xref="x", y0=0, y1=1, yref="paper",
                  line=dict(color=TEXT_2, width=1.5, dash="dot"))
    fig.add_annotation(x=x, y=0.98, xref="x", yref="paper", text=label, showarrow=False,
                       xanchor="left", yanchor="top", font=dict(size=12, color=TEXT_2))


def fmt_int(x) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:,.0f}"


def fmt_min(x) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:,.0f} mnt"


def fmt_pct(x, digits: int = 1) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.{digits}f}%"


def fmt_hours(minutes) -> str:
    if minutes is None or (isinstance(minutes, float) and math.isnan(minutes)):
        return "–"
    return f"{minutes / 60:,.1f} jam"


def pvalue_text(p: float) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n/a"
    return "p < 0,001" if p < 0.001 else f"p = {p:.3f}".replace(".", ",")
