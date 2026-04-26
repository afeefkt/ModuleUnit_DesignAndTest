"""AI Orchestrator - routes requests to local or cloud backend.

Manages prompt rendering, response parsing, retry logic, confidence scoring,
and fallback strategies. The rest of the system is agnostic to which
inference mode is active.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from mudtool.ai.base_backend import AIResponse, BaseAIBackend
from mudtool.ai.cloud_backend import CloudBackend
from mudtool.ai.local_backend import LocalBackend
from mudtool.ai.prompt_engine import PromptEngine
from mudtool.config.settings import AIBackend, Settings
from mudtool.validation.structural_validator import StructuralValidator
from mudtool.validation.autosar_validator import AUTOSARValidator
from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityNodeType,
    ClassDiagram,
    ComponentDiagram,
    DiagramType,
    GenerationResult,
    Provenance,
    SequenceDiagram,
    StateMachineDiagram,
)
from mudtool.models.requirements import Requirement

logger = logging.getLogger(__name__)

# Map diagram types to their Pydantic model
_DIAGRAM_MODELS = {
    DiagramType.SEQUENCE: SequenceDiagram,
    DiagramType.STATE_MACHINE: StateMachineDiagram,
    DiagramType.CLASS: ClassDiagram,
    DiagramType.COMPONENT: ComponentDiagram,
    DiagramType.ACTIVITY: ActivityDiagram,
}


class AIOrchestrator:
    """Central AI orchestration engine.

    Responsibilities:
    - Backend selection (local/cloud/auto)
    - Prompt rendering via PromptEngine
    - Response parsing and validation
    - Retry logic with configurable max retries
    - Confidence scoring and threshold enforcement
    - Fallback to partial generation on failures
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.prompt_engine = PromptEngine(settings)
        self._cloud_backend: Optional[CloudBackend] = None
        self._local_backend: Optional[LocalBackend] = None

        # Compiled naming patterns for computed confidence scoring
        self._swc_pattern = re.compile(settings.swc_naming_regex)

        # Initialize backends based on settings
        self._cloud_backend = CloudBackend(settings)
        self._local_backend = LocalBackend(settings)

        # Load prompt templates
        self.prompt_engine.load_templates()

    def _get_backend(self) -> BaseAIBackend:
        """Select the active backend based on settings."""
        if self.settings.ai_backend == AIBackend.CLOUD:
            if self._cloud_backend and self._cloud_backend.is_available:
                return self._cloud_backend
            provider = self.settings.cloud_provider.value
            if provider == "openai_compatible":
                url = self.settings.openai_base_url or "http://localhost:11434/v1"
                raise RuntimeError(
                    f"Cloud backend ({provider}) configured but API key is missing. "
                    f"Check MUD_OPENAI_API_KEY in python-sidecar/.env. "
                    f"If using Ollama make sure it is running: ollama serve (target: {url})"
                )
            raise RuntimeError(
                f"Cloud backend ({provider}) configured but API key is missing. "
                "Check MUD_ANTHROPIC_API_KEY in python-sidecar/.env."
            )

        if self.settings.ai_backend == AIBackend.LOCAL:
            if self._local_backend and self._local_backend.is_available:
                return self._local_backend
            raise RuntimeError(
                "Local backend selected but not available. Check model_path configuration."
            )

        # AUTO mode: prefer cloud, fall back to local
        if self._cloud_backend and self._cloud_backend.is_available:
            return self._cloud_backend
        if self._local_backend and self._local_backend.is_available:
            logger.info("Cloud unavailable, falling back to local backend")
            return self._local_backend

        raise RuntimeError(
            "No AI backend available. Configure either cloud API key or local model path."
        )

    def _get_reviewer_backend(self) -> BaseAIBackend:
        """Return a backend configured for the reviewer/critic model.

        Uses ``settings.pipeline_reviewer_model`` (e.g. ``deepseek-r1:7b``) so
        that MUD spec review is performed by a reasoning-capable model rather
        than the same generation model.  Falls back to ``_get_backend()`` when:
          - ``pipeline_reviewer_model`` is empty / not configured
          - The active backend is a local model (no per-model override supported)
        """
        reviewer_model = self.settings.pipeline_reviewer_model
        if not reviewer_model:
            logger.debug("Reviewer: no pipeline_reviewer_model configured, using generator backend")
            return self._get_backend()

        gen_backend = self._get_backend()
        if not isinstance(gen_backend, CloudBackend):
            logger.info("Reviewer: local backend active — reviewer model override not supported, using generator")
            return gen_backend

        # Build a CloudBackend instance with the reviewer model name substituted
        try:
            reviewer_settings = self.settings.model_copy(
                update={"openai_model": reviewer_model}
            )
        except AttributeError:
            # Pydantic v1 fallback
            reviewer_settings = self.settings.copy(
                update={"openai_model": reviewer_model}
            )

        reviewer = CloudBackend(reviewer_settings)
        logger.info(
            "Reviewer backend: %s (model=%s)", reviewer.backend_name, reviewer_model
        )
        return reviewer

    def _get_skeleton_backend(self) -> BaseAIBackend:
        """Return a backend configured for MUD-spec Stage 1 skeleton generation.

        Uses ``settings.mud_spec_skeleton_model`` (e.g. ``deepseek-r1:7b``) when
        set so that Stage 1 of the two-stage pipeline runs through a stronger
        reasoning model.  Falls back to ``_get_backend()`` when:
          - ``mud_spec_skeleton_model`` is empty / not configured
          - The active backend is local (no per-model override supported)
          - The configured skeleton model equals the generator model
        """
        skeleton_model = (self.settings.mud_spec_skeleton_model or "").strip()
        if not skeleton_model:
            return self._get_backend()

        gen_backend = self._get_backend()
        if not isinstance(gen_backend, CloudBackend):
            logger.info(
                "Skeleton: local backend active — skeleton model override not supported"
            )
            return gen_backend

        if skeleton_model == self.settings.openai_model:
            return gen_backend

        try:
            skeleton_settings = self.settings.model_copy(
                update={"openai_model": skeleton_model}
            )
        except AttributeError:
            skeleton_settings = self.settings.copy(
                update={"openai_model": skeleton_model}
            )

        skeleton = CloudBackend(skeleton_settings)
        logger.info(
            "Skeleton backend: %s (model=%s)", skeleton.backend_name, skeleton_model
        )
        return skeleton

    def _make_backend_with_model(self, model_name: str) -> BaseAIBackend:
        """Build a CloudBackend variant with ``openai_model`` overridden.

        Falls back to the generator backend when the active backend is local
        or when ``model_name`` matches the generator (no swap needed).
        """
        gen_backend = self._get_backend()
        if not isinstance(gen_backend, CloudBackend):
            return gen_backend
        if not model_name or model_name == self.settings.openai_model:
            return gen_backend
        try:
            new_settings = self.settings.model_copy(update={"openai_model": model_name})
        except AttributeError:
            new_settings = self.settings.copy(update={"openai_model": model_name})
        return CloudBackend(new_settings)

    def _get_activity_skeleton_backend(self) -> BaseAIBackend:
        """Backend for ActivityPipeline Stage 1 (skeleton extraction).

        Uses ``settings.activity_pipeline_skeleton_model`` (e.g.
        ``deepseek-r1:7b``) when set; falls back to the generator backend.
        """
        model = (getattr(self.settings, "activity_pipeline_skeleton_model", "") or "").strip()
        if not model:
            return self._get_backend()
        backend = self._make_backend_with_model(model)
        logger.info("Activity skeleton backend: %s (model=%s)", backend.backend_name, model)
        return backend

    def _get_activity_reviewer_backend(self) -> BaseAIBackend:
        """Backend for ActivityPipeline Stage 4 (cross-runnable review)."""
        model = (getattr(self.settings, "activity_pipeline_reviewer_model", "") or "").strip()
        if not model:
            return self._get_backend()
        backend = self._make_backend_with_model(model)
        logger.info("Activity reviewer backend: %s (model=%s)", backend.backend_name, model)
        return backend

    async def _run_activity_pipeline(
        self,
        mud_ctx_obj,
        module_context: Optional[str],
        requirements: list[Requirement],
        activity_label_style: str,
        temperature: float,
        progress_callback: Optional[callable] = None,
    ) -> Optional["GenerationResult"]:
        """Run the multi-stage ActivityPipeline and return a GenerationResult.

        Returns None on hard failure (caller falls back to legacy single-call).
        Returned dicts go through the same ``_parse_response`` path as the
        legacy AI output so existing repair/validation/provenance logic fires.
        """
        try:
            from mudtool.ai.activity_pipeline_stages import ActivityPipeline
        except Exception as exc:
            logger.warning("ActivityPipeline import failed: %s", exc)
            return None

        try:
            pipeline = ActivityPipeline(
                backend=self._get_backend(),
                skeleton_backend=self._get_activity_skeleton_backend(),
                reviewer_backend=self._get_activity_reviewer_backend(),
                progress_callback=progress_callback,
            )
            diagram_dicts = await pipeline.run(
                mud_activity_context=mud_ctx_obj,
                module_context=module_context,
                requirements=requirements,
                activity_label_style=activity_label_style,
                temperature=temperature,
            )
        except Exception as exc:
            logger.warning("ActivityPipeline.run raised: %s", exc, exc_info=True)
            return None

        if not diagram_dicts:
            return None

        # Funnel through the existing _parse_response path so model_validate +
        # _repair_activity_diagram + provenance stamping all run uniformly.
        import json as _json

        class _PipelineResponse:
            def __init__(self, content: str, model: str, latency_ms: int = 0):
                self.content = content
                self.model = model
                self.latency_ms = latency_ms

        wrapped = _json.dumps({"diagrams": diagram_dicts})
        response = _PipelineResponse(
            content=wrapped,
            model="activity_pipeline",
            latency_ms=0,
        )
        prompt_hash = "activity_pipeline_v1"
        backend_name = getattr(self._get_backend(), "backend_name", "activity_pipeline")
        return self._parse_response(
            response,
            DiagramType.ACTIVITY,
            prompt_hash,
            backend_name,
            req_ids=[r.req_id for r in requirements],
        )

    async def generate_diagram(
        self,
        diagram_type: DiagramType,
        requirements: list[Requirement],
        module_context: Optional[str] = None,
        existing_swcs: Optional[list[str]] = None,
        temperature: float = 0.2,
        progress_callback: Optional[callable] = None,
        generation_profile: str = "autosar",
        activity_label_style: str = "pseudocode",
        autosar_compliant: bool = True,
        elaborated_data: Optional[dict] = None,
        activity_source: str = "requirements",
        mud_activity_context: Any = None,  # str | MudActivityContext | None
    ) -> GenerationResult:
        """Generate a single diagram from requirements.

        This is the main entry point for diagram generation.
        Handles prompt rendering, AI inference, parsing, and retries.

        Args:
            diagram_type: Type of diagram to generate.
            requirements: List of requirements to model.
            module_context: Optional module/SWC context for better results.
            existing_swcs: Optional existing SWC catalog for cross-references.
            temperature: AI sampling temperature.
            progress_callback: Optional callback for SSE progress events.

        Returns:
            GenerationResult containing the generated diagram(s).
        """
        start_time = time.monotonic()
        backend = self._get_backend()

        # Render prompts
        system_prompt = self.prompt_engine.render_system_prompt(
            diagram_type,
            naming_conventions={
                "swc_regex": self.settings.swc_naming_regex,
                "runnable_regex": self.settings.runnable_naming_regex,
                "port_regex": self.settings.port_naming_regex,
            },
            profile=generation_profile,
            activity_label_style=activity_label_style,
        )
        user_prompt = self.prompt_engine.render_user_prompt(
            diagram_type,
            requirements,
            module_context,
            existing_swcs,
            profile=generation_profile,
            activity_label_style=activity_label_style,
        )

        # mud_activity_context may be a MudActivityContext object (preferred —
        # routes.py passes the object so the multi-stage ActivityPipeline can
        # iterate runnables) or a legacy string (already-rendered prompt block).
        mud_ctx_obj = None
        mud_ctx_block: str = ""
        if mud_activity_context is not None:
            if hasattr(mud_activity_context, "to_prompt_block") and hasattr(mud_activity_context, "runnables"):
                mud_ctx_obj = mud_activity_context
                try:
                    mud_ctx_block = mud_ctx_obj.to_prompt_block()
                except Exception:
                    mud_ctx_block = ""
            elif isinstance(mud_activity_context, str):
                mud_ctx_block = mud_activity_context

        if diagram_type == DiagramType.ACTIVITY and activity_source == "mud_spec":
            system_prompt += (
                "\n\nMUD-FIRST ACTIVITY MODE:\n"
                "- The supplied MUD specification is the authoritative source for runnable flow.\n"
                "- Architecture requirements are traceability background only.\n"
                "- Produce one parent activity diagram per runnable described by the MUD spec.\n"
                "- Helper sub-diagrams are allowed only when supported by the MUD text.\n"
                "- Every diagram must contain a valid Start-to-End executable path."
            )
            user_prompt = self._build_activity_mud_user_prompt(
                mud_ctx_block,
                requirements,
                module_context,
                activity_label_style=activity_label_style,
            )

            # ── Multi-stage ActivityPipeline (skeleton → per-runnable → review) ─
            # When enabled, bypass the single-call generation below and run the
            # 5-stage pipeline.  Returns empty list to fall through to legacy
            # path on any failure.
            if (
                mud_ctx_obj is not None
                and getattr(self.settings, "activity_pipeline_enabled", False)
                and mud_ctx_obj.runnables
            ):
                pipeline_result = await self._run_activity_pipeline(
                    mud_ctx_obj=mud_ctx_obj,
                    module_context=module_context,
                    requirements=requirements,
                    activity_label_style=activity_label_style,
                    temperature=temperature,
                    progress_callback=progress_callback,
                )
                if pipeline_result is not None and pipeline_result.diagrams:
                    return pipeline_result
                logger.info(
                    "[Activity Pipeline] empty result — falling back to legacy single-call path"
                )

        # Inject elaborated context if available (from pre-processing step)
        try:
            from mudtool.ai.elaborator import RequirementElaborator, build_enriched_context
            elab_data = elaborated_data
            if elab_data is None:
                elaborator = RequirementElaborator.__new__(RequirementElaborator)
                req_hash = RequirementElaborator._compute_hash(requirements)
                cache_path = RequirementElaborator.get_cache_path(req_hash)
                if cache_path.exists():
                    import json as _json
                    elab_data = _json.loads(cache_path.read_text(encoding="utf-8"))

            if elab_data:
                enriched = build_enriched_context(elab_data)
                if enriched:
                    user_prompt = enriched + "\n\n" + user_prompt
                    logger.info(
                        f"Injected elaborated context ({len(enriched)} chars) "
                        f"into {diagram_type.value} prompt"
                    )
        except Exception as exc:
            logger.debug(f"No elaborated context available: {exc}")

        # Inject guidelines context if available (loaded by Guidelines RAG stage)
        try:
            guidelines_context = (elab_data or {}).get("guidelines_context", {})
            guidelines_block = guidelines_context.get(diagram_type.value, "")
            if guidelines_block:
                user_prompt = guidelines_block + "\n\n" + user_prompt
                logger.info(
                    f"Injected guidelines context ({len(guidelines_block)} chars) "
                    f"into {diagram_type.value} prompt"
                )
        except Exception as exc:
            logger.debug(f"No guidelines context: {exc}")

        # Inject AUTOSAR skill block for activity diagrams (full-document, not chunked)
        if diagram_type == DiagramType.ACTIVITY and self.settings.skills_enabled:
            try:
                from mudtool.ai.skill_loader import SkillLoader
                skill_block = SkillLoader(self.settings).build_activity_skill_block()
                if skill_block:
                    system_prompt = skill_block + "\n\n" + system_prompt
                    logger.info(
                        f"Injected skill block ({len(skill_block)} chars) "
                        f"into activity diagram system prompt"
                    )
            except Exception as exc:
                logger.debug(f"Skill injection skipped: {exc}")

        prompt_hash = self.prompt_engine.compute_prompt_hash(system_prompt, user_prompt)

        # Attempt generation with retries
        last_error: Optional[str] = None
        max_retries = self.settings.max_retries
        base_user_prompt = user_prompt  # preserve original prompt for retry replacement
        best_result: Optional[GenerationResult] = None
        best_score: float = -1.0
        for attempt in range(1, max_retries + 1):
            try:
                # Adaptive temperature: slightly lower for structural fix retries,
                # slightly higher for later attempts to encourage different outputs
                attempt_temp = temperature
                if attempt == 2 or attempt == 3:
                    attempt_temp = max(temperature - 0.05, 0.05)
                elif attempt >= 4:
                    attempt_temp = min(temperature + 0.10, 0.40)

                logger.info(
                    f"Generation attempt {attempt}/{max_retries} "
                    f"for {diagram_type.value} via {backend.backend_name} "
                    f"(temp={attempt_temp:.2f})"
                )
                if progress_callback:
                    progress_callback({
                        "stage": "generate",
                        "diagram_type": diagram_type.value,
                        "attempt": attempt,
                        "max_attempts": max_retries,
                        "message": (
                            f"Generating {diagram_type.value} diagram"
                            f" (attempt {attempt}/{max_retries})..."
                        ),
                    })

                response = await backend.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=self.settings.anthropic_max_tokens,
                    temperature=attempt_temp,
                )

                # Parse the response
                result = self._parse_response(
                    response,
                    diagram_type,
                    prompt_hash,
                    backend.backend_name,
                    req_ids=[r.req_id for r in requirements],
                )

                if result.errors and attempt < self.settings.max_retries:
                    last_error = "; ".join(result.errors)
                    summarized = self._summarize_parse_errors(result.errors)
                    logger.warning(
                        f"Attempt {attempt} produced errors: {summarized}. Retrying..."
                    )
                    # Replace (not append) error context for next attempt
                    user_prompt = (
                        base_user_prompt
                        + f"\n\nPREVIOUS ATTEMPT FAILED:\n{summarized}\n"
                        "Fix these issues. Output ONLY valid JSON matching the schema."
                    )
                    continue

                # Track best result across attempts (score by nodes + diagrams)
                if result.diagrams:
                    node_count = self._count_result_nodes(result)
                    diag_count = len(result.diagrams)
                    score = diag_count * 100 + node_count
                    if score > best_score:
                        best_score = score
                        best_result = result
                        logger.debug(
                            f"Attempt {attempt} is new best: "
                            f"{diag_count} diagrams, {node_count} nodes"
                        )

                # Run quick validation on successful parse to feed issues
                # back into the retry prompt (validation-driven retry).
                if result.diagrams and attempt < self.settings.max_retries:
                    req_id_list = [r.req_id for r in requirements]
                    val_issues = self._quick_validate(
                        result, req_id_list, autosar_compliant=autosar_compliant
                    )

                    # Explicit coverage check: find which requirements are
                    # not traced by any diagram element
                    covered = self._collect_covered_reqs(result)
                    uncovered = sorted(set(req_id_list) - covered)
                    coverage_pct = (
                        len(covered & set(req_id_list))
                        / max(len(req_id_list), 1)
                        * 100
                    )

                    needs_retry = False
                    retry_parts: list[str] = []

                    if val_issues:
                        issues_text = "\n".join(
                            f"  - {v}" for v in val_issues[:15]
                        )
                        retry_parts.append(
                            f"VALIDATION ISSUES:\n{issues_text}"
                        )
                        needs_retry = True

                    if coverage_pct < 60 and uncovered:
                        retry_parts.append(
                            f"CRITICAL: Only {coverage_pct:.0f}% requirement coverage!\n"
                            f"These {len(uncovered)} requirements have NO trace_reqs "
                            f"in any diagram element: {uncovered}\n"
                            "You MUST add trace_reqs referencing these IDs to "
                            "relevant nodes/elements in your output."
                        )
                        needs_retry = True
                        logger.warning(
                            f"Attempt {attempt}: coverage {coverage_pct:.0f}%, "
                            f"uncovered={uncovered}"
                        )

                    # G: Confidence-gated retry — if computed confidence is below
                    # the configured threshold, ask the AI to improve quality.
                    # This wires settings.confidence_threshold into the retry loop
                    # (previously it was only displayed in the UI but never enforced).
                    interim_conf = self._compute_confidence(
                        result, [r.req_id for r in requirements]
                    )
                    conf_threshold = self.settings.confidence_threshold
                    if interim_conf < conf_threshold and not needs_retry:
                        retry_parts.append(
                            f"QUALITY GATE: Confidence {interim_conf:.0%} is below "
                            f"the required {conf_threshold:.0%} threshold.\n"
                            "To improve confidence:\n"
                            "  1. Add trace_reqs to every node and edge that lacks them.\n"
                            "  2. Ensure every node has a non-empty description.\n"
                            "  3. Use AUTOSAR-compliant names (SWC_*, RE_*, PP_*, RP_*).\n"
                            "  4. Fix any structural issues (missing branches, unreachable nodes)."
                        )
                        needs_retry = True
                        logger.info(
                            f"Attempt {attempt}: confidence {interim_conf:.3f} < "
                            f"threshold {conf_threshold:.3f} — retrying for quality"
                        )

                    if needs_retry:
                        logger.info(
                            f"Attempt {attempt} parsed OK but has "
                            f"{len(val_issues)} validation issues, "
                            f"coverage={coverage_pct:.0f}%. Retrying..."
                        )
                        if progress_callback:
                            progress_callback({
                                "stage": "validate",
                                "diagram_type": diagram_type.value,
                                "attempt": attempt,
                                "max_attempts": max_retries,
                                "issues": len(val_issues),
                                "coverage_pct": round(coverage_pct),
                                "message": (
                                    f"Attempt {attempt}: {len(val_issues)} issues, "
                                    f"{coverage_pct:.0f}% coverage — retrying..."
                                ),
                            })
                        feedback = "\n\n".join(retry_parts)
                        # Replace (not append) to keep prompt concise
                        user_prompt = (
                            base_user_prompt
                            + f"\n\nPREVIOUS ATTEMPT produced valid JSON but "
                            f"NEEDS FIXES:\n{feedback}\n"
                            "Fix ALL listed issues in your output. "
                            "Output only the corrected JSON."
                        )
                        continue

                # Success — pick the better of current result vs best_result
                total_time = int((time.monotonic() - start_time) * 1000)
                cur_nodes = self._count_result_nodes(result) if result.diagrams else 0
                best_nodes = self._count_result_nodes(best_result) if best_result else 0

                # If current attempt has fewer nodes than best, use best instead
                final = result
                if best_result and best_nodes > cur_nodes:
                    logger.info(
                        f"Attempt {attempt} has {cur_nodes} nodes but "
                        f"best attempt had {best_nodes} — using best"
                    )
                    final = best_result

                final.total_generation_time_ms = total_time
                final.analyzed_requirements = [r.req_id for r in requirements]

                computed_conf = self._compute_confidence(
                    final, [r.req_id for r in requirements]
                )
                for d in final.diagrams:
                    if d.provenance:
                        d.provenance.confidence = computed_conf

                logger.info(
                    f"Generated {diagram_type.value} diagram in {total_time}ms "
                    f"({len(final.diagrams)} diagrams, attempt {attempt}, "
                    f"confidence={computed_conf:.3f})"
                )
                return final

            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt} failed with exception: {e}")
                if attempt >= self.settings.max_retries:
                    break

        # All retries exhausted — return best result from any attempt if available
        total_time = int((time.monotonic() - start_time) * 1000)
        if best_result and best_result.diagrams:
            best_result.total_generation_time_ms = total_time
            best_result.analyzed_requirements = [r.req_id for r in requirements]
            computed_conf = self._compute_confidence(
                best_result, [r.req_id for r in requirements]
            )
            for d in best_result.diagrams:
                if d.provenance:
                    d.provenance.confidence = computed_conf
            logger.info(
                f"Retries exhausted — returning best result: "
                f"{len(best_result.diagrams)} diagrams, "
                f"{self._count_result_nodes(best_result)} nodes, "
                f"confidence={computed_conf:.3f}"
            )
            return best_result

        return GenerationResult(
            errors=[
                f"Generation failed after {self.settings.max_retries} attempts. "
                f"Last error: {last_error}"
            ],
            analyzed_requirements=[r.req_id for r in requirements],
            total_generation_time_ms=total_time,
        )

    async def generate_all_diagrams(
        self,
        requirements: list[Requirement],
        diagram_types: Optional[list[DiagramType]] = None,
        module_context: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        generation_profile: str = "autosar",
        activity_label_style: str = "pseudocode",
        autosar_compliant: bool = True,
        elaborated_data: Optional[dict] = None,
    ) -> GenerationResult:
        """Generate multiple diagram types from requirements.

        Generates in priority order: sequence -> state_machine -> class -> component.

        Args:
            requirements: Full requirement set.
            diagram_types: Specific types to generate (default: all).
            module_context: Optional module context.

        Returns:
            Combined GenerationResult with all diagrams.
        """
        if diagram_types is None:
            diagram_types = [
                DiagramType.SEQUENCE,
                DiagramType.STATE_MACHINE,
                DiagramType.CLASS,
                DiagramType.COMPONENT,
                DiagramType.ACTIVITY,
            ]

        combined = GenerationResult(
            analyzed_requirements=[r.req_id for r in requirements]
        )
        start_time = time.monotonic()

        req_id_list = [r.req_id for r in requirements]

        for dt in diagram_types:
            logger.info(f"Generating {dt.value} diagrams...")
            try:
                if progress_callback:
                    progress_callback({
                        "stage": "start",
                        "diagram_type": dt.value,
                        "message": f"Starting {dt.value} diagram generation...",
                    })

                result = await self.generate_diagram(
                    dt, requirements, module_context,
                    progress_callback=progress_callback,
                    generation_profile=generation_profile,
                    activity_label_style=activity_label_style,
                    autosar_compliant=autosar_compliant,
                    elaborated_data=elaborated_data,
                )

                # ── Post-generation verification gate ──────────────────
                if progress_callback:
                    progress_callback({
                        "stage": "verify",
                        "diagram_type": dt.value,
                        "message": f"Verifying {dt.value} diagram quality...",
                    })
                result = await self._verify_and_maybe_regen(
                    result, dt, requirements, module_context, req_id_list,
                    generation_profile=generation_profile,
                    activity_label_style=activity_label_style,
                    autosar_compliant=autosar_compliant,
                    elaborated_data=elaborated_data,
                )

                combined.diagrams.extend(result.diagrams)
                combined.warnings.extend(result.warnings)
                combined.errors.extend(result.errors)

                if result.module_assignments:
                    if combined.module_assignments is None:
                        combined.module_assignments = {}
                    combined.module_assignments.update(result.module_assignments)

                if progress_callback:
                    conf = self._compute_confidence(result, req_id_list)
                    progress_callback({
                        "stage": "diagram_complete",
                        "diagram_type": dt.value,
                        "success": bool(result.diagrams),
                        "diagram_count": len(result.diagrams),
                        "confidence": round(conf, 2),
                        "message": (
                            f"{dt.value}: {len(result.diagrams)} diagram(s), "
                            f"confidence={conf:.0%}"
                        ),
                    })
            except Exception as exc:
                error_msg = (
                    f"Generation of {dt.value} diagrams failed with "
                    f"unhandled error: {exc}"
                )
                logger.error(error_msg, exc_info=True)
                combined.errors.append(error_msg)
                if progress_callback:
                    progress_callback({
                        "stage": "diagram_complete",
                        "diagram_type": dt.value,
                        "success": False,
                        "error": str(exc),
                        "message": f"{dt.value}: FAILED - {exc}",
                    })

        combined.total_generation_time_ms = int(
            (time.monotonic() - start_time) * 1000
        )
        return combined

    async def _verify_and_maybe_regen(
        self,
        result: GenerationResult,
        diagram_type: DiagramType,
        requirements: list[Requirement],
        module_context: Optional[str],
        req_id_list: list[str],
        generation_profile: str = "autosar",
        activity_label_style: str = "pseudocode",
        autosar_compliant: bool = True,
        elaborated_data: Optional[dict] = None,
        activity_source: str = "requirements",
        mud_activity_context: Any = None,
    ) -> GenerationResult:
        """Post-generation verification gate.

        Checks:
          1. Has at least one diagram
          2. Coverage > 50%
          3. Computed confidence >= settings.confidence_threshold
          4. No structural ERROR-level issues

        If any check fails, auto-regenerates ONCE with a slightly higher
        temperature to encourage a different output.
        """
        if not result.diagrams:
            logger.warning(
                f"[Verify] {diagram_type.value}: 0 diagrams — auto-regenerating"
            )
            return await self.generate_diagram(
                diagram_type,
                requirements,
                module_context,
                temperature=0.25,
                generation_profile=generation_profile,
                activity_label_style=activity_label_style,
                autosar_compliant=autosar_compliant,
                elaborated_data=elaborated_data,
                activity_source=activity_source,
                mud_activity_context=mud_activity_context,
            )

        covered = self._collect_covered_reqs(result)
        n_reqs = max(len(req_id_list), 1)
        coverage_pct = len(covered & set(req_id_list)) / n_reqs * 100
        confidence = self._compute_confidence(result, req_id_list)

        # Collect structural errors
        try:
            str_issues = StructuralValidator.validate_quick(result)
            str_errors = sum(1 for i in str_issues if i.startswith("[ERROR]"))
        except Exception:
            str_errors = 0

        reasons: list[str] = []
        if coverage_pct < 50:
            reasons.append(f"coverage={coverage_pct:.0f}%")
        if confidence < self.settings.confidence_threshold:
            reasons.append(f"confidence={confidence:.2f} < threshold={self.settings.confidence_threshold:.2f}")
        if str_errors > 0:
            reasons.append(f"{str_errors} structural errors")
        if diagram_type == DiagramType.STATE_MACHINE:
            missing_initial = any(
                isinstance(d, StateMachineDiagram)
                and not any(getattr(state, "is_initial", False) for state in d.states)
                for d in result.diagrams
            )
            no_transitions = any(
                isinstance(d, StateMachineDiagram) and len(d.transitions) == 0
                for d in result.diagrams
            )
            if missing_initial:
                reasons.append("state machine missing initial state")
            if no_transitions:
                reasons.append("state machine has no transitions")
        if diagram_type == DiagramType.ACTIVITY:
            invalid_activity = any(
                isinstance(d, ActivityDiagram)
                and (
                    not d.nodes
                    or not any(n.node_type == ActivityNodeType.INITIAL for n in d.nodes)
                    or not any(n.node_type == ActivityNodeType.FINAL for n in d.nodes)
                )
                for d in result.diagrams
            )
            if invalid_activity:
                reasons.append("activity diagram missing executable Start/End path")

        if reasons:
            logger.warning(
                f"[Verify] {diagram_type.value} FAILED: "
                f"{', '.join(reasons)} — auto-regenerating once"
            )
            regen = await self.generate_diagram(
                diagram_type,
                requirements,
                module_context,
                temperature=0.25,
                generation_profile=generation_profile,
                activity_label_style=activity_label_style,
                autosar_compliant=autosar_compliant,
                elaborated_data=elaborated_data,
                activity_source=activity_source,
                mud_activity_context=mud_activity_context,
            )
            # Keep whichever result is better
            regen_conf = self._compute_confidence(regen, req_id_list)
            if regen_conf > confidence and regen.diagrams:
                logger.info(
                    f"[Verify] Regen improved confidence: "
                    f"{confidence:.2f} → {regen_conf:.2f}"
                )
                return regen
            logger.info(
                f"[Verify] Regen did not improve "
                f"({regen_conf:.2f} vs {confidence:.2f}), keeping original"
            )

        return result

    async def analyze_requirements(
        self,
        requirements: list[Requirement],
    ) -> dict:
        """Analyze requirements: cluster into modules, identify interfaces.

        Stage 2 of the pipeline - requirement analysis and clustering.

        Returns:
            Dict with module_assignments, interface_candidates,
            sequence_hints, and state_behavior_flags.
        """
        backend = self._get_backend()

        system_prompt = """You are an AUTOSAR software architecture expert.
Analyze the given requirements and:
1. Cluster them into logical AUTOSAR Software Component (SWC) modules
2. Identify interfaces between modules (Sender-Receiver or Client-Server)
3. Extract behavioral sequences (interaction flows between components)
4. Flag state-dependent behavior (mode management, error handling, lifecycle)

Output valid JSON with this structure:
{
  "module_assignments": {"SWC_Name": ["REQ-ID-1", "REQ-ID-2"]},
  "interface_candidates": [{"from": "SWC_A", "to": "SWC_B", "type": "sender_receiver", "data": "description"}],
  "sequence_hints": [{"requirements": ["REQ-1", "REQ-2"], "description": "interaction description"}],
  "state_behavior_flags": [{"requirement": "REQ-1", "behavior": "mode_management|error_handling|lifecycle"}]
}"""

        reqs_text = "\n".join(
            f"[{r.req_id}] ({r.req_type.value}) {r.title}: {r.description}"
            for r in requirements
        )

        user_prompt = f"Analyze these AUTOSAR architecture requirements:\n\n{reqs_text}"

        response = await backend.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
        )

        try:
            return self._extract_json(response.content)
        except Exception as e:
            logger.error(f"Failed to parse analysis response: {e}")
            return {
                "module_assignments": {},
                "interface_candidates": [],
                "sequence_hints": [],
                "state_behavior_flags": [],
                "error": str(e),
            }

    def _parse_response(
        self,
        response: AIResponse,
        diagram_type: DiagramType,
        prompt_hash: str,
        backend_name: str,
        req_ids: Optional[list[str]] = None,
    ) -> GenerationResult:
        """Parse AI response into structured diagram models."""
        result = GenerationResult()

        try:
            data = self._extract_json(response.content)
        except Exception as e:
            result.errors.append(f"Failed to extract JSON from AI response: {e}")
            return result

        # Handle GenerationResult wrapper: {"diagrams": [...], "analyzed_requirements": [...]}
        # activity_diagram.yaml v2.0 instructs the AI to return this wrapper so that
        # multiple diagrams (one per runnable) can be returned in a single response.
        # Other prompt types (sequence, state_machine, class, component) return a flat
        # single-diagram object, which falls through to the else branch below.
        if isinstance(data, dict) and "diagrams" in data:
            diagrams_data = data.get("diagrams", [])
            if not isinstance(diagrams_data, list):
                diagrams_data = [diagrams_data]
        else:
            # Single diagram object or array of diagram objects
            diagrams_data = data if isinstance(data, list) else [data]

        diagram_model = _DIAGRAM_MODELS.get(diagram_type)
        if not diagram_model:
            result.errors.append(f"Unknown diagram type: {diagram_type}")
            return result

        for i, d_data in enumerate(diagrams_data):
            try:
                activity_normalization_stats: Optional[dict[str, int]] = None
                if diagram_type == DiagramType.ACTIVITY and isinstance(d_data, dict):
                    activity_normalization_stats = {"inferred": 0, "defaulted": 0}
                    d_data = self._normalize_activity_payload(
                        d_data,
                        stats=activity_normalization_stats,
                    )

                # Inject/override diagram_type
                d_data["diagram_type"] = diagram_type.value

                # Build provenance
                d_data.setdefault("provenance", {})
                d_data["provenance"]["ai_model"] = response.model
                d_data["provenance"]["prompt_version"] = prompt_hash
                d_data["provenance"]["backend"] = backend_name
                d_data["provenance"].setdefault("confidence", 0.7)
                d_data["provenance"]["generation_time_ms"] = response.latency_ms
                d_data["provenance"]["prompt_hash"] = prompt_hash

                # Patch sub_diagram provenance before validation so Pydantic
                # doesn't reject them for missing required fields.
                for sub_d in d_data.get("sub_diagrams", []):
                    if isinstance(sub_d, dict):
                        sub_d.setdefault("provenance", {})
                        sub_d["provenance"].setdefault("ai_model", response.model)
                        sub_d["provenance"].setdefault("prompt_version", prompt_hash)
                        sub_d["provenance"].setdefault("backend", backend_name)
                        sub_d["provenance"].setdefault("confidence", 0.7)

                diagram = diagram_model.model_validate(d_data)

                # Local models often omit trace_req / trace_reqs fields.
                # Guarantee coverage by back-filling source_requirements with
                # the requirement IDs that were fed into this generation call.
                if req_ids and not diagram.source_requirements:
                    diagram.source_requirements = list(req_ids)

                # Auto-repair activity diagrams that are missing required
                # initial / final nodes (common with smaller local models).
                if isinstance(diagram, ActivityDiagram):
                    diagram = self._repair_activity_diagram(diagram, req_ids)
                    has_initial = any(
                        node.node_type == ActivityNodeType.INITIAL for node in diagram.nodes
                    )
                    has_final = any(
                        node.node_type == ActivityNodeType.FINAL for node in diagram.nodes
                    )
                    if not diagram.nodes or not has_initial or not has_final:
                        result.errors.append(
                            f"Activity diagram '{diagram.name or i}' is structurally incomplete after repair."
                        )

                result.diagrams.append(diagram)
                if activity_normalization_stats:
                    inferred_count = activity_normalization_stats.get("inferred", 0)
                    defaulted_count = activity_normalization_stats.get("defaulted", 0)
                    if inferred_count or defaulted_count:
                        result.warnings.append(
                            "Activity normalization (diagram "
                            f"{i}): inferred node_type for {inferred_count} "
                            f"node(s); defaulted {defaulted_count} to action."
                        )

                # Flatten sub-diagrams into the result list
                if isinstance(diagram, ActivityDiagram) and diagram.sub_diagrams:
                    for sub in diagram.sub_diagrams:
                        # Fix child provenance if missing
                        if not sub.provenance:
                            sub.provenance = diagram.provenance
                        result.diagrams.append(sub)

                # Warn about FUNCTION_CALL nodes whose callee has no matching sub-diagram
                if isinstance(diagram, ActivityDiagram):
                    sub_fn_names = {
                        s.function_name for s in diagram.sub_diagrams if s.function_name
                    }
                    for node in diagram.nodes:
                        if (
                            node.node_type == ActivityNodeType.FUNCTION_CALL
                            and node.callee
                            and node.callee not in sub_fn_names
                        ):
                            result.warnings.append(
                                f"FUNCTION_CALL node '{node.id}' references callee "
                                f"'{node.callee}' but no matching sub-diagram was generated."
                            )
                            logger.warning(
                                f"Diagram '{diagram.name}': missing sub-diagram for callee "
                                f"'{node.callee}' (node {node.id})"
                            )

            except Exception as e:
                result.errors.append(f"Failed to parse diagram {i}: {e}")
                result.warnings.append(
                    f"Partial data from diagram {i} may be recoverable"
                )

        return result

    @staticmethod
    def _count_result_nodes(result: GenerationResult) -> int:
        """Count total nodes/elements across all diagrams in a result."""
        count = 0
        for d in result.diagrams:
            if isinstance(d, ActivityDiagram):
                count += len(d.nodes)
                for sub in d.sub_diagrams:
                    count += len(sub.nodes)
            elif isinstance(d, SequenceDiagram):
                count += len(d.lifelines) + len(d.messages)
            elif isinstance(d, StateMachineDiagram):
                count += len(d.states) + len(d.transitions)
            elif isinstance(d, ClassDiagram):
                count += len(d.classes) + len(d.associations)
            elif isinstance(d, ComponentDiagram):
                count += len(d.components) + len(d.connectors)
        return count

    @staticmethod
    def _summarize_parse_errors(errors: list[str]) -> str:
        """Summarize verbose Pydantic errors into concise retry feedback.

        Instead of dumping 500-char raw errors, extract the key missing fields
        so the LLM can fix them without being overwhelmed.
        """
        missing_fields: set[str] = set()
        other_issues: list[str] = []
        for err in errors:
            # Extract "field_name Field required" patterns from Pydantic errors
            for m in re.finditer(r"(\w+(?:\.\w+)*)\s+Field required", err):
                field_path = m.group(1)
                # Keep just the field name, not the full path
                field_name = field_path.rsplit(".", 1)[-1]
                missing_fields.add(field_name)
            if "validation error" not in err.lower() and "Field required" not in err:
                # Non-Pydantic error — keep a short version
                other_issues.append(err[:200])

        parts: list[str] = []
        if missing_fields:
            parts.append(
                f"Missing required fields: {', '.join(sorted(missing_fields))}. "
                "Ensure EVERY node has: id, name, node_type, trace_reqs, confidence, description. "
                "Ensure EVERY edge has: id, source, target. "
                "Use 'node_type' (not 'type')."
            )
        for issue in other_issues[:3]:
            parts.append(issue)
        return "\n".join(parts) if parts else "; ".join(errors)[:500]

    @classmethod
    def _normalize_activity_node_type(cls, raw_type: Any) -> Any:
        """Normalize legacy/LLM activity node type variants to schema values."""
        if not isinstance(raw_type, str):
            return None

        norm = raw_type.strip().lower().replace("-", "_").replace(" ", "_")
        if not norm:
            return None
        if norm.endswith("_node"):
            norm = norm[:-5]
        elif norm.endswith("node"):
            norm = norm[:-4]

        alias_map = {
            "activity": "action",
            "process": "action",
            "operation": "action",
            "step": "action",
            "functioncall": "function_call",
            "function": "function_call",
            "branch": "decision",
            "condition": "decision",
            "error": "exception",
            "fault": "exception",
        }
        norm = alias_map.get(norm, norm)
        return norm

    @staticmethod
    def _is_non_empty_text(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @classmethod
    def _infer_activity_node_type_from_text(cls, node: dict) -> tuple[str, bool]:
        """Infer node type from id/name keywords when explicit type is missing."""
        text_parts = []
        for key in ("name", "id"):
            value = node.get(key)
            if isinstance(value, str):
                text_parts.append(value.lower())
        text = " ".join(text_parts)

        if any(k in text for k in ("start", "initial", "begin")):
            return "initial", True
        if any(k in text for k in ("end", "final", "stop", "terminate")):
            return "final", True
        if "?" in text or any(k in text for k in ("if", "check", "validate", "decision")):
            return "decision", True
        if any(k in text for k in ("call", "invoke", "rte_")):
            return "call", True
        return "action", False

    @classmethod
    def _resolve_activity_node_type(cls, node: dict) -> tuple[str, bool, bool]:
        """
        Resolve node_type from modern, camelCase, or legacy keys.

        Returns:
            (resolved_type, used_inference, defaulted_to_action)
        """
        valid_types = {
            "initial",
            "final",
            "action",
            "call",
            "function_call",
            "decision",
            "fork",
            "join",
            "merge",
            "exception",
        }

        for key in ("node_type", "nodeType", "type"):
            normalized = cls._normalize_activity_node_type(node.get(key))
            if normalized in valid_types:
                return normalized, False, False

        inferred, matched = cls._infer_activity_node_type_from_text(node)
        if inferred in valid_types:
            return inferred, True, not matched and inferred == "action"
        return "action", True, True

    @staticmethod
    def _normalize_activity_node_name(node: dict, fallback_id: str) -> str:
        """Derive a usable node name from common legacy keys."""
        for key in ("name", "label", "title"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        desc = node.get("description")
        if isinstance(desc, str) and desc.strip():
            return desc.strip()[:80]

        clean_id = (fallback_id or "Node").strip()
        clean_id = clean_id.replace("_", " ").replace("-", " ")
        return clean_id or "Node"

    @staticmethod
    def _is_safe_activity_id(raw_id: Any) -> bool:
        if not isinstance(raw_id, str):
            return False
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", raw_id.strip()))

    @classmethod
    def _make_safe_activity_id(
        cls,
        raw_id: Any,
        fallback_name: str,
        idx: int,
        used_ids: set[str],
    ) -> str:
        candidate = str(raw_id).strip() if raw_id is not None else ""
        if cls._is_safe_activity_id(candidate) and candidate not in used_ids:
            used_ids.add(candidate)
            return candidate

        name_seed = fallback_name if isinstance(fallback_name, str) and fallback_name.strip() else candidate
        base = re.sub(r"[^A-Za-z0-9_]+", "_", (name_seed or "").strip())
        base = re.sub(r"_+", "_", base).strip("_")
        if not base or not re.match(r"[A-Za-z_]", base):
            base = f"N_{idx:02d}"

        safe_id = base
        suffix = 2
        while safe_id in used_ids:
            safe_id = f"{base}_{suffix}"
            suffix += 1

        used_ids.add(safe_id)
        return safe_id

    @classmethod
    def _normalize_activity_payload(
        cls,
        payload: dict,
        stats: Optional[dict[str, int]] = None,
    ) -> dict:
        """Normalize common non-schema activity payload variants before validation."""
        node_id_map: dict[str, str] = {}
        nodes = payload.get("nodes")
        if isinstance(nodes, list):
            used_ids: set[str] = set()
            for idx, node in enumerate(nodes, start=1):
                if not isinstance(node, dict):
                    continue
                original_id = node.get("id")
                if original_id is None:
                    original_id = f"N_{idx:02d}"
                node["name"] = cls._normalize_activity_node_name(node, str(original_id))
                safe_id = cls._make_safe_activity_id(
                    original_id,
                    node["name"],
                    idx,
                    used_ids,
                )
                node["id"] = safe_id
                node_id_map[str(original_id)] = safe_id
                node_type, used_inference, defaulted = cls._resolve_activity_node_type(node)
                node["node_type"] = node_type
                if stats is not None:
                    if used_inference and not defaulted:
                        stats["inferred"] = stats.get("inferred", 0) + 1
                    if defaulted:
                        stats["defaulted"] = stats.get("defaulted", 0) + 1

        edges = payload.get("edges")
        if isinstance(edges, list):
            for idx, edge in enumerate(edges, start=1):
                if not isinstance(edge, dict):
                    continue
                edge.setdefault("id", f"E_{idx:02d}")
                if "source" not in edge and "from" in edge:
                    edge["source"] = edge["from"]
                if "source" not in edge and "source_id" in edge:
                    edge["source"] = edge["source_id"]
                if "target" not in edge and "to" in edge:
                    edge["target"] = edge["to"]
                if "target" not in edge and "target_id" in edge:
                    edge["target"] = edge["target_id"]
                if "source" in edge:
                    edge["source"] = node_id_map.get(str(edge["source"]), edge["source"])
                if "target" in edge:
                    edge["target"] = node_id_map.get(str(edge["target"]), edge["target"])

        sub_diagrams = payload.get("sub_diagrams")
        if isinstance(sub_diagrams, list):
            for sub in sub_diagrams:
                if isinstance(sub, dict):
                    cls._normalize_activity_payload(sub, stats=stats)

        return payload

    def _repair_activity_diagram(
        self,
        diagram: ActivityDiagram,
        req_ids: Optional[list[str]],
    ) -> ActivityDiagram:
        """Auto-inject missing initial / final nodes for activity diagrams.

        Small local models (e.g. qwen2.5-coder:7b) sometimes omit the
        mandatory initial/final nodes.  When they're absent we:
          - Add a synthetic INITIAL node connected to the graph root
            (the node with no incoming edges).
          - Add a synthetic FINAL node connected from the graph leaf
            (the node with no outgoing edges).
        This prevents STR-020 validation errors and broken flowcharts.
        """
        from mudtool.models.json_uml import ActivityEdge, ActivityNode, ActivityNodeType

        # ── Empty-diagram fallback ──────────────────────────────────────────
        # If the AI returned a diagram with zero nodes (common with smaller
        # local models when prompts grow long), synthesise a minimal
        # Start → Action(<name>) → End so the diagram is at least valid and
        # renderable. The Action node carries the runnable's name as a
        # placeholder description.
        if not diagram.nodes:
            trace = list(req_ids) if req_ids else (diagram.source_requirements or [])
            runnable_name = (diagram.name or "Action").strip() or "Action"
            synth_nodes = [
                ActivityNode(
                    id="N_START", name="Start",
                    node_type=ActivityNodeType.INITIAL,
                    trace_reqs=trace[:1] if trace else [],
                    confidence=0.5,
                    description=f"Entry point for {runnable_name}",
                ),
                ActivityNode(
                    id="N_ACTION_1", name=runnable_name,
                    node_type=ActivityNodeType.ACTION,
                    trace_reqs=trace,
                    confidence=0.5,
                    description=f"Execute {runnable_name} body (synthesised — AI returned empty diagram)",
                ),
                ActivityNode(
                    id="N_END", name="End",
                    node_type=ActivityNodeType.FINAL,
                    trace_reqs=trace[:1] if trace else [],
                    confidence=0.5,
                    description=f"Exit point for {runnable_name}",
                ),
            ]
            synth_edges = [
                ActivityEdge(id="E_S2A", source="N_START",     target="N_ACTION_1"),
                ActivityEdge(id="E_A2E", source="N_ACTION_1",  target="N_END"),
            ]
            logger.warning(
                f"Activity diagram '{diagram.name}': AI returned 0 nodes — "
                f"synthesised minimal Start → {runnable_name} → End diagram"
            )
            return diagram.model_copy(update={"nodes": synth_nodes, "edges": synth_edges})

        has_initial = any(n.node_type == ActivityNodeType.INITIAL for n in diagram.nodes)
        has_final   = any(n.node_type == ActivityNodeType.FINAL   for n in diagram.nodes)

        if has_initial and has_final:
            return diagram  # nothing to repair

        trace = list(req_ids) if req_ids else diagram.source_requirements or []
        sources = {e.source for e in diagram.edges}
        targets = {e.target for e in diagram.edges}
        all_ids  = {n.id for n in diagram.nodes}

        # Mutate a copy of nodes/edges lists (Pydantic model is not frozen here)
        nodes = list(diagram.nodes)
        edges = list(diagram.edges)

        if not has_initial:
            # Root = node referenced as source but never as target (or first node)
            roots = [n for n in nodes if n.id in sources and n.id not in targets]
            first = roots[0] if roots else nodes[0]
            init_id = "N_INIT"
            # Make sure synthetic id is unique
            while init_id in all_ids:
                init_id += "_0"
            init_node = ActivityNode(
                id=init_id,
                name="Start",
                node_type=ActivityNodeType.INITIAL,
                trace_reqs=trace[:1] if trace else [],
                confidence=0.9,
            )
            nodes.insert(0, init_node)
            edges.insert(0, ActivityEdge(id="E_INIT", source=init_id, target=first.id))
            logger.info(f"Activity diagram '{diagram.name}': auto-injected INITIAL node → {first.id}")

        if not has_final:
            # Leaf = node that is a target but never a source (or last node)
            leaves = [n for n in nodes
                      if n.id in targets and n.id not in sources
                      and n.node_type != ActivityNodeType.INITIAL]
            last = leaves[-1] if leaves else nodes[-1]
            final_id = "N_FINAL"
            while final_id in {n.id for n in nodes}:
                final_id += "_0"
            final_node = ActivityNode(
                id=final_id,
                name="End",
                node_type=ActivityNodeType.FINAL,
                trace_reqs=trace[:1] if trace else [],
                confidence=0.9,
            )
            nodes.append(final_node)
            edges.append(ActivityEdge(id="E_FINAL", source=last.id, target=final_id))
            logger.info(f"Activity diagram '{diagram.name}': auto-injected FINAL node from {last.id}")

        # ── D: Remove dangling edges (STR-022) ───────────────────────────────
        # Edges whose source or target does not reference an existing node ID
        # cause parse failures and validation errors. Drop them silently and log.
        node_id_set = {n.id for n in nodes}
        valid_edges = []
        for e in edges:
            if e.source not in node_id_set or e.target not in node_id_set:
                logger.warning(
                    f"Activity diagram '{diagram.name}': removing dangling edge "
                    f"'{e.id}' ({e.source} → {e.target}) — node(s) do not exist"
                )
            else:
                valid_edges.append(e)
        edges = valid_edges

        # ── E: Fix decision nodes with < 2 outgoing edges (STR-021) ─────────
        # A DECISION/MERGE node must fan out to ≥ 2 targets.  If the AI only
        # generated one branch, add a synthetic "else → next node" edge so the
        # diagram renders and validation passes.
        out_edges: dict[str, list] = {}
        for e in edges:
            out_edges.setdefault(e.source, []).append(e)

        for node in nodes:
            if node.node_type == ActivityNodeType.DECISION and len(out_edges.get(node.id, [])) < 2:
                # Find a reasonable "else" target: the first node that is not already
                # a target of this decision node and is not the decision itself.
                existing_targets = {e.target for e in out_edges.get(node.id, [])}
                else_target = next(
                    (n.id for n in nodes
                     if n.id != node.id and n.id not in existing_targets),
                    None,
                )
                if else_target:
                    synth_id = f"E_ELSE_{node.id}"
                    while synth_id in {e.id for e in edges}:
                        synth_id += "_0"
                    edges.append(ActivityEdge(id=synth_id, source=node.id, target=else_target, guard="else"))
                    out_edges.setdefault(node.id, []).append(edges[-1])
                    logger.info(
                        f"Activity diagram '{diagram.name}': auto-added else-edge "
                        f"'{synth_id}' from DECISION '{node.id}' → '{else_target}'"
                    )

        repaired_sub_diagrams = [
            self._repair_activity_diagram(sub, req_ids)
            for sub in diagram.sub_diagrams
        ]

        # Return rebuilt diagram with repaired node/edge lists
        return diagram.model_copy(
            update={"nodes": nodes, "edges": edges, "sub_diagrams": repaired_sub_diagrams}
        )

    def _build_activity_mud_user_prompt(
        self,
        mud_activity_context: str,
        requirements: list[Requirement],
        module_context: Optional[str],
        activity_label_style: str = "pseudocode",
    ) -> str:
        reqs_text = self.prompt_engine._format_requirements(requirements)
        style_line = (
            "Use short pseudocode-style node labels unless the MUD explicitly shows full call signatures."
            if activity_label_style == "pseudocode"
            else "Use explicit call-signature labels when the MUD spec shows them."
        )
        return (
            f"Generate activity flowcharts for {module_context or 'the selected SWC'}.\n\n"
            "Use the supplied MUD specification as the authoritative control-flow source.\n"
            "Produce one parent flowchart per runnable and helper sub-diagrams only when the MUD text supports them.\n"
            "Every diagram must contain Start and End nodes and at least one executable path between them.\n"
            f"{style_line}\n\n"
            f"{mud_activity_context}\n\n"
            "ARCHITECTURAL REQUIREMENTS FOR TRACEABILITY:\n"
            f"{reqs_text}\n\n"
            "Output ONE JSON object only. No text before or after."
        )

    @staticmethod
    def _collect_covered_reqs(result: GenerationResult) -> set[str]:
        """Collect all requirement IDs referenced by any diagram element."""
        covered: set[str] = set()
        for diagram in result.diagrams:
            if hasattr(diagram, "source_requirements"):
                covered.update(diagram.source_requirements or [])
            if isinstance(diagram, SequenceDiagram):
                for ll in diagram.lifelines:
                    covered.update(ll.trace_reqs)
                for msg in diagram.messages:
                    if msg.trace_req:
                        covered.add(msg.trace_req)
            elif isinstance(diagram, StateMachineDiagram):
                for state in diagram.states:
                    covered.update(state.trace_reqs)
            elif isinstance(diagram, ClassDiagram):
                for cls in diagram.classes:
                    covered.update(cls.trace_reqs)
            elif isinstance(diagram, ComponentDiagram):
                for comp in diagram.components:
                    covered.update(comp.trace_reqs)
            elif isinstance(diagram, ActivityDiagram):
                for node in diagram.nodes:
                    covered.update(node.trace_reqs)
                for sub in diagram.sub_diagrams:
                    for node in sub.nodes:
                        covered.update(node.trace_reqs)
        return covered

    def _compute_confidence(
        self,
        result: GenerationResult,
        req_ids: list[str],
    ) -> float:
        """Compute metrics-based confidence, replacing self-reported AI values.

        Weighted average of:
          trace_coverage    (reqs covered / total reqs)       x 0.40
          naming_compliance (valid AUTOSAR names / total)      x 0.25
          structural_score  (1.0 - errors/elements)            x 0.25
          node_completeness (nodes with all fields / total)    x 0.10
        """
        if not result.diagrams:
            return 0.0

        covered_reqs: set[str] = set()
        total_elements = 0
        named_elements = 0
        valid_names = 0
        complete_nodes = 0
        total_nodes = 0

        for diagram in result.diagrams:
            if hasattr(diagram, "source_requirements"):
                covered_reqs.update(diagram.source_requirements)

            if isinstance(diagram, SequenceDiagram):
                for ll in diagram.lifelines:
                    covered_reqs.update(ll.trace_reqs)
                    total_elements += 1
                    named_elements += 1
                    if ll.name and self._swc_pattern.match(ll.name):
                        valid_names += 1
                for msg in diagram.messages:
                    if msg.trace_req:
                        covered_reqs.add(msg.trace_req)
                    total_elements += 1

            elif isinstance(diagram, StateMachineDiagram):
                for state in diagram.states:
                    covered_reqs.update(state.trace_reqs)
                    total_elements += 1

            elif isinstance(diagram, ClassDiagram):
                for cls in diagram.classes:
                    covered_reqs.update(cls.trace_reqs)
                    total_elements += 1
                    named_elements += 1
                    if cls.name and self._swc_pattern.match(cls.name):
                        valid_names += 1

            elif isinstance(diagram, ComponentDiagram):
                for comp in diagram.components:
                    covered_reqs.update(comp.trace_reqs)
                    total_elements += 1
                    named_elements += 1
                    if comp.name and self._swc_pattern.match(comp.name):
                        valid_names += 1

            elif isinstance(diagram, ActivityDiagram):
                for node in diagram.nodes:
                    covered_reqs.update(node.trace_reqs)
                    total_elements += 1
                    total_nodes += 1
                    if node.description and node.trace_reqs:
                        complete_nodes += 1
                for sub in diagram.sub_diagrams:
                    for node in sub.nodes:
                        covered_reqs.update(node.trace_reqs)
                        total_elements += 1

        trace_coverage = len(covered_reqs & set(req_ids)) / max(len(req_ids), 1)
        naming_score = valid_names / max(named_elements, 1)

        try:
            str_issues = StructuralValidator.validate_quick(result)
            error_count = sum(1 for i in str_issues if i.startswith("[ERROR]"))
        except Exception:
            error_count = 0
        structural_score = max(0.0, 1.0 - (error_count / max(total_elements, 1)))

        completeness = complete_nodes / max(total_nodes, 1) if total_nodes else 1.0

        confidence = (
            trace_coverage * 0.40
            + naming_score * 0.25
            + structural_score * 0.25
            + completeness * 0.10
        )
        return round(min(1.0, max(0.0, confidence)), 3)

    # Warning rules that are critical enough to trigger a retry
    _RETRY_WORTHY_RULES = {"AUT-010", "AUT-007"}

    def _quick_validate(
        self,
        result: GenerationResult,
        req_ids: list[str],
        autosar_compliant: bool = True,
    ) -> list[str]:
        """Run structural + AUTOSAR validators and return retry-worthy issues.

        Returns all ERROR-severity issues plus WARNING-level issues from
        coverage-critical rules (AUT-010 requirement coverage, AUT-007
        traceability) so the retry prompt addresses them.
        """
        issues: list[str] = []
        try:
            structural = StructuralValidator.validate_quick(result)
            issues.extend(i for i in structural if i.startswith("[ERROR]"))
        except Exception as exc:
            logger.debug(f"Structural quick-validate failed: {exc}")

        if autosar_compliant:
            try:
                autosar = AUTOSARValidator(self.settings).validate_quick(result, req_ids)
                issues.extend(i for i in autosar if i.startswith("[ERROR]"))
                # Include WARNING-level issues from coverage-critical rules
                issues.extend(
                    i for i in autosar
                    if i.startswith("[WARNING]")
                    and any(rule in i for rule in self._RETRY_WORTHY_RULES)
                )
            except Exception as exc:
                logger.debug(f"AUTOSAR quick-validate failed: {exc}")

        return issues

    def _extract_json(self, text: str) -> dict | list:
        """Extract JSON from AI response text.

        The AI might wrap JSON in markdown code blocks or include
        explanatory text before/after the JSON.
        """
        # Try direct parse first
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        json_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```",
            text,
            re.DOTALL,
        )
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding JSON object/array boundaries
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = text.find(start_char)
            if start != -1:
                end = text.rfind(end_char)
                if end > start:
                    try:
                        return json.loads(text[start : end + 1])
                    except json.JSONDecodeError:
                        pass

        raise ValueError(
            "Could not extract valid JSON from AI response. "
            f"Response starts with: {text[:200]}..."
        )

    async def health_check(self) -> dict:
        """Check health of all configured backends."""
        result = {"orchestrator": "ok", "backends": {}}

        if self._cloud_backend:
            result["backends"]["cloud"] = await self._cloud_backend.health_check()
        if self._local_backend:
            result["backends"]["local"] = await self._local_backend.health_check()

        result["active_backend"] = self.settings.ai_backend.value
        result["prompt_templates_loaded"] = len(self.prompt_engine._templates)

        # Expose model names for dual-AI UI badges
        result["generator_model"] = self.settings.openai_model or self.settings.local_model_path or "unknown"
        result["reviewer_model"] = self.settings.pipeline_reviewer_model or result["generator_model"]

        return result
