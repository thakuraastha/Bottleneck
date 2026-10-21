from __future__ import annotations

from html import escape

import streamlit as st


STATUS_COLORS = {
    "NEW": "#3b82f6", "INVESTIGATING": "#8b5cf6", "WAITING_FOR_APPROVAL": "#f59e0b",
    "APPROVED": "#10b981", "REJECTED": "#ef4444", "FAILED": "#ef4444",
    "COMPLETED": "#10b981", "RUNNING": "#38bdf8", "SKIPPED": "#64748b",
}


def inject_theme() -> None:
    st.markdown("""
    <style>
      :root { --bn-panel:#111827; --bn-border:#253249; --bn-text:#e5edf8; --bn-muted:#8ea0b8; }
      .stApp { background: radial-gradient(circle at 80% 0%, #13213a 0, #070b13 34%, #070b13 100%); color:var(--bn-text); }
      [data-testid="stSidebar"] { background:#090e18; border-right:1px solid var(--bn-border); }
      [data-testid="stMetric"] { background:linear-gradient(145deg,#121b2b,#0d1420); border:1px solid var(--bn-border); border-radius:12px; padding:14px; }
      [data-testid="stMetricLabel"] { color:var(--bn-muted); }
      div[data-testid="stDataFrame"] { border:1px solid var(--bn-border); border-radius:10px; overflow:hidden; }
      .bn-kicker { color:#57d4ff; font-size:.78rem; letter-spacing:.14em; text-transform:uppercase; font-weight:700; }
      .bn-subtle { color:var(--bn-muted); font-size:.92rem; }
      .bn-panel { background:rgba(17,24,39,.78); border:1px solid var(--bn-border); border-radius:12px; padding:16px; margin-bottom:12px; }
      .bn-badge { display:inline-block; border-radius:999px; padding:4px 9px; font-size:.72rem; font-weight:750; letter-spacing:.04em; }
      h1,h2,h3 { letter-spacing:-.025em; }
      .stButton button { border-radius:8px; border:1px solid #34445f; }
    </style>
    """, unsafe_allow_html=True)


def page_header(title: str, subtitle: str) -> None:
    st.markdown('<div class="bn-kicker">Bottleneck · Operations command center</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="bn-subtle">{escape(subtitle)}</div>', unsafe_allow_html=True)


def badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#64748b")
    return f'<span class="bn-badge" style="color:{color};background:{color}22;border:1px solid {color}55">{escape(status.replace("_", " "))}</span>'


def empty_state(title: str, detail: str) -> None:
    st.markdown(f'<div class="bn-panel"><strong>{escape(title)}</strong><div class="bn-subtle">{escape(detail)}</div></div>', unsafe_allow_html=True)


def format_currency(value: float | int | None) -> str:
    return "Unavailable" if value is None else f"{value:,.0f}"

