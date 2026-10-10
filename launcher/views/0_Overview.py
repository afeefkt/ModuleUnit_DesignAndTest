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
if run is None:
    st.info("Nothing has been run yet. Open **Full chain** for a one-click run on the sample requirements, "
            "or **Requirements & design** to go step by step.")
else:
    verdicts = (run.read_json("run.json") or {}).get("verdicts", {})
    if not verdicts:
        st.info(f"Run `{run.folder.name}` has no report yet — open **Unit tests** to continue it.")
    elif "❌" in verdicts.values():
        bad = next(k for k, v in verdicts.items() if v == "❌")
        st.error(f"The latest run failed at **{bad}**. Open **Runs & reports** for the evidence, "
                 "or **AI monitor** to see what the model returned.")
    elif "⚠️" in verdicts.values():
        st.warning("The latest run finished with partial results (⚠️ in the stage bar). "
                   "Open **Runs & reports** → Test results to see what was only partly done.")
    else:
        st.success("The latest run passed every stage. Review the evidence in **Runs & reports**.")

st.markdown(
    "- **Full chain** — one click from a requirements file to tests and a report.\n"
    "- **AI monitor** — watch every request and answer between this app and the model, or chat with a model to check it works.\n"
    "- **Models** — choose the provider and model for each stage; **Keys** — test connections.\n"
    "- **Settings** — CppUTest location and compiler flags."
)
