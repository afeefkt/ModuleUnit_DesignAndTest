"""Overview — system health and the next step for the current run."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402

ollama_host = c.bootstrap()

st.title("MUD_MUT control center")
st.caption("Requirements → module design (MUD) → C code → CppUTest unit tests (MUT) → traceability, "
           "with local or cloud AI. Every result is an AI-assisted draft for engineer review.")

# ── Health ───────────────────────────────────────────────────────────────────
st.header("System health")
h1, h2, h3 = st.columns(3)
with h1:
    st.subheader("Local AI (Ollama)")
    models = c.ollama_models(ollama_host)
    if models:
        st.success(f"Running — {len(models)} model(s) at {ollama_host}")
        st.caption(", ".join(f"`{m}`" for m in models[:8]) + (" …" if len(models) > 8 else ""))
    else:
        st.error(f"Not reachable at {ollama_host}. Start Ollama, then reload this page. "
                 "Cloud models still work without it.")
with h2:
    st.subheader("Build tools (WSL)")
    report = c.toolchain_report()
    if report is None:
        st.error("Could not run the tool check. Is WSL installed?")
    else:
        for tool in report.tools:
            st.write(f"{'✅' if tool.available else '❌'} **{tool.name}** — {tool.detail}")
        if not report.ok:
            st.info("Missing tools: set the CppUTest folder on **Settings**, or install in WSL (as root):\n\n"
                    f"```\n{c.run_toolchain_install_hint()}\n```")
with h3:
    st.subheader("Cloud AI keys")
    try:
        from mudmut_core.llm import get_providers, has_key
        for p in get_providers().values():
            if p.is_cloud:
                st.write(f"{'✅' if has_key(p) else '⚪'} {p.name} — {'key found' if has_key(p) else 'no key'}")
        st.caption("Cloud models send your requirements and designs off this machine. "
                   "Each run report lists which providers were used.")
    except Exception as exc:  # noqa: BLE001
        st.caption(f"Could not read provider keys: {exc}")

# ── Next step ────────────────────────────────────────────────────────────────
st.header("What to do next")
run = c.current_run()
if run is None and c.list_runs():
    st.info("No run selected (the view was reset). Choose a run in the top bar to see where it stands, "
            "or start a new one on **Full chain**.")
elif run is None:
    st.info("Nothing has been run yet. Open **Full chain** for a one-click run on the sample requirements, "
            "or **Requirements & design** to go step by step.")
else:
    from mudmut_core.report import STAGE_ORDER, effective_verdicts
    verdicts = effective_verdicts(run.read_json("run.json") or {})   # same rules as the stage rail
    name = f"`{run.folder.name}`"
    note = c.run_status_note(run)
    if note:
        st.warning(f"The selected run {name}: {note}.")
    if not verdicts:
        st.info(f"The selected run {name} has no report yet — open **Unit tests** to continue it.")
    elif "❌" in verdicts.values():
        bad = next(k for k in STAGE_ORDER if verdicts.get(k) == "❌")
        st.error(f"The selected run {name} failed at **{bad}**. Open **Runs & reports** for the evidence, "
                 "or **AI monitor** to see what the model returned.")
    elif "⚠️" in verdicts.values():
        st.warning(f"The selected run {name} finished with partial results (⚠️ in the stage bar). "
                   "Open **Runs & reports** → Test results to see what was only partly done.")
    elif "—" in verdicts.values():
        st.info(f"The selected run {name} has stages that have not run yet (grey in the stage bar). "
                "Continue it on **Unit tests**, or start a new run on **Full chain**.")
    else:
        st.success(f"The selected run {name} passed every stage. Review the evidence in **Runs & reports** — "
                   "a pass is an AI-assisted draft, not proof that the requirements are met.")

st.subheader("Pages")
_PAGES = [
    ("views/3_Full_Chain.py", "Full chain", "🔗", "one click from a requirements file to tests and a report"),
    ("views/10_Harden_Requirements.py", "Harden requirements", "🧱", "make requirements atomic and testable first (optional)"),
    ("views/1_Design_MUD.py", "Requirements & design", "📐", "go step by step: import, plan, spec, review, flow, C code"),
    ("views/2_Unit_Tests_MUT.py", "Unit tests", "🧪", "generate, build and run the tests of the selected run"),
    ("views/6_Runs_Reports.py", "Runs & reports", "📊", "all runs, test report, coverage, trace, compare, archive"),
    ("views/9_AI_Monitor.py", "AI monitor", "🛰️", "every request and answer, and a test chat with a model"),
    ("views/4_Workflow_Models.py", "Models", "🧠", "provider and model for each stage"),
    ("views/5_Providers.py", "Keys & providers", "🔑", "key status, connection test, free-model probe"),
    ("views/8_Settings.py", "Settings", "⚙️", "CppUTest location and compiler flags"),
]
for target, label, icon, what in _PAGES:
    left, right = st.columns([1.3, 3], vertical_alignment="center")
    with left:
        st.page_link(target, label=label, icon=icon)
    right.caption(what)
