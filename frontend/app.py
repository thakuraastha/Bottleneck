from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.components.api import ApiError, BottleneckApi
from frontend.components.ui import inject_theme
from frontend.pages import PAGE_RENDERERS


st.set_page_config(page_title="Bottleneck", page_icon="⛓", layout="wide", initial_sidebar_state="expanded")
inject_theme()

api = BottleneckApi()
with st.sidebar:
    st.markdown("## BOTTLENECK")
    st.caption("Supply-chain disruption & recovery")
    page = st.radio("Workspace", list(PAGE_RENDERERS), label_visibility="collapsed")
    st.divider()
    try:
        health = api.get("/health")
        st.success("Backend connected" if health.get("status") == "ok" else "Backend responded")
    except ApiError:
        st.error("Backend offline")

try:
    PAGE_RENDERERS[page](api)
except ApiError as exc:
    st.error(str(exc))
    st.caption("Start the FastAPI backend, then refresh this page. Missing evidence is never replaced with placeholder values.")
