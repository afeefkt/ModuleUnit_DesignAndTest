"""Every page renders without an exception: with no runs, and with complete, failed and damaged runs."""

from __future__ import annotations

import pytest

from conftest import VIEWS, make_run, open_page


@pytest.mark.parametrize("view", VIEWS)
def test_page_loads_without_runs(outputs, view):
    at = open_page(view)
    assert not at.exception, [str(e.value)[:400] for e in at.exception]


@pytest.fixture()
def mixed_runs(outputs):
    """One good run, one with a damaged state.json, one with a damaged run.json, one interrupted."""
    good = make_run(outputs, "SWC_Good", c_code="void RE_Init(void)\n{\n}\n")
    broken_state = make_run(outputs, "SWC_BrokenState")
    broken_state.path("state.json").write_text('{"swc": "SWC_Bro', encoding="utf-8")
    broken_report = make_run(outputs, "SWC_BrokenReport")
    broken_report.path("run.json").write_text("not json", encoding="utf-8")
    interrupted = make_run(outputs, "SWC_Interrupted")
    interrupted.save_state(status="running", pid=2 ** 22 + 12345)
    return good


@pytest.mark.parametrize("view", VIEWS)
def test_page_loads_with_damaged_and_interrupted_runs(mixed_runs, view):
    at = open_page(view)
    assert not at.exception, [str(e.value)[:400] for e in at.exception]


def test_run_bar_marks_an_interrupted_run(outputs):
    from mudmut_core.workspace import Run
    run = make_run(outputs, "SWC_Interrupted")
    run.save_state(status="running", pid=2 ** 22 + 12345)
    at = open_page("6_Runs_Reports.py")
    assert not at.exception
    assert any("interrupted" in str(m.value) for m in at.markdown), "run bar shows no interrupted mark"
    assert Run.load(run.folder).status == "interrupted"


def test_run_bar_escapes_names(outputs):
    run = make_run(outputs, "SWC_Plain")
    run.save_state(swc="<img src=x onerror=alert(1)>")
    at = open_page("0_Overview.py")
    bar = [str(m.value) for m in at.markdown if 'class="runmeta"' in str(m.value)]
    assert bar and "<img" not in bar[0] and "&lt;img" in bar[0]
