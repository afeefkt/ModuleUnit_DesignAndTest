"""FastAPI route definitions for the MUD Tool sidecar API.

These routes are called by the Modelio Java plugin (or any HTTP client)
to drive the requirement import, AI generation, and validation pipeline.
"""

from __future__ import annotations

import asyncio
import json as json_mod
import logging
import math
import tempfile
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from mudtool.config.settings import Settings, get_settings
from mudtool.debug_trace import RunDebugTrace
from mudtool.models.json_uml import DiagramType, GenerationResult
from mudtool.models.requirements import RequirementSet
from mudtool.models.validation import ValidationReport

logger = logging.getLogger(__name__)

router = APIRouter()


def _sanitize_for_json(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_json(item) for item in value]
    return value


def _sse_json(payload: dict) -> str:
    return json_mod.dumps(_sanitize_for_json(payload), default=str, allow_nan=False)


def _estimate_planned_diagrams(request: "GenerateRequest", diagram_types: list[DiagramType]) -> tuple[int, list[str]]:
    planned_items: list[str] = []
    non_activity = [dt for dt in diagram_types if dt != DiagramType.ACTIVITY]
    planned_items.extend(dt.value for dt in non_activity)

    if DiagramType.ACTIVITY in diagram_types:
        try:
            from mudtool.ai.mud_activity_context import build_mud_activity_context
            from mudtool.ai.section7_normalizer import normalize_section7_markdown

            markdown = request.mud_spec_markdown or ""
            try:
                markdown = normalize_section7_markdown(markdown).normalized_markdown
            except Exception:
                pass
            ctx = build_mud_activity_context(markdown, module_context=request.module_context)
            runnable_names = [getattr(r, "name", "") for r in getattr(ctx, "runnables", []) or []]
            planned_items.extend(name or "activity" for name in runnable_names)
        except Exception:
            planned_items.append("activity")

    return len(planned_items), planned_items


def _count_report_findings(report: ValidationReport, attr_name: str) -> int:
    value = getattr(report, attr_name, 0)
    if callable(value):
        value = value()
    return int(value or 0)


def _build_generation_summary(
    *,
    planned_count: int,
    planned_items: list[str],
    result: GenerationResult,
    rendered_count: int,
    validation_report: Optional[ValidationReport],
    lint_results: dict,
) -> dict:
    generated_count = len(result.diagrams or [])
    fallback_items: list[str] = []
    for diagram in result.diagrams or []:
        prov = getattr(diagram, "provenance", None)
        mode = getattr(prov, "provenance_mode", None) if prov is not None else None
        prompt_version = getattr(prov, "prompt_version", "") if prov is not None else ""
        if mode == "ai_failed_cfg_fallback" or str(prompt_version).startswith("activity_pipeline_cfg_"):
            fallback_items.append(
                getattr(diagram, "owner_runnable", None)
                or getattr(diagram, "name", "")
                or "activity"
            )
    ai_enriched_count = max(0, generated_count - len(fallback_items))
    attempted_count = planned_count
    base_count = max(planned_count, attempted_count)
    failed_count = max(0, base_count - generated_count)
    failed_items = planned_items[generated_count:] if failed_count else []
    if result.errors:
        failed_items.extend(str(error) for error in result.errors)

    validation_errors = _count_report_findings(validation_report, "error_count") if validation_report else 0
    validation_warnings = _count_report_findings(validation_report, "warning_count") if validation_report else 0
    lint_errors = sum(len(getattr(item, "errors", []) or []) for item in lint_results.values())
    lint_warnings = sum(len(getattr(item, "warnings", []) or []) for item in lint_results.values())
    render_failures = max(0, generated_count - rendered_count)

    blocking_count = len(result.errors or []) + validation_errors + lint_errors + render_failures
    warning_count = len(result.warnings or []) + validation_warnings + lint_warnings

    if generated_count == 0 or failed_count > 0 or render_failures > 0:
        quality_status = "failed"
    elif blocking_count > 0 or warning_count > 0:
        quality_status = "needs_fix"
    else:
        quality_status = "pass"

    return {
        "planned_count": planned_count,
        "attempted_count": attempted_count,
        "generated_count": generated_count,
        "rendered_count": rendered_count,
        "failed_count": failed_count,
        "ai_enriched_count": ai_enriched_count,
        "fallback_count": len(fallback_items),
        "fallback_items": fallback_items,
        "quality_status": quality_status,
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "failed_items": failed_items,
    }


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────

class ImportResponse(BaseModel):
    requirement_set: RequirementSet
    warnings: list[str] = []
    errors: list[str] = []
    rows_processed: int = 0
    rows_skipped: int = 0
    success: bool = True


class GenerateRequest(BaseModel):
    requirements: RequirementSet
    diagram_types: list[str] = Field(
        default=["sequence"],
        description="Diagram types to generate: sequence, state_machine, class, component, activity",
    )
    module_context: Optional[str] = None
    existing_swcs: Optional[list[str]] = None
    temperature: float = 0.2
    apply_autosar_mapping: bool = True
    autosar_compliant: bool = Field(
        True,
        description="If true generate AUTOSAR-compliant diagrams, else generic C-project diagrams.",
    )
    activity_label_style: Literal["pseudocode", "call_signature"] = Field(
        "pseudocode",
        description="Activity node label style preference.",
    )
    # Pipeline controls — override server defaults per request
    pipeline_mode: Optional[str] = Field(
        None,
        description=(
            "Pipeline mode: single_pass | multi_pass | two_model_fast | two_model. "
            "None = use MUD_PIPELINE_MODE from server config."
        ),
    )
    pipeline_max_passes: Optional[int] = Field(
        None,
        description="Max critique-refine cycles (1–3). None = use server default.",
        ge=1,
        le=3,
    )


    mud_spec_markdown: Optional[str] = Field(
        None,
        description="Latest MUD spec markdown for activity generation.",
    )
    activity_source: Literal["requirements", "mud_spec"] = Field(
        "requirements",
        description="Source of activity diagrams.",
    )


class GenerateResponse(BaseModel):
    result: GenerationResult
    validation_report: Optional[ValidationReport] = None
    generation_mode: str = Field(
        "autosar",
        description="autosar or generic_c",
    )
    elaboration_info: Optional[dict] = Field(
        None,
        description="Elaboration context metadata: source/status/elaborated_count/req_hash",
    )
    pipeline_summary: Optional[dict] = Field(
        None,
        description=(
            "Pipeline execution summary (present when pipeline is active). "
            "Shape: {mode, diagrams: {diagram_type: {passes, was_refined, final_confidence, stages}}}"
        ),
    )


class AnalyzeRequest(BaseModel):
    requirements: RequirementSet


class ValidateRequest(BaseModel):
    result: GenerationResult
    requirement_ids: Optional[list[str]] = None


class ExportRequest(BaseModel):
    result: GenerationResult
    output_path: str
    model_name: str = "MUD_Generated_Model"
    format: str = Field("xmi", description="xmi | plantuml | mermaid | drawio")


class MermaidInlineRequest(BaseModel):
    result: GenerationResult


class DrawIOInlineRequest(BaseModel):
    result: GenerationResult
    diagram_keys: Optional[list[str]] = None


class MermaidRenderRequest(BaseModel):
    mermaid_text: Optional[str] = None
    diagram_source: Optional[str] = None


class DrawIORenderRequest(BaseModel):
    diagram_source: str


class RenderRequest(BaseModel):
    result: GenerationResult
    output_path: str
    format: str = Field("svg", description="svg or png")


class TraceabilityResponse(BaseModel):
    matrix: list[dict] = []
    coverage: Optional[dict] = None


class AcceptElementRequest(BaseModel):
    element_id: str
    accepted_by: str = "engineer"


class HealthResponse(BaseModel):
    status: str
    version: str
    backends: dict = {}


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for the sidecar service."""
    from mudtool import __version__
    from mudtool.api.dependencies import get_orchestrator

    orchestrator = get_orchestrator()
    ai_health = await orchestrator.health_check()

    return HealthResponse(
        status="ok",
        version=__version__,
        backends=ai_health.get("backends", {}),
    )


@router.post("/requirements/import", response_model=ImportResponse)
async def import_requirements(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    sheet_name: Optional[str] = Form(None),
):
    """Import requirements from an uploaded file.

    Supports: .xlsx, .csv, .txt, .md
    Auto-detects format from file extension.
    """
    import json

    from mudtool.importers.factory import ImporterFactory

    # Save uploaded file to temp location
    suffix = Path(file.filename or "requirements.xlsx").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Parse column mapping if provided
        mapping = None
        if column_mapping:
            try:
                mapping = json.loads(column_mapping)
            except json.JSONDecodeError:
                raise HTTPException(400, "Invalid column_mapping JSON")

        kwargs = {}
        if sheet_name:
            kwargs["sheet_name"] = sheet_name

        result = ImporterFactory.import_file(tmp_path, column_mapping=mapping, **kwargs)

        if result.errors:
            logger.warning(
                "Import errors for %s: %s", file.filename, result.errors
            )
        if result.warnings:
            logger.info(
                "Import warnings for %s: %s", file.filename, result.warnings
            )
        logger.info(
            "Import result for %s: %d requirements, %d rows processed, success=%s",
            file.filename, result.requirement_set.count, result.rows_processed, result.success,
        )

        return ImportResponse(
            requirement_set=result.requirement_set,
            warnings=result.warnings,
            errors=result.errors,
            rows_processed=result.rows_processed,
            rows_skipped=result.rows_skipped,
            success=result.success,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/requirements/import/text", response_model=ImportResponse)
async def import_requirements_text(
    requirements_text: str = Form(...),
    format: str = Form("txt", description="txt, csv, or md"),
):
    """Import requirements from raw text input (for quick testing)."""
    from mudtool.importers.factory import ImporterFactory

    suffix = {"txt": ".txt", "csv": ".csv", "md": ".md"}.get(format, ".txt")

    with tempfile.NamedTemporaryFile(
        suffix=suffix, mode="w", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(requirements_text)
        tmp_path = Path(tmp.name)

    try:
        result = ImporterFactory.import_file(tmp_path)
        return ImportResponse(
            requirement_set=result.requirement_set,
            warnings=result.warnings,
            errors=result.errors,
            rows_processed=result.rows_processed,
            rows_skipped=result.rows_skipped,
            success=result.success,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


def _make_elaborator(settings, backend):
    """Return the elaborator instance matching MUD_ELABORATION_MODE.

    "chunked"     → ChunkedElaborator  (2–3B models; multiple small calls)
    "single_shot" → RequirementElaborator  (7B+ models; one large call)
    """
    mode = (settings.elaboration_mode or "single_shot").strip().lower()
    if mode == "chunked":
        from mudtool.ai.chunked_elaborator import ChunkedElaborator
        logger.info("Elaboration mode: chunked (small-model optimised)")
        return ChunkedElaborator(settings, backend)
    from mudtool.ai.elaborator import RequirementElaborator
    logger.info("Elaboration mode: single_shot")
    return RequirementElaborator(settings, backend)


@router.post("/elaborate")
async def elaborate_requirements(request: AnalyzeRequest):
    """Elaborate requirements using AI reasoning.

    Pre-processes requirements into structured AUTOSAR-specific JSON.
    Mode is controlled by MUD_ELABORATION_MODE:
      single_shot (default) — one large prompt, best for 7B+ models.
      chunked               — multiple small focused prompts, reliable on 2–3B.
    Results are cached for reuse.

    Returns: {thinking: [...], elaborated: [...], req_hash: "..."}
    """
    from mudtool.api.dependencies import get_orchestrator

    orchestrator = get_orchestrator()

    if not request.requirements.requirements:
        raise HTTPException(400, "No requirements provided")

    backend = orchestrator._get_backend()
    settings = get_settings()
    elaborator = _make_elaborator(settings, backend)
    result = await elaborator.elaborate(
        request.requirements.requirements, force_refresh=False
    )
    return result


@router.post("/elaborate/refresh")
async def elaborate_requirements_refresh(request: AnalyzeRequest):
    """Force-refresh requirement elaboration and overwrite existing cache.

    Mode is controlled by MUD_ELABORATION_MODE (see /elaborate).
    """
    from mudtool.api.dependencies import get_orchestrator

    orchestrator = get_orchestrator()

    if not request.requirements.requirements:
        raise HTTPException(400, "No requirements provided")

    backend = orchestrator._get_backend()
    settings = get_settings()
    elaborator = _make_elaborator(settings, backend)
    result = await elaborator.elaborate(
        request.requirements.requirements, force_refresh=True
    )
    return result


@router.post("/analyze", response_model=dict)
async def analyze_requirements(request: AnalyzeRequest):
    """Analyze requirements: cluster into modules, identify interfaces.

    Stage 2 of the pipeline. Returns module assignments, interface
    candidates, sequence hints, and state behavior flags.
    """
    from mudtool.api.dependencies import get_orchestrator

    orchestrator = get_orchestrator()

    if not request.requirements.requirements:
        raise HTTPException(400, "No requirements provided")

    result = await orchestrator.analyze_requirements(
        request.requirements.requirements
    )
    return result


async def _ensure_elaboration_data(
    orchestrator,
    requirements: list,
    progress_callback: Optional[callable] = None,
) -> dict:
    """Ensure valid elaboration context exists (cache hit or regenerated).

    Respects MUD_ELABORATION_MODE:
      single_shot — RequirementElaborator (one large prompt, 7B+ models)
      chunked     — ChunkedElaborator    (small focused prompts, 2–3B models)
    """
    backend = orchestrator._get_backend()
    settings = get_settings()
    elaborator = _make_elaborator(settings, backend)
    return await elaborator.elaborate(
        requirements=requirements,
        progress_callback=progress_callback,
        force_refresh=False,
    )


async def _generate_activity_per_swc(
    orchestrator,
    all_requirements: list,
    elaboration_data: dict,
    pipeline_orch,
    pipeline_config,
    module_context: Optional[str],
    existing_swcs: Optional[list],
    effective_mode,
    req_ids: list[str],
    progress_callback: Optional[callable] = None,
) -> "GenerationResult":
    """Generate one activity diagram per SWC when chunked elaboration is active.

    When `elaboration_data` contains a `swc_list` (produced by ChunkedElaborator),
    this function iterates over each SWC, filters its requirements, and generates
    an individual activity diagram.  All per-SWC results are merged into one
    GenerationResult.

    Falls back to a single call over all requirements if swc_list is absent
    (single_shot elaboration path).
    """
    from mudtool.ai.pipeline import PipelineMode, merge_pipeline_results
    from mudtool.models.json_uml import DiagramType, GenerationResult

    swc_list = elaboration_data.get("swc_list", [])
    req_map = {r.req_id: r for r in all_requirements}
    merged = GenerationResult(analyzed_requirements=req_ids)

    if not swc_list:
        # No SWC breakdown available — fall through to single call
        swc_list = [{"name": module_context or "SWC_Main",
                     "req_ids": req_ids,
                     "purpose": "All requirements"}]

    for idx, swc in enumerate(swc_list, start=1):
        swc_name = swc.get("name", f"SWC_{idx}")
        swc_req_ids = swc.get("req_ids", [])
        swc_reqs = [req_map[rid] for rid in swc_req_ids if rid in req_map]

        if not swc_reqs:
            logger.warning(f"[PerSWC] {swc_name}: no matched requirements, skipping")
            continue

        swc_context = swc_name
        if module_context:
            swc_context = f"{module_context} / {swc_name}"

        # Build a narrowed elaboration_data copy for this SWC's requirements
        swc_elaborated = [
            e for e in elaboration_data.get("elaborated", [])
            if e.get("req_id") in {r.req_id for r in swc_reqs}
        ]
        swc_elab_data = {
            **elaboration_data,
            "elaborated": swc_elaborated,
            "swc_ports": {swc_name: elaboration_data.get("swc_ports", {}).get(swc_name, [])},
            "swc_runnables": {swc_name: elaboration_data.get("swc_runnables", {}).get(swc_name, [])},
        }

        if progress_callback:
            progress_callback({
                "stage": "start",
                "diagram_type": "activity",
                "swc_name": swc_name,
                "req_count": len(swc_reqs),
                "swc_index": idx,
                "swc_total": len(swc_list),
                "message": (
                    f"[{idx}/{len(swc_list)}] Generating activity diagram "
                    f"for {swc_name} ({len(swc_reqs)} req(s))..."
                ),
            })

        try:
            from mudtool.ai.pipeline import PipelineMode
            if effective_mode == PipelineMode.SINGLE_PASS or pipeline_config is None:
                # Single-pass or no config available: one direct call per SWC
                swc_result = await orchestrator.generate_diagram(
                    DiagramType.ACTIVITY,
                    swc_reqs,
                    module_context=swc_context,
                    existing_swcs=existing_swcs,
                    elaborated_data=swc_elab_data,
                    progress_callback=progress_callback,
                )
            else:
                import dataclasses
                from mudtool.ai.pipeline import PipelineOrchestrator
                swc_config = dataclasses.replace(
                    pipeline_config,
                    elaborated_data=swc_elab_data,
                )
                swc_pipe = PipelineOrchestrator(get_settings(), orchestrator)
                swc_results = await swc_pipe.generate_with_pipeline(
                    requirements=swc_reqs,
                    diagram_types=[DiagramType.ACTIVITY],
                    config=swc_config,
                    module_context=swc_context,
                    existing_swcs=existing_swcs,
                    progress_callback=progress_callback,
                )
                swc_result, _ = merge_pipeline_results(swc_results, swc_req_ids)

            merged.diagrams.extend(swc_result.diagrams)
            merged.warnings.extend(swc_result.warnings)
            merged.errors.extend(swc_result.errors)
            logger.info(
                f"[PerSWC] {swc_name}: generated {len(swc_result.diagrams)} "
                f"activity diagram(s)"
            )
        except Exception as exc:
            logger.error(f"[PerSWC] {swc_name} generation failed: {exc}")
            merged.errors.append(f"Activity diagram for {swc_name} failed: {exc}")

    return merged


def _validate_activity_request(request: GenerateRequest, diagram_types: list[DiagramType]) -> None:
    if DiagramType.ACTIVITY not in diagram_types:
        return
    if request.activity_source != "mud_spec":
        raise HTTPException(
            400,
            "Activity diagrams are MUD-first and require activity_source='mud_spec'.",
        )
    if not (request.mud_spec_markdown or "").strip():
        raise HTTPException(
            400,
            "Activity diagrams require mud_spec_markdown from the selected module.",
        )


async def _generate_activity_from_mud(
    orchestrator,
    requirements: list,
    request: GenerateRequest,
    progress_callback: Optional[callable] = None,
) -> "GenerationResult":
    from mudtool.ai.mud_activity_context import (
        build_mud_activity_context,
        synthesize_activity_diagrams_from_context,
    )
    from mudtool.ai.section7_normalizer import normalize_section7_markdown
    from mudtool.models.json_uml import ActivityDiagram, DiagramType, GenerationResult

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

    result = await orchestrator.generate_diagram(
        DiagramType.ACTIVITY,
        requirements,
        module_context=request.module_context,
        existing_swcs=request.existing_swcs,
        temperature=request.temperature,
        progress_callback=progress_callback,
        generation_profile=("autosar" if request.autosar_compliant else "generic_c"),
        activity_label_style=request.activity_label_style,
        autosar_compliant=request.autosar_compliant,
        activity_source="mud_spec",
        # Pass the parsed MudActivityContext object so the multi-stage
        # ActivityPipeline can iterate runnables.  generate_diagram falls
        # back to to_prompt_block() for the legacy single-call path.
        mud_activity_context=mud_context,
    )

    def _looks_like_placeholder_activity(result_obj: "GenerationResult") -> bool:
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

    if _looks_like_placeholder_activity(result):
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


@router.post("/generate", response_model=GenerateResponse)
async def generate_diagrams(request: GenerateRequest):
    """Generate UML diagrams from requirements using AI.

    Main generation endpoint. Runs the full pipeline:
    1. AI generation for requested diagram types (single-pass or multi-stage pipeline)
    2. AUTOSAR mapping (if enabled)
    3. Validation

    Pipeline modes (set via request.pipeline_mode or MUD_PIPELINE_MODE in .env):
      single_pass    — one AI call per diagram (fastest)
      multi_pass     — codellama self-critiques & refines
      two_model_fast — codellama generates, llama3.2 critiques
      two_model      — codellama generates, mistral critiques (best quality)
    """
    from mudtool.ai.pipeline import (
        PipelineConfig,
        PipelineMode,
        PipelineOrchestrator,
        merge_pipeline_results,
    )
    from mudtool.api.dependencies import get_mapper, get_orchestrator, get_validator

    orchestrator = get_orchestrator()
    mapper = get_mapper()
    validator = get_validator()
    settings: Settings = get_settings()

    if not request.requirements.requirements:
        raise HTTPException(400, "No requirements provided")

    # Parse diagram types
    diagram_types = []
    for dt_str in request.diagram_types:
        try:
            diagram_types.append(DiagramType(dt_str))
        except ValueError:
            raise HTTPException(400, f"Invalid diagram type: {dt_str}")
    _validate_activity_request(request, diagram_types)

    req_ids = [r.req_id for r in request.requirements.requirements]
    generation_mode = "autosar" if request.autosar_compliant else "generic_c"
    generation_profile = generation_mode

    from mudtool.validation.structural_precheck import StructuralPreCheck
    precheck = StructuralPreCheck()
    precheck_results = {
        dt.value: precheck.check(request.requirements.requirements, dt).to_summary()
        for dt in diagram_types
        if dt != DiagramType.ACTIVITY
    }
    diagram_types = [
        dt for dt in diagram_types
        if dt == DiagramType.ACTIVITY
        or not precheck_results.get(dt.value, {}).get("blocked", False)
    ]
    if not diagram_types:
        raise HTTPException(
            400,
            "All requested architecture diagrams are blocked by structural pre-check.",
        )

    elaboration_data = await _ensure_elaboration_data(
        orchestrator, request.requirements.requirements
    )
    # Guidelines RAG injection (non-streaming path)
    if settings.guidelines_enabled:
        try:
            from mudtool.ai.guidelines_reader import GuidelinesReader
            _g_reader = GuidelinesReader(settings)
            _g_status = await _g_reader.load_all()
            if _g_status.chunk_count > 0:
                _req_text = " ".join(
                    f"{r.title or ''} {r.description or ''}"
                    for r in request.requirements.requirements
                )
                _g_ctx: dict[str, str] = {}
                for _dt in diagram_types:
                    _block = await _g_reader.build_guidelines_context(_dt.value, _req_text)
                    if _block:
                        _g_ctx[_dt.value] = _block
                if _g_ctx:
                    elaboration_data["guidelines_context"] = _g_ctx
        except Exception as _exc:
            logger.warning("[Guidelines] Non-streaming load failed (non-fatal): %s", _exc)
    elaboration_info = {
        "source": elaboration_data.get("source", "failed"),
        "status": elaboration_data.get("status", "unknown"),
        "elaborated_count": len(elaboration_data.get("elaborated", [])),
        "req_hash": elaboration_data.get("req_hash"),
        "quality_score": elaboration_data.get("quality_score"),
    }
    logger.info(
        "Elaboration context: source=%s status=%s count=%s",
        elaboration_info["source"],
        elaboration_info["status"],
        elaboration_info["elaborated_count"],
    )

    # Determine effective pipeline mode
    raw_mode = request.pipeline_mode or (
        settings.pipeline_mode if settings.pipeline_enabled else "single_pass"
    )
    try:
        effective_mode = PipelineMode(raw_mode)
    except ValueError:
        raise HTTPException(
            400,
            f"Invalid pipeline_mode '{raw_mode}'. "
            "Use: single_pass | multi_pass | two_model_fast | two_model"
        )

    pipeline_summary: Optional[dict] = None

    # Split activity diagrams per-SWC when chunked elaboration produced a swc_list
    has_swc_list = bool(elaboration_data.get("swc_list"))
    activity_types = [dt for dt in diagram_types if dt == DiagramType.ACTIVITY]
    other_types = [dt for dt in diagram_types if dt != DiagramType.ACTIVITY]

    pipeline_config = None
    result = GenerationResult(analyzed_requirements=req_ids)

    # ── Non-activity diagram types (sequence, state_machine, class, component) ──
    if other_types:
        if effective_mode == PipelineMode.SINGLE_PASS:
            other_result = await orchestrator.generate_all_diagrams(
                requirements=request.requirements.requirements,
                diagram_types=other_types,
                module_context=request.module_context,
                generation_profile=generation_profile,
                activity_label_style=request.activity_label_style,
                autosar_compliant=request.autosar_compliant,
                elaborated_data=elaboration_data,
            )
        else:
            reviewer = (
                "llama3.2"
                if effective_mode == PipelineMode.TWO_MODEL_FAST
                else settings.pipeline_reviewer_model
            )
            pipeline_config = PipelineConfig(
                mode=effective_mode,
                generator_model=settings.pipeline_generator_model,
                reviewer_model=reviewer,
                max_passes=request.pipeline_max_passes or settings.pipeline_max_passes,
                min_confidence=settings.pipeline_confidence_threshold,
                draft_temperature=request.temperature,
                generation_profile=generation_profile,
                activity_label_style=request.activity_label_style,
                autosar_compliant=request.autosar_compliant,
                elaborated_data=elaboration_data,
            )
            logger.info(
                f"Pipeline mode={effective_mode.value}, "
                f"generator={pipeline_config.generator_model}, "
                f"reviewer={pipeline_config.reviewer_model}, "
                f"max_passes={pipeline_config.max_passes}"
            )
            pipeline_orch = PipelineOrchestrator(settings, orchestrator)
            pipeline_results = await pipeline_orch.generate_with_pipeline(
                requirements=request.requirements.requirements,
                diagram_types=other_types,
                config=pipeline_config,
                module_context=request.module_context,
                existing_swcs=request.existing_swcs,
            )
            other_result, pipeline_summary = merge_pipeline_results(pipeline_results, req_ids)
        result.diagrams.extend(other_result.diagrams)
        result.warnings.extend(other_result.warnings)
        result.errors.extend(other_result.errors)

    # ── Activity diagrams — one per SWC when swc_list is available ──────────
    if activity_types:
        activity_result = await _generate_activity_from_mud(
            orchestrator=orchestrator,
            requirements=request.requirements.requirements,
            request=request,
        )
        result.diagrams.extend(activity_result.diagrams)
        result.warnings.extend(activity_result.warnings)
        result.errors.extend(activity_result.errors)

    # AUTOSAR mapping (unchanged)
    if request.autosar_compliant and request.apply_autosar_mapping:
        result = mapper.map_generation_result(result)

    # Validate (unchanged)
    validation_report = validator.validate(
        result,
        requirement_ids=req_ids,
        autosar_compliant=request.autosar_compliant,
    )

    # Store trace links, but don't let traceability persistence undo a successful generation.
    try:
        from mudtool.api.dependencies import get_trace_store
        trace_store = get_trace_store()
        trace_store.extract_and_store_traces(result)
    except Exception as exc:
        logger.warning("Traceability store write failed during /generate: %s", exc, exc_info=True)
        result.warnings.append(f"Traceability persistence failed: {exc}")

    return GenerateResponse(
        result=result,
        validation_report=validation_report,
        generation_mode=generation_mode,
        elaboration_info=elaboration_info,
        pipeline_summary=pipeline_summary,
    )


@router.post("/generate/stream")
async def generate_diagrams_stream(request: GenerateRequest):
    """Generate UML diagrams with Server-Sent Events for real-time progress.

    Same logic as /generate, but streams progress events via SSE.
    Events: progress, diagram_complete, complete, error
    """
    from mudtool.ai.pipeline import (
        PipelineConfig,
        PipelineMode,
        PipelineOrchestrator,
        merge_pipeline_results,
    )
    from mudtool.api.dependencies import get_mapper, get_orchestrator, get_validator

    orchestrator = get_orchestrator()
    mapper = get_mapper()
    validator = get_validator()
    settings: Settings = get_settings()

    if not request.requirements.requirements:
        raise HTTPException(400, "No requirements provided")

    diagram_types = []
    for dt_str in request.diagram_types:
        try:
            diagram_types.append(DiagramType(dt_str))
        except ValueError:
            raise HTTPException(400, f"Invalid diagram type: {dt_str}")
    _validate_activity_request(request, diagram_types)

    req_ids = [r.req_id for r in request.requirements.requirements]
    generation_mode = "autosar" if request.autosar_compliant else "generic_c"
    generation_profile = generation_mode

    raw_mode = request.pipeline_mode or (
        settings.pipeline_mode if settings.pipeline_enabled else "single_pass"
    )
    try:
        effective_mode = PipelineMode(raw_mode)
    except ValueError:
        raise HTTPException(400, f"Invalid pipeline_mode '{raw_mode}'.")

    trace = RunDebugTrace(
        settings,
        "diagram_generate_stream",
        {
            "diagram_types": [dt.value for dt in diagram_types],
            "requirement_count": len(request.requirements.requirements),
            "requirement_ids": req_ids,
            "generation_mode": generation_mode,
            "pipeline_mode": effective_mode.value,
            "activity_source": request.activity_source,
            "module_context": request.module_context,
        },
    )

    # SSE event queue — progress_callback pushes, generator yields
    queue: asyncio.Queue = asyncio.Queue()

    def progress_callback(event: dict) -> None:
        trace.record_event("progress", event)
        queue.put_nowait(event)

    async def run_generation():
        """Background coroutine that runs the full enhanced pipeline."""
        try:
            pipeline_summary = None
            visual_qa_summary: list[dict] = []

            # ── Stage 0: Structural Pre-check ─────────────────────────────────
            from mudtool.validation.structural_precheck import StructuralPreCheck
            precheck = StructuralPreCheck()
            precheck_results = {}
            precheck_hints: dict[str, str] = {}  # diagram_type.value → hint block
            for dt in diagram_types:
                if dt == DiagramType.ACTIVITY and request.activity_source == "mud_spec":
                    precheck_results[dt.value] = {
                        "diagram_type": dt.value,
                        "blocked": False,
                        "quality_score": 1.0,
                        "gap_count": 0,
                        "warning_count": 0,
                        "gaps": [],
                        "warnings": [],
                        "suggestions": [],
                    }
                    continue
                pc = precheck.check(request.requirements.requirements, dt)
                precheck_results[dt.value] = pc.to_summary()
                if pc.gaps or pc.warnings:
                    progress_callback({
                        "stage": "precheck",
                        "diagram_type": dt.value,
                        "blocked": pc.blocked,
                        "quality_score": pc.quality_score,
                        "gap_count": len(pc.gaps),
                        "warning_count": len(pc.warnings),
                        "gaps": pc.gaps,
                        "warnings": pc.warnings,
                        "suggestions": pc.suggestions,
                        "message": (
                            f"[PreCheck:{dt.value}] "
                            f"{len(pc.gaps)} gap(s), {len(pc.warnings)} warning(s) "
                            f"- quality={pc.quality_score:.0%}"
                        ),
                    })
                if pc.to_hint_block():
                    precheck_hints[dt.value] = pc.to_hint_block()
                logger.info(
                    "[PreCheck:%s] score=%.2f blocked=%s gaps=%d warnings=%d",
                    dt.value, pc.quality_score, pc.blocked,
                    len(pc.gaps), len(pc.warnings),
                )

            # Filter out blocked diagram types
            active_diagram_types = [
                dt for dt in diagram_types
                if not precheck_results.get(dt.value, {}).get("blocked", False)
            ]
            planned_count, planned_items = _estimate_planned_diagrams(request, active_diagram_types)
            if not active_diagram_types:
                event = trace.attach_path({
                    "_error": True,
                    "message": "All diagram types blocked by structural pre-check - "
                               "requirements are too sparse. Check precheck warnings.",
                })
                trace.record_event("error", event)
                queue.put_nowait(event)
                return

            # ── Stage 0.5: Guidelines RAG Load ───────────────────────────────
            _guidelines_context: dict[str, str] = {}
            if settings.guidelines_enabled:
                try:
                    from mudtool.ai.guidelines_reader import GuidelinesReader
                    _g_reader = GuidelinesReader(settings)
                    _g_status = await _g_reader.load_all(
                        progress_callback=progress_callback
                    )
                    if _g_status.chunk_count > 0:
                        _req_text = " ".join(
                            f"{r.title or ''} {r.description or ''}"
                            for r in request.requirements.requirements
                        )
                        for dt in active_diagram_types:
                            block = await _g_reader.build_guidelines_context(
                                dt.value, _req_text
                            )
                            if block:
                                _guidelines_context[dt.value] = block
                        logger.info(
                            "[Guidelines] %d doc(s), %d chunks, %d diagram contexts",
                            _g_status.doc_count,
                            _g_status.chunk_count,
                            len(_guidelines_context),
                        )
                except Exception as exc:
                    logger.warning("[Guidelines] Load failed (non-fatal): %s", exc)

            # ── Stage 1: Elaboration ──────────────────────────────────────────
            elaboration_data = await _ensure_elaboration_data(
                orchestrator,
                request.requirements.requirements,
                progress_callback=progress_callback,
            )
            # Inject pre-check hints into elaboration data for prompt rendering
            if precheck_hints:
                elaboration_data["precheck_hints"] = precheck_hints
            # Inject guidelines context into elaboration data for orchestrator injection
            if _guidelines_context:
                elaboration_data["guidelines_context"] = _guidelines_context

            elaboration_info = {
                "source": elaboration_data.get("source", "failed"),
                "status": elaboration_data.get("status", "unknown"),
                "elaborated_count": len(elaboration_data.get("elaborated", [])),
                "req_hash": elaboration_data.get("req_hash"),
                "quality_score": elaboration_data.get("quality_score"),
            }
            logger.info(
                "Elaboration context: source=%s status=%s count=%s",
                elaboration_info["source"],
                elaboration_info["status"],
                elaboration_info["elaborated_count"],
            )

            # ── Stage 2: AI Generation ────────────────────────────────────────
            has_swc_list = bool(elaboration_data.get("swc_list"))
            act_types = [dt for dt in active_diagram_types if dt == DiagramType.ACTIVITY]
            other_types = [dt for dt in active_diagram_types if dt != DiagramType.ACTIVITY]

            pipeline_config = None
            result = GenerationResult(analyzed_requirements=req_ids)

            # Non-activity types (sequence, state_machine, class, component)
            if other_types:
                if effective_mode == PipelineMode.SINGLE_PASS:
                    other_result = await orchestrator.generate_all_diagrams(
                        requirements=request.requirements.requirements,
                        diagram_types=other_types,
                        module_context=request.module_context,
                        progress_callback=progress_callback,
                        generation_profile=generation_profile,
                        activity_label_style=request.activity_label_style,
                        autosar_compliant=request.autosar_compliant,
                        elaborated_data=elaboration_data,
                    )
                else:
                    reviewer = (
                        "llama3.2"
                        if effective_mode == PipelineMode.TWO_MODEL_FAST
                        else settings.pipeline_reviewer_model
                    )
                    pipeline_config = PipelineConfig(
                        mode=effective_mode,
                        generator_model=settings.pipeline_generator_model,
                        reviewer_model=reviewer,
                        max_passes=request.pipeline_max_passes or settings.pipeline_max_passes,
                        min_confidence=settings.pipeline_confidence_threshold,
                        draft_temperature=request.temperature,
                        generation_profile=generation_profile,
                        activity_label_style=request.activity_label_style,
                        autosar_compliant=request.autosar_compliant,
                        elaborated_data=elaboration_data,
                    )
                    pipeline_orch = PipelineOrchestrator(settings, orchestrator)
                    pipeline_results = await pipeline_orch.generate_with_pipeline(
                        requirements=request.requirements.requirements,
                        diagram_types=other_types,
                        config=pipeline_config,
                        module_context=request.module_context,
                        existing_swcs=request.existing_swcs,
                        progress_callback=progress_callback,
                    )
                    other_result, pipeline_summary = merge_pipeline_results(pipeline_results, req_ids)
                result.diagrams.extend(other_result.diagrams)
                result.warnings.extend(other_result.warnings)
                result.errors.extend(other_result.errors)

            # Activity diagrams — one per SWC when swc_list is available
            if act_types:
                if has_swc_list:
                    logger.info(
                        "[PerSWC] Generating activity diagrams for %d SWC(s)",
                        len(elaboration_data["swc_list"]),
                    )
                activity_result = await _generate_activity_from_mud(
                    orchestrator=orchestrator,
                    requirements=request.requirements.requirements,
                    request=request,
                    progress_callback=progress_callback,
                )
                result.diagrams.extend(activity_result.diagrams)
                result.warnings.extend(activity_result.warnings)
                result.errors.extend(activity_result.errors)

            # ── Stage 3: AUTOSAR Mapping ──────────────────────────────────────
            if request.autosar_compliant and request.apply_autosar_mapping:
                result = mapper.map_generation_result(result)

            # ── Stage 4: Validation ───────────────────────────────────────────
            validation_report = validator.validate(
                result,
                requirement_ids=req_ids,
                autosar_compliant=request.autosar_compliant,
            )

            # ── Stage 5: Mermaid Lint ─────────────────────────────────────────
            from mudtool.generator.mermaid_exporter import MermaidExporter
            from mudtool.validation.mermaid_linter import MermaidLinter

            mermaid_exporter = MermaidExporter()
            linter = MermaidLinter()
            mermaid_inline = mermaid_exporter.export_result_inline(result)
            lint_results = linter.lint_all(mermaid_inline)

            # Suppress cosmetic/heuristic lint warnings that fire for valid compact diagrams.
            # These are not actionable by the user and clutter the UI with false positives.
            # Structural errors (missing INITIAL/FINAL, disconnected subgraphs) are kept.
            _SUPPRESSED_LINT_PATTERNS = (
                "branching paths may be missing",  # fires whenever edge_count <= node_count
                "may be unreachable",              # fires for exception / sink nodes
                "no outgoing edges",               # fires for FINAL nodes by design
            )
            for _lint in lint_results.values():
                if _lint.warnings:
                    _lint.warnings = [
                        w for w in _lint.warnings
                        if not any(p in w for p in _SUPPRESSED_LINT_PATTERNS)
                    ]

            for key, lint in lint_results.items():
                if lint.errors or lint.warnings:
                    progress_callback({
                        "stage": "mermaid_lint",
                        "diagram_key": key,
                        "diagram_type": lint.diagram_type,
                        "valid": lint.valid,
                        "auto_fixed": lint.auto_fixed,
                        "error_count": len(lint.errors),
                        "warning_count": len(lint.warnings),
                        "errors": lint.errors,
                        "warnings": lint.warnings,
                        "message": (
                            f"[Lint:{key}] "
                            f"{'x ' + str(len(lint.errors)) + ' error(s)' if lint.errors else 'ok'}"
                            f"{', ' + str(len(lint.warnings)) + ' warning(s)' if lint.warnings else ''}"
                            f"{' (auto-fixed)' if lint.auto_fixed else ''}"
                        ),
                    })
                # Apply auto-fixes to the inline mermaid map for Visual QA
                if lint.auto_fixed and lint.fixed_text:
                    mermaid_inline[key] = lint.fixed_text

            logger.info(
                "[MermaidLint] %d diagram(s) checked: %d with errors, %d with warnings",
                len(lint_results),
                sum(1 for r in lint_results.values() if r.errors),
                sum(1 for r in lint_results.values() if r.warnings),
            )

            # ── Stage 6: Traceability ─────────────────────────────────────────
            try:
                from mudtool.api.dependencies import get_trace_store
                trace_store = get_trace_store()
                trace_store.extract_and_store_traces(result)
            except Exception as exc:
                logger.warning("Traceability store write failed during /generate/stream: %s", exc, exc_info=True)
                result.warnings.append(f"Traceability persistence failed: {exc}")

            # ── Stage 7: Visual QA + Correction Loop ─────────────────────────
            generation_summary = _build_generation_summary(
                planned_count=planned_count,
                planned_items=planned_items,
                result=result,
                rendered_count=len(mermaid_inline),
                validation_report=validation_report,
                lint_results=lint_results,
            )

            if settings.visual_qa_enabled and pipeline_config is not None:
                from mudtool.ai.visual_qa import VisualCorrectionLoop, VisualQAAgent

                qa_agent = VisualQAAgent(settings)
                correction_loop = VisualCorrectionLoop(
                    settings=settings,
                    visual_qa_agent=qa_agent,
                    orchestrator=orchestrator,
                    mermaid_exporter=mermaid_exporter,
                )
                progress_callback({
                    "stage": "visual_qa_start",
                    "diagram_count": len(mermaid_inline),
                    "model": settings.visual_qa_model,
                    "max_rounds": settings.visual_qa_max_rounds,
                    "message": (
                        f"[VisualQA] Starting visual review of "
                        f"{len(mermaid_inline)} diagram(s) "
                        f"via {settings.visual_qa_model}..."
                    ),
                })
                result, visual_qa_summary = await correction_loop.run(
                    generation_result=result,
                    requirements=request.requirements.requirements,
                    pipeline_config=pipeline_config,
                    progress_callback=progress_callback,
                )
                logger.info(
                    "[VisualQA] Correction loop done: %d QA result(s)",
                    len(visual_qa_summary),
                )
            elif settings.visual_qa_enabled:
                # Single-pass mode: run QA-only (no correction — no pipeline config)
                from mudtool.ai.visual_qa import VisualQAAgent
                qa_agent = VisualQAAgent(settings)
                progress_callback({
                    "stage": "visual_qa_start",
                    "diagram_count": len(mermaid_inline),
                    "model": settings.visual_qa_model,
                    "max_rounds": 1,
                    "message": (
                        f"[VisualQA] Reviewing {len(mermaid_inline)} diagram(s) "
                        f"(QA-only in single-pass mode)..."
                    ),
                })
                qa_results = await qa_agent.run_visual_qa_pass(
                    mermaid_inline,
                    progress_callback=progress_callback,
                    round_num=1,
                )
                visual_qa_summary = [r.to_summary() for r in qa_results.values()]

            # ── Final event ───────────────────────────────────────────────────
            generation_summary = _build_generation_summary(
                planned_count=planned_count,
                planned_items=planned_items,
                result=result,
                rendered_count=len(mermaid_inline),
                validation_report=validation_report,
                lint_results=lint_results,
            )
            event = trace.attach_path({
                "_final": True,
                "result": result.model_dump(mode="json"),
                "validation_report": (
                    validation_report.model_dump(mode="json")
                    if validation_report else None
                ),
                "pipeline_summary": pipeline_summary,
                "generation_mode": generation_mode,
                "elaboration_info": elaboration_info,
                "precheck_summary": precheck_results,
                "visual_qa_summary": visual_qa_summary or [],
                "lint_summary": {k: v.to_summary() for k, v in lint_results.items()},
                "generation_summary": generation_summary,
            })
            trace.record_event("complete", event)
            queue.put_nowait(event)
        except Exception as exc:
            logger.error(f"SSE generation failed: {exc}", exc_info=True)
            event = trace.attach_path({"_error": True, "message": str(exc)})
            trace.record_event("error", event)
            queue.put_nowait(event)

    async def event_generator():
        """Yields SSE-formatted events from the queue."""
        # Start generation as a background task
        task = asyncio.create_task(run_generation())
        emitted_terminal_event = False

        try:
            while True:
                if task.done() and queue.empty() and not emitted_terminal_event:
                    detail = "Generation finished without emitting a final result."
                    try:
                        task_exc = task.exception()
                    except asyncio.CancelledError:
                        task_exc = None
                    if task_exc is not None:
                        logger.error(
                            "SSE generation task completed with exception after queue drained",
                            exc_info=(type(task_exc), task_exc, task_exc.__traceback__),
                        )
                        detail = str(task_exc)
                    else:
                        logger.error("SSE generation task completed without a terminal event")
                    yield (
                        f"event: error\n"
                        f"data: {_sse_json({'message': detail})}\n\n"
                    )
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120)
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
                    continue

                if event.get("_final"):
                    emitted_terminal_event = True
                    try:
                        payload = _sse_json(event)
                    except Exception as exc:
                        logger.error("Failed to serialize SSE complete event: %s", exc, exc_info=True)
                        yield (
                            f"event: error\n"
                            f"data: {_sse_json({'message': f'Failed to serialize final generation result: {exc}'})}\n\n"
                        )
                        break
                    yield (
                        f"event: complete\n"
                        f"data: {payload}\n\n"
                    )
                    break
                elif event.get("_error"):
                    emitted_terminal_event = True
                    yield (
                        f"event: error\n"
                        f"data: {_sse_json(event)}\n\n"
                    )
                    break
                else:
                    event_type = event.get("stage", "progress")
                    try:
                        payload = _sse_json(event)
                    except Exception as exc:
                        logger.error("Failed to serialize SSE progress event '%s': %s", event_type, exc, exc_info=True)
                        emitted_terminal_event = True
                        yield (
                            f"event: error\n"
                            f"data: {_sse_json({'message': f'Failed to serialize progress event {event_type}: {exc}'})}\n\n"
                        )
                        break
                    yield (
                        f"event: {event_type}\n"
                        f"data: {payload}\n\n"
                    )
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/validate", response_model=ValidationReport)
async def validate_model(request: ValidateRequest):
    """Run validation on an existing generation result."""
    from mudtool.api.dependencies import get_validator

    validator = get_validator()
    return validator.validate(request.result, request.requirement_ids)


@router.post("/export")
async def export_model(request: ExportRequest):
    """Export generated models.

    Supported formats: xmi, plantuml, mermaid, drawio
    """
    from mudtool.generator.drawio_exporter import DrawIOExporter
    from mudtool.generator.mermaid_exporter import MermaidExporter
    from mudtool.generator.plantuml_exporter import PlantUMLExporter
    from mudtool.generator.xmi_exporter import XMIExporter

    output_path = Path(request.output_path)

    if request.format == "xmi":
        exporter = XMIExporter()
        path = exporter.export_result(
            request.result, output_path / "model.xmi", request.model_name
        )
        return {"format": "xmi", "path": str(path)}

    elif request.format == "plantuml":
        exporter = PlantUMLExporter()
        paths = exporter.export_result(request.result, output_path)
        return {"format": "plantuml", "paths": [str(p) for p in paths]}

    elif request.format == "mermaid":
        exporter = MermaidExporter()
        paths = exporter.export_result(request.result, output_path)
        return {"format": "mermaid", "paths": [str(p) for p in paths]}

    elif request.format == "drawio":
        exporter = DrawIOExporter()
        paths = exporter.export_result(request.result, output_path)
        return {"format": "drawio", "paths": [str(p) for p in paths]}

    else:
        raise HTTPException(
            400,
            f"Unsupported export format: {request.format}. "
            "Use: xmi, plantuml, mermaid, or drawio"
        )


@router.post("/export/mermaid/inline")
async def export_mermaid_inline(request: MermaidInlineRequest):
    """Return Mermaid diagram text inline (no file I/O).

    Used by the Web UI to render diagrams live in the browser.
    Returns: {"diagrams": {"key": "mermaid_text", ...}}
    """
    from mudtool.generator.mermaid_exporter import MermaidExporter

    exporter = MermaidExporter()
    diagrams = exporter.export_result_inline(request.result, preview=True)
    return {"diagrams": diagrams}


@router.post("/export/drawio/inline")
async def export_drawio_inline(request: DrawIOInlineRequest):
    """Return draw.io XML inline (no file I/O)."""
    from mudtool.generator.drawio_exporter import DrawIOExporter

    exporter = DrawIOExporter()
    requested = set(request.diagram_keys or [])
    diagrams: dict[str, str] = {}
    for i, diagram in enumerate(request.result.diagrams):
        try:
            name = getattr(diagram, "name", "") or f"diagram_{i}"
            suffix = diagram.diagram_type.value
            key = f"{suffix}_{name}"
            if not requested or key in requested:
                diagrams[key] = exporter.export_diagram(diagram)
            for sub in getattr(diagram, "sub_diagrams", []) or []:
                sub_name = getattr(sub, "function_name", None) or getattr(sub, "name", None) or "sub"
                sub_key = f"{suffix}_{name}__fn__{sub_name}"
                if not requested or sub_key in requested:
                    diagrams[sub_key] = exporter.export_diagram(sub)
        except Exception as exc:
            logger.error("Failed to export diagram %s inline to draw.io: %s", i, exc)
    return {"diagrams": diagrams}


@router.post("/render/mermaid")
async def render_mermaid_svg(request: MermaidRenderRequest):
    """Render Mermaid text to SVG bytes for preview fallback."""
    from mudtool.api.dependencies import get_render_service

    mermaid_text = (request.diagram_source or request.mermaid_text or "").strip()
    if not mermaid_text:
        raise HTTPException(400, "mermaid_text must not be empty")

    try:
        svg_bytes = await get_render_service().render_mermaid_to_svg(mermaid_text)
    except Exception as exc:
        raise HTTPException(502, f"Failed to render Mermaid preview: {exc}") from exc

    return Response(content=svg_bytes, media_type="image/svg+xml")


@router.post("/render/drawio")
async def render_drawio_svg(request: DrawIORenderRequest):
    """Render draw.io XML to SVG bytes for preview."""
    from mudtool.api.dependencies import get_render_service

    drawio_xml = (request.diagram_source or "").strip()
    if not drawio_xml:
        raise HTTPException(400, "diagram_source must not be empty")

    try:
        svg_bytes = await get_render_service().render_drawio_to_svg(drawio_xml)
    except Exception as exc:
        raise HTTPException(502, f"Failed to render draw.io preview: {exc}") from exc

    return Response(content=svg_bytes, media_type="image/svg+xml")


class CSkeletonRequest(BaseModel):
    result: GenerationResult


@router.post("/export/c-skeleton")
async def export_c_skeleton(request: CSkeletonRequest):
    """Generate C-code skeleton files from ActivityDiagram JSON.

    Returns: {"files": {"diagram_name": "c_code_string", ...}}
    Only processes ActivityDiagram instances (other diagram types are skipped).
    """
    from mudtool.generator.c_skeleton_exporter import CSkeletonExporter

    exporter = CSkeletonExporter()
    files = exporter.export_result(request.result)

    if not files:
        raise HTTPException(
            400,
            "No ActivityDiagram found in the generation result. "
            "C skeleton export only works with activity/flow diagrams."
        )

    return {"files": files}


@router.post("/render")
async def render_diagrams(request: RenderRequest):
    """Render diagrams to SVG or PNG image files via Kroki.io.

    Requires internet access to https://kroki.io (or a local plantuml.jar).
    """
    from mudtool.generator.render_service import RenderService
    from mudtool.api.dependencies import get_render_service

    service = get_render_service()
    output_path = Path(request.output_path)

    if request.format not in ("svg", "png"):
        raise HTTPException(400, "format must be 'svg' or 'png'")

    try:
        paths = await service.render_all(request.result, output_path, request.format)
        return {"format": request.format, "paths": [str(p) for p in paths]}
    except Exception as e:
        raise HTTPException(500, f"Render failed: {e}")


@router.get("/traceability", response_model=TraceabilityResponse)
async def get_traceability(requirement_ids: Optional[str] = None):
    """Get the full traceability matrix and coverage report."""
    from mudtool.api.dependencies import get_trace_store

    store = get_trace_store()
    matrix = store.get_traceability_matrix()

    coverage = None
    if requirement_ids:
        ids = [r.strip() for r in requirement_ids.split(",")]
        coverage = store.get_coverage_report(ids)

    return TraceabilityResponse(matrix=matrix, coverage=coverage)


@router.get("/traceability/requirement/{req_id}")
async def get_traces_for_requirement(req_id: str):
    """Get all model elements traced to a specific requirement."""
    from mudtool.api.dependencies import get_trace_store

    store = get_trace_store()
    links = store.get_traces_for_requirement(req_id)
    return {"requirement_id": req_id, "traces": [l.model_dump() for l in links]}


@router.post("/traceability/accept")
async def accept_element(request: AcceptElementRequest):
    """Mark a model element as accepted by human reviewer."""
    from mudtool.api.dependencies import get_trace_store

    store = get_trace_store()
    count = store.accept_element(request.element_id, request.accepted_by)
    return {"element_id": request.element_id, "links_updated": count}


@router.get("/config")
async def get_config():
    """Get current configuration (non-sensitive fields only)."""
    settings = get_settings()

    # Per-stage model overrides — surfaced to the UI as a "Pipeline AI Map"
    # so users see exactly which model runs at each stage and can change one
    # stage without disturbing the global backend.
    default_model = (
        settings.anthropic_model if settings.cloud_provider.value == "anthropic"
        else (settings.deepseek_model if settings.cloud_provider.value == "deepseek"
              else settings.openai_model)
    )

    def _stage(label: str, override: str | None, env_var: str, desc: str) -> dict:
        return {
            "stage_label": label,
            "model": override or default_model,
            "uses_default": not override,
            "env_var": env_var,
            "description": desc,
        }

    pipeline_stages = {
        "mud_spec_skeleton": _stage(
            "MUD Spec — Skeleton (Stage 1)",
            settings.mud_spec_skeleton_model,
            "MUD_SPEC_SKELETON_MODEL",
            "Extracts runnable list + per-runnable key steps from requirements.",
        ),
        "mud_spec_generator": _stage(
            "MUD Spec — Generator (Stage 3)",
            settings.pipeline_generator_model,
            "MUD_PIPELINE_GENERATOR_MODEL",
            "Fills runnable details: signature, pseudo-code, traceability.",
        ),
        "activity_skeleton": _stage(
            "Activity — Skeleton (Stage 1)",
            settings.activity_pipeline_skeleton_model,
            "MUD_ACTIVITY_PIPELINE_SKELETON_MODEL",
            "Extracts runnable list + IRV/DEM cross-references for flowcharts.",
        ),
        "activity_generator": _stage(
            "Activity — Per-Runnable (Stage 3)",
            settings.pipeline_generator_model,
            "MUD_PIPELINE_GENERATOR_MODEL",
            "Generates one activity diagram per runnable with pseudo-code labels.",
        ),
        "activity_reviewer": _stage(
            "Activity — Reviewer (Stage 4)",
            settings.activity_pipeline_reviewer_model,
            "MUD_ACTIVITY_PIPELINE_REVIEWER_MODEL",
            "Reviews drafted diagrams; emits structural patches.",
        ),
    }

    return {
        "ai_backend": settings.ai_backend.value,
        "cloud_provider": settings.cloud_provider.value,
        "anthropic_model": settings.anthropic_model,
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "deepseek_base_url": settings.deepseek_base_url,
        "deepseek_model": settings.deepseek_model,
        "local_model_path": settings.local_model_path,
        "confidence_threshold": settings.confidence_threshold,
        "max_retries": settings.max_retries,
        "swc_naming_regex": settings.swc_naming_regex,
        "runnable_naming_regex": settings.runnable_naming_regex,
        "port_naming_regex": settings.port_naming_regex,
        "validation_strict_mode": settings.validation_strict_mode,
        "use_kroki": settings.use_kroki,
        "kroki_base_url": settings.kroki_base_url,
        "mud_spec_pipeline": settings.mud_spec_pipeline,
        "pipeline_stages": pipeline_stages,
    }


class ConfigUpdateRequest(BaseModel):
    """Runtime AI backend configuration update.

    Changes are written to .env and take effect immediately (no restart).
    """
    # Which backend type to activate
    backend_type: str = Field(
        ...,
        description=(
            "anthropic | ollama | localai | lmstudio | openai | "
            "openai_compatible | local_llamacpp"
        ),
    )
    # Shared optional fields
    api_key: Optional[str] = Field(None, description="API key (leave empty for local backends)")
    model: Optional[str] = Field(None, description="Model name to use")
    base_url: Optional[str] = Field(None, description="Server base URL (for local/compatible backends)")
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_retries: Optional[int] = Field(None, ge=1, le=20)


@router.post("/config/update")
async def update_config(request: ConfigUpdateRequest):
    """Update AI backend configuration at runtime.

    Writes changes to the .env file and reinitialises the AI orchestrator
    immediately — no server restart required.

    Supported backend_type values:
    - anthropic       → Claude API (requires api_key)
    - ollama          → Ollama local server (default: localhost:11434)
    - localai         → LocalAI Docker server (default: localhost:8080)
    - lmstudio        → LM Studio (default: localhost:1234)
    - openai          → OpenAI API (requires api_key)
    - openai_compatible → Any custom OpenAI-compatible endpoint
    - local_llamacpp  → Built-in llama.cpp (model path via base_url field)
    """
    from mudtool.api.dependencies import reset_orchestrator

    # Build the env var updates for this backend type
    preset_urls = {
        "ollama": "http://localhost:11434/v1",
        "localai": "http://localhost:8080/v1",
        "lmstudio": "http://localhost:1234/v1",
        "openai": "https://api.openai.com/v1",
    }

    updates: dict[str, str] = {}

    bt = request.backend_type.lower()

    if bt == "anthropic":
        updates["MUD_AI_BACKEND"] = "cloud"
        updates["MUD_CLOUD_PROVIDER"] = "anthropic"
        if request.api_key:
            updates["MUD_ANTHROPIC_API_KEY"] = request.api_key
        if request.model:
            updates["MUD_ANTHROPIC_MODEL"] = request.model

    elif bt == "deepseek":
        updates["MUD_AI_BACKEND"] = "cloud"
        updates["MUD_CLOUD_PROVIDER"] = "deepseek"
        if request.api_key:
            updates["MUD_DEEPSEEK_API_KEY"] = request.api_key
        if request.model:
            updates["MUD_DEEPSEEK_MODEL"] = request.model
        if request.base_url:
            updates["MUD_DEEPSEEK_BASE_URL"] = request.base_url

    elif bt in ("ollama", "localai", "lmstudio", "openai", "openai_compatible"):
        updates["MUD_AI_BACKEND"] = "cloud"
        updates["MUD_CLOUD_PROVIDER"] = "openai_compatible"
        url = request.base_url or preset_urls.get(bt, "")
        if url:
            updates["MUD_OPENAI_BASE_URL"] = url
        if request.api_key:
            updates["MUD_OPENAI_API_KEY"] = request.api_key
        else:
            # Local backends don't need a real key
            updates["MUD_OPENAI_API_KEY"] = bt
        if request.model:
            updates["MUD_OPENAI_MODEL"] = request.model
        if bt in ("ollama", "localai", "lmstudio"):
            # Local OpenAI-compatible backends use provider-local model names.
            # Keep stage overrides aligned even when the UI switches backend
            # without sending a model value; otherwise stale hosted aliases such
            # as deepseek-reasoner can survive and break the next run.
            local_stage_model = request.model or get_settings().openai_model
            if local_stage_model:
                updates["MUD_PIPELINE_GENERATOR_MODEL"] = local_stage_model
                updates["MUD_PIPELINE_REVIEWER_MODEL"] = local_stage_model
            updates["MUD_SPEC_SKELETON_MODEL"] = ""
            updates["MUD_ACTIVITY_PIPELINE_SKELETON_MODEL"] = ""
            updates["MUD_ACTIVITY_PIPELINE_REVIEWER_MODEL"] = ""

    elif bt == "local_llamacpp":
        updates["MUD_AI_BACKEND"] = "local"
        if request.base_url:  # We reuse base_url for model path in this case
            updates["MUD_LOCAL_MODEL_PATH"] = request.base_url
        elif request.model:
            updates["MUD_LOCAL_MODEL_PATH"] = request.model

    else:
        raise HTTPException(
            400,
            f"Unknown backend_type: {bt}. Use: anthropic, deepseek, ollama, localai, "
            "lmstudio, openai, openai_compatible, local_llamacpp"
        )

    # Optional tuning params
    if request.confidence_threshold is not None:
        updates["MUD_CONFIDENCE_THRESHOLD"] = str(request.confidence_threshold)
    if request.max_retries is not None:
        updates["MUD_MAX_RETRIES"] = str(request.max_retries)

    # Write to .env file
    _write_env_updates(updates)

    # Reload settings and reset AI orchestrator
    get_settings.cache_clear()
    reset_orchestrator()

    new_settings = get_settings()
    return {
        "success": True,
        "message": f"Backend switched to '{bt}' and AI orchestrator reloaded.",
        "active_backend": new_settings.ai_backend.value,
        "cloud_provider": new_settings.cloud_provider.value,
        "openai_base_url": new_settings.openai_base_url,
        "openai_model": new_settings.openai_model,
        "anthropic_model": new_settings.anthropic_model,
        "confidence_threshold": new_settings.confidence_threshold,
    }


# ── Per-stage model overrides (Pipeline AI Map) ───────────────────────────────

_STAGE_TO_ENV: dict[str, str] = {
    "mud_spec_skeleton":   "MUD_SPEC_SKELETON_MODEL",
    "mud_spec_generator":  "MUD_PIPELINE_GENERATOR_MODEL",
    "activity_skeleton":   "MUD_ACTIVITY_PIPELINE_SKELETON_MODEL",
    "activity_generator":  "MUD_PIPELINE_GENERATOR_MODEL",
    "activity_reviewer":   "MUD_ACTIVITY_PIPELINE_REVIEWER_MODEL",
}


class StageModelUpdateRequest(BaseModel):
    """Override which model a single pipeline stage uses.

    Passing model=null reverts the stage to the global generator default.
    """
    stage_key: str
    model: Optional[str] = None


@router.post("/config/stage")
async def update_stage_model(request: StageModelUpdateRequest):
    """Set or clear a per-stage model override.

    Writes to .env (key = `_STAGE_TO_ENV[stage_key]`) and resets the
    orchestrator so the new model is picked up on the next generation.
    """
    env_key = _STAGE_TO_ENV.get(request.stage_key)
    if not env_key:
        raise HTTPException(
            400,
            f"Unknown stage_key: {request.stage_key}. "
            f"Valid: {sorted(_STAGE_TO_ENV.keys())}",
        )

    if request.model and request.model.strip() and request.model.lower() != "(default)":
        _write_env_updates({env_key: request.model.strip()})
    else:
        _remove_env_keys({env_key})

    get_settings.cache_clear()
    reset_orchestrator()

    return {
        "ok": True,
        "stage_key": request.stage_key,
        "model": request.model or "(default)",
        "env_var": env_key,
    }


@router.get("/config/available-models")
async def list_available_models():
    """Return models the current backend can use, for the UI dropdowns.

    For local Ollama, queries `/api/tags`. For Anthropic/DeepSeek/OpenAI,
    returns a curated hardcoded list (their APIs don't expose a stable
    /models endpoint in all versions).
    """
    import httpx
    settings = get_settings()
    provider = settings.cloud_provider.value

    if provider == "anthropic":
        return {
            "provider": "anthropic",
            "models": [
                "claude-sonnet-4-5-20250514",
                "claude-opus-4-20250514",
                "claude-haiku-4-20250514",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
            ],
        }

    if provider == "deepseek":
        return {
            "provider": "deepseek",
            "models": ["deepseek-chat", "deepseek-reasoner"],
        }

    # OpenAI-compatible: try /api/tags (Ollama) first, then /models
    base = settings.openai_base_url or "https://api.openai.com/v1"
    api_key = settings.openai_api_key or ""

    # Ollama variant — /api/tags lives at the root, not under /v1
    if any(h in base for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1")):
        ollama_root = base.rstrip("/").removesuffix("/v1")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{ollama_root}/api/tags")
                if r.status_code == 200:
                    data = r.json()
                    names = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    return {"provider": "ollama", "models": sorted(set(names))}
        except Exception as exc:
            logger.debug("ollama /api/tags failed: %s", exc)

    # Fallback: /models on the OpenAI-compatible endpoint
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{base.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            )
            if r.status_code == 200:
                data = r.json()
                items = data.get("data", []) if isinstance(data, dict) else []
                names = [item.get("id") for item in items if isinstance(item, dict) and item.get("id")]
                if names:
                    return {"provider": "openai_compatible", "models": sorted(set(names))}
    except Exception as exc:
        logger.debug("openai-compatible /models failed: %s", exc)

    # Last resort: just the currently-configured model
    return {
        "provider": provider,
        "models": [settings.openai_model] if settings.openai_model else [],
    }


@router.post("/config/test")
async def test_connection():
    """Test if the current AI backend is reachable and responding.

    Returns: {"ok": true/false, "backend": "...", "latency_ms": ..., "error": "..."}
    """
    from mudtool.api.dependencies import get_orchestrator
    import time

    orchestrator = get_orchestrator()
    start = time.monotonic()
    try:
        result = await orchestrator.health_check()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        any_ok = any(result.get("backends", {}).values())
        return {
            "ok": any_ok,
            "backends": result.get("backends", {}),
            "latency_ms": elapsed_ms,
            "error": None if any_ok else "No backends responded successfully",
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {"ok": False, "backends": {}, "latency_ms": elapsed_ms, "error": str(e)}


@router.get("/guidelines/status")
async def get_guidelines_status():
    """Return status of the guidelines directory and cache.

    Returns doc count, chunk count, filenames, embedding mode, and directory paths.
    """
    from mudtool.ai.guidelines_reader import GuidelinesReader
    settings: Settings = get_settings()
    reader = GuidelinesReader(settings)
    return reader.get_status()


@router.post("/guidelines/clear-cache")
async def clear_guidelines_cache():
    """Delete all cached guideline chunk/embedding JSON files.

    Forces full re-parse and re-embed on the next generation run.
    """
    from mudtool.ai.guidelines_reader import GuidelinesReader
    settings: Settings = get_settings()
    reader = GuidelinesReader(settings)
    deleted = reader.clear_cache()
    return {
        "deleted_count": deleted,
        "message": f"Cleared {deleted} cached guideline file(s)",
    }


@router.post("/prompts/reload")
async def reload_prompts():
    """Reload all prompt YAML templates from disk without restarting the server.

    Call this after editing any file under prompts/ to pick up changes immediately.
    Returns the list of template keys that were loaded.
    """
    from mudtool.api.dependencies import get_orchestrator
    orchestrator = get_orchestrator()
    orchestrator.prompt_engine.load_templates()
    keys = list(orchestrator.prompt_engine._templates.keys())
    return {
        "reloaded": len(keys),
        "templates": keys,
        "message": f"Reloaded {len(keys)} prompt template(s) from disk",
    }


# ══════════════════════════════════════════════════════════════════════════════
# MODULE PLANNING & MUD SPEC ENDPOINTS  (Enhanced Workflow — Stage 1 & 2)
# ══════════════════════════════════════════════════════════════════════════════

class PlanModulesRequest(BaseModel):
    """Request body for POST /modules/plan."""
    requirements_text: str = Field(
        ...,
        description="Full raw requirements text (any format, all SWCs).",
    )
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class MudSpecRequest(BaseModel):
    """Request body for POST /modules/mud-spec (SSE stream)."""
    swc_name: str
    description: str = ""
    asil: str = "QM"
    runnables: list[str] = []
    req_ids: list[str] = []
    requirements_text: str = Field(
        ...,
        description="Full raw requirements text used as architectural context.",
    )
    temperature: float = Field(0.25, ge=0.0, le=1.0)
    spec_pipeline: str = Field(
        "two_stage",
        description=(
            "MUD spec generation pipeline mode: "
            "'single_pass' (fast, one call) or "
            "'two_stage' (skeleton + per-runnable Section 7 + validation)"
        ),
    )


class ReviewSpecRequest(BaseModel):
    """Request body for POST /modules/review."""
    swc_name: str
    asil: str = "QM"
    req_ids: list[str] = []
    requirements_text: str
    mud_spec_markdown: str
    temperature: float = Field(0.1, ge=0.0, le=1.0)
    iteration: int = Field(1, ge=1, description="Generation iteration number (1 = first draft)")


@router.post("/modules/plan")
async def plan_modules(request: PlanModulesRequest):
    """Stage 1 — Analyse architectural requirements and return module decomposition.

    Uses AI to detect all SWCs, their runnables, ASIL levels, and linked
    requirement IDs.  The UI displays these as module cards for the user to
    select from.

    Returns:
        {
          "modules": [...],
          "architecture_summary": "...",
          "module_count": 4
        }
    """
    from mudtool.api.dependencies import get_orchestrator
    from mudtool.ai.module_planner import ModulePlanner

    orchestrator = get_orchestrator()
    planner = ModulePlanner(orchestrator)

    plan = await planner.plan_modules(
        requirements_text=request.requirements_text,
        temperature=request.temperature,
    )

    return {
        "modules": [m.to_dict() for m in plan.modules],
        "architecture_summary": plan.architecture_summary,
        "module_count": len(plan.modules),
    }


@router.post("/modules/mud-spec")
async def generate_mud_spec_stream(request: MudSpecRequest):
    """Stage 2 — Generate a detailed MUD spec Markdown for ONE selected SWC.

    Streams progress events via Server-Sent Events (SSE).
    Final event carries the full Markdown in ``data.mud_spec_markdown``.

    Event types:
        ``mud_spec``    — progress updates
        ``complete``    — final event with full spec
        ``error``       — generation failed
    """
    logger.info(
        "mud-spec request received for %s (asil=%s, %d req_ids, pipeline=%s)",
        request.swc_name, request.asil, len(request.req_ids), request.spec_pipeline,
    )
    import asyncio as _asyncio
    from mudtool.api.dependencies import get_orchestrator
    from mudtool.ai.mud_spec_generator import MudSpecGenerator

    orchestrator = get_orchestrator()
    generator = MudSpecGenerator(orchestrator)
    settings: Settings = get_settings()
    trace = RunDebugTrace(
        settings,
        "mud_spec_generate",
        {
            "swc_name": request.swc_name,
            "asil": request.asil,
            "requirement_count": len(request.req_ids),
            "requirement_ids": request.req_ids,
            "spec_pipeline": request.spec_pipeline,
            "runnables": request.runnables,
        },
    )

    # Override MUD_SPEC_PIPELINE setting with per-request value (if provided)
    # by temporarily patching settings — the generator reads it at call time.
    _pipeline_override = request.spec_pipeline  # "single_pass" | "two_stage"

    queue: asyncio.Queue = asyncio.Queue()

    def _progress(event: dict) -> None:
        trace.record_event("progress", event)
        queue.put_nowait(event)

    async def _run():
        try:
            spec_md = await generator.generate_spec(
                swc_name=request.swc_name,
                description=request.description,
                asil=request.asil,
                runnables=request.runnables,
                req_ids=request.req_ids,
                requirements_text=request.requirements_text,
                temperature=request.temperature,
                progress_callback=_progress,
                pipeline_mode=_pipeline_override,
            )
            event = trace.attach_path({
                "_final": True,
                "mud_spec_markdown": spec_md,
                "swc_name": request.swc_name,
                "char_count": len(spec_md),
                "section7_normalization": generator.last_normalization_result.to_dict(),
            })
            trace.record_event("complete", event)
            queue.put_nowait(event)
        except Exception as exc:
            logger.exception("mud_spec generation failed for %s", request.swc_name)
            event = trace.attach_path({"_error": True, "detail": str(exc)})
            trace.record_event("error", event)
            queue.put_nowait(event)

    async def event_generator():
        task = asyncio.create_task(_run())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event.get("_final"):
                    yield (
                        f"event: complete\n"
                        f"data: {_sse_json(event)}\n\n"
                    )
                    break
                elif event.get("_error"):
                    yield (
                        f"event: error\n"
                        f"data: {_sse_json(event)}\n\n"
                    )
                    break
                else:
                    yield (
                        f"event: mud_spec\n"
                        f"data: {_sse_json(event)}\n\n"
                    )
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class RegenerateSpecRequest(BaseModel):
    """Request body for POST /modules/mud-spec/regenerate (SSE stream)."""
    swc_name: str
    asil: str = "QM"
    req_ids: list[str] = []
    requirements_text: str
    current_spec_markdown: str = Field(..., description="MUD spec from the previous iteration")
    review: dict = Field(..., description="SpecReviewResult.to_dict() from the review pass")
    temperature: float = Field(0.0, ge=0.0, le=1.0)


@router.post("/modules/mud-spec/regenerate")
async def regenerate_mud_spec_stream(request: RegenerateSpecRequest):
    """Stage 2c — Regenerate an improved MUD spec by fixing all review issues.

    Streams progress events via SSE.  The review report (all errors + warnings +
    suggestions) is fed back to the AI so it can produce an improved version.

    Event types:
        ``mud_regen``   — progress updates with current iteration number
        ``complete``    — final event: improved spec + new iteration number
        ``error``       — regeneration failed
    """
    logger.info("mud-spec regenerate request for %s (iter=%s)", request.swc_name, request.review.get("iteration"))
    
    from mudtool.api.dependencies import get_orchestrator
    from mudtool.ai.mud_spec_generator import (
        MudSpecGenerator, SpecReviewResult, compare_review_results, build_unresolved_review,
    )

    orchestrator = get_orchestrator()
    generator = MudSpecGenerator(orchestrator)
    settings: Settings = get_settings()

    # Reconstruct review object from the dict sent by the client
    review = SpecReviewResult.from_dict(
        request.review,
        iteration=request.review.get("iteration", 1),
    )
    trace = RunDebugTrace(
        settings,
        "mud_spec_regenerate",
        {
            "swc_name": request.swc_name,
            "asil": request.asil,
            "review_iteration": review.iteration,
            "requirement_count": len(request.req_ids),
            "requirement_ids": request.req_ids,
            "incoming_issue_count": review.error_count + review.warning_count + len(review.uncovered_req_ids),
        },
    )

    queue: asyncio.Queue = asyncio.Queue()

    def _progress(event: dict) -> None:
        trace.record_event("progress", event)
        queue.put_nowait(event)

    async def _run():
        try:
            regen_temperature = min(request.temperature, 0.1)
            improved_md = await generator.regenerate_spec(
                swc_name=request.swc_name,
                asil=request.asil,
                requirements_text=request.requirements_text,
                current_spec_markdown=request.current_spec_markdown,
                review=review,
                temperature=regen_temperature,
                progress_callback=_progress,
            )

            event = {
                "stage": "mud_regen_verify",
                "message": "Verifying regenerated MUD spec against reviewer comments...",
                "progress": 96,
                "iteration": review.iteration + 1,
            }
            trace.record_event("progress", event)
            queue.put_nowait(event)
            post_review = await generator.review_spec(
                swc_name=request.swc_name,
                asil=request.asil,
                req_ids=request.req_ids,
                requirements_text=request.requirements_text,
                mud_spec_markdown=improved_md,
                temperature=0.0,
                iteration=review.iteration + 1,
            )
            comparison = compare_review_results(review, post_review)
            retry_count = 0

            if comparison["repeated_issue_count"] > 0:
                retry_count = 1
                # Build a filtered review containing ONLY the unresolved issues so
                # the repair attempt focuses exclusively on the stuck items rather
                # than re-processing everything (which dilutes AI attention and may
                # re-break freshly fixed sections).
                unresolved_review = build_unresolved_review(comparison, post_review)
                event = {
                    "stage": "mud_regen_retry",
                    "message": (
                        f"{comparison['repeated_issue_count']} repeated issue(s) remain; "
                        "running targeted repair retry..."
                    ),
                    "progress": 97,
                    "iteration": review.iteration + 2,
                    "remaining_issue_count": comparison["repeated_issue_count"],
                }
                trace.record_event("progress", event)
                queue.put_nowait(event)
                improved_md = await generator.regenerate_spec(
                    swc_name=request.swc_name,
                    asil=request.asil,
                    requirements_text=request.requirements_text,
                    current_spec_markdown=improved_md,
                    review=unresolved_review,   # only the stuck issues
                    temperature=0.15,           # break deterministic cycle
                    progress_callback=_progress,
                    repair_attempt=True,        # escalation header in system prompt
                )
                event = {
                    "stage": "mud_regen_verify",
                    "message": "Verifying retry result...",
                    "progress": 98,
                    "iteration": review.iteration + 2,
                }
                trace.record_event("progress", event)
                queue.put_nowait(event)
                post_review = await generator.review_spec(
                    swc_name=request.swc_name,
                    asil=request.asil,
                    req_ids=request.req_ids,
                    requirements_text=request.requirements_text,
                    mud_spec_markdown=improved_md,
                    temperature=0.0,
                    iteration=review.iteration + 2,
                )
                comparison = compare_review_results(review, post_review)

            remaining_issue_count = post_review.error_count + post_review.warning_count + len(post_review.uncovered_req_ids)
            quality_status = "pass" if post_review.approved and post_review.warning_count == 0 else "needs_fix"
            event = trace.attach_path({
                "_final": True,
                "mud_spec_markdown": improved_md,
                "swc_name": request.swc_name,
                "iteration": review.iteration + 1 + retry_count,
                "char_count": len(improved_md),
                "section7_normalization": generator.last_normalization_result.to_dict(),
                "post_review": post_review.to_dict(),
                "remaining_issue_count": remaining_issue_count,
                "resolved_issue_count": comparison["resolved_issue_count"],
                "retry_count": retry_count,
                "quality_status": quality_status,
                "repeated_issue_count": comparison["repeated_issue_count"],
                "repair_mode": getattr(generator, "last_patch_meta", {}).get("mode", "ai_editor"),
                "patch_meta": getattr(generator, "last_patch_meta", {}),
            })
            trace.record_event("complete", event)
            queue.put_nowait(event)
        except Exception as exc:
            logger.exception("mud_spec regeneration failed for %s", request.swc_name)
            event = trace.attach_path({"_error": True, "detail": str(exc)})
            trace.record_event("error", event)
            queue.put_nowait(event)

    async def event_generator():
        task = asyncio.create_task(_run())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event.get("_final"):
                    yield (
                        f"event: complete\n"
                        f"data: {_sse_json(event)}\n\n"
                    )
                    break
                elif event.get("_error"):
                    yield (
                        f"event: error\n"
                        f"data: {_sse_json(event)}\n\n"
                    )
                    break
                else:
                    yield (
                        f"event: mud_regen\n"
                        f"data: {_sse_json(event)}\n\n"
                    )
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/modules/review")
async def review_mud_spec(request: ReviewSpecRequest):
    """Stage 2b — Run an AI reviewer pass on a generated MUD spec.

    Checks completeness, naming conventions, safety requirements, and
    IRV/CalPrm coverage.

    Returns:
        {
          "approved": true,
          "coverage_pct": 87,
          "issues": [...],
          "suggestions": [...]
        }
    """
    from mudtool.api.dependencies import get_orchestrator
    from mudtool.ai.mud_spec_generator import MudSpecGenerator

    orchestrator = get_orchestrator()
    generator = MudSpecGenerator(orchestrator)
    settings: Settings = get_settings()
    trace = RunDebugTrace(
        settings,
        "mud_spec_review",
        {
            "swc_name": request.swc_name,
            "asil": request.asil,
            "iteration": request.iteration,
            "requirement_count": len(request.req_ids),
            "requirement_ids": request.req_ids,
            "spec_length": len(request.mud_spec_markdown or ""),
        },
    )

    try:
        review = await generator.review_spec(
            swc_name=request.swc_name,
            asil=request.asil,
            req_ids=request.req_ids,
            requirements_text=request.requirements_text,
            mud_spec_markdown=request.mud_spec_markdown,
            temperature=request.temperature,
            iteration=request.iteration,
        )
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        body = getattr(getattr(exc, "response", None), "text", "")
        trace.record(
            "error",
            message=str(exc),
            provider_status=status,
            provider_body_preview=(body[:500] if body else ""),
        )
        if status:
            detail = f"AI review provider rejected the request ({status})"
            if body:
                detail += f": {body[:500]}"
            raise HTTPException(502, detail) from exc
        raise

    response = review.to_dict()
    trace.attach_path(response)
    trace.record(
        "complete",
        approved=review.approved,
        coverage_pct=review.coverage_pct,
        error_count=review.error_count,
        warning_count=review.warning_count,
        uncovered_req_ids=review.uncovered_req_ids,
    )
    return response


# ── Private helpers ───────────────────────────────────────────────────────────

def _write_env_updates(updates: dict[str, str]) -> None:
    """Write key=value pairs into the .env file (updating existing keys in-place)."""
    import os
    # Find .env relative to cwd (where the server was launched from)
    env_path = Path(".env")
    if not env_path.exists():
        # Fallback: look next to settings.py
        env_path = Path(__file__).parent.parent.parent.parent / ".env"

    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Uncommented key=value line
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
                continue
        # Commented-out version of a key we want to set — keep as comment
        if stripped.startswith("#") and "=" in stripped:
            commented_key = stripped.lstrip("#").split("=", 1)[0].strip()
            if commented_key in updates and commented_key not in updated_keys:
                # Replace the comment with the live value on the next write pass
                pass
        new_lines.append(line)

    # Append any keys that weren't already in the file
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _remove_env_keys(keys: set[str]) -> None:
    """Delete the given keys from the .env file (so they fall back to defaults)."""
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in keys:
                continue   # drop this line — falls back to settings default
        new_lines.append(line)
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
