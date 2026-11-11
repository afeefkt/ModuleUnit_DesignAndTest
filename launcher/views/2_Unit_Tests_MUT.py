"""Unit Tests (MUT): generate → build/run → coverage → trace.

Generating and building run in the background with a live bar (the page stays usable). Each step
updates the run's ``results.json``, ``run.json`` verdicts and ``RUN_REPORT.md``, so the stage rail
and Runs & reports show what was done by hand.
"""

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
from mudmut_core import progress as progress_mod  # noqa: E402
from mudmut_core import report as report_mod  # noqa: E402
from mudmut_core import verify  # noqa: E402

ss = st.session_state


def _expected(stage: str) -> float:
    return progress_mod.expected_seconds(quick=True).get(stage, 120.0)


def _done(message: str) -> None:
    ss["mut_flash"] = message
    st.rerun()


def _results(run) -> dict:
    data = run.read_json_in("mut", "results.json") or {}
    return data if isinstance(data, dict) else {}


def _write_trace(run, generation: dict) -> dict:
    code = run.read_in("code", f"{run.swc}.c", "")
    record = trace_mod.build_trace(run.swc, code, generation)
    run.save_json_in("trace", "trace.json", record)
    run.save_in("trace", "trace.md", report_mod.trace_markdown(record))
    return record


st.title("Unit tests")

runs = c.list_runs()
if not runs:
    st.info("No runs yet. Create one with **Full chain**, or step by step on **Requirements & design**.")
    st.page_link("views/3_Full_Chain.py", label="Open Full chain", icon="🔗")
    st.stop()

run = c.current_run()  # chosen in the run bar at the top of every page
if run is None:
    st.info("No run selected. Choose a run in the bar at the top, or create one with **Full chain** or "
            "**Requirements & design**.")
    st.stop()

st.caption(f"Run folder: `{run.folder}`")
flash = ss.pop("mut_flash", None)
if flash:
    st.success(flash)

project_dir = run.dir("code")
if not project_dir.is_dir() or not any(project_dir.glob("*.c")):
    st.warning(f"Run `{run.folder.name}` has no C skeleton yet, so there is nothing to test. "
               "Pick another run in the bar above, or create the C code first.")
    l1, l2 = st.columns(2)
    with l1:
        st.page_link("views/1_Design_MUD.py", label="Requirements & design → step ⑥ C skeleton", icon="📐")
    with l2:
        st.page_link("views/3_Full_Chain.py", label="Full chain", icon="🔗")
    st.stop()

busy = c.any_step_running()
mut_dir = run.dir("mut")

with st.expander("C skeleton (compilable)", expanded=False):
    _stub_c = run.read_in("code", f"{run.swc}.c", "") or run.read_text("skeleton.c", "")
    st.code(_stub_c or "(none)", language="c")

# ── Generate tests ────────────────────────────────────────────────────────────
out = c.step_outcome("mut_generate")
if out and out.ok and out.context.get("run") == str(run.folder):
    generation = out.result or {}
    previous = _results(run)
    record = {"generation": generation}
    if previous.get("run"):
        record["previous_run"] = previous["run"]   # results of the old tests, kept for the record
    run.save_json_in("mut", "results.json", record)
    report_mod.update_after_manual_step(
        run, generation=generation,
        note=f"Unit tests page: generated {generation.get('tests_generated', 0)} test file(s); not built yet")
    _done(f"{generation.get('tests_generated', 0)} test file(s) generated. Press **Rebuild & run** to build them.")
elif out and out.ok:
    st.warning(f"Tests were generated for `{Path(out.context.get('run', '')).name}`, not for the run shown now. "
               "Select that run in the bar above to see them.")
elif out and not out.running:
    c.show_step_failure(out, "Test generation")

if st.button("Generate tests", type="primary", disabled=busy,
             help="Writes one CppUTest file per runnable into 03_mut/. Existing test files are replaced."):
    def _gen(report, src=project_dir, dst=mut_dir):
        def on_fn(done: int, total: int, name: str) -> None:
            report({"stage": "tests", "message": f"function {done + 1} of {total}: {name}",
                    "fraction": done / max(total, 1)})
        return aio.run_sync(verify.generate_tests(src, output_dir=dst, progress=on_fn))

    c.start_step("mut_generate", "Generating tests", _gen, expected_seconds=_expected("generate_tests"),
                 context={"run": str(run.folder)})
    st.rerun()

data = _results(run)
generation = data.get("generation")
if not generation:
    st.caption("No generated tests in this run yet.")
    st.stop()

st.success(f"{generation.get('tests_generated')} test(s) for {generation.get('functions_analyzed')} function(s)")
failed_fns = generation.get("failed_functions") or []
if failed_fns:
    st.warning("No test could be generated for: " + ", ".join(str(f) for f in failed_fns))

# The tests live in this run's 03_mut/. An older results.json may name another folder (a moved or
# renamed run), so the run's own folder wins when it has the test files.
recorded = Path(generation.get("output_directory") or "")
if any(mut_dir.glob("Test_*.cpp")) or any((mut_dir / "quarantined").glob("Test_*.cpp")):
    test_dir = mut_dir
elif str(recorded) not in ("", ".") and recorded.is_dir():
    test_dir = recorded
else:
    test_dir = None
    st.error(f"The generated test files are missing from `{mut_dir}`"
             + (f" (and from `{recorded}`)" if str(recorded) not in ("", ".") else "")
             + ". Press **Generate tests** again.")

# ── Build & run ───────────────────────────────────────────────────────────────
out = c.step_outcome("mut_build")
if out and out.ok and out.context.get("run") == str(run.folder):
    result = out.result or {}
    current = _results(run)
    current["run"] = result
    run.save_json_in("mut", "results.json", current)
    junit = result.get("junit") or {}
    report_mod.update_after_manual_step(
        run, generation=current.get("generation"), test_result=result,
        note=(f"Unit tests page: rebuild & run — {result.get('status')}, {junit.get('passed', 0)} passed, "
              f"{junit.get('failures', 0)} failed (fix attempts {result.get('fix_attempts', 0)})"))
    _done(f"Build & run finished: {result.get('status')} — {junit.get('passed', 0)} passed, "
          f"{junit.get('failures', 0)} failed.")
elif out and out.ok:
    st.warning(f"The build finished for `{Path(out.context.get('run', '')).name}`, not for the run shown now.")
elif out and not out.running:
    c.show_step_failure(out, "Build & run")

if test_dir is not None:
    st.caption("The Makefile is regenerated on every build from the CppUTest folder in Settings "
               "(no need to regenerate the tests after changing it).")
    if st.button("Rebuild & run (+ fix loop)", disabled=busy,
                 help="Builds in WSL, asks the model to fix test files that do not compile (2 rounds), "
                      "then runs the tests with coverage. It cannot be cancelled half-way."):
        c.start_step("mut_build", "Building and running the tests",
                     lambda report, d=test_dir: verify.fix_loop(d, max_attempts=verify.MAX_FIX_ATTEMPTS),
                     expected_seconds=_expected("build_run"), cancellable=False,
                     context={"run": str(run.folder)})
        st.rerun()

result = data.get("run")
if not result:
    if data.get("previous_run"):
        st.info("The tests were regenerated after the last build — press **Rebuild & run** for current results.")
    st.stop()

junit = result.get("junit") or {}
m1, m2, m3, m4 = st.columns(4)
m1.metric("Status", result.get("status"))
m2.metric("Passed", junit.get("passed", "?"))
m3.metric("Failed", junit.get("failures", "?"))
m4.metric("Fix attempts", result.get("fix_attempts", 0))
if result.get("quarantined_tests"):
    st.warning(
        "Quarantined (still failed to compile after the fix attempts): "
        + ", ".join(result["quarantined_tests"])
        + " — kept in the `quarantined/` folder of the test run."
    )
if result.get("smoke_fallback"):
    st.info("No AI-generated test compiled, so a deterministic smoke test "
            "(each runnable executed once) was built and run instead.")
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

# ── Traceability ──────────────────────────────────────────────────────────────
st.subheader("Traceability (requirement → tests)")
if st.button("Write traceability", disabled=busy,
             help="Links each requirement ID in the C skeleton to the test file of its function and the JUnit result."):
    try:
        record = _write_trace(run, generation)
        report_mod.update_after_manual_step(
            run, trace_record=record,
            note=f"Unit tests page: traceability — {record['summary'].get('verified_by_test', 0)} of "
                 f"{record['summary']['requirements']} requirement(s) verified")
    except Exception as exc:  # noqa: BLE001 - a malformed skeleton or results file
        st.error(f"Could not write the traceability: {exc}")
    else:
        _done("Traceability written.")
# Always this run's own file (a screen copy would leak into other runs).
c.trace_view(run.read_json_in("trace", "trace.json"), key="mut")
