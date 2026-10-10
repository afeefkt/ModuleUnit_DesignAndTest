"""MUD_MUT — one Streamlit platform for design (MUD) + unit tests (MUT).

    streamlit run launcher/streamlit_app.py

This file is the router: it sets the page, theme and the shared run bar, then runs the
selected page from ``views/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_HERE = Path(__file__).resolve().parent
for p in (str(_HERE.parent), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402

st.set_page_config(page_title="MUD_MUT", page_icon="🧭", layout="wide")
c.inject_theme()

pages = {
    "Start": [
        st.Page("views/0_Overview.py", url_path="overview", title="Overview", icon="🏠", default=True),
    ],
    "Design": [
        st.Page("views/1_Design_MUD.py", url_path="design", title="Requirements & design", icon="📐"),
    ],
    "Verify": [
        st.Page("views/2_Unit_Tests_MUT.py", url_path="unit-tests", title="Unit tests", icon="🧪"),
        st.Page("views/3_Full_Chain.py", url_path="full-chain", title="Full chain", icon="🔗"),
    ],
    "Review": [
        st.Page("views/6_Runs_Reports.py", url_path="reports", title="Runs & reports", icon="📊"),
        st.Page("views/9_AI_Monitor.py", url_path="ai-monitor", title="AI monitor", icon="🛰️"),
    ],
    "Setup": [
        st.Page("views/4_Workflow_Models.py", url_path="models", title="Models", icon="🧠"),
        st.Page("views/5_Providers.py", url_path="keys", title="Keys & providers", icon="🔑"),
        st.Page("views/8_Settings.py", url_path="settings", title="Settings", icon="⚙️"),
    ],
    "Agent": [
        st.Page("views/7_OpenCode_Agent.py", url_path="agent", title="OpenCode agent", icon="🤖"),
    ],
}

page = st.navigation(pages)
c.run_bar()
page.run()
