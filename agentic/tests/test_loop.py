"""Tests for the deterministic agentic loop runner (no model calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "agentic" / "loop"))

import run_loop  # noqa: E402


@pytest.fixture
def loop(tmp_path, monkeypatch):
    monkeypatch.setattr(run_loop, "LOOPS_ROOT", tmp_path / "loops")
    lp = run_loop.Loop("test_loop")
    lp.init()
    return lp


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fake_run(tmp_path: Path, *, build="✅", passed=3, failures=0,
              failed_names=(), stubbed=0, logic=0, never=(), dropped=0,
              generated=2, quarantined=(), smoke=False) -> Path:
    run = tmp_path / "run_x"
    _write(run / "state.json", json.dumps({"swc": run_loop.SWC, "preset": run_loop.PRESET,
                                           "quick": False, "code_source": "pinned"}))
    verdicts = {s: "✅" for s in run_loop.STAGE_ORDER}
    verdicts["build_run"] = build
    _write(run / "run.json", json.dumps({
        "verdicts": verdicts,
        "models": {},
        "cloud_providers": ["deepseek"],
        "timings": {"spec": 1.0, "build_run": 0.5},
        "tests": {"status": "passed" if not smoke else "passed",
                  "junit": {"passed": passed, "failures": failures, "errors": 0},
                  "quarantined_tests": list(quarantined),
                  "smoke_fallback": smoke,
                  "fix_attempts": 0},
    }))
    _write(run / "02_code" / "compilability.json", json.dumps({
        "swc": run_loop.SWC, "total_statements": 10, "kept_statements": 10 - stubbed,
        "stubbed_statements": stubbed, "rounds": 1, "compile_ok": True,
        "logic_stubbed": logic, "stubbed_logic": ["x"] * logic,
        "never_assigned": list(never), "dropped_arguments": dropped,
    }))
    _write(run / "02_code" / f"{run_loop.SWC}.c", "/* Requirements: REQ-1 */\nvoid f(void){}\n")
    gen = {"tests_generated": generated, "failed_functions": [], "output_directory": str(run / "03_mut")}
    _write(run / "03_mut" / "generation.json", json.dumps(gen))
    _write(run / "03_mut" / "results.json", json.dumps({"generation": gen,
                                                        "run": {"status": "passed"}}))
    cases = "".join(f'<testcase name="{n}"><failure message="x"/></testcase>' for n in failed_names)
    _write(run / "03_mut" / "test-results.xml",
           f'<testsuite><testcase name="ok"/>{cases}</testsuite>')
    _write(run / "04_trace" / "trace.json", json.dumps({
        "source_requirements": ["REQ-1"],
        "trace": [], "summary": {"requirements": 1, "verified_by_test": 0, "not_verified": 1},
    }))
    _write(run / "llm_log.jsonl", "\n".join([
        json.dumps({"stage": "spec", "input_tokens": 10, "output_tokens": 5}),
        json.dumps({"stage": "tests", "input_tokens": 7, "output_tokens": 3}),
    ]) + "\n")
    return run


def test_tokens_sum(loop, tmp_path):
    run = _fake_run(tmp_path)
    assert loop.tokens(run) == {"calls": 2, "input": 17, "output": 8, "total": 25}


def test_snapshot_copies_key_artifacts(loop, tmp_path):
    run = _fake_run(tmp_path)
    loop.snapshot(run, tmp_path / "snap")
    assert (tmp_path / "snap" / "run.json").is_file()
    assert (tmp_path / "snap" / "02_code" / f"{run_loop.SWC}.c").is_file()
    assert (tmp_path / "snap" / "snapshot.sha256").is_file()


def test_verdicts_tool_green_with_clean_run(loop, tmp_path):
    v = loop.verdicts(_fake_run(tmp_path))
    assert v["pipeline_green"] is True
    assert v["tool_green"] is True
    assert v["strict_green"] is True
    assert v["test_app_issues"] == []


def test_verdicts_code_defect_is_not_a_test_app_issue(loop, tmp_path):
    v = loop.verdicts(_fake_run(tmp_path, build="⚠️", passed=2, failures=1,
                                failed_names=["test_RE_Foo"]))
    assert v["pipeline_green"] is True
    assert v["tool_green"] is True
    assert v["failed_tests"] == ["test_RE_Foo"]
    assert v["code_defect_candidates"] == ["test_RE_Foo"]


def test_verdicts_quarantine_blocks_tool_green(loop, tmp_path):
    v = loop.verdicts(_fake_run(tmp_path, build="⚠️", passed=2, failures=1,
                                failed_names=["t"], quarantined=["Test_X.cpp"]))
    assert v["pipeline_green"] is False
    assert v["tool_green"] is False
    assert any("quarantined" in x for x in v["test_app_issues"])


def test_verdicts_stub_blocks_tool_green(loop, tmp_path):
    v = loop.verdicts(_fake_run(tmp_path, stubbed=2))
    assert v["pipeline_green"] is False
    assert any("stubbed" in x for x in v["test_app_issues"])


def test_freeze_accepts_zero_stub_baseline(loop, tmp_path):
    run = _fake_run(tmp_path)
    loop.it_dir(0).mkdir(parents=True, exist_ok=True)
    (loop.it_dir(0) / "run.txt").write_text(str(run) + "\n", encoding="utf-8")
    prov = loop.freeze(0)
    assert prov["gate"]["stubbed_statements"] == 0
    assert (loop.dir / "code_baseline" / f"{run_loop.SWC}.c").is_file()
    assert (loop.dir / "code_baseline" / "provenance.json").is_file()


def test_freeze_blocks_on_stubs(loop, tmp_path):
    run = _fake_run(tmp_path, stubbed=2)
    loop.it_dir(0).mkdir(parents=True, exist_ok=True)
    (loop.it_dir(0) / "run.txt").write_text(str(run) + "\n", encoding="utf-8")
    with pytest.raises(run_loop.LoopError, match="freeze blocked"):
        loop.freeze(0)
    assert (loop.dir / "freeze_blocked.json").is_file()


def test_analyze_writes_triage(loop, tmp_path):
    run = _fake_run(tmp_path, build="⚠️", passed=2, failures=1, failed_names=["t"])
    it = loop.it_dir(0)
    it.mkdir(parents=True, exist_ok=True)
    (it / "run.txt").write_text(str(run) + "\n", encoding="utf-8")
    verdict = loop.verdicts(run)
    verdict["tokens"] = loop.tokens(run)
    (it / "verdicts.json").write_text(json.dumps(verdict), encoding="utf-8")
    triage = loop.analyze(0)
    assert triage["verdicts"]["build_run"] == "⚠️"
    assert (it / "triage.md").is_file()
    assert (it / "analyst_input.md").is_file()
    assert any(i["class"] == "code_defect" for i in triage["issues"])


def test_compare_and_report(loop, tmp_path):
    for i in (0, 1):
        run = _fake_run(tmp_path / str(i))
        it = loop.it_dir(i)
        it.mkdir(parents=True, exist_ok=True)
        (it / "run.txt").write_text(str(run) + "\n", encoding="utf-8")
        v = loop.verdicts(run)
        v["tokens"] = loop.tokens(run)
        (it / "verdicts.json").write_text(json.dumps(v), encoding="utf-8")
    assert "iteration" in loop.compare().lower()
    text = loop.report()
    assert "What this does not prove" in text
    assert (loop.dir / "final" / "EVIDENCE.md").is_file()
