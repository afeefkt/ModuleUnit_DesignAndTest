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
    quarantined = tests.get("quarantined_tests") or []

    def compilable_v():
        if not compile_ok:
            return "❌"
        return "⚠️" if stubbed else "✅"

    def gen_v():
        if tests_generated == 0:
            return "❌"
        return "⚠️" if generation_failed else "✅"

    def run_v():
        if status == "build_failed":
            return "❌"
        if status == "passed" and not smoke and not quarantined:
            return "✅"
        if status in ("test_failed", "passed"):
            return "⚠️"
        return "⚠️"  # skipped / unknown

    def review_v():
        if summary.get("quick"):
            return "—"
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
        "compilability": comp,
        "tests": {k: tests.get(k) for k in ("status", "junit", "fix_attempts", "quarantined_tests", "smoke_fallback")},
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
    for key in ("import", "plan", "spec", "review", "activity", "compilable", "generate_tests", "build_run", "trace"):
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
        "",
        "## Timings (seconds)",
        "",
    ]
    for key, val in (summary.get("timings") or {}).items():
        lines.append(f"- {key}: {val:.1f}s")

    report = run.save_text(RUN_REPORT, "\n".join(lines) + "\n")
    return report
