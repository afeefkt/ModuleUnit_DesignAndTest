"""Runs & Reports — browse runs, view a run, and compare two side-by-side."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402

st.set_page_config(page_title="Runs & Reports", page_icon="📊", layout="wide")

st.title("📊 Runs & Reports")

runs = c.list_runs()
if not runs:
    st.info("No runs yet — run the Design, Full Chain, or OpenCode Agent page first.")
    st.stop()

# ── Run list with verdict badges ──────────────────────────────────────────────
st.subheader("Runs")
for r in runs:
    run_json = r.read_json("run.json")
    verdicts = (run_json or {}).get("verdicts", {})
    cloud = (run_json or {}).get("cloud_providers", [])
    badge = " ".join(verdicts.values()) if verdicts else ""
    st.write(f"- `{r.folder.name}` — {r.swc} ({r.preset})  {badge}  "
             f"{('☁️ ' + ','.join(cloud)) if cloud else '🏠 local'}")

st.divider()

mode = st.radio("View", ["Single run", "Compare two runs"], horizontal=True)

if mode == "Single run":
    run = c.run_picker("run_view")
    if run:
        report = run.read_text("RUN_REPORT.md", "")
        st.markdown(report or "_No report_")
        with st.expander("MUD spec"):
            st.markdown(run.read_in("mud", "mud_spec.md", "(none)"))
        with st.expander("Flow chart"):
            c.render_mermaid(run.read_in("mud", "flow.mmd", ""), height=360)
        with st.expander("C skeleton"):
            st.code(run.read_in("code", f"{run.swc}.c", "(none)"), language="c")
        with st.expander("Trace"):
            st.json(run.read_json_in("trace", "trace.json", {}))

else:
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Run A**")
        a = c.run_picker("compare_a")
    with col_b:
        st.markdown("**Run B**")
        b = c.run_picker("compare_b")
    if a and b:
        ja = a.read_json("run.json") or {}
        jb = b.read_json("run.json") or {}
        rows = []
        for key in ("preset", "compilability", "tests", "trace"):
            rows.append((key, str(ja.get(key, "")), str(jb.get(key, ""))))
        st.table([
            {"field": "preset", "A": ja.get("preset", ""), "B": jb.get("preset", "")},
            {"field": "cloud", "A": ", ".join(ja.get("cloud_providers", [])), "B": ", ".join(jb.get("cloud_providers", []))},
            {"field": "compile_ok", "A": ja.get("compilability", {}).get("compile_ok", ""), "B": jb.get("compilability", {}).get("compile_ok", "")},
            {"field": "tests status", "A": ja.get("tests", {}).get("status", ""), "B": jb.get("tests", {}).get("status", "")},
            {"field": "tests passed", "A": (ja.get("tests", {}).get("junit") or {}).get("passed", ""), "B": (jb.get("tests", {}).get("junit") or {}).get("passed", "")},
            {"field": "requirements", "A": ja.get("trace", {}).get("requirements", ""), "B": jb.get("trace", {}).get("requirements", "")},
            {"field": "timings (s)", "A": str(ja.get("timings", {})), "B": str(jb.get("timings", {}))},
        ])
