"""Activity-from-MUD generation helpers.

Moved out of ``api/routes.py`` so the in-process engine (``mudmut_core``) and the
FastAPI routes share exactly one implementation. ``routes.py`` imports these back,
so the HTTP behaviour is unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from mudtool.models.json_uml import ActivityDiagram, DiagramType, GenerationResult

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids a runtime circular import
    from mudtool.api.routes import GenerateRequest

logger = logging.getLogger(__name__)

# With more runnables than this, the AI activity step asks for one runnable at a time.
PER_RUNNABLE_FROM = 3


def _looks_like_placeholder_activity(result_obj: "GenerationResult", mud_context) -> bool:
    """Return True when the AI produced a shallow/placeholder activity diagram.

    Mirrors the original nested helper; ``mud_context`` is now passed explicitly.
    """
    diagrams = [d for d in result_obj.diagrams if isinstance(d, ActivityDiagram) and not d.function_name]
    if not diagrams:
        return True
    if not mud_context.has_structured_flow_source:
        return False
    for diagram in diagrams:
        non_terminal = [
            n for n in diagram.nodes
            if n.node_type.value not in ("initial", "final")
        ]
        meaningful_node_types = {"decision", "merge", "fork", "join", "function_call", "call", "exception"}
        if diagram.sub_diagrams:
            return False
        if any(n.node_type.value in meaningful_node_types for n in non_terminal):
            return False
        if any(edge.guard for edge in diagram.edges):
            return False
        if len(non_terminal) >= 2:
            return False
        if non_terminal:
            label = (non_terminal[0].name or "").strip().lower()
            if label not in {
                "action",
                (diagram.owner_runnable or "").strip().lower(),
                diagram.name.replace(" Code Flow", "").replace(" Flowchart", "").strip().lower(),
            }:
                return False
    return True


async def _generate_activity_from_mud(
    orchestrator,
    requirements: list,
    request,
    progress_callback: Optional[Callable] = None,
) -> "GenerationResult":
    from mudtool.ai.mud_activity_context import (
        build_mud_activity_context,
        synthesize_activity_diagrams_from_context,
    )
    from mudtool.ai.section7_normalizer import normalize_section7_markdown

    original_markdown = request.mud_spec_markdown or ""
    normalization_warnings: list[str] = []
    try:
        normalization = normalize_section7_markdown(original_markdown)
        normalized_markdown = normalization.normalized_markdown
        if progress_callback:
            summary = normalization.summary()
            progress_callback({
                "stage": "activity_normalization",
                "diagram_type": "activity",
                "source": "mud_spec",
                "message": (
                    f"[Activity:MUD] Section 7 normalized - "
                    f"{summary['changed_runnable_count']}/{summary['normalized_runnable_count']} runnable block(s) adjusted, "
                    f"{summary['warning_count']} warning(s)"
                ),
                "section7_normalization": {
                    **summary,
                    "runnable_reports": [report.to_dict() for report in normalization.runnable_reports],
                    "warnings": list(normalization.warnings),
                },
            })
        normalization_warnings.extend(
            f"Section 7 normalization: {warning}" for warning in normalization.warnings
        )
    except Exception as exc:
        logger.warning("_generate_activity_from_mud: Section 7 normalization failed: %s", exc, exc_info=True)
        normalized_markdown = original_markdown
        normalization_warnings.append(f"Section 7 normalization failed - using original markdown: {exc}")
        if progress_callback:
            progress_callback({
                "stage": "activity_normalization",
                "diagram_type": "activity",
                "source": "mud_spec",
                "message": f"[Activity:MUD] Section 7 normalization failed - using original markdown ({exc})",
            })

    mud_context = build_mud_activity_context(
        normalized_markdown,
        module_context=request.module_context,
    )
    req_ids = [r.req_id for r in requirements]
    logger.info(
        "_generate_activity_from_mud: swc=%s runnables=%d has_flow=%s structured_flow=%s md_len=%d original_len=%d",
        mud_context.swc_name,
        len(mud_context.runnables),
        mud_context.has_usable_flow_source,
        mud_context.has_structured_flow_source,
        len(normalized_markdown),
        len(original_markdown),
    )
    if not mud_context.has_usable_flow_source:
        return GenerationResult(
            analyzed_requirements=req_ids,
            warnings=normalization_warnings,
            errors=[
                "Selected MUD spec does not contain runnable flow details usable for activity generation."
            ],
        )

    if progress_callback:
        progress_callback({
            "stage": "activity_context",
            "diagram_type": "activity",
            "source": "mud_spec",
            "runnable_count": len(mud_context.runnables),
            "message": (
                f"[Activity:MUD] Using MUD spec for {mud_context.swc_name or (request.module_context or 'selected SWC')} "
                f"with {len(mud_context.runnables)} runnable(s)"
            ),
        })

    # Callers may skip the AI step (e.g. a quick run on a small local model,
    # where it often times out) and build straight from Section 7.
    if not getattr(request, "use_ai_activity", True):
        synthesized = synthesize_activity_diagrams_from_context(mud_context, req_ids)
        if synthesized:
            if progress_callback:
                progress_callback({
                    "stage": "activity_deterministic",
                    "diagram_type": "activity",
                    "source": "mud_spec",
                    "runnable_count": len(synthesized),
                    "message": (
                        f"[Activity:MUD] Built {len(synthesized)} runnable diagram(s) deterministically "
                        f"from Section 7 (AI step skipped)."
                    ),
                })
            return GenerationResult(
                diagrams=synthesized,
                analyzed_requirements=req_ids,
                warnings=normalization_warnings + [
                    "Activity built deterministically from MUD Section 7 (AI step skipped)."
                ],
            )
        # The caller asked for no AI step: never fall back to it silently (on a small local
        # model that fallback took 40+ minutes and still failed). Say why instead.
        return GenerationResult(
            analyzed_requirements=req_ids,
            warnings=normalization_warnings,
            errors=[
                "Quick mode builds the flow from MUD Section 7 without AI, but Section 7 has no steps the "
                "builder can read (numbered steps or a C function body per runnable). Regenerate the spec, "
                "or switch Quick mode off to let the AI draw the flow (slow on local models)."
            ],
        )

    async def _generate(ctx, reqs):
        return await orchestrator.generate_diagram(
            DiagramType.ACTIVITY,
            reqs,
            module_context=request.module_context,
            existing_swcs=request.existing_swcs,
            temperature=request.temperature,
            progress_callback=progress_callback,
            generation_profile=("autosar" if request.autosar_compliant else "generic_c"),
            activity_label_style=request.activity_label_style,
            autosar_compliant=request.autosar_compliant,
            activity_source="mud_spec",
            mud_activity_context=ctx,
        )

    # Strict rule: the AI activity step only gets runnables whose Section 7 pseudo code passes
    # (real assignments / conditions / RTE access). Placeholder or empty runnables are never sent.
    import dataclasses
    from mudtool.ai.mud_activity_context import runnable_flow_quality
    quality = {r.name: runnable_flow_quality(r) for r in mud_context.runnables}
    rejected = [f"{name} ({q})" for name, q in quality.items() if q != "logic"]
    runnables = [r for r in mud_context.runnables if quality[r.name] == "logic"]
    if not runnables:
        return GenerationResult(
            analyzed_requirements=req_ids,
            warnings=normalization_warnings,
            errors=[
                "MUD spec Section 7 fails the pseudo-code rule for every runnable, so the AI activity step "
                f"was not called: {', '.join(rejected)}. Each runnable needs real steps (assignments, "
                "conditions, Rte_Read/Rte_Write, Dem_ reports), not callback stubs or TODOs. Regenerate the "
                "spec (a stronger model helps)."
            ],
        )
    if rejected:
        normalization_warnings = list(normalization_warnings) + [
            "Not sent to the AI activity step (pseudo code failed the rule): " + ", ".join(rejected)
        ]
        mud_context = dataclasses.replace(mud_context, runnables=runnables)

    if len(runnables) > PER_RUNNABLE_FROM:
        # One answer for many runnables runs into the output-token limit (seen: 8192 of
        # 8192 tokens, truncated JSON, three slow retries). Ask for one runnable at a time,
        # with only the requirements that runnable names (so the coverage check does not
        # demand every module requirement from a single runnable).
        from mudtool.ai import observer as _observer
        from mudtool.ai.mud_activity_context import ids_named
        all_ids = [r.req_id for r in requirements]
        result = GenerationResult(analyzed_requirements=req_ids)
        for i, runnable in enumerate(runnables, 1):
            _observer.check_cancel(f"before activity of {runnable.name}")
            if progress_callback:
                progress_callback({
                    "stage": "activity_runnable", "diagram_type": "activity",
                    "message": f"[Activity:MUD] Runnable {i}/{len(runnables)}: {runnable.name}",
                })
            own = set(ids_named(all_ids, f"{runnable.summary}\n{runnable.functional_description}"))
            # A spec that cites no requirement IDs (the usual case) names none per runnable: send the module's
            # requirements, otherwise the prompt has an empty traceability block, the model invents IDs and the
            # validator retries three times per runnable.
            own_reqs = [r for r in requirements if r.req_id in own] or list(requirements)
            part = await _generate(dataclasses.replace(mud_context, runnables=[runnable]), own_reqs)
            result.diagrams.extend(part.diagrams)
            result.warnings.extend(part.warnings)
            result.errors.extend(f"{runnable.name}: {e}" for e in part.errors)
    else:
        result = await _generate(mud_context, requirements)

    if _looks_like_placeholder_activity(result, mud_context):
        synthesized = synthesize_activity_diagrams_from_context(mud_context, req_ids)
        if synthesized:
            logger.warning(
                "_generate_activity_from_mud: replacing placeholder AI activity output with deterministic MUD Section 7 flow"
            )
            if progress_callback:
                progress_callback({
                    "stage": "activity_fallback",
                    "diagram_type": "activity",
                    "source": "mud_spec",
                    "runnable_count": len(synthesized),
                    "message": (
                        f"[Activity:MUD] AI returned placeholder flow; built {len(synthesized)} runnable diagram(s) from Section 7."
                    ),
                })
            return GenerationResult(
                diagrams=synthesized,
                analyzed_requirements=req_ids,
                warnings=result.warnings + normalization_warnings + [
                    "Activity AI output was too shallow; using deterministic flow generated from MUD Section 7."
                ],
                errors=result.errors,
            )
    if normalization_warnings:
        result.warnings.extend(normalization_warnings)
    return result
