"""Run report — build ``RUN_REPORT.md`` and ``run.json`` for a run.

Every run gets a machine-readable ``run.json`` and a human-readable
``RUN_REPORT.md`` with a verdict per stage, the provider+model per stage, a
cloud-data notice, timings, compile ratio, JUnit counts and the trace summary.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from mudmut_core.workspace import RUN_JSON, RUN_REPORT, Run


# Pipeline stages in execution order (verdict keys).
STAGE_ORDER = (
    "import", "plan", "spec", "review", "activity", "activity_qa",
    "compilable", "generate_tests", "build_run", "trace",
)


def _models_snapshot() -> dict[str, Any]:
    """Snapshot of the real provider+model per stage (from ``agents.get_stages()``)."""
    try:
        from mudmut_core import agents
        stages = agents.get_stages()
        mud = {}
        mut = {}
        for key, st in stages.items():
            entry = {"provider": st.get("provider", "ollama"), "model": st.get("model", "")}
            (mud if st.get("side") == "mud" else mut)[key] = entry
        return {"mud": mud, "mut": mut}
    except Exception:
        return {"mud": {}, "mut": {}}


def cloud_providers(models: dict[str, Any]) -> list[str]:
    """Distinct cloud provider ids in a models snapshot (local providers excluded)."""
    seen: set[str] = set()
    for group in ("mud", "mut"):
        for stage in (models.get(group) or {}).values():
            p = stage.get("provider", "")
            if p and p != "ollama":
                seen.add(p)
    return sorted(seen)


def trace_markdown(trace_record: dict[str, Any]) -> str:
    lines = ["# Traceability", "", "| Requirement | Status | Verified by |", "|---|---|---|"]
    for t in trace_record.get("trace", []):
        lines.append(
            f"| {t['requirement']} | {t.get('status', '')} | {', '.join(t.get('verified_by', [])) or '—'} |"
        )
    return "\n".join(lines) + "\n"


def effective_verdicts(run_json: dict[str, Any]) -> dict[str, str]:
    """Stage verdicts with today's rules applied to an older ``run.json``.

    Runs written before the smoke-test rule stored ✅/⚠️ for a smoke-only result; show them
    as failures so old and new runs are judged the same way.
    """
    verdicts = dict(run_json.get("verdicts") or {})
    tests = run_json.get("tests") or {}
    if tests.get("smoke_fallback"):
        if verdicts.get("build_run") not in (None, "—"):
            verdicts["build_run"] = "❌"
        if verdicts.get("generate_tests") not in (None, "—"):
            verdicts["generate_tests"] = "❌"
    comp = run_json.get("compilability") or {}
    if comp.get("logic_stubbed") or comp.get("never_assigned") or comp.get("dropped_arguments"):
        if verdicts.get("compilable") not in (None, "—"):
            verdicts["compilable"] = "❌"
    return verdicts


def quality_notes(summary: dict[str, Any]) -> list[str]:
    """Plain warnings a reviewer must see before trusting the run (shown at the top of the report)."""
    notes: list[str] = []
    tests = summary.get("tests") or {}
    comp = summary.get("compilability") or {}
    asil = summary.get("max_asil")
    if asil in ("ASIL-B", "ASIL-C", "ASIL-D"):
        notes.append(f"🛑 **{asil} requirements:** this is an AI-assisted draft. A safety engineer must review the "
                     "design, code and tests; nothing here claims ISO 26262 compliance.")
    if tests.get("smoke_fallback"):
        notes.append("❌ **No AI-written test compiled.** The smoke test only calls each runnable once "
                     "(`CHECK(true)`); a pass here does not verify any requirement.")
    if comp.get("logic_stubbed"):
        notes.append(f"❌ **{comp['logic_stubbed']} statement(s) of design logic were commented out** to make the C "
                     "compile (assignments / calls). The code compiles because that logic is missing — see "
                     "`02_code/compilability.json`.")
    if comp.get("uninitialized_uses"):
        names = ", ".join(comp.get("never_assigned") or [])
        notes.append(f"❌ **Read but never assigned: {names or comp['uninitialized_uses']}.** "
                     "A computed value was dropped, so the output uses a default (zero) value.")
    if comp.get("dropped_arguments"):
        notes.append(f"❌ **{comp['dropped_arguments']} helper call(s) lost the arguments the design passes** "
                     "(helpers are generated as `void f(void)`); see the `TODO(args)` comments in the C file.")
    req_scope = summary.get("requirements_for_module")
    if req_scope:
        notes.append(f"ℹ️ The model was given {req_scope[0]} of {req_scope[1]} requirements (the ones planned for "
                     "this component).")
    return notes


def _verdict(ok: bool, warn: bool = False) -> str:
    if ok:
        return "✅"
    return "⚠️" if warn else "❌"


def generate_tests_verdict(tests_generated: int, generation_failed: int, quarantined: list) -> str:
    if not tests_generated:
        return "❌"
    if quarantined and len(quarantined) >= tests_generated:
        return "❌"          # every AI-written test failed to compile
    return "⚠️" if (generation_failed or quarantined) else "✅"


def build_run_verdict(tests: dict[str, Any]) -> str:
    status = tests.get("status")
    if status == "build_failed":
        return "❌"
    if tests.get("smoke_fallback"):
        return "❌"          # only the smoke test ran: CHECK(true) proves nothing
    if status == "passed" and not (tests.get("quarantined_tests") or []):
        return "✅"
    return "⚠️"  # test failures, quarantined tests, skipped / unknown


def _test_fields(tests: dict[str, Any]) -> dict[str, Any]:
    return {k: tests.get(k) for k in ("status", "junit", "fix_attempts", "quarantined_tests", "smoke_fallback", "cpputest")}


def update_after_manual_step(run: Run, *, generation: Optional[dict] = None, test_result: Optional[dict] = None,
                             trace_record: Optional[dict] = None, note: str = "") -> Optional[Path]:
    """Refresh the test / trace verdicts of an existing ``run.json`` after a step run by hand.

    Used by the Unit tests page (Generate tests, Rebuild & run, Write traceability). Only the
    stages that step touches change; the models, timings and earlier verdicts stay as the run
    recorded them. A line is added to ``RUN_REPORT.md``. Returns None when the run has no
    ``run.json`` yet.
    """
    data = run.read_json(RUN_JSON)
    if not isinstance(data, dict):
        return None
    verdicts = dict(data.get("verdicts") or {})
    if generation is not None:
        quarantined = (test_result or {}).get("quarantined_tests") or []
        verdicts["generate_tests"] = generate_tests_verdict(
            int(generation.get("tests_generated") or 0), len(generation.get("failed_functions") or []), quarantined)
        if test_result is None:
            verdicts["build_run"] = "—"     # new tests have not been built yet
            verdicts["trace"] = "—"
            data["tests"] = _test_fields({})
    if test_result is not None:
        verdicts["build_run"] = build_run_verdict(test_result)
        data["tests"] = _test_fields(test_result)
    if trace_record is not None:
        verdicts["trace"] = "✅"
        data["trace"] = {"requirements": len(trace_record.get("source_requirements", [])),
                         "summary": trace_record.get("summary", {})}
    data["verdicts"] = verdicts
    data["updated_at"] = datetime.now().isoformat()
    run.save_json(RUN_JSON, data)
    if note:
        report = run.read_text(RUN_REPORT, "")
        if "## Manual steps" not in report:
            report = report.rstrip("\n") + "\n\n## Manual steps\n\n"
        run.save_text(RUN_REPORT, report.rstrip("\n") + f"\n- {datetime.now():%Y-%m-%d %H:%M} — {note}\n")
    return run.path(RUN_JSON)


def write_run_report(run: Run, summary: dict[str, Any], *, stage_notes: Optional[dict[str, str]] = None,
                     reached: Optional[Sequence[str]] = None) -> Path:
    """Write ``run.json`` and ``RUN_REPORT.md`` for ``run`` and return the report path.

    ``reached`` (optional) lists the stages that have run so far (a design made step by step);
    every other stage is reported as not run (—) instead of passed.
    """
    stage_notes = stage_notes or {}
    tests = summary.get("tests", {})
    comp = summary.get("compilability", {})
    trace = summary.get("trace", {})
    models = _models_snapshot()
    clouds = cloud_providers(models)

    junit = tests.get("junit") or {}
    passed = junit.get("passed", 0)
    failed = junit.get("failures", 0)
    tests_generated = summary.get("tests_generated", 0)
    generation_failed = summary.get("generation_failed", 0)
    compile_ok = bool(comp.get("compile_ok"))
    stubbed = int(comp.get("stubbed") or 0)
    cpp = tests.get("cpputest") or {}
    quarantined = tests.get("quarantined_tests") or []

    logic_stubbed = int(comp.get("logic_stubbed") or 0)
    uninit = int(comp.get("uninitialized_uses") or 0)
    dropped_args = int(comp.get("dropped_arguments") or 0)

    def compilable_v():
        # Compiling is not enough: commenting out real logic (assignments, calls) or reading
        # uninitialised variables means the design was not implemented — that is a failure.
        if not compile_ok or logic_stubbed or uninit or dropped_args:
            return "❌"
        return "⚠️" if stubbed else "✅"

    def gen_v():
        return generate_tests_verdict(tests_generated, generation_failed, quarantined)

    def run_v():
        return build_run_verdict(tests)

    def review_v():
        if summary.get("quick"):
            return "—"
        if summary.get("review_ai_empty"):
            return "⚠️"   # the reviewer model answered nothing: only the deterministic ID check ran
        return "✅" if summary.get("review_approved", True) else "⚠️"

    def activity_qa_v():
        qa = summary.get("activity_quality")
        if not qa:
            return "—"
        return _verdict(qa.get("passed", False))

    verdicts: dict[str, str] = {
        "import": "✅",
        "plan": "✅",
        "spec": "✅",
        "review": review_v(),
        "activity": "✅",
        "activity_qa": activity_qa_v(),
        "compilable": compilable_v(),
        "generate_tests": gen_v(),
        "build_run": run_v(),
        "trace": "✅",
    }

    # A failed run: the failing stage is ❌, every stage after it was never reached.
    failed_stage = summary.get("failed_stage")
    if failed_stage in STAGE_ORDER:
        idx = STAGE_ORDER.index(failed_stage)
        verdicts[failed_stage] = "❌"
        for later in STAGE_ORDER[idx + 1:]:
            verdicts[later] = "—"
    if reached is not None:
        for key in STAGE_ORDER:
            if key not in reached:
                verdicts[key] = "—"

    cloud_notice = (
        f"Data sent to cloud: {', '.join(clouds)}" if clouds else "Data sent to cloud: none (all local)"
    )

    run_json = {
        "swc": summary.get("swc", run.swc),
        "preset": summary.get("preset", run.preset),
        "generated_at": datetime.now().isoformat(),
        "verdicts": verdicts,
        "models": models,
        "cloud_providers": clouds,
        "cloud_notice": cloud_notice,
        "timings": summary.get("timings", {}),
        "failed_stage": failed_stage,
        "max_asil": summary.get("max_asil"),
        "quality_notes": quality_notes(summary),
        "error": summary.get("error"),
        "warnings": summary.get("warnings", []),
        "compilability": comp,
        "tests": _test_fields(tests),
        "trace": {
            "requirements": len(trace.get("source_requirements", [])),
            "summary": trace.get("summary", {}),
        },
        "activity_quality": summary.get("activity_quality"),
    }
    run.save_json(RUN_JSON, run_json)

    lines = [
        f"# Run report — {summary.get('swc', run.swc)}",
        "",
        f"- **Preset:** {summary.get('preset', run.preset)}",
        f"- **Generated:** {datetime.now().isoformat()}",
        f"- **{cloud_notice}**",
    ]
    if failed_stage:
        lines.append(f"- **❌ Run failed in stage `{failed_stage}`:** {summary.get('error', '')}")
    for warning in summary.get("warnings", []):
        lines.append(f"- ⚠️ {warning}")
    for note in quality_notes(summary):
        lines.append(f"- {note}")
    lines += [
        "",
        "## Stage verdicts",
        "",
        "| Stage | Verdict | Notes |",
        "|---|---|---|",
    ]
    stage_labels = {
        "import": "Import requirements",
        "plan": "Plan modules",
        "spec": "MUD spec",
        "review": "Review",
        "activity": "Activity flow",
        "activity_qa": "Activity quality",
        "compilable": "Compilable C skeleton",
        "generate_tests": "Generate tests",
        "build_run": "Build & run",
        "trace": "Traceability",
    }
    for key in STAGE_ORDER:
        lines.append(f"| {stage_labels[key]} | {verdicts.get(key, '✅')} | {stage_notes.get(key, '')} |")

    lines += [
        "",
        "## Models (provider → model)",
        "",
    ]
    for group in ("mud", "mut"):
        lines.append(f"### {group.upper()}")
        for stage, cfg in (models.get(group) or {}).items():
            lines.append(f"- **{stage}:** `{cfg.get('provider', 'ollama')}` → `{cfg.get('model', '')}`")

    lines += [
        "",
        "## Results",
        "",
        f"- **Compilable:** {comp.get('kept', '?')} kept / {comp.get('stubbed', '?')} stubbed (compile_ok={comp.get('compile_ok')})",
        f"- **Tests:** {tests.get('status', 'skipped')} — {passed} passed / {failed} failed"
        f" (fix_attempts={tests.get('fix_attempts', 0)})",
        f"- **Trace:** {len(trace.get('source_requirements', []))} requirement(s)",
    ]
    qa = summary.get("activity_quality")
    if qa:
        lines += ["", "## Activity quality (threshold 80%)", "",
                  f"- **Score:** {qa.get('score')} / 100 {verdicts.get('activity_qa', '—')}"]
        for part, val in (qa.get("parts") or {}).items():
            lines.append(f"- {part}: {val:g}")
        if qa.get("missing_requirements"):
            lines.append("- Missing requirements: " + ", ".join(qa["missing_requirements"]))
        if qa.get("missing_steps"):
            lines.append("- Missing Section 7 steps: " + ", ".join(qa["missing_steps"]))
        if qa.get("problems"):
            lines.append("- Problems: " + "; ".join(qa["problems"]))
        judge = qa.get("judge")
        if isinstance(judge, dict):
            lines.append(f"- Judge ({judge.get('score'):g}): " + ("; ".join(judge.get("wrong") or []) or "no wrong findings"))
        r = qa.get("render")
        if r is not None:
            lines.append("- Render: " + ("ok → " + r.get("png", "") if r.get("ok") else "failed — " + r.get("error", "")))
        lines.append("")
        lines.append("_AI-assisted draft — not a requirement-verification claim._")
    lines += ([
        f"- **CppUTest:** `{cpp.get('home')}` (include `{cpp.get('include_dir')}`, lib `{cpp.get('lib_dir')}`)"
        if cpp.get("found") else "- **CppUTest:** ❌ not found — set the folder on the Settings page"
    ] if cpp else []) + [
        "",
        "## Timings (seconds)",
        "",
    ]
    for key, val in (summary.get("timings") or {}).items():
        lines.append(f"- {key}: {val:.1f}s")

    report = run.save_text(RUN_REPORT, "\n".join(lines) + "\n")
    return report
