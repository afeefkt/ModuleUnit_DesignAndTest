"""Streamlit chat client for the MUD_MUT agentic spike (experimental).

Chat input → `opencode serve` → mud-designer agent → streamed tool events.
Displays a tool-call timeline, the final Mermaid chart, and a download of the run folder.

Run:  opencode serve --port 4096   (in another terminal)
      streamlit run agentic/ui/app.py
"""

from __future__ import annotations

import json
import os
import zipfile
from io import BytesIO
from pathlib import Path

import streamlit as st

from opencode_client import OpenCodeClient

REPO = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO / "agentic" / "runs"

st.set_page_config(page_title="MUD_MUT agentic", layout="wide")
st.title("MUD_MUT — agentic mode (experimental)")

base_url = os.environ.get("OPENCODE_BASE_URL", "http://127.0.0.1:4096")
client = OpenCodeClient(base_url)

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "events" not in st.session_state:
    st.session_state.events = []


def _zip_run(run_id: str) -> bytes | None:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        return None
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(run_dir.iterdir()):
            if f.is_file():
                zf.write(f, arcname=f.name)
    return buf.getvalue()


def _cmd_of(evt: dict) -> str:
    state = evt.get("state") or evt.get("input") or {}
    cmd = state.get("command") or state.get("input", {}).get("command", "")
    if isinstance(cmd, dict):
        cmd = cmd.get("command", "")
    return str(cmd)[:120]


col1, col2 = st.columns([1, 1])
with col1:
    if st.button("New session"):
        try:
            sess = client.create_session()
            st.session_state.session_id = sess.get("id") or json.dumps(sess)
            st.session_state.events = []
            st.success(f"session {st.session_state.session_id}")
        except Exception as e:
            st.error(f"connect failed: {e}")

with col2:
    run_id = st.text_input("Run id", value="ui-demo")

prompt = st.chat_input("e.g. Design the activity flow for RE_EstimateSOC from bms_requirements.csv")

if prompt:
    if not st.session_state.session_id:
        st.warning("Start a session first.")
    else:
        with st.chat_message("user"):
            st.write(prompt)
        try:
            client.send_prompt(st.session_state.session_id, prompt)
            with st.chat_message("assistant"):
                timeline = st.empty()
                for evt in client.stream_events(st.session_state.session_id):
                    st.session_state.events.append(evt)
                    t = evt.get("type", "")
                    if t == "tool_use":
                        timeline.write(f"⚙️ {evt.get('tool', '?')}: {_cmd_of(evt)}")
                    elif t == "text":
                        timeline.write(evt.get("part", {}).get("text", "")[:300])
        except Exception as e:
            st.error(f"stream error: {e}")

# Artifact download + final mermaid
st.divider()
if run_id:
    zipped = _zip_run(run_id)
    if zipped:
        st.download_button("⬇ Download run folder", zipped, file_name=f"{run_id}.zip")
    mmd_files = sorted((RUNS_DIR / run_id).glob("*.mmd")) if (RUNS_DIR / run_id).exists() else []
    if mmd_files:
        st.subheader("Mermaid")
        st.code(mmd_files[0].read_text(encoding="utf-8"), language="mermaid")
