"""OpenCode Agent — drive the mud-designer agent via `opencode serve`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher"), str(_REPO_ROOT / "agentic" / "ui")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core.llm import get_providers  # noqa: E402

st.set_page_config(page_title="OpenCode Agent", page_icon="🤖", layout="wide")

st.title("🤖 OpenCode Agent")

PORT = 4096
BASE = f"http://127.0.0.1:{PORT}"


def _serve_running() -> bool:
    try:
        from opencode_client import OpenCodeClient
        OpenCodeClient(BASE).create_session()
        return True
    except Exception:
        return False


# ── Serve control ─────────────────────────────────────────────────────────────
st.subheader("Serve")
running = _serve_running()
if running:
    st.success(f"`opencode serve` running at {BASE}")
    if st.button("Stop serve"):
        subprocess.run(["pkill", "-f", "opencode serve"], capture_output=True)
        st.rerun()
else:
    st.warning(f"`opencode serve` not reachable at {BASE}.")
    if st.button("Start serve"):
        subprocess.Popen(
            ["opencode", "serve", "--port", str(PORT), "--hostname", "127.0.0.1"],
            cwd=str(_REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        st.info("Starting… refresh in a few seconds.")

st.divider()

# ── Agent + model picker ───────────────────────────────────────────────────────
st.subheader("Agent & model")
agent = st.selectbox("Agent", ["mud-designer", "build"], index=0)
providers = get_providers()
provider_ids = list(providers.keys())
provider = st.selectbox("Provider", provider_ids, index=0)
model = st.text_input("Model", "qwen3:8b")

# ── Chat ───────────────────────────────────────────────────────────────────────
st.subheader("Chat")
if "oc_messages" not in st.session_state:
    st.session_state["oc_messages"] = []
if "oc_session" not in st.session_state:
    st.session_state["oc_session"] = None

for m in st.session_state["oc_messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["text"])

prompt = st.chat_input("e.g. Design and test RE_EstimateSOC from the BMS sample")
if prompt:
    st.session_state["oc_messages"].append({"role": "user", "text": prompt})
    from opencode_client import OpenCodeClient
    client = OpenCodeClient(BASE)
    try:
        if not st.session_state["oc_session"]:
            sess = client.create_session()
            st.session_state["oc_session"] = sess.get("id") or sess.get("sessionID")
        sid = st.session_state["oc_session"]
        client.send_message(
            sid, prompt, agent=agent,
            model={"providerID": provider, "modelID": model},
        )
        # Stream tool events into a timeline.
        timeline = st.empty()
        actions = []
        for event in client.stream_events(sid):
            from opencode_client import is_tool_event, tool_state
            if is_tool_event(event):
                ts = tool_state(event)
                if ts["status"] in ("running", "completed", "error"):
                    actions.append(ts)
                lines = []
                for a in actions[-15:]:
                    icon = {"completed": "✅", "error": "❌", "running": "⏳"}.get(a["status"], "•")
                    lines.append(f"- {icon} **{a['tool']}** ({a['status']})")
                timeline.markdown("\n".join(lines))
        st.session_state["oc_messages"].append({"role": "assistant", "text": "_done — see timeline below_ "})
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.error(f"opencode serve error: {exc}")
        st.info("Start the serve (above) and make sure `opencode` is on PATH.")

st.divider()

# ── Artifacts ─────────────────────────────────────────────────────────────────
st.subheader("Artifacts (outputs/)")
latest = c.run_latest()
if latest:
    st.write(f"Latest run: `{latest.folder.name}` ({latest.swc})")
    report = latest.read_text("RUN_REPORT.md", "")
    if report:
        with st.expander("RUN_REPORT.md"):
            st.markdown(report)
else:
    st.caption("No run yet — the agent writes to outputs/<run>/.")
