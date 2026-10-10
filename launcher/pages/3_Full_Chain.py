"""Full Chain: one-click end-to-end run with a step timeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import aio, chain  # noqa: E402

st.set_page_config(page_title="Full Chain", page_icon="🔗", layout="wide")

st.title("🔗 Full Chain (one-click)")

SAMPLE = _REPO_ROOT / "inputs" / "requirements" / "samples" / "bms_requirements.csv"

st.markdown("Runs the whole pipeline: import → plan → spec → activity → C → tests → coverage → trace.")

col1, col2 = st.columns(2)
with col1:
    req_path = st.text_input("Requirements file", str(SAMPLE))
with col2:
    quick = st.checkbox("Quick mode (single-pass, skip review)", value=True)

if st.button("▶ Run full chain", type="primary"):
    steps = st.empty()
    log = []

    def progress(event: dict) -> None:
        log.append(event)
        steps.markdown("\n".join(
            f"- **{e['stage']}**: {e['message']}" for e in log[-12:]
        ))

    try:
        summary = aio.run_sync(chain.run_full_chain(req_path, quick=quick, progress=progress))
        steps.markdown("\n".join(f"- ✅ {e['stage']}: {e['message']}" for e in log))
        st.session_state["current_run_folder"] = summary["run_folder"]
        st.success("Chain complete.")
        st.json({
            "run_folder": summary["run_folder"],
            "swc": summary["swc"],
            "timings": summary["timings"],
            "compilability": summary["compilability"],
            "tests": {k: summary["tests"].get(k) for k in ("status", "junit", "fix_attempts")},
        })
    except Exception as exc:  # noqa: BLE001
        st.exception(exc)
