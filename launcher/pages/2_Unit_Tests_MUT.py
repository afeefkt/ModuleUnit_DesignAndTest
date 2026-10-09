"""Unit Tests (MUT): generate → build/run → coverage → trace."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import aio, trace as trace_mod  # noqa: E402
from mudmut_core import verify, workspace  # noqa: E402

st.set_page_config(page_title="Unit Tests (MUT)", page_icon="🧪", layout="wide")

st.title("🧪 Unit Tests (MUT)")

runs = c.list_runs()
if not runs:
    st.info("No runs yet — create one on the Design page or the Full Chain page.")
    st.stop()

run_names = [r.folder.name for r in runs]
# Default to the newest run that already has a C skeleton (skip unfinished ones).
default_idx = next((i for i, r in enumerate(runs) if r.path("project").is_dir()), 0)
current = st.session_state.get("current_run_folder")
if current:
    for i, r in enumerate(runs):
        if r.folder.name == Path(current).name:
            default_idx = i

choice = st.selectbox("Run", run_names, index=default_idx)
run = next(r for r in runs if r.folder.name == choice)

st.caption(f"Folder: `{run.folder}`")

project_dir = run.path("project")
if not project_dir.is_dir():
    st.error("No `project/` directory (C skeleton) found for this run.")
    st.stop()

st.subheader("C skeleton (compilable)")
st.code(run.read_text(workspace.SKELETON, "(none)"), language="c")

if st.button("Generate tests", type="primary"):
    with st.status("Analyzing + generating tests…", expanded=True) as status:
        generation = aio.run_sync(verify.generate_tests(project_dir))
        run.save_json(workspace.RESULTS, {"generation": generation})
        status.update(label="Tests generated", state="complete")

generation = (run.read_json(workspace.RESULTS) or {}).get("generation")
if generation:
    st.success(
        f"{generation.get('tests_generated')} test(s) for "
        f"{generation.get('functions_analyzed')} function(s)"
    )
    out_dir = Path(generation.get("output_directory", ""))
    if out_dir.is_dir():
        if st.button("Build & run (+ fix loop)"):
            with st.status("Building + running…", expanded=True) as status:
                result = verify.fix_loop(out_dir, max_attempts=2)
                run.save_json(workspace.RESULTS, {"generation": generation, "run": result})
                status.update(label="Done", state="complete")
        result = (run.read_json(workspace.RESULTS) or {}).get("run")
        if result:
            junit = result.get("junit") or {}
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Status", result.get("status"))
            m2.metric("Passed", junit.get("passed", "?"))
            m3.metric("Failed", junit.get("failures", "?"))
            if result.get("quarantined_tests"):
                st.warning(
                    "Quarantined (still failed to compile after the fix attempts): "
                    + ", ".join(result["quarantined_tests"])
                    + " — kept in the `quarantined/` folder of the test run."
                )
            if result.get("smoke_fallback"):
                st.info("No AI-generated test compiled, so a deterministic smoke test "
                        "(each runnable executed once) was built and run instead.")
            m4.metric("Fix attempts", result.get("fix_attempts", 0))
            if result.get("build_error"):
                with st.expander("Build output"):
                    st.code(result.get("build_error", ""))
            if result.get("test_output"):
                with st.expander("Test output"):
                    st.code(result.get("test_output", ""))
            for label, path_key in (("Coverage HTML", "coverage_html_path"), ("Test report", "report_path")):
                p = result.get(path_key)
                if p and Path(p).exists():
                    st.link_button(f"Open {label}", f"file://{p}")
            # traceability
            if st.button("Write traceability"):
                code = run.read_text(workspace.SKELETON, "")
                record = trace_mod.build_trace(run.swc, code, generation)
                run.save_json(workspace.TRACE, record)
                st.session_state["trace"] = record
            trace_record = st.session_state.get("trace") or run.read_json(workspace.TRACE)
            if trace_record:
                st.subheader("Traceability (requirement → tests)")
                summary = trace_record.get("summary")
                if summary:
                    st.caption(
                        f"{summary.get('verified_by_test', 0)} of {summary['requirements']} requirement(s) "
                        f"verified (tests ran and passed) · {summary.get('failing_test', 0)} with failing tests · "
                        f"{summary.get('test_not_run', 0)} tests not run · {summary.get('not_verified', 0)} not verified"
                    )
                st.table([
                    {
                        "requirement": t["requirement"],
                        "status": t.get("status", ""),
                        "verified_by": ", ".join(t["verified_by"]) or "—",
                    }
                    for t in trace_record["trace"]
                ])
