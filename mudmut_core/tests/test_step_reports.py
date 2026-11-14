"""Run reports for steps made by hand (Requirements & design page, Unit tests page)."""

from mudmut_core import design_run, report
from mudmut_core.workspace import Run


def _verdicts(run):
    return run.read_json("run.json")["verdicts"]


def test_reached_marks_later_stages_not_run(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    report.write_run_report(run, {"swc": "SWC_Test", "quick": True}, reached=["import", "plan", "spec"])
    v = _verdicts(run)
    assert v["spec"] == "✅"
    for stage in ("review", "activity", "compilable", "generate_tests", "build_run", "trace"):
        assert v[stage] == "—", stage


def test_design_steps_write_run_json_and_redo_invalidates_later_steps(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path, preset=design_run.PRESET)
    run.save_state(reached=["import", "plan"], stage_notes={})
    design_run.record_step(run, "spec", note="1200 chars")
    design_run.record_step(run, "activity", note="1 diagram(s)")
    run.save_json_in("code", "compilability.json", {
        "kept_statements": 10, "stubbed_statements": 0, "compile_ok": True,
        "logic_stubbed": 0, "never_assigned": [], "dropped_arguments": 0})
    design_run.record_step(run, "compilable", note="10 kept")
    v = _verdicts(run)
    assert (v["spec"], v["review"], v["activity"], v["compilable"]) == ("✅", "—", "✅", "✅")
    assert v["generate_tests"] == "—" and v["trace"] == "—"
    assert "RUN_REPORT.md" in {p.name for p in run.folder.iterdir()}

    # Saving spec edits = the spec stage again: the flow and C code made from the old text are not run any more.
    design_run.record_step(run, "spec", note="edited by hand")
    v = _verdicts(run)
    assert v["spec"] == "✅" and v["activity"] == "—" and v["compilable"] == "—"
    assert run.state["stage_notes"] == {"spec": "edited by hand"}


def test_design_compile_with_dropped_logic_is_a_failure(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path, preset=design_run.PRESET)
    run.save_state(reached=["import", "plan", "spec", "activity"], stage_notes={})
    run.save_json_in("code", "compilability.json", {
        "kept_statements": 8, "stubbed_statements": 2, "compile_ok": True,
        "logic_stubbed": 2, "never_assigned": ["x"], "dropped_arguments": 0})
    design_run.record_step(run, "compilable")
    assert _verdicts(run)["compilable"] == "❌"


def test_manual_rebuild_updates_only_test_verdicts(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    report.write_run_report(run, {"swc": "SWC_Test", "quick": True, "tests_generated": 2,
                                  "compilability": {"compile_ok": True, "stubbed": 0},
                                  "tests": {"status": "build_failed"}})
    before = run.read_json("run.json")
    assert before["verdicts"]["build_run"] == "❌"

    generation = {"tests_generated": 2, "failed_functions": []}
    report.update_after_manual_step(run, generation=generation,
                                    test_result={"status": "passed", "junit": {"passed": 5, "failures": 0}},
                                    note="rebuild")
    after = run.read_json("run.json")
    assert after["verdicts"]["build_run"] == "✅"
    assert after["verdicts"]["generate_tests"] == "✅"
    assert after["models"] == before["models"]                 # what the run used is kept
    assert after["verdicts"]["compilable"] == before["verdicts"]["compilable"]
    assert "## Manual steps" in run.read_text("RUN_REPORT.md")


def test_new_tests_reset_build_and_trace_until_rebuilt(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    report.write_run_report(run, {"swc": "SWC_Test", "quick": True, "tests_generated": 1,
                                  "tests": {"status": "passed"}})
    report.update_after_manual_step(run, generation={"tests_generated": 3, "failed_functions": ["f"]})
    v = _verdicts(run)
    assert v["generate_tests"] == "⚠️"           # one function got no test
    assert v["build_run"] == "—" and v["trace"] == "—"


def test_manual_step_without_run_json_is_skipped(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    assert report.update_after_manual_step(run, trace_record={"summary": {}}) is None


def test_smoke_only_rebuild_is_a_failure(tmp_path):
    assert report.build_run_verdict({"status": "passed", "smoke_fallback": True}) == "❌"
    assert report.build_run_verdict({"status": "passed", "quarantined_tests": ["Test_a.cpp"]}) == "⚠️"
    assert report.generate_tests_verdict(2, 0, ["Test_a.cpp", "Test_b.cpp"]) == "❌"
