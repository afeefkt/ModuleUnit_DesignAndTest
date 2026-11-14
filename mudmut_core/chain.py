"""End-to-end chain: requirements → MUD → C → MUT → trace.

Headless entry point::

    python -m mudmut_core.chain --requirements inputs/requirements/samples/bms_requirements.csv \\
        --swc SWC_BatteryManagement --quick
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from mudmut_core import aio, compilable, design, design_run, env, progress as progress_mod, report as report_mod, trace as trace_mod, verify
from mudmut_core.llm import observe, ollama_unload
from mudmut_core.workspace import Run


class ChainError(RuntimeError):
    pass


from mudmut_core.jobs import Cancelled  # noqa: E402


class ChainCancelled(Cancelled):
    """The user pressed Cancel; the run stopped between two stages."""


def _check_cancel(cancel: Optional[Callable[[], bool]], before: str) -> None:
    if cancel is not None and cancel():
        raise ChainCancelled(f"Cancelled before stage '{before}'")


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
    cancel: Optional[Callable[[], bool]] = None,
    prepared: Optional[tuple[Any, Any]] = None,
    code_baseline: Optional[Path] = None,
) -> dict[str, Any]:
    """Run the whole MUD → MUT pipeline and return a summary dict.

    ``cancel`` (optional) is polled between stages; when it returns True the run stops
    with :class:`ChainCancelled` and a partial report is written. ``prepared`` =
    ``(requirement_set, plan)`` skips import + planning (used by :func:`run_all_swcs`).

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
        # Only a finished stage counts: a warning emitted while the spec stage is still being
        # checked made a spec failure show up as "failed in stage review" (run 20261111_003217).
        if event.get("done") and event.get("stage") in report_mod.STAGE_ORDER:
            run_holder["done"] = event["stage"]
        if progress:
            progress(event)

    observer = _mudtool_observer()
    if observer is not None:
        # lets Cancel stop between AI attempts and while a model is streaming
        observer.set_cancel_check(cancel)
    try:
        try:
            return await _run_full_chain(
                requirements_file, swc=swc, quick=quick, preset=preset,
                progress=tracking_progress, keep_run=keep_run, root=root, run_holder=run_holder,
                cancel=cancel, prepared=prepared, code_baseline=code_baseline,
            )
        except BaseException as raw:
            if observer is not None and isinstance(raw, observer.GenerationCancelled):
                raise ChainCancelled(str(raw)) from raw
            if isinstance(raw, asyncio.CancelledError) and cancel is not None and cancel():
                # Cancel aborted a running AI request: finish as a cancelled run (partial report below).
                raise ChainCancelled("Cancelled while an AI request was running") from raw
            raise
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
                    "review_ai_empty": run_holder.get("review_ai_empty", False),
                    "compilability": {"compile_ok": False, "stubbed": 0, "kept": 0},
                    "tests": {"status": "error"},
                    "trace": {},
                    "failed_stage": _failed_stage(run_holder.get("done"), quick),
                    "error": f"{type(exc).__name__}: {exc}",
                    "warnings": run_holder.get("warnings", []),
                }, stage_notes={"error": str(exc)})
            except Exception:
                pass
            try:
                run.mark_finished("cancelled" if isinstance(exc, Cancelled) else "failed")
            except Exception:  # noqa: BLE001 - the status is informational
                pass
        raise
    finally:
        if observer is not None:
            observer.set_cancel_check(None)
        _unload_models(_mud_models())
        _unload_models([m for m in [_test_model()] if m])


def _mudtool_observer():
    """mud-tool's observer module (cancel hook), or None if mud-tool is not importable."""
    try:
        env.ensure_environment()
        from mudtool.ai import observer
        return observer
    except Exception:  # noqa: BLE001
        return None


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
    cancel: Optional[Callable[[], bool]] = None,
    prepared: Optional[tuple[Any, Any]] = None,
    code_baseline: Optional[Path] = None,
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

    if prepared is not None:
        # ── 1+2 done by the caller (multi-SWC run: one import + one plan) ─────
        reqs, plan = prepared
        text = design.requirements_text(reqs)
        _emit(progress, "import", f"Using {reqs.count} imported requirement(s)", done=True)
    else:
        # ── 1. import ─────────────────────────────────────────────────────────
        t0 = time.time()
        reqs = _import(requirements_file)
        _emit(progress, "import", f"Imported {reqs.count} requirement(s)", done=True)
        timings["import"] = time.time() - t0
        text = design.requirements_text(reqs)

        # ── 2. plan modules ───────────────────────────────────────────────────
        _check_cancel(cancel, "plan")
        t0 = time.time()
        observe.set_stage("plan")
        plan = await design.plan_modules(text)
        timings["plan"] = time.time() - t0
    modules = plan.modules
    if not modules:
        raise ChainError("module planning returned no SWC modules")

    if swc:
        chosen = next((m for m in modules if m.swc_name == swc), None)
        if chosen is None:
            chosen = modules[0]
            _emit(progress, "plan", f"SWC '{swc}' not found; using {chosen.swc_name}")
    else:
        chosen = modules[0]
    _emit(progress, "plan", f"Selected {chosen.swc_name} ({len(modules)} module(s) planned)", done=True)

    # Give the model only this component's requirements (a 120-requirement prompt for one
    # SWC is beyond small models); fall back to all when the plan has no IDs for it.
    module_reqs = requirements_for_module(reqs, chosen)
    scope = (module_reqs.count, reqs.count)
    if module_reqs is not reqs:
        text = design.requirements_text(module_reqs)
        _emit(progress, "plan", f"{chosen.swc_name}: {scope[0]} of {scope[1]} requirements go to the model")
    max_asil = highest_asil(module_reqs)

    # Create the run workspace only once the SWC is known.
    run = Run.create(chosen.swc_name, preset=run_label, root=root)
    if run_holder is not None:
        run_holder["run"] = run
    observe.set_run(run.folder)
    observe.adopt_orphans(run.folder)
    run.save_json_in("input", "requirements.json", design.requirements_to_dicts(reqs))
    run.save_state(swc=chosen.swc_name, quick=quick, preset=run_label)
    run.mark_running()
    _emit(progress, "workspace", f"Run workspace: {run.folder}", run_folder=str(run.folder))

    # ── 3. generate MUD spec ──────────────────────────────────────────────────
    mode = "single_pass" if quick else "two_stage"
    _check_cancel(cancel, "spec")
    t0 = time.time()
    observe.set_stage("spec")
    spec_md = design.clean_spec_markdown(await design.generate_mud_spec(chosen, text, mode=mode, progress=progress))
    if not spec_md or len(spec_md.strip()) < 200:
        raise ChainError(f"MUD spec generation produced too little content ({len(spec_md or '')} chars)")
    run.save_in("mud", "mud_spec.md", spec_md)
    timings["spec"] = time.time() - t0
    stage_notes["spec"] = f"{len(spec_md)} chars, mode={mode}"
    # Strict pseudo-code rule: stop here (before any slow AI step) when Section 7 has no
    # implementable logic — everything after it would be built on nothing.
    from mudmut_core import spec_check
    sc = spec_check.check_spec(spec_md, chosen.swc_name, chosen.runnables)
    # Concrete design gaps (a local read but never set, a helper whose logic is written nowhere,
    # a runnable without logic): one targeted repair call, kept only if the re-check is better.
    if spec_check.gap_count(sc):
        _check_cancel(cancel, "spec")
        _emit(progress, "spec", f"Spec check found {spec_check.gap_count(sc)} design gap(s) — asking the model to fix them")
        t1 = time.time()
        try:
            repaired = design.clean_spec_markdown(
                await design.repair_spec_from_check(chosen, text, spec_md, sc, progress=progress))
        except Exception as exc:  # noqa: BLE001 - the repair is optional; keep the first spec
            repaired = ""
            warnings.append(f"Spec repair call failed ({exc}); kept the first spec.")
        if repaired and len(repaired.strip()) >= 200:
            sc2 = spec_check.check_spec(repaired, chosen.swc_name, chosen.runnables)
            # A rewrite cut off at the output limit has fewer gaps simply because a runnable is gone.
            truncated = spec_check.rewrite_problem(spec_md, repaired)
            better = (sc2["ok"] or not sc["ok"]) and spec_check.gap_count(sc2) < spec_check.gap_count(sc) \
                and not truncated
            repair_note = (f"repair: gaps {spec_check.gap_count(sc)} → {spec_check.gap_count(sc2)}, "
                           f"{'kept' if better else 'discarded'}{': ' + truncated if truncated else ''} "
                           f"({time.time() - t1:.0f}s)")
            if truncated:
                warnings.append(f"The spec repair was discarded: {truncated}.")
            stage_notes["spec"] += f"; {repair_note}"
            if better:
                run.save_in("mud", "mud_spec_first.md", spec_md)
                spec_md, sc = repaired, sc2
                run.save_in("mud", "mud_spec.md", spec_md)
            _emit(progress, "spec", "Spec " + repair_note)
        timings["spec"] = time.time() - t0
    run.save_json_in("mud", "spec_check.json", sc)
    for w in spec_check.warnings_for(sc, chosen.swc_name):
        warnings.append(w)
        _emit(progress, "spec", w)
    if not sc["ok"]:
        raise ChainError("MUD spec rejected: " + " ".join(sc["problems"])
                         + " The AI activity step was not called. Regenerate the spec or use a stronger model.")
    stage_notes["spec"] += f"; Section 7: {len(sc['usable'])} of {sc['runnables']} runnable(s) with real logic"
    _emit(progress, "spec", f"MUD spec generated ({len(spec_md)} chars, mode={mode})", done=True)

    # ── 4. review (skip in quick mode) ────────────────────────────────────────
    if not quick:
        _check_cancel(cancel, "review")
        t0 = time.time()
        observe.set_stage("review")
        best_md, best_sc = spec_md, sc
        review_approved = False
        review_empty = False
        review = None
        review_note = ""
        for attempt in range(1, 3):          # retry once: the reviewer model sometimes answers empty
            reviewed_md, review = await design.review_and_improve(
                chosen, text, best_md, progress=progress,
                max_rounds=int(os.environ.get("MUDMUT_REVIEW_ROUNDS", "4") or 4))
            reviewed_md = design.clean_spec_markdown(reviewed_md)
            review_empty = bool(getattr(review, "ai_review_empty", False))
            review_approved = bool(review.approved)
            if reviewed_md and reviewed_md != best_md:
                sc_rev = spec_check.check_spec(reviewed_md, chosen.swc_name, chosen.runnables)
                truncated = spec_check.rewrite_problem(best_md, reviewed_md)
                worse = (not sc_rev["ok"]) or len(sc_rev["usable"]) < len(best_sc["usable"]) \
                    or spec_check.gap_count(sc_rev) > spec_check.gap_count(best_sc) or bool(truncated)
                if worse and not truncated and spec_check.gap_count(sc_rev) and len(sc_rev["usable"]) >= len(best_sc["usable"]):
                    # The review fixed its findings but left deterministic gaps (e.g. a read of a never-set
                    # local): one targeted repair of the rewrite instead of throwing the review's work away.
                    try:
                        fixed_md = design.clean_spec_markdown(
                            await design.repair_spec_from_check(chosen, text, reviewed_md, sc_rev, progress=progress))
                    except Exception as exc:  # noqa: BLE001 - optional
                        fixed_md = ""
                        warnings.append(f"Repair of the review rewrite failed ({exc}).")
                    if fixed_md and len(fixed_md.strip()) >= 200:
                        sc_fix = spec_check.check_spec(fixed_md, chosen.swc_name, chosen.runnables)
                        if (sc_fix["ok"] and len(sc_fix["usable"]) >= len(best_sc["usable"])
                                and spec_check.gap_count(sc_fix) <= spec_check.gap_count(best_sc)
                                and not spec_check.rewrite_problem(best_md, fixed_md)):
                            reviewed_md, sc_rev, worse = fixed_md, sc_fix, False
                            review_note += "; review rewrite repaired"
                if worse:
                    run.save_in("mud", "mud_spec_review_rejected.md", reviewed_md)
                    warnings.append("The review's rewritten spec was worse in the spec check"
                                    + (f" ({truncated})" if truncated else "")
                                    + " (saved as 01_mud/mud_spec_review_rejected.md); the checked spec was kept.")
                else:
                    best_md, best_sc = reviewed_md, sc_rev
                    review_note = "; review rewrite kept"
            if review_approved and not review_empty:
                break
            if attempt == 1:
                _emit(progress, "review", "Review not approved (or empty answer) — retrying once")
        spec_md, sc = best_md, best_sc
        holder["review_approved"] = review_approved
        holder["review_ai_empty"] = review_empty
        run.save_json_in("mud", "review.json", review.to_dict() if review else {})
        run.save_json_in("mud", "spec_check.json", sc)
        run.save_in("mud", "mud_spec.md", spec_md)
        timings["review"] = time.time() - t0
        stage_notes["review"] = f"approved={review_approved} coverage={getattr(review, 'coverage_pct', '?')}%{review_note}"
        if review_empty:
            stage_notes["review"] += "; ⚠️ the AI reviewer returned no answer — only the deterministic ID check ran"
            warnings.append("The AI spec reviewer returned an empty answer; the review verdict is the "
                            "deterministic requirement-ID check only.")
        _emit(
            progress, "review",
            f"Review: approved={review_approved} coverage={getattr(review, 'coverage_pct', '?')}% "
            f"errors={getattr(review, 'error_count', '?')} warnings={getattr(review, 'warning_count', '?')}",
            done=True,
        )

    # ── 5. activity diagram ───────────────────────────────────────────────────
    _check_cancel(cancel, "activity")
    t0 = time.time()
    # quick: build the flow straight from Section 7 — on 7-9B models the AI
    # activity step routinely times out and ends in this same fallback anyway.
    observe.set_stage("activity")
    activity = await design.generate_activity(
        module_reqs, spec_md, chosen.swc_name, use_ai=not quick, progress=progress
    )
    if not activity.diagrams:
        reason = "; ".join(getattr(activity, "errors", None) or []) or "no diagrams produced"
        raise ChainError(f"activity generation failed: {reason}")
    run.save_json_in("mud", "activity.json", activity.model_dump() if hasattr(activity, "model_dump") else activity.dict())
    timings["activity"] = time.time() - t0
    _emit(progress, "activity", f"Generated {len(activity.diagrams)} activity diagram(s)", done=True)

    # ── 5b. activity quality (≥ 80 %) with recovery ───────────────────────────
    # Score the flow against Section 7 and the requirements (optional DeepSeek judge, local render).
    # When the AI flow drops Section 7 steps (calibration reads, saturations, ...) the C built from it
    # reads variables nobody assigns — so the flow built straight from Section 7 is scored too and the
    # more faithful one is kept. The loop's TOOL_GREEN gate enforces the pass.
    from mudmut_core import flow_quality, flow_quality_render
    from mudtool.models.json_uml import GenerationResult
    req_ids = [getattr(r, "req_id", str(r)) for r in module_reqs.requirements]
    qa_render = flow_quality_render.render_mermaid_png if flow_quality_render.renderer_available() else None
    qa_judge = flow_quality.deepseek_judge() if not quick else None

    def _score_activity(act, png_name):
        if not isinstance(act, GenerationResult):
            return None
        try:
            return flow_quality.evaluate(act, spec_md, req_ids, render=qa_render, judge=qa_judge,
                                         png_path=run.dir("mud") / "activity_qa" / png_name)
        except Exception as exc:  # noqa: BLE001 - QA is advisory in the chain
            warnings.append(f"Activity quality check failed: {exc}")
            return None

    activity_quality = _score_activity(activity, "flow.png")
    activity_note = ""
    if (not quick and activity_quality is not None
            and (not activity_quality["passed"] or activity_quality["missing_steps"])):
        try:
            det = await design.generate_activity(module_reqs, spec_md, chosen.swc_name,
                                                 use_ai=False, progress=progress)
            if det.diagrams:
                # The Section 7 flow carries no requirement tags: tag its diagrams with the module's
                # requirement IDs the spec itself cites (never invented traceability).
                cited = {r for r in req_ids if r in spec_md}
                for d in det.diagrams:
                    d.source_requirements = sorted(set(d.source_requirements or []) | cited)
            det_quality = _score_activity(det, "flow_deterministic.png") if det.diagrams else None
        except Exception as exc:  # noqa: BLE001
            det, det_quality = None, None
            warnings.append(f"Deterministic activity fallback failed: {exc}")
        if det_quality is not None:
            use_det = flow_quality.prefer_alternative(activity_quality, det_quality)
            run.save_json_in("mud", "flow_quality_ai_discarded.json" if use_det
                             else "flow_quality_deterministic.json",
                             activity_quality if use_det else det_quality)
            if use_det:
                activity_note = (f" (AI flow dropped {len(activity_quality['missing_steps'])} Section 7 step(s)"
                                 f" at {activity_quality['score']}%; Section 7 flow used)")
                warnings.append("The AI activity flow was incomplete against Section 7; the flow built "
                                "directly from Section 7 was used instead.")
                activity, activity_quality = det, det_quality
                run.save_json_in("mud", "activity.json",
                                 activity.model_dump() if hasattr(activity, "model_dump") else activity.dict())

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

    if activity_quality is not None:
        run.save_json_in("mud", "flow_quality.json", activity_quality)
        run.save_in("mud", "flow_quality.md", flow_quality.markdown(activity_quality))
        stage_notes["activity_qa"] = (f"{activity_quality['score']}% "
                                      f"{flow_quality.verdict(activity_quality['score'])}{activity_note}")
        _emit(progress, "activity_qa",
              f"Activity quality: {activity_quality['score']}% {flow_quality.verdict(activity_quality['score'])}",
              done=True)
        if not activity_quality["passed"]:
            warnings.append(f"Activity quality {activity_quality['score']}% < 80%: "
                            f"{flow_quality.feedback_text(activity_quality)[:200]}")
    else:
        stage_notes["activity_qa"] = "skipped (not an AI/diagram result)"
        _emit(progress, "activity_qa", "Activity quality: skipped", done=True)

    # ── 7. make the C compilable ──────────────────────────────────────────────
    project_dir = run.dir("code")
    _check_cancel(cancel, "compilable")
    t0 = time.time()
    # Compiler errors go back to the model until the C compiles (MUDMUT_COMPILE_FIX=off disables it).
    fixer = None if os.environ.get("MUDMUT_COMPILE_FIX", "on").lower() in ("off", "0", "false", "no") \
        else compilable.llm_code_fixer()
    rep = compilable.make_compilable(c_code, chosen.swc_name, project_dir, spec_md=spec_md, fixer=fixer)
    comp_record = design_run.compilability_json(rep, chosen.swc_name)
    run.save_json_in("code", "compilability.json", comp_record)
    timings["compilable"] = time.time() - t0
    stage_notes["compilable"] = rep.summary()
    if not rep.compile_ok and code_baseline is None:
        # Tests cannot build against code that does not compile: generating them only costs
        # model calls and ends with every file quarantined and a smoke test that cannot link.
        first = next((ln.strip() for ln in (rep.last_error or "").splitlines() if "error" in ln), "")
        raise ChainError("The generated C does not compile, so no tests were generated"
                         + (f": {first[-240:]}" if first else "")
                         + " (see 02_code/compilability.json).")
    _emit(progress, "compilable", f"Compilability: {rep.summary()}", done=True)

    # ── 7b. pin an already completed code baseline (loop experiment) ──────────
    code_source = "generated"
    if code_baseline is not None:
        project_dir, c_code, comp_record = _pin_code_baseline(
            code_baseline, chosen.swc_name, project_dir, run, warnings, progress)
        code_source = "pinned"
        stage_notes["compilable"] = _pinned_compilability_note(comp_record)
        run.save_state(code_baseline=str(Path(code_baseline).resolve()))
    run.save_state(code_source=code_source)

    # (Models are unloaded in run_full_chain's finally.)

    # ── 8-10. tests, build/run, trace ─────────────────────────────────────────
    code_result = await test_existing_code(
        run, chosen.swc_name, project_dir, c_code=c_code,
        progress=progress, cancel=cancel, timings=timings,
    )
    generation = code_result["generation"]
    test_result = code_result["test_result"]
    trace_record = code_result["trace_record"]

    run.save_state(timings=timings)
    progress_mod.record_timings(timings, quick=quick)

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
        "review_ai_empty": holder.get("review_ai_empty", False),
        "compilability": design_run.compilability_summary(comp_record),
        "max_asil": max_asil,
        "requirements_for_module": list(scope) if scope[0] != scope[1] else None,
        "tests": test_result,
        "trace": trace_record,
        "code_source": code_source,
        "activity_quality": activity_quality,
    }

    # ── 11. run report ────────────────────────────────────────────────────────
    report_mod.write_run_report(run, summary, stage_notes=stage_notes)
    run.mark_finished("done")

    return summary


def _pinned_compilability_note(record: dict[str, Any]) -> str:
    return (f"pinned code baseline: {record.get('kept_statements', '?')} kept / "
            f"{record.get('stubbed_statements', '?')} stubbed "
            f"(compile_ok={record.get('compile_ok')})")


def _pin_code_baseline(
    baseline: str | Path,
    swc: str,
    project_dir: Path,
    run: Run,
    warnings: list[str],
    progress: Optional[Callable[[dict], None]],
) -> tuple[Path, str, dict[str, Any]]:
    """Replace the generated ``02_code`` with a completed, frozen baseline."""
    pinned = Path(baseline).resolve()
    pinned_c = pinned / f"{swc}.c"
    pinned_comp = pinned / "compilability.json"
    if not pinned_c.is_file():
        raise ChainError(f"code_baseline has no {swc}.c: {pinned}")
    if not pinned_comp.is_file():
        raise ChainError(f"code_baseline has no compilability.json: {pinned}")
    try:
        record = json.loads(pinned_comp.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - malformed baseline is a hard stop
        raise ChainError(f"code_baseline compilability.json is invalid: {exc}") from exc
    if record.get("swc") not in (None, swc):
        raise ChainError(f"code_baseline is for {record.get('swc')!r}, not {swc!r}")
    if not record.get("compile_ok"):
        raise ChainError("code_baseline did not compile; refusing to pin it")
    project_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(pinned.iterdir()):
        if path.is_file():
            shutil.copy2(path, project_dir / path.name)
    pinned_text = pinned_c.read_text(encoding="utf-8")
    run.save_in("code", f"{swc}.c", pinned_text)
    run.save_json_in("code", "compilability.json", record)
    warnings.append(f"Code pinned from {pinned} (completed baseline; not regenerated).")
    _emit(progress, "compilable", f"Pinned code baseline: {pinned}", done=True)
    return project_dir, pinned_text, record


async def test_existing_code(
    run: Run,
    swc: str,
    project_dir: Path,
    *,
    c_code: str,
    progress: Optional[Callable[[dict], None]] = None,
    cancel: Optional[Callable[[], bool]] = None,
    timings: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """Generate tests, build/run them and write traceability for an existing code folder.

    Shared by the full chain and the agentic loop, so the test/build/trace steps exist once.
    """
    timings = timings if timings is not None else {}

    # ── 8. analyze + generate tests ───────────────────────────────────────────
    _check_cancel(cancel, "generate_tests")
    t0 = time.time()
    observe.set_stage("generate_tests")

    def _gen_progress(done: int, total: int, name: str) -> None:
        _emit(progress, "generate_tests", f"Generating test {done + 1}/{total}: {name}",
              fraction=done / max(total, 1))

    generation = await verify.generate_tests(project_dir, output_dir=run.dir("mut"), progress=_gen_progress)
    run.save_json_in("mut", "results.json", {"generation": generation})
    timings["generate_tests"] = time.time() - t0
    _emit(
        progress, "generate_tests",
        f"Generated {generation.get('tests_generated')} test file(s) "
        f"({len(generation.get('failed_functions') or [])} function(s) failed)",
        done=True,
    )

    # ── 9. build + run (+ fix loop) ───────────────────────────────────────────
    out_dir = Path(generation.get("output_directory", ""))
    test_result: dict[str, Any] = {"status": "skipped"}
    if out_dir and out_dir.is_dir():
        _check_cancel(cancel, "build_run")
        t0 = time.time()
        observe.set_stage("build_run")
        test_result = verify.fix_loop(out_dir, max_attempts=verify.MAX_FIX_ATTEMPTS)
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
            done=True,
        )

    # ── 10. traceability ──────────────────────────────────────────────────────
    _check_cancel(cancel, "trace")
    t0 = time.time()
    trace_record = trace_mod.build_trace(swc, c_code, generation)
    run.save_json_in("trace", "trace.json", trace_record)
    run.save_in("trace", "trace.md", report_mod.trace_markdown(trace_record))
    timings["trace"] = time.time() - t0
    _emit(progress, "trace", f"Traceability: {len(trace_record['source_requirements'])} requirement(s)", done=True)

    return {"generation": generation, "test_result": test_result, "trace_record": trace_record}


_ASIL_RANK = {"QM": 0, "ASIL-A": 1, "ASIL-B": 2, "ASIL-C": 3, "ASIL-D": 4}


def highest_asil(reqs) -> Optional[str]:
    """The highest ASIL among the requirements (``None`` if none is set)."""
    best, rank = None, -1
    for r in getattr(reqs, "requirements", reqs):
        level = getattr(getattr(r, "safety_level", None), "value", getattr(r, "safety_level", None))
        if level in _ASIL_RANK and _ASIL_RANK[level] > rank:
            best, rank = level, _ASIL_RANK[level]
    return best


def requirements_for_module(reqs, module):
    """Only the requirements that belong to ``module`` (all of them if nothing says which do).

    The requirement file's own allocation ("Allocated To" / module hint) decides first: every
    requirement allocated to this SWC is in, and one allocated elsewhere (another SWC, or
    "System") is out, whatever the planner model answered — run 20261111_001000 got 19
    system-level requirements on top of its own 10 and designed other components' runnables
    (object fusion, driver warning) inside the brake actuator. Planner IDs only add
    requirements the file leaves unallocated. ``module.req_ids`` is updated to the result, so
    the spec and the review work on the same scope.
    """
    name = getattr(module, "swc_name", None)
    planned = set(getattr(module, "req_ids", None) or [])
    hints = {r.req_id: (getattr(r, "module_hint", None) or "").strip() for r in reqs.requirements}
    allocated = {rid for rid, hint in hints.items() if name and hint == name}
    if allocated:
        ids = allocated | {rid for rid in planned if not hints.get(rid, "")}
    else:
        ids = planned
    if not ids:
        return reqs
    items = [r for r in reqs.requirements if r.req_id in ids]
    if not items or len(items) == len(reqs.requirements):
        return reqs
    try:
        module.req_ids = [r.req_id for r in items]
    except (AttributeError, TypeError):
        pass
    try:
        return reqs.model_copy(update={"requirements": items})
    except AttributeError:
        return reqs.copy(update={"requirements": items})


def _import(requirements_file: str | Path):
    imported = design.import_requirements(requirements_file)
    if not imported.requirement_set.requirements:
        raise ChainError(f"no requirements imported from {requirements_file}: {imported.errors}")
    return imported.requirement_set


async def run_all_swcs(
    requirements_file: str | Path,
    *,
    only: Optional[list[str]] = None,
    quick: bool = False,
    preset: Optional[str] = None,
    progress: Optional[Callable[[dict], None]] = None,
    root: Optional[Path] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> dict[str, Any]:
    """Design and test every planned SWC (or the ones in ``only``) — one run folder each.

    Requirements are imported and planned **once**, so every SWC sees the same plan. A failing
    SWC does not stop the others; its partial report is written as usual. Progress events are
    re-scaled to the whole job (``fraction``) and tagged with the SWC.
    """
    env.ensure_environment()
    env.export_provider_keys()
    reqs = _import(requirements_file)
    _emit(progress, "import", f"Imported {reqs.count} requirement(s)", done=True)
    _check_cancel(cancel, "plan")
    observe.set_stage("plan")
    plan = await design.plan_modules(design.requirements_text(reqs))
    modules = [m for m in plan.modules if not only or m.swc_name in only]
    if not modules:
        raise ChainError(f"no planned SWC matches {only}" if only else "module planning returned no SWC modules")
    names = [m.swc_name for m in modules]
    _emit(progress, "plan", f"Planned {len(plan.modules)} SWC(s); running {len(modules)}: {', '.join(names)}",
          done=True)

    results: list[dict[str, Any]] = []
    for i, module in enumerate(modules):
        _check_cancel(cancel, f"SWC {module.swc_name}")
        tracker = progress_mod.ProgressTracker(quick=quick)
        tracker.update({"stage": "import", "done": True})
        tracker.update({"stage": "plan", "done": True})

        def scaled(event: dict, i: int = i, tracker=tracker, swc=module.swc_name) -> None:
            tracker.update(event)
            if progress:
                out = dict(event)
                out["message"] = f"[{swc} {i + 1}/{len(modules)}] {event.get('message', '')}"
                out["fraction"] = (i + tracker.percent / 100.0) / len(modules)
                out["swc"] = swc
                progress(out)

        try:
            summary = await run_full_chain(
                requirements_file, swc=module.swc_name, quick=quick, preset=preset if i == 0 else None,
                progress=scaled, root=root, cancel=cancel, prepared=(reqs, plan),
            )
            results.append({"swc": module.swc_name, "status": "done", "run_folder": summary["run_folder"],
                            "summary": summary})
        except ChainCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - keep going with the next SWC
            results.append({"swc": module.swc_name, "status": "error", "error": f"{type(exc).__name__}: {exc}"})
            _emit(progress, "error", f"{module.swc_name} failed: {exc}")
    done = [r for r in results if r["status"] == "done"]
    return {
        "swcs": results,
        "run_folder": done[-1]["run_folder"] if done else "",
        "warnings": [f"{r['swc']}: {r['error']}" for r in results if r["status"] == "error"],
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="MUD → MUT end-to-end chain (headless)")
    parser.add_argument("--requirements", required=True, help="Path to the requirements file (csv/txt/md/xlsx)")
    parser.add_argument("--swc", default=None,
                        help="SWC name to design + test (default: first planned module; 'all' = every planned "
                             "SWC, one run folder each)")
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

    if args.swc == "all":
        multi = aio.run_sync(
            run_all_swcs(args.requirements, quick=args.quick, preset=args.preset, progress=progress)
        )
        print("\n=== SUMMARY (all SWCs) ===")
        print(json.dumps([{k: r.get(k) for k in ("swc", "status", "run_folder", "error")} for r in multi["swcs"]],
                         indent=2))
        return 0 if all(r["status"] == "done" for r in multi["swcs"]) else 1

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
        "tests": {k: summary["tests"].get(k) for k in ("status", "junit", "fix_attempts", "quarantined_tests", "smoke_fallback", "cpputest")},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
