"""Multi-stage AI generation pipeline for AUTOSAR UML diagrams.

Supports four modes selectable from the web UI or .env:

  single_pass     — one generation call per diagram (legacy, fastest)
  multi_pass      — codellama drafts → codellama self-critiques → codellama refines
  two_model_fast  — codellama drafts → llama3.2 critiques → codellama refines
  two_model       — codellama drafts → mistral critiques  → codellama refines (best quality)

Hardware note:
  Only one model is in memory at a time. Ollama automatically handles the
  model swap between stages. Sequential execution means no race conditions.

Model assignment rationale:
  codellama 7B  → Generator + Refiner  (trained on code; best at JSON schema output)
  mistral 7B    → Primary Critic       (best language understanding; catches AUTOSAR issues)
  llama3.2 3.2B → Fast Critic          (faster / lighter; use when time matters)
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from mudtool.ai.base_backend import AIResponse
from mudtool.config.settings import Settings
from mudtool.models.json_uml import DiagramType, GenerationResult
from mudtool.models.requirements import Requirement
from mudtool.validation.structural_validator import StructuralValidator
from mudtool.validation.autosar_validator import AUTOSARValidator

logger = logging.getLogger(__name__)


# ── Enums & Config ────────────────────────────────────────────────────────────

class PipelineMode(str, Enum):
    SINGLE_PASS    = "single_pass"
    MULTI_PASS     = "multi_pass"
    TWO_MODEL_FAST = "two_model_fast"
    TWO_MODEL      = "two_model"


@dataclass
class PipelineConfig:
    """Configuration for one pipeline run."""
    mode: PipelineMode = PipelineMode.SINGLE_PASS
    generator_model: str = "codellama"      # Stage 1 (draft) + Stage 3 (refine)
    reviewer_model: str = "mistral"         # Stage 2 (critique) — ignored in multi_pass
    max_passes: int = 1                      # critique-refine cycles per diagram type
    min_confidence: float = 0.75            # early-exit: skip critique if draft meets this
    draft_temperature: float = 0.20
    critique_temperature: float = 0.40
    refine_temperature: float = 0.15
    max_tokens: int = 8192
    generation_profile: str = "autosar"
    activity_label_style: str = "pseudocode"
    autosar_compliant: bool = True
    elaborated_data: Optional[dict] = None


# ── Result Data Classes ───────────────────────────────────────────────────────

@dataclass
class CritiqueResult:
    """Parsed output of the critique stage."""
    issues: list[dict] = field(default_factory=list)
    # Each issue: {"element": str, "severity": "error"|"warning", "description": str}
    quality_score: float = 0.0
    approved: bool = False
    missing_elements: list[str] = field(default_factory=list)
    naming_violations: list[str] = field(default_factory=list)
    traceability_gaps: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def has_errors(self) -> bool:
        return any(i.get("severity") == "error" for i in self.issues)

    @property
    def has_issues(self) -> bool:
        return bool(self.issues or self.missing_elements
                    or self.naming_violations or self.traceability_gaps)


@dataclass
class StageResult:
    """Outcome of one pipeline stage execution."""
    stage_name: str                              # "draft" | "critique" | "refinement"
    model_used: str
    diagram_result: Optional[GenerationResult]  # None for critique stages
    critique: Optional[CritiqueResult]          # None for non-critique stages
    duration_ms: int
    skipped: bool = False
    error: Optional[str] = None

    def to_summary(self) -> dict:
        return {
            "stage": self.stage_name,
            "model": self.model_used,
            "duration_ms": self.duration_ms,
            "skipped": self.skipped,
            "error": self.error,
            "quality_score": (
                self.critique.quality_score if self.critique else None
            ),
            "approved": (
                self.critique.approved if self.critique else None
            ),
        }


@dataclass
class PipelineGenerationResult:
    """Full result of a pipeline run for one diagram type."""
    diagram_type: DiagramType
    final_result: GenerationResult
    stages: list[StageResult] = field(default_factory=list)
    total_duration_ms: int = 0
    pipeline_mode: PipelineMode = PipelineMode.SINGLE_PASS
    passes_completed: int = 1

    @property
    def was_refined(self) -> bool:
        return any(
            s.stage_name == "refinement" and not s.skipped
            for s in self.stages
        )

    @property
    def final_confidence(self) -> float:
        if self.final_result.diagrams:
            p = self.final_result.diagrams[0].provenance
            return p.confidence if (p and p.confidence is not None) else 0.0
        return 0.0

    def to_summary(self) -> dict:
        return {
            "passes": self.passes_completed,
            "was_refined": self.was_refined,
            "final_confidence": round(self.final_confidence, 3),
            "stages": [s.to_summary() for s in self.stages],
            "total_duration_ms": self.total_duration_ms,
        }


# ── Model Override Context Manager ────────────────────────────────────────────

class _TemporaryModelOverride:
    """Temporarily change settings.openai_model for one AI call.

    CloudBackend._generate_openai() reads settings.openai_model to decide
    which Ollama model to call. This context manager swaps it for a single
    stage, then restores the original value.

    Safe because the pipeline runs all stages sequentially (no concurrency).
    Uses object.__setattr__ to bypass Pydantic's immutable model validation.
    """

    def __init__(self, settings: Settings, model_name: str):
        self._settings = settings
        self._model_name = model_name
        self._original: Optional[str] = None

    def __enter__(self) -> "_TemporaryModelOverride":
        self._original = self._settings.openai_model
        object.__setattr__(self._settings, "openai_model", self._model_name)
        return self

    def __exit__(self, *_) -> None:
        if self._original is not None:
            object.__setattr__(self._settings, "openai_model", self._original)


# ── Critique Prompt Builders ───────────────────────────────────────────────────

def _build_critique_system_prompt(
    diagram_type: DiagramType,
    autosar_compliant: bool = True,
) -> str:
    if not autosar_compliant:
        return f"""You are a senior software architecture reviewer.

Review the provided {diagram_type.value} diagram JSON and identify issues in:
- structural correctness
- requirement traceability coverage
- completeness and naming consistency for a generic C-project design

OUTPUT: Return ONLY a valid JSON object.
{{
  "issues": [
    {{"element": "element_id_or_name", "severity": "error|warning", "description": "what is wrong"}}
  ],
  "quality_score": 0.0,
  "approved": false,
  "missing_elements": [],
  "naming_violations": [],
  "traceability_gaps": []
}}"""

    return f"""You are a senior AUTOSAR software architecture reviewer with expertise in \
ISO 26262 functional safety and AUTOSAR Classic platform standards.

Review the provided {diagram_type.value} diagram JSON and identify ALL issues.

REVIEW CRITERIA:

1. AUTOSAR Compliance:
   - SWC names must follow: SWC_PascalCase  (e.g., SWC_SensorFusion)
   - Runnable names must follow: RE_PascalCase  (e.g., RE_FuseSensorData)
   - Provided ports: PP_PascalCase | Required ports: RP_PascalCase
   - Interface names: IF_SR_Name (Sender-Receiver) or IF_CS_Name (Client-Server)
   - RTE API: Rte_Read/Rte_Write for SR communication; Rte_Call/Rte_Result for CS
   - Rte_Read MUST come FROM an R-Port (RP_); Rte_Write MUST go TO a P-Port (PP_)

2. Completeness:
   - Every requirement ID in the input must be traceable to at least one element
   - Every SWC must have at least one Runnable (operation)
   - State machines must have exactly one initial state

3. Structural Correctness:
   - No orphan lifelines with zero messages in sequence diagrams
   - Every port in a component diagram must participate in at least one connector
   - Confidence scores (0.0–1.0) must be present on every element

4. Traceability:
   - Every diagram element must have trace_req or trace_reqs populated
   - No element may reference a requirement ID not present in the requirements list

OUTPUT: Return ONLY a valid JSON object — no explanation, no markdown outside the JSON.
{{
  "issues": [
    {{"element": "element_id_or_name", "severity": "error|warning", "description": "what is wrong"}}
  ],
  "quality_score": 0.0,
  "approved": false,
  "missing_elements": ["description of what should be added"],
  "naming_violations": ["element_name: expected SWC_PascalCase, got SomeName"],
  "traceability_gaps": ["REQ-ID-that-has-no-traced-element"]
}}

SCORING:
  1.0   — Perfect, no issues
  0.8+  — Minor warnings only → set approved=true
  0.6–0.8 — Several warnings → set approved=false
  0.4–0.6 — Errors present → set approved=false
  <0.4  — Major structural problems → set approved=false

Set approved=true ONLY when quality_score >= 0.75 AND there are zero severity="error" issues."""


def _build_critique_user_prompt(
    draft_result: GenerationResult,
    requirements: list[Requirement],
    diagram_type: DiagramType,
    autosar_compliant: bool = True,
) -> str:
    diagrams_json = [
        d.model_dump(mode="json", exclude_none=True)
        for d in draft_result.diagrams
    ]
    draft_str = json.dumps(
        diagrams_json[0] if len(diagrams_json) == 1 else diagrams_json,
        indent=2,
    )
    reqs_text = "\n".join(
        f"[{r.req_id}] ({r.req_type.value if hasattr(r.req_type, 'value') else r.req_type})"
        f" {r.title or ''}: {r.description or ''}"
        for r in requirements
    )
    domain = "AUTOSAR" if autosar_compliant else "generic C-project"
    return (
        f"Review this {domain} {diagram_type.value} diagram JSON.\n\n"
        f"REQUIREMENTS (all must be traced):\n{reqs_text}\n\n"
        f"GENERATED DIAGRAM JSON:\n{draft_str}\n\n"
        "Identify all issues. Output only the JSON review result — no other text."
    )


def _build_refinement_user_prompt(
    draft_result: GenerationResult,
    critique: CritiqueResult,
    requirements: list[Requirement],
    diagram_type: DiagramType,
    autosar_compliant: bool = True,
) -> str:
    diagrams_json = [
        d.model_dump(mode="json", exclude_none=True)
        for d in draft_result.diagrams
    ]
    draft_str = json.dumps(
        diagrams_json[0] if len(diagrams_json) == 1 else diagrams_json,
        indent=2,
    )

    issues_text = "\n".join(
        f"  [{i.get('severity','warning').upper()}] {i.get('element','?')}: {i.get('description','')}"
        for i in critique.issues
    ) or "  None"

    missing_text = "\n".join(f"  - {m}" for m in critique.missing_elements) or "  None"
    naming_text  = "\n".join(f"  - {n}" for n in critique.naming_violations) or "  None"
    trace_text   = "\n".join(f"  - {t}" for t in critique.traceability_gaps) or "  None"

    reqs_text = "\n".join(
        f"[{r.req_id}] ({r.req_type.value if hasattr(r.req_type, 'value') else r.req_type})"
        f" {r.title or ''}: {r.description or ''}"
        for r in requirements
    )

    domain = "AUTOSAR" if autosar_compliant else "generic C-project"
    return (
        f"Fix ALL issues listed below in this {domain} {diagram_type.value} diagram JSON.\n\n"
        f"REQUIREMENTS (trace every element back to these):\n{reqs_text}\n\n"
        f"CURRENT DIAGRAM JSON (fix this):\n{draft_str}\n\n"
        f"ISSUES TO FIX:\n{issues_text}\n\n"
        f"MISSING ELEMENTS TO ADD:\n{missing_text}\n\n"
        f"NAMING VIOLATIONS TO CORRECT:\n{naming_text}\n\n"
        f"TRACEABILITY GAPS (add trace_req for each):\n{trace_text}\n\n"
        "Output ONLY the corrected JSON diagram — apply ALL fixes above.\n"
        "Do not change elements that were not flagged. No explanation, no markdown."
    )


# ── Critique Response Parser ───────────────────────────────────────────────────

def _parse_critique_response(text: str) -> CritiqueResult:
    """Extract JSON critique from AI response text.

    Mirrors orchestrator._extract_json() — tries direct parse, then markdown
    code block, then boundary scan. On complete failure returns a low-confidence
    unapproved result so the pipeline can continue with the draft.
    """
    text = text.strip()

    def _try_parse(s: str) -> Optional[dict]:
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None

    # 1. Direct parse
    raw = _try_parse(text)

    # 2. Markdown code block
    if raw is None:
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if m:
            raw = _try_parse(m.group(1).strip())

    # 3. Boundary scan for first JSON object
    if raw is None:
        start = text.find("{")
        end   = text.rfind("}")
        if start != -1 and end > start:
            raw = _try_parse(text[start: end + 1])

    if raw is None:
        logger.warning("Critique response could not be parsed as JSON; using fallback")
        return CritiqueResult(raw_text=text, quality_score=0.3, approved=False)

    return CritiqueResult(
        issues=raw.get("issues", []),
        quality_score=float(raw.get("quality_score", 0.0)),
        approved=bool(raw.get("approved", False)),
        missing_elements=raw.get("missing_elements", []),
        naming_violations=raw.get("naming_violations", []),
        traceability_gaps=raw.get("traceability_gaps", []),
        raw_text=text,
    )


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────

class PipelineOrchestrator:
    """Multi-stage diagram generation with draft → critique → refine loop.

    Wraps the existing AIOrchestrator — does NOT replace it.
    All actual AI inference still goes through orchestrator.generate_diagram()
    and orchestrator._parse_response() / orchestrator._get_backend().
    """

    def __init__(self, settings: Settings, orchestrator) -> None:
        # orchestrator: AIOrchestrator (avoid circular import with type annotation)
        self.settings = settings
        self.orchestrator = orchestrator

    async def generate_with_pipeline(
        self,
        requirements: list[Requirement],
        diagram_types: list[DiagramType],
        config: PipelineConfig,
        module_context: Optional[str] = None,
        existing_swcs: Optional[list[str]] = None,
    ) -> list[PipelineGenerationResult]:
        """Run multi-stage generation for all requested diagram types sequentially.

        Returns one PipelineGenerationResult per diagram type.
        """
        results: list[PipelineGenerationResult] = []
        for dt in diagram_types:
            pr = await self._run_pipeline_for_type(
                dt, requirements, config, module_context, existing_swcs
            )
            results.append(pr)
        return results

    async def _run_pipeline_for_type(
        self,
        diagram_type: DiagramType,
        requirements: list[Requirement],
        config: PipelineConfig,
        module_context: Optional[str],
        existing_swcs: Optional[list[str]],
    ) -> PipelineGenerationResult:
        start = time.monotonic()
        stages: list[StageResult] = []

        # ── SINGLE_PASS: delegate entirely to existing orchestrator ──────────
        if config.mode == PipelineMode.SINGLE_PASS:
            gen = await self.orchestrator.generate_diagram(
                diagram_type, requirements, module_context, existing_swcs,
                temperature=config.draft_temperature,
                generation_profile=config.generation_profile,
                activity_label_style=config.activity_label_style,
                autosar_compliant=config.autosar_compliant,
                elaborated_data=config.elaborated_data,
            )
            return PipelineGenerationResult(
                diagram_type=diagram_type,
                final_result=gen,
                stages=[StageResult(
                    stage_name="draft",
                    model_used=config.generator_model,
                    diagram_result=gen,
                    critique=None,
                    duration_ms=gen.total_generation_time_ms or 0,
                )],
                total_duration_ms=int((time.monotonic() - start) * 1000),
                pipeline_mode=config.mode,
                passes_completed=1,
            )

        # ── MULTI-STAGE PIPELINE ─────────────────────────────────────────────

        # Stage 1: Draft
        logger.info(f"[Pipeline:{diagram_type.value}] Stage 1 — DRAFT ({config.generator_model})")
        draft_stage = await self._run_draft_stage(
            diagram_type, requirements, config, module_context, existing_swcs
        )
        stages.append(draft_stage)

        if draft_stage.error and not draft_stage.diagram_result:
            return PipelineGenerationResult(
                diagram_type=diagram_type,
                final_result=GenerationResult(
                    errors=[draft_stage.error or "Draft stage failed"],
                    analyzed_requirements=[r.req_id for r in requirements],
                ),
                stages=stages,
                total_duration_ms=int((time.monotonic() - start) * 1000),
                pipeline_mode=config.mode,
                passes_completed=0,
            )

        current_result = draft_stage.diagram_result  # type: ignore[assignment]

        # Early exit: draft confidence already above threshold
        draft_conf = self._extract_confidence(current_result)
        if draft_conf >= config.min_confidence:
            logger.info(
                f"[Pipeline:{diagram_type.value}] Draft confidence {draft_conf:.2f} "
                f">= {config.min_confidence:.2f} — skipping critique/refine"
            )
            stages.append(StageResult(
                stage_name="critique", model_used="skipped",
                diagram_result=None, critique=None, duration_ms=0, skipped=True,
            ))
            return PipelineGenerationResult(
                diagram_type=diagram_type, final_result=current_result,
                stages=stages,
                total_duration_ms=int((time.monotonic() - start) * 1000),
                pipeline_mode=config.mode, passes_completed=1,
            )

        # Stage 2 + 3: Critique-Refinement loop with convergence tracking
        final_result = current_result
        passes = 0
        prev_issue_count: Optional[int] = None

        for pass_num in range(1, config.max_passes + 1):
            passes = pass_num

            # Determine reviewer model
            reviewer = (
                config.generator_model           # multi_pass: same model, different prompt
                if config.mode == PipelineMode.MULTI_PASS
                else config.reviewer_model        # llama3.2 or mistral
            )

            logger.info(
                f"[Pipeline:{diagram_type.value}] Stage 2 — CRITIQUE pass {pass_num}/{config.max_passes}"
                f" ({reviewer})"
            )
            critique_stage = await self._run_critique_stage(
                diagram_type, current_result, requirements, config, reviewer, pass_num
            )
            stages.append(critique_stage)

            if critique_stage.error or not critique_stage.critique:
                logger.warning(
                    f"[Pipeline:{diagram_type.value}] Critique failed: {critique_stage.error} "
                    "— keeping draft result"
                )
                break

            critique = critique_stage.critique
            current_issue_count = len(critique.issues)

            # Early exit: critique approved
            if critique.approved and critique.quality_score >= config.min_confidence:
                logger.info(
                    f"[Pipeline:{diagram_type.value}] Critique approved "
                    f"(score={critique.quality_score:.2f}) — skipping refinement"
                )
                stages.append(StageResult(
                    stage_name="refinement", model_used="skipped",
                    diagram_result=None, critique=None, duration_ms=0, skipped=True,
                ))
                break

            # Convergence check: if issues are not decreasing, stop early
            if prev_issue_count is not None and current_issue_count >= prev_issue_count:
                logger.warning(
                    f"[Pipeline:{diagram_type.value}] Convergence stalled: "
                    f"pass {pass_num} has {current_issue_count} issues "
                    f"(prev: {prev_issue_count}) — stopping refinement"
                )
                break
            prev_issue_count = current_issue_count

            # Adaptive temperature: adjust refinement temp based on critique findings
            refine_temp = self._adaptive_temperature(critique, config, pass_num)

            logger.info(
                f"[Pipeline:{diagram_type.value}] Stage 3 — REFINEMENT pass {pass_num} "
                f"({config.generator_model}), {current_issue_count} issue(s), temp={refine_temp:.2f}"
            )
            refine_stage = await self._run_refinement_stage(
                diagram_type, current_result, critique, requirements, config, pass_num,
                temperature_override=refine_temp,
            )
            stages.append(refine_stage)

            if refine_stage.diagram_result and not refine_stage.error:
                final_result = refine_stage.diagram_result
                current_result = final_result
                logger.info(
                    f"[Pipeline:{diagram_type.value}] Refinement pass {pass_num} complete, "
                    f"confidence={self._extract_confidence(final_result):.2f}"
                )
            else:
                logger.warning(
                    f"[Pipeline:{diagram_type.value}] Refinement failed: {refine_stage.error} "
                    "— keeping previous result"
                )
                break

        return PipelineGenerationResult(
            diagram_type=diagram_type,
            final_result=final_result,
            stages=stages,
            total_duration_ms=int((time.monotonic() - start) * 1000),
            pipeline_mode=config.mode,
            passes_completed=passes,
        )

    # ── Internal stage runners ────────────────────────────────────────────────

    async def _run_draft_stage(
        self,
        diagram_type: DiagramType,
        requirements: list[Requirement],
        config: PipelineConfig,
        module_context: Optional[str],
        existing_swcs: Optional[list[str]],
    ) -> StageResult:
        t0 = time.monotonic()
        try:
            with _TemporaryModelOverride(self.settings, config.generator_model):
                result = await self.orchestrator.generate_diagram(
                    diagram_type, requirements, module_context, existing_swcs,
                    temperature=config.draft_temperature,
                    generation_profile=config.generation_profile,
                    activity_label_style=config.activity_label_style,
                    autosar_compliant=config.autosar_compliant,
                    elaborated_data=config.elaborated_data,
                )
            return StageResult(
                stage_name="draft",
                model_used=config.generator_model,
                diagram_result=result,
                critique=None,
                duration_ms=int((time.monotonic() - t0) * 1000),
                error="; ".join(result.errors) if result.errors else None,
            )
        except Exception as exc:
            logger.error(f"Draft stage exception: {exc}")
            return StageResult(
                stage_name="draft", model_used=config.generator_model,
                diagram_result=None, critique=None,
                duration_ms=int((time.monotonic() - t0) * 1000),
                error=str(exc),
            )

    async def _run_critique_stage(
        self,
        diagram_type: DiagramType,
        draft_result: GenerationResult,
        requirements: list[Requirement],
        config: PipelineConfig,
        reviewer_model: str,
        pass_num: int,
    ) -> StageResult:
        t0 = time.monotonic()
        try:
            system_prompt = _build_critique_system_prompt(
                diagram_type, autosar_compliant=config.autosar_compliant
            )
            user_prompt = _build_critique_user_prompt(
                draft_result,
                requirements,
                diagram_type,
                autosar_compliant=config.autosar_compliant,
            )

            # Inject real validation results so the AI reviewer sees actual
            # structural / AUTOSAR issues, not just generic rules.
            req_ids = [r.req_id for r in requirements]
            real_issues: list[str] = []
            try:
                real_issues.extend(StructuralValidator.validate_quick(draft_result))
            except Exception:
                pass
            if config.autosar_compliant:
                try:
                    real_issues.extend(
                        AUTOSARValidator(self.settings).validate_quick(draft_result, req_ids)
                    )
                except Exception:
                    pass
            if real_issues:
                issues_block = "\n".join(f"  - {v}" for v in real_issues[:20])
                user_prompt += (
                    f"\n\nAUTOMATED VALIDATION RESULTS (must be addressed):\n"
                    f"{issues_block}\n"
                    "Include these automated findings in your review."
                )

            backend = self.orchestrator._get_backend()
            with _TemporaryModelOverride(self.settings, reviewer_model):
                response: AIResponse = await backend.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=2048,  # critique is shorter than generation
                    temperature=config.critique_temperature,
                )

            critique = _parse_critique_response(response.content)
            logger.info(
                f"[Pipeline] Critique result: approved={critique.approved}, "
                f"score={critique.quality_score:.2f}, issues={len(critique.issues)}"
            )
            return StageResult(
                stage_name="critique", model_used=reviewer_model,
                diagram_result=None, critique=critique,
                duration_ms=int((time.monotonic() - t0) * 1000),
                error=None, skipped=False,
            )
        except Exception as exc:
            logger.error(f"Critique stage exception: {exc}")
            return StageResult(
                stage_name="critique", model_used=reviewer_model,
                diagram_result=None, critique=None,
                duration_ms=int((time.monotonic() - t0) * 1000),
                error=str(exc),
            )

    @staticmethod
    def _adaptive_temperature(
        critique: CritiqueResult,
        config: PipelineConfig,
        pass_num: int,
    ) -> float:
        """Compute refinement temperature based on critique findings and pass number.

        Strategy:
          - Naming violations → lower temp (precise corrections)
          - Missing elements  → higher temp (creative additions)
          - Later passes      → progressively lower (converge)
        """
        base = config.refine_temperature  # default 0.15

        if critique.naming_violations:
            base = min(base, 0.12)
        elif critique.missing_elements:
            base = max(base, 0.25)

        # Converge: reduce temperature by 0.03 per pass beyond the first
        base = max(0.05, base - 0.03 * (pass_num - 1))

        return round(base, 2)

    async def _run_refinement_stage(
        self,
        diagram_type: DiagramType,
        draft_result: GenerationResult,
        critique: CritiqueResult,
        requirements: list[Requirement],
        config: PipelineConfig,
        pass_num: int,
        temperature_override: Optional[float] = None,
    ) -> StageResult:
        t0 = time.monotonic()
        refine_temp = temperature_override if temperature_override is not None else config.refine_temperature
        try:
            # Reuse existing YAML system prompt for the refiner (same domain knowledge)
            system_prompt = self.orchestrator.prompt_engine.render_system_prompt(
                diagram_type,
                naming_conventions={
                    "swc_regex":      self.settings.swc_naming_regex,
                    "runnable_regex": self.settings.runnable_naming_regex,
                    "port_regex":     self.settings.port_naming_regex,
                },
                profile=config.generation_profile,
                activity_label_style=config.activity_label_style,
            )
            user_prompt = _build_refinement_user_prompt(
                draft_result,
                critique,
                requirements,
                diagram_type,
                autosar_compliant=config.autosar_compliant,
            )
            prompt_hash = self.orchestrator.prompt_engine.compute_prompt_hash(
                system_prompt, user_prompt
            )

            backend = self.orchestrator._get_backend()
            with _TemporaryModelOverride(self.settings, config.generator_model):
                response: AIResponse = await backend.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=config.max_tokens,
                    temperature=refine_temp,
                )

            # Parse refined output using the orchestrator's existing parser
            refined = self.orchestrator._parse_response(
                response, diagram_type, prompt_hash,
                config.generator_model,
                req_ids=[r.req_id for r in requirements],
            )
            return StageResult(
                stage_name="refinement", model_used=config.generator_model,
                diagram_result=refined, critique=None,
                duration_ms=int((time.monotonic() - t0) * 1000),
                error="; ".join(refined.errors) if refined.errors else None,
            )
        except Exception as exc:
            logger.error(f"Refinement stage exception: {exc}")
            return StageResult(
                stage_name="refinement", model_used=config.generator_model,
                diagram_result=None, critique=None,
                duration_ms=int((time.monotonic() - t0) * 1000),
                error=str(exc),
            )

    # ── Utility ───────────────────────────────────────────────────────────────

    def _extract_confidence(self, result: GenerationResult) -> float:
        """Return average provenance.confidence across all diagrams in a result."""
        scores = []
        for d in result.diagrams:
            if d.provenance and d.provenance.confidence is not None:
                scores.append(d.provenance.confidence)
        return sum(scores) / len(scores) if scores else 0.0


# ── Helper used by routes.py ──────────────────────────────────────────────────

def merge_pipeline_results(
    pipeline_results: list[PipelineGenerationResult],
    requirement_ids: list[str],
) -> tuple[GenerationResult, dict]:
    """Flatten per-diagram PipelineGenerationResults into a single GenerationResult
    plus a pipeline_summary dict suitable for the API response.

    Returns: (merged_result, pipeline_summary)
    """
    merged = GenerationResult(analyzed_requirements=requirement_ids)
    summaries: dict[str, dict] = {}

    for pr in pipeline_results:
        merged.diagrams.extend(pr.final_result.diagrams)
        merged.warnings.extend(pr.final_result.warnings)
        merged.errors.extend(pr.final_result.errors)
        if pr.final_result.module_assignments:
            if merged.module_assignments is None:
                merged.module_assignments = {}
            merged.module_assignments.update(pr.final_result.module_assignments)
        summaries[pr.diagram_type.value] = pr.to_summary()

    if pipeline_results:
        merged.total_generation_time_ms = sum(
            pr.total_duration_ms for pr in pipeline_results
        )

    pipeline_summary = {
        "mode": pipeline_results[0].pipeline_mode.value if pipeline_results else "single_pass",
        "diagrams": summaries,
    }
    return merged, pipeline_summary
