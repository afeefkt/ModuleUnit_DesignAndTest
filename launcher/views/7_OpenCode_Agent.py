"""OpenCode Agent — drive the mud-designer agent via `opencode serve`.

The page talks to a local ``opencode serve`` (started here, inside WSL). The
agent's tool calls are streamed live from ``/event`` into a timeline; its
artifacts land in ``outputs/<run>/`` like any other run.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher"), str(_REPO_ROOT / "agentic" / "ui")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import agents, env  # noqa: E402
from mudmut_core.llm import get_providers  # noqa: E402
from opencode_client import EventWatcher, OpenCodeClient  # noqa: E402

st.title("OpenCode agent")
st.caption("An extra agentic layer on the same engine: the agent calls `agentic/tools/mudmut_cli.py`, "
           "which runs mudmut_core and writes to `outputs/<run>/`.")

PORT = 4096
BASE = f"http://127.0.0.1:{PORT}"
STATE_DIR = _REPO_ROOT / "outputs" / "_state"
PID_FILE = STATE_DIR / "opencode_serve.pid"
LOG_FILE = STATE_DIR / "opencode_serve.log"
INSTALL_HINT = "curl -fsSL https://opencode.ai/install | bash   # run inside WSL"

env.ensure_environment()
client = OpenCodeClient(BASE)


def _find_opencode() -> str | None:
    """A native opencode binary. The Windows npm shim under /mnt/c does not run in WSL."""
    candidates = [shutil.which("opencode"), str(Path.home() / ".opencode" / "bin" / "opencode")]
    for cand in candidates:
        if cand and not cand.startswith("/mnt/") and os.access(cand, os.X_OK):
            return cand
    return None


def _start_serve(binary: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_FILE, "ab")
    proc = subprocess.Popen(
        [binary, "serve", "--port", str(PORT), "--hostname", "127.0.0.1"],
        cwd=str(_REPO_ROOT), stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True, env=os.environ.copy(),  # provider keys already exported
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    for _ in range(30):
        if client.healthy():
            return
        time.sleep(0.5)


def _stop_serve() -> None:
    """Stop only the serve this page started (by PID), never other opencode processes."""
    if not PID_FILE.is_file():
        return
    try:
        os.killpg(int(PID_FILE.read_text().strip()), signal.SIGTERM)
    except (ProcessLookupError, ValueError, PermissionError):
        pass
    PID_FILE.unlink(missing_ok=True)


# ── Serve control ─────────────────────────────────────────────────────────────
st.subheader("① Serve")
running = client.healthy()
binary = _find_opencode()
col_a, col_b = st.columns([3, 1])
if running:
    col_a.success(f"`opencode serve` is running at {BASE}")
    if PID_FILE.is_file() and col_b.button("Stop serve"):
        _stop_serve()
        st.rerun()
elif binary:
    col_a.warning(f"`opencode serve` is not running ({binary}).")
    if col_b.button("Start serve", type="primary"):
        with st.spinner("Starting opencode serve…"):
            _start_serve(binary)
        st.rerun()
else:
    col_a.error("No native OpenCode found in WSL (the Windows npm shim under /mnt/c can't run here).")
    st.code(INSTALL_HINT, language="bash")
    st.stop()

if not running:
    st.stop()

# ── Agent + model ─────────────────────────────────────────────────────────────
st.subheader("② Agent & model")
agent_names = client.list_agents() or ["mud-designer"]
col1, col2, col3 = st.columns(3)
agent = col1.selectbox("Agent", agent_names,
                       index=agent_names.index("mud-designer") if "mud-designer" in agent_names else 0)
provider_ids = ["(agent default)"] + list(get_providers().keys())
provider = col2.selectbox("Provider", provider_ids, index=0,
                          help="'(agent default)' uses the model in .opencode/agents/<agent>.md")


@st.cache_data(ttl=300, show_spinner=False)
def _models(pid: str) -> list[str]:
    return [m["id"] for m in agents.available_models(pid)]


model = None
if provider != "(agent default)":
    options = _models(provider)
    model = col3.selectbox("Model", options) if options else col3.text_input("Model id")
    if get_providers()[provider].privacy == "cloud":
        st.warning(f"☁️ The agent will send requirement text and designs to **{provider}**.")

# ── Chat + live timeline ──────────────────────────────────────────────────────
st.subheader("③ Chat")
ss = st.session_state
ss.setdefault("oc_session", "")
ss.setdefault("oc_watcher", None)
ss.setdefault("oc_messages", [])

if st.button("New session"):
    if ss["oc_watcher"]:
        ss["oc_watcher"].stop()
    ss["oc_session"], ss["oc_watcher"], ss["oc_messages"] = "", None, []

for m in ss["oc_messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["text"])

prompt = st.chat_input("e.g. Design and test RE_EstimateSOC from inputs/requirements/samples/bms_requirements.csv")
if prompt:
    try:
        if not ss["oc_session"]:
            ss["oc_session"] = client.create_session("mudmut")
        if ss["oc_watcher"] is None or ss["oc_watcher"].session_id != ss["oc_session"]:
            ss["oc_watcher"] = EventWatcher(client, ss["oc_session"]).start()
        ss["oc_watcher"].reset()  # open the stream first, then send (no missed events)
        client.prompt_async(ss["oc_session"], prompt, agent=agent,
                            provider_id=None if model is None else provider, model_id=model)
        ss["oc_messages"].append({"role": "user", "text": prompt})
    except Exception as exc:  # noqa: BLE001
        st.error(f"opencode serve error: {exc}")

_ICON = {"pending": "🕓", "running": "⏳", "completed": "✅", "error": "❌"}


@st.fragment(run_every=1.5)
def _timeline() -> None:
    watcher = ss.get("oc_watcher")
    if watcher is None:
        st.caption("Send a prompt to start — the agent's actions appear here live.")
        return
    snap = watcher.snapshot()
    status = snap["status"]
    badge = {"busy": "⏳ working", "retry": "🔁 retrying", "done": "✅ finished",
             "error": "❌ error", "idle": "… waiting"}.get(status, status)
    head, abort_col = st.columns([4, 1])
    head.markdown(f"**Agent status:** {badge} · {len(snap['order'])} action(s)")
    if status in ("busy", "retry") and abort_col.button("Abort", key="oc_abort"):
        client.abort(watcher.session_id)
    if snap["error"]:
        st.error(snap["error"])

    for perm_id, perm in snap["permissions"].items():
        with st.container(border=True):
            st.markdown(f"🔐 **Permission requested:** `{perm['permission']}` → `{', '.join(perm['patterns'])}`")
            a, b = st.columns(2)
            if a.button("Allow once", key=f"allow_{perm_id}"):
                client.reply_permission(watcher.session_id, perm_id, "once")
            if b.button("Reject", key=f"reject_{perm_id}"):
                client.reply_permission(watcher.session_id, perm_id, "reject")

    for call in snap["order"]:
        t = snap["tools"][call]
        dur = ""
        if t.get("start") and t.get("end"):
            dur = f" · {(t['end'] - t['start']) / 1000:.1f}s"
        label = t.get("title") or json.dumps(t.get("input"), ensure_ascii=False)[:90]
        with st.expander(f"{_ICON.get(t['status'], '•')} **{t['tool']}** — {label}{dur}"):
            st.code(json.dumps(t.get("input"), indent=2, ensure_ascii=False)[:2000], language="json")
            if t.get("output"):
                st.code(str(t["output"])[:4000])
            if t.get("error"):
                st.error(t["error"][:2000])

    text = "\n\n".join(v for v in snap["text"].values() if v)
    if text:
        with st.chat_message("assistant"):
            st.markdown(text)


_timeline()

# ── Artifacts ─────────────────────────────────────────────────────────────────
st.divider()
st.subheader("④ Artifacts (latest run in outputs/)")
latest = c.run_latest()
if latest:
    st.write(f"Latest run: `{latest.folder.name}` ({latest.swc}, {latest.preset})")
    flows = sorted(latest.dir("mud").glob("*.mmd"))
    if flows:
        pick = st.selectbox("Flow chart", [f.name for f in flows])
        c.render_mermaid((latest.dir("mud") / pick).read_text(encoding="utf-8"))
    report = latest.read_text("RUN_REPORT.md", "")
    if report:
        with st.expander("RUN_REPORT.md"):
            st.markdown(report)
else:
    st.caption("No run yet — the agent writes to outputs/<run>/.")
