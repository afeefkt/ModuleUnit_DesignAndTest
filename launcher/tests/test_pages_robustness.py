"""One test per robustness fix of the GUI plan (DevPlan GUI_ROBUSTNESS_PLAN tier A)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from conftest import errors, make_run, open_page, settle

LONG_SPEC = "# MUD spec\n\n" + ("Section text for the test component. " * 20)


# ── A2: cloud consent belongs to one provider set ────────────────────────────
def test_cloud_consent_is_asked_again_for_another_provider(outputs, monkeypatch):
    import mudmut_core.agents as agents
    monkeypatch.setattr(agents, "get_stages", lambda: {"spec": {"provider": "deepseek", "model": "m"}})
    at = open_page("3_Full_Chain.py")
    at.checkbox(key="chain_cloud_ok_deepseek").check().run()
    assert not at.button[[b.label for b in at.button].index("Start full chain")].disabled

    monkeypatch.setattr(agents, "get_stages", lambda: {"spec": {"provider": "openrouter", "model": "m"}})
    at.run()
    assert at.checkbox(key="chain_cloud_ok_openrouter").value is False
    start = at.button[[b.label for b in at.button].index("Start full chain")]
    assert start.disabled, "consent for deepseek must not cover openrouter"
    assert not at.exception


def test_full_chain_refuses_a_missing_file(outputs):
    at = open_page("3_Full_Chain.py")
    at.selectbox[0].select("Other file (type a path)…").run()
    at.text_input[0].set_value("inputs/requirements/does_not_exist.csv").run()
    assert any("File not found" in e for e in errors(at))
    start = at.button[[b.label for b in at.button].index("Start full chain")]
    assert start.disabled


# ── A3: a selected table row does not pull the run bar back ──────────────────
def test_run_bar_choice_survives_a_selected_table_row(outputs):
    a = make_run(outputs, "SWC_A")
    b = make_run(outputs, "SWC_B")
    at = open_page("6_Runs_Reports.py")
    table_key = at.session_state["_runs_table_key"]
    row_of_a = [r["run"] for r in at.dataframe[0].value.to_dict("records")].index(a.folder.name)

    # Click row A in the table: A becomes the current run.
    at.session_state[table_key] = {"selection": {"rows": [row_of_a], "columns": [], "cells": []}}
    at.run()
    assert at.session_state["current_run_folder"] == str(a.folder), "the table click was not simulated"

    # Row A stays selected; now run B is chosen in the top bar. B must stay current.
    bar = next(s for s in at.selectbox if s.label == "Current run")
    bar.select(b.folder.name).run()
    at.run()
    assert not at.exception
    assert at.session_state["current_run_folder"] == str(b.folder)


# ── A4: Unit tests — background build, errors shown, results merged ──────────
@pytest.fixture()
def run_with_tests(outputs):
    run = make_run(outputs, "SWC_Mut", c_code="void RE_Init(void)\n{\n}\n")
    (run.dir("mut") / "Test_RE_Init.cpp").write_text("// test", encoding="utf-8")
    # output_directory empty: an older results.json; the run's own 03_mut/ must be used, not ".".
    run.save_json_in("mut", "results.json", {"generation": {"tests_generated": 1, "functions_analyzed": 1,
                                                            "failed_functions": [], "output_directory": ""}})
    return run


def _click(at, label):
    at.button[[b.label for b in at.button].index(label)].click().run()
    return at


def test_rebuild_failure_is_an_error_box_not_a_traceback(run_with_tests, monkeypatch):
    from mudmut_core import verify
    monkeypatch.setattr(verify, "fix_loop", lambda d, max_attempts=2: (_ for _ in ()).throw(RuntimeError("make: not found")))
    at = open_page("2_Unit_Tests_MUT.py")
    settle(_click(at, "Rebuild & run (+ fix loop)"))
    assert not at.exception
    assert any("Build & run failed" in e and "make: not found" in e for e in errors(at))


def test_rebuild_runs_in_the_run_folder_and_updates_the_report(run_with_tests, monkeypatch):
    from mudmut_core import verify
    seen = {}

    def fake_fix_loop(test_dir, max_attempts=2):
        seen["dir"] = test_dir
        return {"status": "passed", "junit": {"passed": 3, "failures": 0}, "fix_attempts": 0,
                "quarantined_tests": [], "smoke_fallback": False}

    monkeypatch.setattr(verify, "fix_loop", fake_fix_loop)
    at = open_page("2_Unit_Tests_MUT.py")
    settle(_click(at, "Rebuild & run (+ fix loop)"))
    assert not at.exception
    assert seen["dir"] == run_with_tests.dir("mut")
    saved = run_with_tests.read_json_in("mut", "results.json")
    assert saved["generation"]["tests_generated"] == 1 and saved["run"]["status"] == "passed"
    assert run_with_tests.read_json("run.json")["verdicts"]["build_run"] == "✅"
    assert "## Manual steps" in run_with_tests.read_text("RUN_REPORT.md")


# ── A5 / A6: Requirements & design — errors shown, one complete run folder ────
def _fake_plan():
    module = SimpleNamespace(swc_name="SWC_Alpha", req_ids=[], description="d", asil="QM", runnables=[])
    other = SimpleNamespace(swc_name="SWC_Beta", req_ids=[], description="d", asil="QM", runnables=[])
    return SimpleNamespace(modules=[module, other], architecture_summary="two components")


def _imported(monkeypatch):
    at = open_page("1_Design_MUD.py")
    _click(at, "Import requirements")
    assert not at.exception and "design_reqs" in at.session_state
    return at


def test_design_model_error_is_shown_and_earlier_steps_stay(outputs, monkeypatch):
    from mudmut_core import design

    async def broken(text):
        raise RuntimeError("model not reachable")

    monkeypatch.setattr(design, "plan_modules", broken)
    at = _imported(monkeypatch)
    settle(_click(at, "Plan SWC modules"))
    assert not at.exception
    assert any("Planning failed" in e and "model not reachable" in e for e in errors(at))
    assert "design_reqs" in at.session_state      # the import is still there


def test_design_spec_writes_one_complete_run_and_freezes_the_component(outputs, monkeypatch):
    from mudmut_core import design
    from mudmut_core.workspace import Run

    async def plan(text):
        return _fake_plan()

    async def spec(module, text, mode="two_stage", progress=None):
        return LONG_SPEC

    monkeypatch.setattr(design, "plan_modules", plan)
    monkeypatch.setattr(design, "generate_mud_spec", spec)
    at = _imported(monkeypatch)
    settle(_click(at, "Plan SWC modules"))
    settle(_click(at, "Generate MUD spec"))
    assert not at.exception

    runs = Run.list_runs()
    assert len(runs) == 1, "one run folder per generated spec"
    run = runs[0]
    assert run.swc == "SWC_Alpha"
    assert run.read_in("mud", "mud_spec.md") == LONG_SPEC
    assert run.read_json_in("input", "requirements.json")
    verdicts = run.read_json("run.json")["verdicts"]
    assert verdicts["spec"] == "✅" and verdicts["activity"] == "—" and verdicts["build_run"] == "—"
    assert at.session_state["current_run_folder"] == str(run.folder)

    # Choosing another component afterwards does not silently re-label the spec.
    at.selectbox(key="dsg_swc").select("SWC_Beta").run()
    assert any("This spec was made for **SWC_Alpha**" in str(w.value) for w in at.warning)
    assert not at.exception


def test_design_upload_is_not_overridden_by_the_sample(outputs):
    at = open_page("1_Design_MUD.py")
    at.radio(key="dsg_source").set_value("Upload a file").run()
    import_btn = at.button[[b.label for b in at.button].index("Import requirements")]
    assert import_btn.disabled, "without an uploaded file there is nothing to import (the sample is not used)"


# ── Keys & providers: Test connection used to crash (result stored under the button's key) ──
def test_test_connection_does_not_crash(outputs):
    at = open_page("5_Providers.py")
    at.button[[b.label for b in at.button].index("Test connection")].click().run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]


# ── A7: an error inside a page is shown in a box; the app keeps running ───────
def test_router_shows_page_errors_in_a_box(outputs, monkeypatch):
    import _common
    monkeypatch.setattr(_common, "list_runs", lambda: (_ for _ in ()).throw(ValueError("disk on fire")))
    at = open_page("0_Overview.py")
    assert any("Something went wrong" in e and "disk on fire" in e for e in errors(at))
    assert at.title, "the page itself still renders below the run-bar error"
