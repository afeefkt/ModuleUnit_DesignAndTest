"""FastAPI route definitions for the MUD Tool sidecar API.

These routes are called by the Modelio Java plugin (or any HTTP client)
to drive the requirement import, AI generation, and validation pipeline.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from mudtool.config.settings import Settings, get_settings
from mudtool.models.json_uml import DiagramType, GenerationResult
from mudtool.models.requirements import RequirementSet
from mudtool.models.validation import ValidationReport

logger = logging.getLogger(__name__)

router = APIRouter()


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


class GenerateResponse(BaseModel):
    result: GenerationResult
    validation_report: Optional[ValidationReport] = None
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

    req_ids = [r.req_id for r in request.requirements.requirements]

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

    if effective_mode == PipelineMode.SINGLE_PASS:
        # ── Legacy path: unchanged behavior ────────────────────────────────
        result = await orchestrator.generate_all_diagrams(
            requirements=request.requirements.requirements,
            diagram_types=diagram_types,
            module_context=request.module_context,
        )
    else:
        # ── Multi-stage pipeline path ───────────────────────────────────────
        # two_model_fast uses llama3.2 as reviewer; two_model uses mistral
        reviewer = (
            "llama3.2"
            if effective_mode == PipelineMode.TWO_MODEL_FAST
            else settings.pipeline_reviewer_model
        )
        config = PipelineConfig(
            mode=effective_mode,
            generator_model=settings.pipeline_generator_model,
            reviewer_model=reviewer,
            max_passes=request.pipeline_max_passes or settings.pipeline_max_passes,
            min_confidence=settings.pipeline_confidence_threshold,
            draft_temperature=request.temperature,
        )
        logger.info(
            f"Pipeline mode={effective_mode.value}, "
            f"generator={config.generator_model}, reviewer={config.reviewer_model}, "
            f"max_passes={config.max_passes}"
        )
        pipeline_orch = PipelineOrchestrator(settings, orchestrator)
        pipeline_results = await pipeline_orch.generate_with_pipeline(
            requirements=request.requirements.requirements,
            diagram_types=diagram_types,
            config=config,
            module_context=request.module_context,
            existing_swcs=request.existing_swcs,
        )
        result, pipeline_summary = merge_pipeline_results(pipeline_results, req_ids)

    # AUTOSAR mapping (unchanged)
    if request.apply_autosar_mapping:
        result = mapper.map_generation_result(result)

    # Validate (unchanged)
    validation_report = validator.validate(result, requirement_ids=req_ids)

    # Store trace links (unchanged)
    from mudtool.api.dependencies import get_trace_store
    trace_store = get_trace_store()
    trace_store.extract_and_store_traces(result)

    return GenerateResponse(
        result=result,
        validation_report=validation_report,
        pipeline_summary=pipeline_summary,
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
    diagrams = exporter.export_result_inline(request.result)
    return {"diagrams": diagrams}


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
    return {
        "ai_backend": settings.ai_backend.value,
        "cloud_provider": settings.cloud_provider.value,
        "anthropic_model": settings.anthropic_model,
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "local_model_path": settings.local_model_path,
        "confidence_threshold": settings.confidence_threshold,
        "max_retries": settings.max_retries,
        "swc_naming_regex": settings.swc_naming_regex,
        "runnable_naming_regex": settings.runnable_naming_regex,
        "port_naming_regex": settings.port_naming_regex,
        "validation_strict_mode": settings.validation_strict_mode,
        "use_kroki": settings.use_kroki,
        "kroki_base_url": settings.kroki_base_url,
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

    elif bt == "local_llamacpp":
        updates["MUD_AI_BACKEND"] = "local"
        if request.base_url:  # We reuse base_url for model path in this case
            updates["MUD_LOCAL_MODEL_PATH"] = request.base_url
        elif request.model:
            updates["MUD_LOCAL_MODEL_PATH"] = request.model

    else:
        raise HTTPException(
            400,
            f"Unknown backend_type: {bt}. Use: anthropic, ollama, localai, "
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
