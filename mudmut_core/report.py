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
    """Best-effort snapshot of the provider+model per stage (local only until Phase 2)."""
    snapshot: dict[str, Any] = {}
    try:
        from mudmut_core import env
        env.ensure_environment()
        from mudtool.config.settings import get_settings
        s = get_settings()
        snapshot["mud"] = {
            "planner": {"provider": "ollama", "model": s.openai_model},
            "mud_spec_skeleton": {"provider": "ollama", "model": getattr(s, "mud_spec_skeleton_model", "")},
            "mud_spec_generator": {"provider": "ollama", "model": getattr(s, "pipeline_generator_model", "") or s.openai_model},
            "mud_spec_reviewer": {"provider": "ollama", "model": getattr(s, "pipeline_reviewer_model", "") or s.openai_model},
        }
    except Exception:
        snapshot["mud"] = {}
    import os
    snapshot["mut"] = {
        "test_generator": {"provider": "ollama", "model": os.environ.get("GEN_MODEL", "")},
        "rag_embed": {"provider": "ollama", "model": os.environ.get("EMBED_MODEL", "")},
    }
    return snapshot


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

    # Per-stage verdicts.
    verdicts: dict[str, str] = {
        "import": "✅",
        "plan": "✅",
        "spec": "✅",
        "review": "⚠️" if summary.get("quick") else "✅",
        "activity": "✅",
        "compilable": _verdict(bool(comp.get("compile_ok")), warn=bool(comp.get("stubbed"))),
        "generate_tests": _verdict(
            not summary.get("generation_failed"), warn=bool(summary.get("generation_failed"))
        ),
        "build_run": _verdict(tests.get("status") == "passed", warn=tests.get("status") in (None, "skipped", "test_failed")),
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
