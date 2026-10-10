"""End-to-end chain: requirements → MUD → C → MUT → trace.

Headless entry point::

    python -m mudmut_core.chain --requirements inputs/requirements/samples/bms_requirements.csv \\
        --swc SWC_BatteryManagement --quick
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from mudmut_core import aio, compilable, design, env, report as report_mod, trace as trace_mod, verify
from mudmut_core.llm import ollama_unload
from mudmut_core.workspace import Run


class ChainError(RuntimeError):
    pass


def _emit(progress, stage: str, message: str, **extra: Any) -> None:
    if progress:
        progress({"stage": stage, "message": message, **extra})


def _mud_models() -> list[str]:
    """Collect the distinct MUD-stage model names currently configured (best-effort)."""
    try:
        env.ensure_environment()
        from mudtool.config.settings import get_settings
        s = get_settings()
        return list(dict.fromkeys([
            n for n in (
                s.openai_model,
                getattr(s, "pipeline_generator_model", ""),
                getattr(s, "pipeline_reviewer_model", ""),
                getattr(s, "mud_spec_skeleton_model", ""),
                getattr(s, "activity_pipeline_skeleton_model", ""),
                getattr(s, "activity_pipeline_reviewer_model", ""),
            ) if n
        ]))
    except Exception:
        return []


def _unload_models(models: list[str]) -> None:
    for m in models:
        ollama_unload(m)


def _test_model() -> str:
    """The current MUT test-generation model name (best-effort)."""
    import os
    return os.environ.get("GEN_MODEL", "")


async def run_full_chain(
    requirements_file: str | Path,
    *,
    swc: Optional[str] = None,
    quick: bool = False,
    preset: Optional[str] = None,
    progress: Optional[Callable[[dict], None]] = None,
    keep_run: bool = True,
    root: Optional[Path] = None,
) -> dict[str, Any]:
    """Run the whole MUD → MUT pipeline and return a summary dict.

    ``preset=None`` (default) runs with the current per-stage selection
    (Workflow & Models / ``config/stages.json``) and does not change it. Pass a
    preset id from ``config/presets.json`` to apply that preset first.

    ``quick=True`` uses ``single_pass`` spec generation, skips the review and
    builds the activity flow deterministically from Section 7.

    A ``RUN_REPORT.md`` + ``run.json`` are always written (even on failure), and
    the LLM models are unloaded on exit.
    """
    run_holder: dict[str, Any] = {"done": None, "warnings": []}

    def tracking_progress(event: dict) -> None:
        # Remember the last completed pipeline stage, so a failure can be
        # attributed to the stage that was running.
        if event.get("stage") in report_mod.STAGE_ORDER:
            run_holder["done"] = event["stage"]
        if progress:
            progress(event)

    try:
        return await _run_full_chain(
            requirements_file, swc=swc, quick=quick, preset=preset,
            progress=tracking_progress, keep_run=keep_run, root=root, run_holder=run_holder,
        )
    except Exception as exc:
        run = run_holder.get("run")
        if run is not None:
            try:
                report_mod.write_run_report(run, {
                    "run_folder": str(run.folder),
                    "swc": run.swc,
                    "preset": run.preset,
                    "quick": quick,
                    "timings": run.state.get("timings", {}),
                    "tests_generated": 0,
                    "generation_failed": 0,
                    "review_approved": run_holder.get("review_approved", True),
                    "compilability": {"compile_ok": False, "stubbed": 0, "kept": 0},
                    "tests": {"status": "error"},
                    "trace": {},
                    "failed_stage": _failed_stage(run_holder.get("done"), quick),
                    "error": f"{type(exc).__name__}: {exc}",
                    "warnings": run_holder.get("warnings", []),
                }, stage_notes={"error": str(exc)})
            except Exception:
                pass
        raise
    finally:
        _unload_models(_mud_models())
        _unload_models([m for m in [_test_model()] if m])


def _failed_stage(last_done: Optional[str], quick: bool) -> str:
    """The stage after the last completed one (review is skipped in quick mode)."""
    order = [s for s in report_mod.STAGE_ORDER if not (quick and s == "review")]
    if last_done not in order:
        return order[0]
    idx = order.index(last_done)
    return order[min(idx + 1, len(order) - 1)]


async def _run_full_chain(
    requirements_file: str | Path,
    *,
    swc: Optional[str] = None,
    quick: bool = False,
    preset: Optional[str] = None,
    progress: Optional[Callable[[dict], None]] = None,
    keep_run: bool = True,
    root: Optional[Path] = None,
    run_holder: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """The linear pipeline (run by ``run_full_chain``, which adds error/finally handling)."""
    env.ensure_environment()
    env.export_provider_keys()
    timings: dict[str, float] = {}
    stage_notes: dict[str, str] = {}
    review_approved: bool = True

    holder = run_holder if run_holder is not None else {}
    warnings: list[str] = holder.setdefault("warnings", [])

    # Only an explicitly requested preset changes the stage selection; by
    # default the run uses (and never overwrites) the user's current choices.
    from mudmut_core import agents
    if preset:
        try:
            _, skipped = agents.apply_preset_with_report(preset)
            _emit(progress, "preset", f"Applied preset '{preset}'")
            if skipped:
                msg = (f"Preset '{preset}' has no model for: {', '.join(skipped)} — "
                       f"these stages kept their current model (pick one on Workflow & Models)")
                warnings.append(msg)
                _emit(progress, "preset", msg)
        except KeyError:
            msg = f"Preset '{preset}' unknown — using the current selection"
            warnings.append(msg)
            _emit(progress, "preset", msg)
    run_label = preset or "custom"

    # ── 1. import ─────────────────────────────────────────────────────────────
    t0 = time.time()
    imported = design.import_requirements(requirements_file)
    if not imported.requirement_set.requirements:
        raise ChainError(f"no requirements imported from {requirements_file}: {imported.errors}")
    reqs = imported.requirement_set
    _emit(progress, "import", f"Imported {reqs.count} requirement(s)")
    timings["import"] = time.time() - t0

    text = design.requirements_text(reqs)

    # ── 2. plan modules ───────────────────────────────────────────────────────
    t0 = time.time()
    plan = await design.plan_modules(text)
    modules = plan.modules
    if not modules:
        raise ChainError("module planning returned no SWC modules")
    timings["plan"] = time.time() - t0

    if swc:
        chosen = next((m for m in modules if m.swc_name == swc), None)
        if chosen is None:
            chosen = modules[0]
            _emit(progress, "plan", f"SWC '{swc}' not found; using {chosen.swc_name}")
    else:
        chosen = modules[0]
    _emit(progress, "plan", f"Selected {chosen.swc_name} ({len(modules)} module(s) planned)")

    # Create the run workspace only once the SWC is known.
    run = Run.create(chosen.swc_name, preset=run_label, root=root)
    if run_holder is not None:
        run_holder["run"] = run
    run.save_json_in("input", "requirements.json", design.requirements_to_dicts(reqs))
    run.save_state(swc=chosen.swc_name, quick=quick, preset=run_label)
    _emit(progress, "workspace", f"Run workspace: {run.folder}")

    # ── 3. generate MUD spec ──────────────────────────────────────────────────
    mode = "single_pass" if quick else "two_stage"
    t0 = time.time()
    spec_md = await design.generate_mud_spec(chosen, text, mode=mode, progress=progress)
    if not spec_md or len(spec_md.strip()) < 200:
        raise ChainError(f"MUD spec generation produced too little content ({len(spec_md or '')} chars)")
    run.save_in("mud", "mud_spec.md", spec_md)
    timings["spec"] = time.time() - t0
    stage_notes["spec"] = f"{len(spec_md)} chars, mode={mode}"
    _emit(progress, "spec", f"MUD spec generated ({len(spec_md)} chars, mode={mode})")

    # ── 4. review (skip in quick mode) ────────────────────────────────────────
    if not quick:
        t0 = time.time()
        spec_md, review = await design.review_and_improve(chosen, text, spec_md, max_rounds=1, progress=progress)
        review_approved = bool(review.approved)
        holder["review_approved"] = review_approved
        run.save_json_in("mud", "review.json", review.to_dict())
        run.save_in("mud", "mud_spec.md", spec_md)
        timings["review"] = time.time() - t0
        stage_notes["review"] = f"approved={review.approved} coverage={review.coverage_pct}%"
        _emit(
            progress, "review",
            f"Review: approved={review.approved} coverage={review.coverage_pct}% "
            f"errors={review.error_count} warnings={review.warning_count}",
        )

    # ── 5. activity diagram ───────────────────────────────────────────────────
    t0 = time.time()
    # quick: build the flow straight from Section 7 — on 7-9B models the AI
    # activity step routinely times out and ends in this same fallback anyway.
    activity = await design.generate_activity(
        reqs, spec_md, chosen.swc_name, use_ai=not quick, progress=progress
    )
    if not activity.diagrams:
        raise ChainError("activity generation produced no diagrams")
    run.save_json_in("mud", "activity.json", activity.model_dump() if hasattr(activity, "model_dump") else activity.dict())
    timings["activity"] = time.time() - t0
    _emit(progress, "activity", f"Generated {len(activity.diagrams)} activity diagram(s)")

    # ── 6. export C + Mermaid ─────────────────────────────────────────────────
    t0 = time.time()
    exported = design.export(activity)
    c_map: dict[str, str] = exported["c"]
    mermaid_map: dict[str, str] = exported["mermaid"]
    if not c_map:
        raise ChainError("no C skeleton produced (no top-level ActivityDiagram)")

    first_mmd = next(iter(mermaid_map.values()), "")
    run.save_in("mud", "flow.mmd", first_mmd)
    c_code = "\n\n".join(c_map.values())
    run.save_in("code", f"{chosen.swc_name}.c", c_code)
    timings["export"] = time.time() - t0

    # ── 7. make the C compilable ──────────────────────────────────────────────
    project_dir = run.dir("code")
    t0 = time.time()
    rep = compilable.make_compilable(c_code, chosen.swc_name, project_dir)
    run.save_json_in("code", "compilability.json", {
        "swc": chosen.swc_name,
        "total_statements": rep.total_statements,
        "kept_statements": rep.kept_statements,
        "stubbed_statements": rep.stubbed_statements,
        "rounds": rep.rounds,
        "compile_ok": rep.compile_ok,
        "last_error": rep.last_error,
    })
    timings["compilable"] = time.time() - t0
    stage_notes["compilable"] = rep.summary()
    _emit(progress, "compilable", f"Compilability: {rep.summary()}")

    # (Models are unloaded in run_full_chain's finally.)

    # ── 8. analyze + generate tests ───────────────────────────────────────────
    t0 = time.time()
    generation = await verify.generate_tests(project_dir, output_dir=run.dir("mut"))
    run.save_json_in("mut", "results.json", {"generation": generation})
    timings["generate_tests"] = time.time() - t0
    _emit(
        progress, "generate_tests",
        f"Generated {generation.get('tests_generated')} test file(s) "
        f"({len(generation.get('failed_functions') or [])} function(s) failed)",
    )

    # ── 9. build + run (+ fix loop) ───────────────────────────────────────────
    out_dir = Path(generation.get("output_directory", ""))
    test_result: dict[str, Any] = {"status": "skipped"}
    if out_dir and out_dir.is_dir():
        t0 = time.time()
        test_result = verify.fix_loop(out_dir, max_attempts=2)
        run.save_json_in("mut", "results.json", {"generation": generation, "run": test_result})
        timings["build_run"] = time.time() - t0
        junit = test_result.get("junit") or {}
        quarantined = test_result.get("quarantined_tests") or []
        _emit(
            progress, "build_run",
            f"Tests: {test_result.get('status')} — {junit.get('passed', 0)} passed, "
            f"{junit.get('failures', 0)} failed (fix_attempts={test_result.get('fix_attempts', 0)}"
            f", quarantined={len(quarantined)}"
            f"{', smoke-test fallback' if test_result.get('smoke_fallback') else ''})",
        )

    # ── 10. traceability ──────────────────────────────────────────────────────
    t0 = time.time()
    trace_record = trace_mod.build_trace(chosen.swc_name, rep.c_code, generation)
    run.save_json_in("trace", "trace.json", trace_record)
    run.save_in("trace", "trace.md", report_mod.trace_markdown(trace_record))
    timings["trace"] = time.time() - t0
    _emit(progress, "trace", f"Traceability: {len(trace_record['source_requirements'])} requirement(s)")

    run.save_state(timings=timings)

    summary = {
        "run_folder": str(run.folder),
        "swc": chosen.swc_name,
        "preset": run_label,
        "quick": quick,
        "warnings": warnings,
        "timings": timings,
        "tests_generated": generation.get("tests_generated", 0),
        "generation_failed": len(generation.get("failed_functions") or []),
        "review_approved": review_approved,
        "compilability": {
            "kept": rep.kept_statements,
            "stubbed": rep.stubbed_statements,
            "compile_ok": rep.compile_ok,
        },
        "tests": test_result,
        "trace": trace_record,
    }

    # ── 11. run report ────────────────────────────────────────────────────────
    report_mod.write_run_report(run, summary, stage_notes=stage_notes)

    return summary


def _main() -> int:
    parser = argparse.ArgumentParser(description="MUD → MUT end-to-end chain (headless)")
    parser.add_argument("--requirements", required=True, help="Path to the requirements file (csv/txt/md/xlsx)")
    parser.add_argument("--swc", default=None, help="SWC name to design + test (default: first planned module)")
    parser.add_argument("--quick", action="store_true", help="single_pass spec, skip review (fast demo)")
    parser.add_argument("--preset", default=None,
                        help="apply a preset id from config/presets.json first (default: keep the "
                             "current per-stage selection from Workflow & Models)")
    args = parser.parse_args()

    def progress(event: dict) -> None:
        msg = event.get("message", "")
        print(f"  [{event.get('stage', '?')}] {msg}")

    print("MUD_MUT chain")
    print(f"  requirements: {args.requirements}")
    print(f"  swc: {args.swc or '(auto)'}   quick={args.quick}   preset={args.preset}\n")

    summary = aio.run_sync(
        run_full_chain(args.requirements, swc=args.swc, quick=args.quick, preset=args.preset, progress=progress)
    )

    print("\n=== SUMMARY ===")
    print(json.dumps({
        "run_folder": summary["run_folder"],
        "swc": summary["swc"],
        "preset": summary["preset"],
        "timings": summary["timings"],
        "compilability": summary["compilability"],
        "tests": {k: summary["tests"].get(k) for k in ("status", "junit", "fix_attempts", "quarantined_tests", "smoke_fallback")},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
