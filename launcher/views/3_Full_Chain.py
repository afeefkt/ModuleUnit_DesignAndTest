"""Full chain: one-click end-to-end run with a live progress bar and AI activity."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import agents, aio, chain, jobs  # noqa: E402

LABEL = "Full chain"
SAMPLE = _REPO_ROOT / "inputs" / "requirements" / "samples" / "bms_requirements.csv"

st.title("Full chain")
st.markdown("One click from a requirements file to a design, C code, unit tests, coverage and a report. "
            "On local 7–8 B models a quick run takes about 13 minutes.")

col1, col2 = st.columns([3, 2])
with col1:
    req_path = st.text_input("Requirements file", str(SAMPLE),
                             help="CSV, Excel, ReqIF, Markdown or text. DOORS and Polarion exports are recognised.")
with col2:
    quick = st.checkbox("Quick mode", value=True,
                        help="Single-pass spec, no review round, flow built from the spec. Much faster.")

CURRENT = "Current selection (Models page)"
preset_choice = st.selectbox(
    "Models", [CURRENT] + list(agents.load_presets().keys()), index=0,
    help="'Current selection' uses your per-stage choices and leaves them unchanged. "
         "A preset replaces every stage's model first and saves it as your selection.",
)
preset = None if preset_choice == CURRENT else preset_choice

# What will run, and where does the data go?
if preset:
    plan_stages = dict(agents.load_presets()[preset].get("stages", {}))
else:
    plan_stages = agents.get_stages()
cloud = sorted({v.get("provider") for v in plan_stages.values() if v.get("provider") not in (None, "", "ollama")})
with st.expander("Which model runs each stage", expanded=bool(cloud)):
    st.dataframe(
        [{"stage": agents.STAGES_BY_KEY[k].label if k in agents.STAGES_BY_KEY else k,
          "provider": v.get("provider") or "ollama", "model": v.get("model") or "(set when the run starts)"}
         for k, v in plan_stages.items()],
        hide_index=True, width="stretch",
    )
confirmed = True
if cloud:
    st.warning(f"This run sends your requirements and designs to: **{', '.join(cloud)}** (outside this machine). "
               "The run report will list it.")
    confirmed = st.checkbox("I understand — send data to these providers", key="chain_cloud_ok")

job = jobs.current(LABEL)
busy = bool(job and job.running)
if st.button("Start full chain", type="primary", disabled=busy or not confirmed,
             help="A run is already in progress." if busy else
             ("Tick the confirmation above first." if not confirmed else None)):
    from mudmut_core.llm import observe
    observe.clear()

    def _work(progress):
        return aio.run_sync(chain.run_full_chain(req_path, quick=quick, preset=preset, progress=progress))

    job = jobs.start(LABEL, _work, quick=quick)
    st.rerun()


@st.fragment(run_every=1)
def _live() -> None:
    job = jobs.current(LABEL)
    if job is None:
        st.info("No run yet. Press **Start full chain**; progress and every model request appear here live.")
        return
    still_running = c.job_progress_panel(job)
    left, right = st.columns([3, 2])
    with right:
        st.subheader("AI activity")
        c.ai_feed(5, compact=True)
        st.caption("Full detail on the **AI monitor** page.")
    with left:
        if job.status == "done":
            summary = job.result or {}
            st.session_state["current_run_folder"] = summary.get("run_folder", "")
            st.success(f"Finished in {int(job.elapsed)} s. Open **Runs & reports** for test results and coverage.")
            for warning in summary.get("warnings", []):
                st.warning(warning)
        elif job.status == "error":
            st.error(f"The run stopped: {job.error}")
            st.caption("Open **AI monitor** to see the last model request, and **Runs & reports** for the "
                       "partial report.")
    if not still_running and st.session_state.get("_chain_job_seen") != job.id:
        st.session_state["_chain_job_seen"] = job.id
        st.rerun()  # refresh the run bar / stage rail once with the final verdicts


_live()
