"""Regression tests for the second review round: optional preset, blank stage
values, late key export, and failure reports."""

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from mudmut_core import agents, chain, design, env, verify


def _write_reqs(tmp_path: Path) -> Path:
    p = tmp_path / "reqs.csv"
    p.write_text(
        "Req_ID,Title,Description,Type,Priority,Safety,Module\n"
        "REQ-001,Do a thing,The SWC shall do a thing,functional,must,QM,SWC_Test\n"
    )
    return p


@pytest.fixture()
def stubbed_chain(tmp_path, monkeypatch):
    """Stub every LLM / build step; returns a dict that records preset calls."""
    calls = {"preset": []}

    async def fake_plan(text, temperature=0.2):
        return SimpleNamespace(modules=[SimpleNamespace(
            swc_name="SWC_Test", description="t", asil="QM", runnables=["RE_Foo"], req_ids=["REQ-001"],
        )], architecture_summary="x")

    async def fake_spec(module, text, mode="two_stage", progress=None):
        return "# MUD Spec\n## 7. Runnable RE_Foo\nl_u8X = 1;\n" * 20

    async def fake_activity(requirements, spec, swc, use_ai=True, progress=None):
        d = SimpleNamespace(diagrams=[SimpleNamespace()])
        d.model_dump = lambda: {"diagrams": []}
        return d

    def fake_export(result):
        return {"c": {"RE_Foo": 'void RE_Foo(void)\n{\n    l_u8X = 1;\n    return;\n}\n'},
                "mermaid": {"RE_Foo": "graph TD; A-->B;"}}

    async def fake_generate_tests(project_dir, function_name=None, output_dir=None):
        return {"output_directory": str(output_dir), "tests_generated": 1,
                "functions_analyzed": 1, "failed_functions": []}

    def fake_fix_loop(test_dir, max_attempts=2):
        return {"status": "passed", "junit": {"tests": 1, "failures": 0, "errors": 0, "passed": 1},
                "fix_attempts": 0}

    def fake_apply(name):
        calls["preset"].append(name)
        return agents.get_stages(), ["mud_spec_generator"]

    monkeypatch.setattr(design, "plan_modules", fake_plan)
    monkeypatch.setattr(design, "generate_mud_spec", fake_spec)
    monkeypatch.setattr(design, "generate_activity", fake_activity)
    monkeypatch.setattr(design, "export", fake_export)
    monkeypatch.setattr(verify, "generate_tests", fake_generate_tests)
    monkeypatch.setattr(verify, "fix_loop", fake_fix_loop)
    monkeypatch.setattr(agents, "apply_preset_with_report", fake_apply)
    monkeypatch.setattr(chain, "_unload_models", lambda models: None)
    monkeypatch.setattr(chain, "_mud_models", lambda: [])
    calls["req_file"] = _write_reqs(tmp_path)
    calls["root"] = tmp_path / "runs"
    return calls


def _run(calls, **kwargs):
    return asyncio.run(chain.run_full_chain(
        str(calls["req_file"]), swc="SWC_Test", quick=True, root=calls["root"], **kwargs,
    ))


def test_chain_without_preset_keeps_current_selection(stubbed_chain):
    summary = _run(stubbed_chain)
    assert stubbed_chain["preset"] == []          # never touched the user's stages
    assert summary["preset"] == "custom"
    assert Path(summary["run_folder"]).name.endswith("_custom")


def test_chain_with_preset_applies_it_and_warns_about_skipped(stubbed_chain):
    summary = _run(stubbed_chain, preset="openrouter-free")
    assert stubbed_chain["preset"] == ["openrouter-free"]
    assert summary["preset"] == "openrouter-free"
    assert any("mud_spec_generator" in w for w in summary["warnings"])
    report = (Path(summary["run_folder"]) / "RUN_REPORT.md").read_text(encoding="utf-8")
    assert "mud_spec_generator" in report


def test_failure_report_marks_failing_stage_and_unreached(stubbed_chain, monkeypatch):
    async def broken_activity(*args, **kwargs):
        raise RuntimeError("model timed out")

    monkeypatch.setattr(design, "generate_activity", broken_activity)
    with pytest.raises(RuntimeError):
        _run(stubbed_chain)
    run_dir = next(d for d in stubbed_chain["root"].iterdir() if d.is_dir())
    data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert data["failed_stage"] == "activity"
    assert data["verdicts"]["spec"] == "✅"
    assert data["verdicts"]["activity"] == "❌"
    assert data["verdicts"]["compilable"] == "—"
    assert data["verdicts"]["trace"] == "—"
    assert "model timed out" in data["error"]
    report = (run_dir / "RUN_REPORT.md").read_text(encoding="utf-8")
    assert "Run failed in stage `activity`" in report


def test_failed_stage_skips_review_in_quick_mode():
    assert chain._failed_stage("spec", quick=True) == "activity"
    assert chain._failed_stage("spec", quick=False) == "review"
    assert chain._failed_stage(None, quick=True) == "import"


def test_apply_stages_to_env_ignores_blank_models(monkeypatch):
    stage = next(s for s in agents.STAGES if s.side == "mut")
    monkeypatch.setenv(stage.model_env, "qwen2.5:7b")
    agents.apply_stages_to_env({stage.key: {"provider": "openrouter", "model": ""}})
    assert os.environ[stage.model_env] == "qwen2.5:7b"


def test_late_key_export_refreshes_cached_settings(monkeypatch):
    env.ensure_environment()
    from mudtool.config.settings import get_settings
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()
    assert not get_settings().openrouter_api_key           # cached without the key

    from mudmut_core.llm import providers
    monkeypatch.setattr(providers, "resolve_key",
                        lambda name: "test-key-not-real" if name == "OPENROUTER_API_KEY" else None)
    env.export_provider_keys()
    assert get_settings().openrouter_api_key == "test-key-not-real"
    get_settings.cache_clear()
