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


st.title("Unit tests")

runs = c.list_runs()
if not runs:
    st.info("No runs yet — create one on the Design page or the Full Chain page.")
    st.stop()

run = c.current_run()  # chosen in the run bar at the top of every page

st.caption(f"Run folder: `{run.folder}`")

project_dir = run.dir("code")
if not project_dir.is_dir():
    st.error("No `02_code/` directory (C skeleton) found for this run.")
    st.stop()

st.subheader("C skeleton (compilable)")
_stub_c = run.read_in("code", f"{run.swc}.c", "")
if not _stub_c:
    _stub_c = run.read_text("skeleton.c", "(none)")
st.code(_stub_c or "(none)", language="c")

if st.button("Generate tests", type="primary"):
    with st.status("Analyzing + generating tests…", expanded=True) as status:
        def _gen(report):
            def on_fn(done: int, total: int, name: str) -> None:
                report({"stage": "tests", "message": f"function {done + 1} of {total}: {name}",
                        "fraction": done / max(total, 1)})
            return aio.run_sync(verify.generate_tests(project_dir, output_dir=run.dir("mut"), progress=on_fn))

        generation = c.run_with_progress("Generating tests", _gen)
        run.save_json_in("mut", "results.json", {"generation": generation})
        status.update(label="Tests generated", state="complete")

generation = (run.read_json_in("mut", "results.json") or {}).get("generation")
if generation:
    st.success(
        f"{generation.get('tests_generated')} test(s) for "
        f"{generation.get('functions_analyzed')} function(s)"
    )
    out_dir = Path(generation.get("output_directory", ""))
    if out_dir.is_dir():
        st.caption("The Makefile is regenerated on every build from the CppUTest folder in Settings "
                   "(no need to regenerate the tests after changing it).")
        if st.button("Rebuild & run (+ fix loop)"):
            with st.status("Building + running…", expanded=True) as status:
                result = verify.fix_loop(out_dir, max_attempts=2)
                run.save_json_in("mut", "results.json", {"generation": generation, "run": result})
                status.update(label="Done", state="complete")
        result = (run.read_json_in("mut", "results.json") or {}).get("run")
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
            cpp = result.get("cpputest") or {}
            if result.get("cpputest_missing"):
                st.error("CppUTest was not found. Set its folder on the **Settings** page "
                         "(or install it) and rebuild.")
            elif cpp.get("found"):
                st.caption(f"CppUTest: `{cpp.get('home')}` (lib `{cpp.get('lib_dir')}`)")
            if result.get("build_error"):
                with st.expander("Build output"):
                    st.code(result.get("build_error", ""))
            if result.get("test_output"):
                with st.expander("Test output"):
                    st.code(result.get("test_output", ""))
            st.subheader("Results")
            c.results_panel(run, key="mut")
            # traceability
            if st.button("Write traceability"):
                code = run.read_in("code", f"{run.swc}.c", "")
                record = trace_mod.build_trace(run.swc, code, generation)
                run.save_json_in("trace", "trace.json", record)
                st.session_state["trace"] = record
            trace_record = st.session_state.get("trace") or run.read_json_in("trace", "trace.json")
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
