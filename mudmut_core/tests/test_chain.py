"""End-to-end chain test with stubbed LLM calls (no Ollama, no cpputest)."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from mudmut_core import agents, chain, design, verify


def _write_reqs(tmp_path: Path) -> Path:
    p = tmp_path / "reqs.csv"
    p.write_text(
        "Req_ID,Title,Description,Type,Priority,Safety,Module\n"
        "REQ-001,Do a thing,The SWC shall do a thing,functional,must,QM,SWC_Test\n"
    )
    return p


def _module():
    return SimpleNamespace(
        swc_name="SWC_Test", description="test swc", asil="QM",
        runnables=["RE_Foo"], req_ids=["REQ-001"],
    )


def test_run_full_chain_quick_with_stubs(tmp_path, monkeypatch):
    req_file = _write_reqs(tmp_path)

    async def fake_plan(text, temperature=0.2):
        return SimpleNamespace(modules=[_module()], architecture_summary="x")

    async def fake_spec(module, text, mode="two_stage", progress=None):
        return "# MUD Spec\n## 7. Runnable RE_Foo\nl_u8X = 1;\n" * 20

    async def fake_activity(requirements, spec, swc, use_ai=True, progress=None):
        assert use_ai is False  # quick mode builds the flow deterministically
        d = SimpleNamespace(diagrams=[SimpleNamespace()])
        d.model_dump = lambda: {"diagrams": []}
        return d

    def fake_export(result):
        return {
            "c": {"RE_Foo_Code_Flow": 'void RE_Foo(void)\n{\n    l_u8X = 1;\n    return;\n}\n'},
            "mermaid": {"RE_Foo_Code_Flow": "graph TD; A-->B;"},
        }

    out_dir = tmp_path / "tests_x"
    out_dir.mkdir()

    async def fake_generate_tests(project_dir, function_name=None, output_dir=None, progress=None):
        return {
            "output_directory": str(output_dir or out_dir),
            "tests_generated": 1,
            "functions_analyzed": 1,
            "failed_functions": [],
        }

    def fake_fix_loop(test_dir, max_attempts=2):
        return {
            "status": "passed",
            "junit": {"tests": 1, "failures": 0, "errors": 0, "passed": 1},
            "fix_attempts": 0,
        }

    monkeypatch.setattr(design, "plan_modules", fake_plan)
    monkeypatch.setattr(design, "generate_mud_spec", fake_spec)
    monkeypatch.setattr(design, "generate_activity", fake_activity)
    monkeypatch.setattr(design, "export", fake_export)
    monkeypatch.setattr(verify, "generate_tests", fake_generate_tests)
    monkeypatch.setattr(verify, "fix_loop", fake_fix_loop)
    # Avoid writing to the real mud-tool .env / unloading real models.
    monkeypatch.setattr(agents, "apply_preset", lambda name: agents.get_stages())
    monkeypatch.setattr(chain, "_unload_models", lambda models: None)
    monkeypatch.setattr(chain, "_mud_models", lambda: [])

    summary = asyncio.run(chain.run_full_chain(
        str(req_file), swc="SWC_Test", quick=True, root=tmp_path / "runs",
    ))

    run_folder = Path(summary["run_folder"])
    assert (run_folder / "00_input" / "requirements.json").is_file()
    assert (run_folder / "01_mud" / "mud_spec.md").is_file()
    assert (run_folder / "02_code" / "SWC_Test.c").is_file()
    assert (run_folder / "02_code" / "compilability.json").is_file()
    assert (run_folder / "04_trace" / "trace.json").is_file()
    assert (run_folder / "RUN_REPORT.md").is_file()
    assert (run_folder / "run.json").is_file()
    assert summary["compilability"]["compile_ok"] is True
