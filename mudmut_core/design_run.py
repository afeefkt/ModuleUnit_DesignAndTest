"""Step-by-step design runs — the Requirements & design page writes the same run folder as a chain run.

Each step saves its artifact (``00_input``, ``01_mud``, ``02_code``) and rewrites ``run.json`` +
``RUN_REPORT.md``. Stages that have not run yet are reported as not run (—), never as passed, and
redoing an earlier step (a new spec, saved spec edits) marks every later stage as not run again.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional

from mudmut_core import report as report_mod
from mudmut_core.workspace import Run

PRESET = "manual"


def compilability_json(rep: Any, swc: str) -> dict[str, Any]:
    """``02_code/compilability.json`` for a :class:`compilable` report (same keys as a chain run)."""
    return {
        "swc": swc,
        "total_statements": rep.total_statements,
        "kept_statements": rep.kept_statements,
        "stubbed_statements": rep.stubbed_statements,
        "rounds": rep.rounds,
        "compile_ok": rep.compile_ok,
        "last_error": rep.last_error,
        "logic_stubbed": rep.logic_stubbed,
        "stubbed_logic": rep.stubbed_logic,
        "never_assigned": rep.never_assigned,
        "dropped_arguments": rep.dropped_arguments,
    }


def compilability_summary(data: dict[str, Any]) -> dict[str, Any]:
    """The ``compilability`` block of ``run.json`` from ``compilability.json``."""
    return {
        "kept": data.get("kept_statements", data.get("kept")),
        "stubbed": data.get("stubbed_statements", data.get("stubbed")),
        "compile_ok": data.get("compile_ok"),
        "logic_stubbed": data.get("logic_stubbed") or 0,
        "uninitialized_uses": len(data.get("never_assigned") or []),
        "never_assigned": data.get("never_assigned") or [],
        "dropped_arguments": data.get("dropped_arguments") or 0,
    }


def start(swc: str, reqs: Any, *, source: Optional[Path] = None, quick: bool = True,
          root: Optional[Path] = None) -> Run:
    """Create the run folder for one component's design (when its spec is generated)."""
    from mudmut_core import chain, design
    run = Run.create(swc, preset=PRESET, root=root)
    run.save_json_in("input", "requirements.json", design.requirements_to_dicts(reqs))
    if source is not None and Path(source).is_file():
        shutil.copy2(source, run.dir("input") / Path(source).name)
    run.save_state(swc=swc, preset=PRESET, quick=quick, source="Requirements & design page",
                   max_asil=chain.highest_asil(reqs), reached=["import", "plan"], stage_notes={})
    return run


def record_step(run: Run, stage: str, *, note: str = "", **state: Any) -> None:
    """Mark ``stage`` as done (later stages become not run) and rewrite the run report."""
    order = report_mod.STAGE_ORDER
    idx = order.index(stage)
    reached = [s for s in (run.state.get("reached") or ["import", "plan"]) if order.index(s) < idx] + [stage]
    notes = {k: v for k, v in (run.state.get("stage_notes") or {}).items() if k in reached and k != stage}
    if note:
        notes[stage] = note
    run.save_state(reached=reached, stage_notes=notes, **state)
    write_report(run)


def write_report(run: Run) -> None:
    reached = list(run.state.get("reached") or ["import", "plan"])
    comp = compilability_summary(run.read_json_in("code", "compilability.json") or {}) \
        if "compilable" in reached else {}
    report_mod.write_run_report(run, {
        "run_folder": str(run.folder),
        "swc": run.swc,
        "preset": PRESET,
        "quick": "review" not in reached,
        "timings": run.state.get("timings") or {},
        "tests_generated": 0,
        "generation_failed": 0,
        "review_approved": run.state.get("review_approved", True),
        "review_ai_empty": run.state.get("review_ai_empty", False),
        "compilability": comp,
        "tests": {},
        "trace": {},
        "max_asil": run.state.get("max_asil"),
        "warnings": ["Made step by step on the Requirements & design page; continue on the Unit tests page."],
    }, stage_notes=run.state.get("stage_notes") or {}, reached=reached)
