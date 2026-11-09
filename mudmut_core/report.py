"""Run report — build ``RUN_REPORT.md`` and ``run.json`` for a run.

Every run gets a machine-readable ``run.json`` and a human-readable
``RUN_REPORT.md`` with a verdict per stage, the provider+model per stage, a
cloud-data notice, timings, compile ratio, JUnit counts and the trace summary.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mudmut_core.workspace import RUN_JSON, RUN_REPORT, Run


# Pipeline stages in execution order (verdict keys).
STAGE_ORDER = (
    "import", "plan", "spec", "review", "activity",
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


def write_run_report(run: Run, summary: dict[str, Any], *, stage_notes: Optional[dict[str, str]] = None) -> Path:
    """Write ``run.json`` and ``RUN_REPORT.md`` for ``run`` and return the report path."""
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
    status = tests.get("status")
    smoke = bool(tests.get("smoke_fallback"))
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
        if tests_generated == 0:
            return "❌"
        if quarantined and len(quarantined) >= tests_generated:
            return "❌"          # every AI-written test failed to compile
        return "⚠️" if (generation_failed or quarantined) else "✅"

    def run_v():
        if status == "build_failed":
            return "❌"
        if smoke:
            return "❌"          # only the smoke test ran: CHECK(true) proves nothing
        if status == "passed" and not quarantined:
            return "✅"
        return "⚠️"  # test failures, quarantined tests, skipped / unknown

    def review_v():
        if summary.get("quick"):
            return "—"
        if summary.get("review_ai_empty"):
            return "⚠️"   # the reviewer model answered nothing: only the deterministic ID check ran
        return "✅" if summary.get("review_approved", True) else "⚠️"

    verdicts: dict[str, str] = {
        "import": "✅",
        "plan": "✅",
        "spec": "✅",
        "review": review_v(),
        "activity": "✅",
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
        "tests": {k: tests.get(k) for k in ("status", "junit", "fix_attempts", "quarantined_tests", "smoke_fallback", "cpputest")},
        "trace": {
            "requirements": len(trace.get("source_requirements", [])),
            "summary": trace.get("summary", {}),
        },
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
    ] + ([
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
