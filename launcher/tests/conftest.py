"""Headless page tests (Streamlit AppTest): isolated outputs/, no network, no WSL."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
for p in (str(REPO), str(REPO / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

APP = str(REPO / "launcher" / "streamlit_app.py")
VIEWS = sorted(p.name for p in (REPO / "launcher" / "views").glob("*.py"))


@pytest.fixture()
def outputs(tmp_path, monkeypatch):
    """An empty ``outputs/`` in tmp; user config, timings and the LLM log are isolated too."""
    import streamlit as st
    from mudmut_core import jobs, progress, toolchain, workspace
    from mudmut_core.llm import observe, probe
    import mudmut_core.agents as agents
    import mudmut_core.llm as llm
    import _common

    root = tmp_path / "outputs"
    root.mkdir()
    monkeypatch.setattr(workspace, "RUNS_ROOT", root)
    monkeypatch.setattr(progress, "TIMINGS_FILE", tmp_path / "stage_timings.json")
    monkeypatch.setattr(probe, "PROBE_FILE", tmp_path / "model_probe.json")
    monkeypatch.setattr(observe, "STATE_LOG", tmp_path / "llm_log.jsonl")
    # No network and no WSL in page tests.
    monkeypatch.setattr(_common, "_get_json", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(llm, "list_models", lambda provider: [])
    monkeypatch.setattr(agents, "available_models", lambda provider_id: [])
    monkeypatch.setattr(toolchain, "check_toolchain", lambda: SimpleNamespace(
        ok=True, tools=[SimpleNamespace(name="gcc", available=True, detail="test stub")]))
    st.cache_data.clear()
    jobs.clear_finished()
    yield root
    wait_for_jobs()
    jobs.clear_finished()
    st.cache_data.clear()


def wait_for_jobs(timeout: float = 30.0) -> None:
    from mudmut_core import jobs
    end = time.monotonic() + timeout
    while jobs.any_running() and time.monotonic() < end:
        time.sleep(0.05)
    assert not jobs.any_running(), "a background job did not finish"


def open_page(view: str):
    """The app with ``views/<view>`` open (the router runs first, as in the browser)."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.switch_page(f"views/{view}")
    at.run()
    return at


def settle(at):
    """Wait for the background step the last click started; redraw if the page has not picked up its result.

    A fast step can finish before the rerun that follows the click, and the page then shows its
    outcome at once — redrawing again would hide a one-time error box.
    """
    wait_for_jobs()
    if any(str(k).startswith("step::") for k in at.session_state._state.filtered_state):
        at.run()
    return at


def errors(at) -> list[str]:
    return [str(e.value) for e in at.error]


def make_run(root: Path, swc: str = "SWC_Test", *, tests: dict | None = None, c_code: str | None = None):
    """A finished run folder like a chain run writes (run.json + RUN_REPORT.md)."""
    from mudmut_core import report
    from mudmut_core.workspace import Run
    run = Run.create(swc, preset="local-fast", root=root)
    if c_code is not None:
        run.save_in("code", f"{swc}.c", c_code)
    run.save_in("mud", "flow.mmd", "flowchart LR\n  A --> B\n")
    report.write_run_report(run, {
        "swc": swc, "preset": "local-fast", "quick": True, "tests_generated": 1,
        "compilability": {"compile_ok": True, "kept": 3, "stubbed": 0},
        "tests": tests or {"status": "passed", "junit": {"passed": 1, "failures": 0}}})
    run.mark_finished("done")
    return run
