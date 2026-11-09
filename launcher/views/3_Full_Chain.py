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
from mudmut_core import agents, aio, chain, jobs, settings  # noqa: E402

LABEL = "Full chain"
SAMPLE = _REPO_ROOT / "inputs" / "requirements" / "samples" / "bms_requirements.csv"
OTHER = "Other file (type a path)…"

st.title("Full chain")
st.markdown("One click from a requirements file to a design, C code, unit tests, coverage and a report. "
            "On local 7–8 B models a quick run takes about 13 minutes per software component.")

# ── Requirements file ────────────────────────────────────────────────────────
files = c.requirement_files()
labels = [c.file_label(p) for p in files] + [OTHER]
wanted = st.session_state.get("chain_req_path") or str(SAMPLE)
default = next((i for i, p in enumerate(files) if str(p) == wanted), 0)
col1, col2 = st.columns([3, 2])
with col1:
    choice = st.selectbox("Requirements file", labels, index=default if files else 0,
                          help="Files under inputs/requirements*/ (hardened baselines are marked). "
                               "CSV, Excel, ReqIF, Markdown or text; DOORS and Polarion exports are recognised.")
    if choice == OTHER or not files:
        req_path = st.text_input("Path to the requirements file", wanted)
    else:
        req_path = str(files[labels.index(choice)])
with col2:
    quick = st.checkbox("Quick mode", value=True,
                        help="Single-pass spec, no review round, flow built from the spec. Much faster.")
    if st.button("Check file", help="Import only (no AI): how many requirements are recognised."):
        from mudmut_core import design
        try:
            res = design.import_requirements(req_path)
            n = res.requirement_set.count
            (st.success if n else st.error)(
                f"{n} requirement(s) recognised" + (f", {len(res.warnings)} warning(s)" if res.warnings else "")
                + ("" if n else f": {res.errors}"))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not read the file: {exc}")

# ── Software components ──────────────────────────────────────────────────────
SWC_FIRST, SWC_ALL, SWC_NAMED = ("The first planned component", "Every planned component (one run each)",
                                 "Specific components…")
swc_mode = st.radio("Software components", [SWC_FIRST, SWC_ALL, SWC_NAMED], horizontal=True,
                    help="Requirements for a whole feature usually plan into several SWCs. The plan is made once; "
                         "each component then gets its own run folder and report.")
only: list[str] = []
if swc_mode == SWC_NAMED:
    raw = st.text_input("Component names (comma separated)", placeholder="SWC_AEB_Controller, SWC_AEB_RiskAssessor",
                        help="Names as the planner writes them; unknown names are reported.")
    only = [x.strip() for x in raw.split(",") if x.strip()]

# ── Models ───────────────────────────────────────────────────────────────────
CURRENT = "Current selection (Models page)"
preset_choice = st.selectbox(
    "Models", [CURRENT] + list(agents.load_presets().keys()), index=0,
    help="'Current selection' uses your per-stage choices and leaves them unchanged. "
         "A preset replaces every stage's model first and saves it as your selection.",
)
preset = None if preset_choice == CURRENT else preset_choice

plan_stages = dict(agents.load_presets()[preset].get("stages", {})) if preset else agents.get_stages()
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
needs_names = swc_mode == SWC_NAMED and not only
start_help = ("A run is already in progress." if busy else
              "Tick the confirmation above first." if not confirmed else
              "Type at least one component name." if needs_names else None)
if st.button("Start full chain", type="primary", disabled=busy or not confirmed or needs_names, help=start_help):
    if settings.auto_reset_enabled():
        c.reset_view()          # start clean: previous job panel, AI list, caches, page state
    else:
        from mudmut_core.llm import observe
        observe.clear()
    st.session_state["chain_req_path"] = req_path

    if swc_mode == SWC_FIRST:
        def _work(progress):
            return aio.run_sync(chain.run_full_chain(
                req_path, quick=quick, preset=preset, progress=progress,
                cancel=getattr(progress, "cancelled", None)))
        jobs.start(LABEL, _work, quick=quick)
    else:
        def _work(progress):
            return aio.run_sync(chain.run_all_swcs(
                req_path, only=only or None, quick=quick, preset=preset, progress=progress,
                cancel=getattr(progress, "cancelled", None)))
        jobs.start(LABEL, _work, quick=quick, track=False)
    st.rerun()


def _new_run() -> None:
    ok, msg = c.reset_view()
    st.session_state["_reset_msg"] = (ok, msg)


def _live() -> None:
    """Refresh every 2 s only while a run is going; a finished run is drawn once.

    Refreshing every second forever (with the AI call texts) made the browser hang after a run.
    """
    job = jobs.current(LABEL)
    if job is not None and job.running:
        _live_running()
    else:
        _live_body()


@st.fragment(run_every=2)
def _live_running() -> None:
    _live_body()


def _live_body() -> None:
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
        result = job.result or {}
        if job.status == "done":
            st.success(f"Finished in {int(job.elapsed)} s. Open **Runs & reports** for test results and coverage.")
            for item in result.get("swcs", []):
                if item["status"] == "done":
                    st.markdown(f"- ✅ **{item['swc']}** — `{Path(item['run_folder']).name}`")
                else:
                    st.markdown(f"- ❌ **{item['swc']}** — {item.get('error', '')}")
            for warning in result.get("warnings", []):
                st.warning(warning)
        elif job.status == "cancelled":
            st.info(f"Cancelled: {job.error}. The partial report is in **Runs & reports**.")
        elif job.status == "error":
            st.error(f"The run stopped: {job.error}")
            st.caption("Open **AI monitor** to see the last model request, and **Runs & reports** for the "
                       "partial report.")
        if not job.running:
            st.button("New run — clear these results", key=f"new_run_{job.id}", on_click=_new_run,
                      help="Clears this panel, the AI call list and cached lookups. Saved runs stay in Runs & reports.")
    if not still_running and st.session_state.get("_chain_job_seen") != job.id:
        # Select the finished run once (not on every refresh, so you can pick another run afterwards).
        st.session_state["_chain_job_seen"] = job.id
        folder = (job.result or {}).get("run_folder") or job.run_folder
        if folder:
            c.select_run(folder)
        # Full rerun once: refreshes the run bar / stage rail and stops the timed refresh.
        st.rerun(scope="app")


_live()
