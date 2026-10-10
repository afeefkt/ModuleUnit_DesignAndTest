"""MUD_MUT — one Streamlit platform for design (MUD) + unit tests (MUT).

    streamlit run launcher/streamlit_app.py

Home / Status page: Ollama, WSL toolchain, workspace runs, one-click example.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import _common as c

st.set_page_config(page_title="MUD_MUT", page_icon="🧭", layout="wide")

ollama_host = c.bootstrap()

st.title("🧭 MUD_MUT Control Center")
st.caption("Local-AI AUTOSAR: requirements → flow charts → C → unit tests. No Docker.")

# ── Status ────────────────────────────────────────────────────────────────────
st.header("① Status")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Ollama (LLM runtime)")
    models = c.ollama_models(ollama_host)
    if models:
        st.success(f"{len(models)} model(s) available at {ollama_host}")
        st.write(", ".join(f"`{m}`" for m in models[:12]) + ("…" if len(models) > 12 else ""))
    else:
        st.warning(f"Ollama not reachable at {ollama_host}. Start Ollama, then pull models.")

with c2:
    st.subheader("C/C++ toolchain (WSL)")
    report = c.toolchain_report()
    if report is None:
        st.error("Could not run toolchain check.")
    else:
        for tool in report.tools:
            icon = "✅" if tool.available else "❌"
            st.write(f"{icon} **{tool.name}** — {tool.detail}")
        if not report.ok:
            st.info("Install missing tools (in WSL, as root):\n\n"
                    f"```\n{c.run_toolchain_install_hint()}\n```")

# ── Runs ──────────────────────────────────────────────────────────────────────
st.divider()
st.header("② Workspace runs")
runs = c.list_runs()
if not runs:
    st.caption("No runs yet — start on the Design or Full Chain page.")
else:
    for run in runs[:15]:
        st.write(f"- `{run.folder.name}` ({run.swc})")

# ── Quick links ───────────────────────────────────────────────────────────────
st.divider()
st.header("③ Get started")
st.markdown(
    "- **Setup** → `pages/5_Providers` (keys + test connections) · `pages/4_Workflow_Models` (flow charts + per-stage provider/model)\n"
    "- **Pipeline** → `pages/1_Design_MUD` (import → plan → spec → flow → C skeleton)\n"
    "                 `pages/2_Unit_Tests_MUT` (generate → build → coverage → trace)\n"
    "                 `pages/3_Full_Chain` (one-click end-to-end)"
)
