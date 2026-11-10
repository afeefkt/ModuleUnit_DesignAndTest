"""The chain's ``code_baseline`` adapter: pinned code must be what tests and trace see."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def _stub_chain(monkeypatch, generated_c: str, seen: dict):
    async def fake_plan(text, temperature=0.2):
        return SimpleNamespace(modules=[_module()], architecture_summary="x")

    async def fake_spec(module, text, mode="two_stage", progress=None):
        return ("# MUD Spec: SWC_Test\n" + "Overview text for the test component. " * 6 +
                "\n## 7. Functional Description\n### RE_Foo\n1. l_u8X = 7;\n2. Rte_Write_PP_X(l_u8X);\n")

    async def fake_activity(requirements, spec, swc, use_ai=True, progress=None):
        d = SimpleNamespace(diagrams=[SimpleNamespace()])
        d.model_dump = lambda: {"diagrams": []}
        return d

    def fake_export(result):
        return {
            "c": {"RE_Foo_Code_Flow": generated_c},
            "mermaid": {"RE_Foo_Code_Flow": "graph TD; A-->B;"},
        }

    out_dir = seen["tmp_path"] / "tests_x"
    out_dir.mkdir()

    async def fake_generate_tests(project_dir, function_name=None, output_dir=None, progress=None):
        seen["test_c"] = (Path(project_dir) / "SWC_Test.c").read_text(encoding="utf-8")
        return {
            "output_directory": str(output_dir or out_dir),
            "tests_generated": 1,
            "functions_analyzed": 1,
            "failed_functions": [],
        }

    def fake_fix_loop(test_dir, max_attempts=2):
        return {"status": "passed", "junit": {"tests": 1, "failures": 0, "errors": 0, "passed": 1},
                "fix_attempts": 0}

    def fake_trace(swc, c_code, generation):
        seen["trace_c"] = c_code
        seen["trace_swc"] = swc
        return {"source_requirements": ["REQ-001"], "trace": [], "summary": {}}

    monkeypatch.setattr(design, "plan_modules", fake_plan)
    monkeypatch.setattr(design, "generate_mud_spec", fake_spec)
    monkeypatch.setattr(design, "generate_activity", fake_activity)
    monkeypatch.setattr(design, "export", fake_export)
    monkeypatch.setattr(verify, "generate_tests", fake_generate_tests)
    monkeypatch.setattr(verify, "fix_loop", fake_fix_loop)
    monkeypatch.setattr(chain.trace_mod, "build_trace", fake_trace)
    monkeypatch.setattr(agents, "apply_preset", lambda name: agents.get_stages())
    monkeypatch.setattr(chain, "_unload_models", lambda models: None)
    monkeypatch.setattr(chain, "_mud_models", lambda: [])


def _baseline(tmp_path: Path, *, compile_ok: bool = True) -> Path:
    base = tmp_path / "baseline"
    base.mkdir()
    (base / "SWC_Test.c").write_text(
        "/* Requirements: REQ-001 */\n"
        "void RE_Foo(void)\n{\n    l_u8X = 7;\n    return;\n}\n",
        encoding="utf-8",
    )
    (base / "compilability.json").write_text(json.dumps({
        "swc": "SWC_Test", "total_statements": 2, "kept_statements": 2,
        "stubbed_statements": 0, "rounds": 1, "compile_ok": compile_ok,
        "last_error": "", "logic_stubbed": 0, "stubbed_logic": [],
        "never_assigned": [], "dropped_arguments": 0,
    }), encoding="utf-8")
    return base


def test_pinned_code_is_used_by_tests_and_trace(tmp_path, monkeypatch):
    seen = {"tmp_path": tmp_path}
    generated = "void RE_Foo(void)\n{\n    l_u8X = 999;\n    return;\n}\n"
    _stub_chain(monkeypatch, generated, seen)

    summary = asyncio.run(chain.run_full_chain(
        str(_write_reqs(tmp_path)), swc="SWC_Test", quick=True,
        root=tmp_path / "runs", code_baseline=_baseline(tmp_path),
    ))

    assert summary["code_source"] == "pinned"
    assert summary["compilability"]["kept"] == 2
    run_c = (Path(summary["run_folder"]) / "02_code" / "SWC_Test.c").read_text(encoding="utf-8")
    assert "l_u8X = 7;" in run_c and "999" not in run_c
    assert "l_u8X = 7;" in seen["test_c"] and "999" not in seen["test_c"]
    assert "l_u8X = 7;" in seen["trace_c"] and "999" not in seen["trace_c"]
    assert seen["trace_swc"] == "SWC_Test"


def test_no_baseline_keeps_generated_code(tmp_path, monkeypatch):
    seen = {"tmp_path": tmp_path}
    generated = "void RE_Foo(void)\n{\n    l_u8X = 999;\n    return;\n}\n"
    _stub_chain(monkeypatch, generated, seen)

    summary = asyncio.run(chain.run_full_chain(
        str(_write_reqs(tmp_path)), swc="SWC_Test", quick=True, root=tmp_path / "runs",
    ))

    assert summary["code_source"] == "generated"
    assert seen["trace_c"].strip() == generated.strip()


def test_uncompiled_baseline_is_refused(tmp_path, monkeypatch):
    seen = {"tmp_path": tmp_path}
    _stub_chain(monkeypatch, "void RE_Foo(void)\n{\n    l_u8X = 1;\n}\n", seen)

    with pytest.raises(chain.ChainError, match="did not compile"):
        asyncio.run(chain.run_full_chain(
            str(_write_reqs(tmp_path)), swc="SWC_Test", quick=True,
            root=tmp_path / "runs", code_baseline=_baseline(tmp_path, compile_ok=False),
        ))
