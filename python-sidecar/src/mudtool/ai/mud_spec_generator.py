"""MUD Spec Generator — generates detailed Module Unit Design specification docs.

Stage 2 of the enhanced MUD workflow:
  1. User selects one SWC from the module list produced by ModulePlanner
  2. MudSpecGenerator calls AI with ALL architectural requirements as context
     but focuses the generation on the selected module only
  3. Produces a rich Markdown file covering:
       - Interfaces (P-Ports, R-Ports with interface names)
       - Data types and signal ranges
       - Runnables (trigger type, period, ASIL)
       - Inter-Runnable Variables (IRV) and ExclusiveAreas
       - Calibration Parameters (CalPrm)
       - Functional description per runnable
  4. Stage 2b: AI reviewer pass — full issue report persisted in SpecReviewResult
  5. Stage 2c: AI-driven regeneration — fixes every issue from the review report
               and produces an improved MUD spec (iterative until approved or max rounds)

Produced document is consumed directly by Stage 3 (diagram generation pipeline).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

# ── Generation system prompt ─────────────────────────────────────────────────

_GEN_SYSTEM_PROMPT = """You are an expert AUTOSAR software architect producing Module Unit
Design (MUD) specifications.

Your output is a detailed Markdown document for ONE Software Component.
Structure it EXACTLY as shown below — do not add or remove sections.

════════════════════════════════════════════════
# MUD Spec: {swc_name}

## 1. Overview
| Field | Value |
|-------|-------|
| SWC Name | {swc_name} |
| ASIL Level | <ASIL-X or QM> |
| Complexity | <low / medium / high> |
| Description | <one-sentence purpose> |

## 2. Ports
### 2.1 Provided Ports (P-Ports)
| Port Name | Interface | Data Element | Data Type | Range / Unit | Period | Description |
|-----------|-----------|--------------|-----------|--------------|--------|-------------|
| PP_TorqueOut | IF_SR_Torque | DE_MotorTorque | float32 | −100–100 Nm | 10 ms | Motor torque command |

### 2.2 Required Ports (R-Ports)
| Port Name | Interface | Data Element | Data Type | Range / Unit | Provider | Description |
|-----------|-----------|--------------|-----------|--------------|----------|-------------|
| RP_SteerAngle | IF_SR_Steering | DE_SteerAngle | float32 | −540–540 deg | SWC_Sensors | Steering wheel angle |

### 2.3 Calibration Ports (CalPrm)
| Port Name | Interface | Data Type | Default | Range | Description |
|-----------|-----------|-----------|---------|-------|-------------|
| RP_CalPrm_TorqueGain | IF_Prm_Torque | float32 | 1.0 | 0.1–5.0 | Torque gain factor |

## 3. Runnables

### 3.1 Main Runnables (OS-scheduled via AUTOSAR RTE)
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Init | Init | — | QM | Module initialisation — restores NvM state, sets IRV defaults |
| RE_Control | Cyclic | 10 ms | ASIL-D | Main control loop — reads sensors, computes and writes output |

### 3.2 Sub-Functions (internal C helpers called by main runnables)
| Function | Called By | Description |
|----------|-----------|-------------|
| ReadSensorInputs() | RE_Control | Reads all RP_ port signals into local variables |
| ValidateInputs() | RE_Control | Range-checks all read values against CalPrm limits |
| ComputeOutput() | RE_Control | Applies control algorithm using IRVs and CalPrm |

## 4. Inter-Runnable Variables (IRV)
| IRV Name | Data Type | Producer Runnable | Consumer Runnable | ExclusiveArea? | Description |
|----------|-----------|-------------------|-------------------|----------------|-------------|
| irvTorqueSetpoint | float32 | RE_Init | RE_Control | — | Initialised torque target (Nm) |
| irvFilteredTorque | float32 | RE_Control | RE_Control | EA_TorqueData | Low-pass filtered torque output |

## 5. Data Types
| Type Name | Base Type | Range | Unit | Description |
|-----------|-----------|-------|------|-------------|
| Torque_t | float32 | −100–100 | Nm | Motor torque value |
| Angle_t | float32 | −540–540 | deg | Steering wheel angle |

## 6. Error Handling & Safety
<Describe ASIL decomposition, DEM event IDs (format: SWC_DEM_E_FAULT_NAME), safe-state output
values for all ASIL-C/D runnables, redundancy mechanisms, and fault reaction strategies>

## 7. Functional Description

### RE_Init
// Reads:  RP_NvM_State
// Writes: PP_InitStatus
// IRVs produced: irvTorqueSetpoint, irvModuleStatus
// CalPrm used:   RP_CalPrm_DefaultTorque

1. Rte_Read(RP_NvM_State, &nvmState);
   if (nvmState == NVM_VALID) → irvTorqueSetpoint = nvmState.lastTorque (Nm)
   else → irvTorqueSetpoint = RP_CalPrm_DefaultTorque.value (default: 0.0 Nm)
2. Validate irvTorqueSetpoint ∈ [−100.0, 100.0] Nm; clamp to safe range if violated
3. Rte_Write(PP_InitStatus, INIT_DONE); irvModuleStatus = STATUS_READY
4. On error: Dem_ReportErrorStatus(SWC_DEM_E_INIT_FAIL, DEM_EVENT_STATUS_FAILED);
             Rte_Write(PP_InitStatus, INIT_FAIL); irvModuleStatus = STATUS_ERROR

### RE_Control
// Reads:  RP_SteerAngle, RP_MotorCurrent
// Writes: PP_TorqueOut
// IRVs consumed: irvTorqueSetpoint, irvModuleStatus
// IRVs produced: irvFilteredTorque
// CalPrm used:   RP_CalPrm_TorqueGain, RP_CalPrm_CurrentLimit

1. ReadSensorInputs(): Rte_Read(RP_SteerAngle, &steerAngle);
                       Rte_Read(RP_MotorCurrent, &motorCurrent)
2. ValidateInputs(): if steerAngle ∉ [−540, 540] deg OR motorCurrent > RP_CalPrm_CurrentLimit
                     → SAFE_STATE: Rte_Write(PP_TorqueOut, 0.0 Nm);
                                    Dem_ReportErrorStatus(SWC_DEM_E_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED)
3. ComputeOutput(): torqueCmd = steerAngle × RP_CalPrm_TorqueGain + irvTorqueSetpoint
                    irvFilteredTorque = LowPassFilter(torqueCmd, RP_CalPrm_FilterCoeff)
4. Rte_Write(PP_TorqueOut, clamp(irvFilteredTorque, −100.0, 100.0 Nm))
════════════════════════════════════════════════

RULES:
- Use AUTOSAR naming: SWC_PascalCase, RE_PascalCase, PP_/RP_ ports,
  IF_SR_/IF_CS_/IF_Prm_ interfaces, EA_ ExclusiveAreas, DEM event IDs (SWC_DEM_E_*)
- Section 3.1: include ALL OS-scheduled runnables — at minimum RE_Init + one RE_Cyclic
- Section 3.2: include ALL internal helper functions called by those runnables
- Section 7 MUST use the pseudo-code format shown above for EVERY runnable in Section 3.1:
    * // Reads / Writes / IRVs consumed / IRVs produced / CalPrm used — header comment block
    * Numbered steps using Rte_Read/Rte_Write with actual port/signal names from Section 2
    * SAFE_STATE output value (0 or fail-safe) for every ASIL-C/D validation step
    * Dem_ReportErrorStatus() call with named DEM event ID on every error path
    * Sub-function calls (e.g. ReadSensorInputs()) referencing names from Section 3.2
- Signal ranges must use engineering units (Nm, deg, m/s, %, A, V)
- Every CalPrm must have a default value and valid range in Section 2.3
- If an IRV is shared between runnables in different OS tasks, list the ExclusiveArea name
- Do NOT output JSON — output ONLY the Markdown document above
"""

_GEN_USER_PROMPT_TMPL = """Generate the MUD specification document for SWC: {swc_name}

MODULE CONTEXT:
- SWC Name: {swc_name}
- Description: {description}
- ASIL Level: {asil}
- Detected Runnables: {runnables}
- Linked Requirement IDs: {req_ids}

ALL ARCHITECTURAL REQUIREMENTS (use as context):
{requirements_text}

Focus ONLY on {swc_name}. Use the other SWC requirements only to determine
interface partners and port names.

Output the Markdown document. No JSON. No code fences around the document."""

# ── Review system prompt ─────────────────────────────────────────────────────

_REVIEW_SYSTEM_PROMPT = """You are an AUTOSAR MUD specification reviewer.
Output ONLY a single JSON object — no markdown fences, no prose, no explanations.
Start your response with { and end with }.

JSON structure (fill in EVERY field — do not omit any):
{
  "approved": false,
  "coverage_pct": 45,
  "uncovered_req_ids": ["REQ-003", "REQ-007"],
  "coverage_gaps": [
    "REQ-003 (Torque limit enforcement): Section 7 RE_Control does not mention max torque clamping or CalPrm_TorqueMax",
    "REQ-007 (NvM persistence): RE_Init has no Rte_Read(RP_NvM_State) call or NvM restore logic"
  ],
  "issues": [
    {"severity": "error", "section": "3.1", "message": "RE_Control missing ASIL level in table"},
    {"severity": "warning", "section": "2.1", "message": "PP_TorqueOut port lacks physical unit in Range column"}
  ],
  "suggestions": [
    "Add Rte_Read(RP_NvM_State) in RE_Init step 1 to restore irvTorqueSetpoint from NvM",
    "Add torque clamping step in RE_Control using RP_CalPrm_TorqueMax (default: 100.0 Nm)",
    "Add DEM event ID SWC_DEM_E_SENSOR_FAIL to Section 6 and reference it in RE_Control step 2"
  ]
}

REVIEW RULES — follow all:
- coverage_pct: integer 0-100. For EACH requirement ID in the list, read Section 7 pseudo-code.
  If the requirement's described behaviour appears in any runnable's numbered steps → covered (+1).
  If not found anywhere in Section 7 → uncovered. coverage_pct = covered_count / total_count × 100.
- uncovered_req_ids: list EVERY requirement ID you could NOT find addressed in Section 7.
  Empty list [] means all requirements are covered.
- coverage_gaps: for EACH uncovered ID write exactly one sentence: what logic is absent and
  which runnable/section should contain it. Length must match uncovered_req_ids.
- approved: true ONLY if coverage_pct >= 80 AND zero "error" severity issues.
- issues: concrete structural problems. "error" = missing required field/section.
  "warning" = incomplete or ambiguous. "info" = style/naming.
- suggestions: 3-5 SPECIFIC improvement actions naming section, port, runnable, or CalPrm.
  Never leave this list empty."""

_REVIEW_USER_PROMPT_TMPL = """Review this MUD specification against the requirements.

MODULE: {swc_name}
ASIL: {asil}
REQUIREMENT IDs TO COVER: {req_ids}

ALL REQUIREMENTS (for context):
{requirements_text}

MUD SPECIFICATION TO REVIEW:
{mud_spec_markdown}

Return the JSON review result."""

# ── Regeneration prompt ───────────────────────────────────────────────────────

_REGEN_SYSTEM_PROMPT = """You are an AUTOSAR MUD specification editor operating in PATCH MODE.

You will receive:
  - A CURRENT MUD SPEC (the base document — already partially correct)
  - A REVIEW REPORT listing specific issues to fix
  - A list of UNCOVERED REQUIREMENT IDs that must now be addressed in Section 7

PATCH MODE RULES — follow ALL of these exactly:
1. Output the COMPLETE document from "# MUD Spec:" to the final line.
2. Copy EVERY section that has NO listed issues CHARACTER-FOR-CHARACTER from the current spec.
3. ONLY modify the specific sections/fields referenced in the ERRORS and WARNINGS below.
4. For each UNCOVERED REQUIREMENT: add the missing logic to Section 7 of the most relevant
   runnable's pseudo-code steps — do NOT invent new runnables or restructure the document.
5. Apply each SUGGESTION by making the minimum targeted change it describes — do not rewrite.
6. Do NOT expand, improve, or rewrite any section that is not explicitly broken.
7. The output MUST be structurally identical to the current spec with only the fixes applied.
8. Output ONLY the Markdown document — no JSON, no code fences, no commentary before or after.
"""

_REGEN_USER_PROMPT_TMPL = """You are patching a MUD specification. Apply ONLY the fixes listed below.
Copy all unchanged sections VERBATIM from the current spec.

═══════════════════════════════════════════════
MODULE: {swc_name}   |   ASIL: {asil}
ITERATION: {iteration}   |   Current Coverage: {coverage_pct}%
═══════════════════════════════════════════════

REVIEW REPORT — fix ONLY these items:
Approved: {approved}

ERRORS to fix ({error_count}):
{errors_text}

WARNINGS to fix ({warning_count}):
{warnings_text}

SUGGESTIONS to apply ({suggestion_count}):
{suggestions_text}

UNCOVERED REQUIREMENT IDs — add their logic to Section 7 ({uncovered_count} uncovered):
{uncovered_req_ids_text}

COVERAGE GAPS — what is missing per requirement:
{coverage_gaps_text}

═══════════════════════════════════════════════
REQUIREMENTS (context — only add logic explicitly listed in coverage gaps above):
{requirements_text}

═══════════════════════════════════════════════
CURRENT MUD SPECIFICATION — PATCH THIS DOCUMENT (copy unchanged sections verbatim):
{mud_spec_markdown}

PATCH MODE: Output the complete document. Copy every section that has no issue verbatim.
Only change the sections addressed in the ERRORS, WARNINGS, SUGGESTIONS, and COVERAGE GAPS above."""

# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class ReviewIssue:
    severity: str  # error | warning | info
    section: str
    message: str

    def to_dict(self) -> dict:
        return {"severity": self.severity, "section": self.section, "message": self.message}


@dataclass
class SpecReviewResult:
    approved: bool
    coverage_pct: int
    issues: list[ReviewIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    uncovered_req_ids: list[str] = field(default_factory=list)  # IDs not found in Section 7
    coverage_gaps: list[str] = field(default_factory=list)       # one explanation per uncovered ID
    raw_response: str = ""
    iteration: int = 1          # which generation round produced the spec that was reviewed
    error_count: int = 0        # computed on first access
    warning_count: int = 0
    info_count: int = 0

    def __post_init__(self):
        self.error_count   = sum(1 for i in self.issues if i.severity == "error")
        self.warning_count = sum(1 for i in self.issues if i.severity == "warning")
        self.info_count    = sum(1 for i in self.issues if i.severity == "info")

    def issues_by_severity(self) -> dict[str, list[ReviewIssue]]:
        result: dict[str, list[ReviewIssue]] = {"error": [], "warning": [], "info": []}
        for issue in self.issues:
            result.setdefault(issue.severity, []).append(issue)
        return result

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "coverage_pct": self.coverage_pct,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": self.suggestions,
            "uncovered_req_ids": self.uncovered_req_ids,
            "coverage_gaps": self.coverage_gaps,
            "iteration": self.iteration,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
        }

    @classmethod
    def from_dict(cls, d: dict, raw: str = "", iteration: int = 1) -> "SpecReviewResult":
        return cls(
            approved=bool(d.get("approved", False)),
            coverage_pct=int(d.get("coverage_pct", 0)),
            issues=[
                ReviewIssue(
                    severity=i.get("severity", "info"),
                    section=i.get("section", ""),
                    message=i.get("message", ""),
                )
                for i in d.get("issues", [])
            ],
            suggestions=d.get("suggestions", []),
            uncovered_req_ids=d.get("uncovered_req_ids", []),
            coverage_gaps=d.get("coverage_gaps", []),
            raw_response=raw,
            iteration=iteration,
        )


# ── Generator class ───────────────────────────────────────────────────────────

class MudSpecGenerator:
    """Generates a Module Unit Design spec Markdown for a single SWC.

    Usage:
        gen = MudSpecGenerator(orchestrator)
        spec_md = await gen.generate_spec(module_info, requirements_text)
        review  = await gen.review_spec(module_info, requirements_text, spec_md)
    """

    def __init__(self, orchestrator):
        self._orchestrator = orchestrator

    async def generate_spec(
        self,
        swc_name: str,
        description: str,
        asil: str,
        runnables: list[str],
        req_ids: list[str],
        requirements_text: str,
        temperature: float = 0.1,
        progress_callback=None,
    ) -> str:
        """Generate the MUD spec Markdown for the selected SWC.

        Args:
            swc_name:           AUTOSAR SWC name (e.g. SWC_SensorFusion)
            description:        One-sentence purpose of the SWC
            asil:               ASIL level (QM / ASIL-A / … / ASIL-D)
            runnables:          List of runnable names detected by ModulePlanner
            req_ids:            Requirement IDs belonging to this SWC
            requirements_text:  Full raw architectural requirements text (all SWCs)
            temperature:        AI sampling temperature
            progress_callback:  Optional callable(dict) for SSE progress events

        Returns:
            The generated MUD spec as a Markdown string.
        """
        if progress_callback:
            progress_callback({
                "stage": "mud_spec",
                "message": f"Connecting to AI for {swc_name}…",
                "progress": 5,
            })

        logger.info("generate_spec: building prompts for %s", swc_name)
        system_prompt = _GEN_SYSTEM_PROMPT.replace("{swc_name}", swc_name)
        user_prompt = _GEN_USER_PROMPT_TMPL.format(
            swc_name=swc_name,
            description=description,
            asil=asil,
            runnables=", ".join(runnables) if runnables else "not yet determined",
            req_ids=", ".join(req_ids) if req_ids else "all",
            requirements_text=requirements_text,
        )
        logger.info(
            "generate_spec: prompt ready for %s — system=%d chars, user=%d chars",
            swc_name, len(system_prompt), len(user_prompt),
        )

        logger.info("generate_spec: calling _get_backend() for %s", swc_name)
        backend = self._orchestrator._get_backend()
        logger.info("generate_spec: backend selected = %s for %s", backend.backend_name, swc_name)

        # ── Token-streaming generation ────────────────────────────────────────
        # Use generate_stream() so tokens appear in the UI as they arrive instead
        # of a silent multi-minute wait.  response_format is intentionally "text"
        # (not "json") — Markdown must NOT be generated with JSON mode enabled.
        import asyncio as _asyncio
        import time as _time

        chunks: list[str] = []
        char_count = 0
        last_progress_chars = 0

        # ── Heartbeat task: fires progress events every 30s while waiting ──
        _first_token_received = False
        _heartbeat_start = _time.monotonic()

        async def _heartbeat():
            """Sends keepalive progress events until the first token arrives."""
            tick = 0
            while not _first_token_received:
                await _asyncio.sleep(15)
                tick += 1
                elapsed = int(_time.monotonic() - _heartbeat_start)
                msg = (
                    f"Waiting for AI response… {elapsed}s elapsed "
                    f"(model: {backend.backend_name})"
                )
                logger.info("generate_spec heartbeat: %s — %s", swc_name, msg)
                if progress_callback:
                    progress_callback({
                        "stage": "mud_spec",
                        "message": msg,
                        "progress": 10,
                        "debug_heartbeat": tick,
                        "debug_elapsed_s": elapsed,
                    })

        _hb_task = _asyncio.ensure_future(_heartbeat())

        try:
            if progress_callback:
                progress_callback({
                    "stage": "mud_spec",
                    "message": f"AI is writing the MUD spec for {swc_name}…",
                    "progress": 10,
                })

            logger.info("generate_spec: calling backend.generate_stream() for %s", swc_name)
            async for chunk in backend.generate_stream(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=6144,
            ):
                if not _first_token_received:
                    _first_token_received = True
                    elapsed = int(_time.monotonic() - _heartbeat_start)
                    logger.info(
                        "generate_spec: FIRST TOKEN received for %s after %ds",
                        swc_name, elapsed,
                    )
                    _hb_task.cancel()

                chunks.append(chunk)
                char_count += len(chunk)

                # Fire a progress event every ~400 chars so the UI shows live text
                if progress_callback and (char_count - last_progress_chars) >= 400:
                    last_progress_chars = char_count
                    partial = "".join(chunks)
                    # Strip any partial <think> block before showing in UI
                    partial_display = re.sub(
                        r"<think>.*?</think>", "", partial, flags=re.DOTALL
                    ).strip()
                    progress_callback({
                        "stage": "mud_spec",
                        "message": f"Generating… {char_count:,} chars",
                        "progress": min(88, 10 + char_count // 80),
                        "partial_content": partial_display,
                    })

            logger.info(
                "generate_spec: stream finished for %s — %d chars total",
                swc_name, char_count,
            )
        except Exception as exc:
            logger.warning(
                "MudSpecGenerator: streaming failed (%s), falling back to non-streaming", exc
            )
            if progress_callback:
                progress_callback({
                    "stage": "mud_spec",
                    "message": "Streaming unavailable — waiting for full response…",
                    "progress": 15,
                })
            # Fallback: single blocking call (still correct, just no live preview)
            logger.warning("generate_spec: streaming failed for %s — fallback to blocking generate(). Reason: %s", swc_name, exc)
            response = await backend.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=6144,
                response_format="text",   # ← no JSON mode for Markdown output
            )
            chunks = [response.content]

        if progress_callback:
            progress_callback({
                "stage": "mud_spec",
                "message": "MUD spec generation complete — finalising…",
                "progress": 92,
            })

        raw = "".join(chunks).strip()

        # Strip residual <think> blocks from reasoning models
        spec_md = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        # Strip accidental code fences around the whole document
        if spec_md.startswith("```"):
            spec_md = re.sub(r"^```[a-z]*\n?", "", spec_md)
            spec_md = re.sub(r"\n?```$", "", spec_md)

        logger.info("MudSpecGenerator: generated %d chars for %s", len(spec_md), swc_name)
        return spec_md

    async def review_spec(
        self,
        swc_name: str,
        asil: str,
        req_ids: list[str],
        requirements_text: str,
        mud_spec_markdown: str,
        temperature: float = 0.1,
        iteration: int = 1,
    ) -> SpecReviewResult:
        """Run an AI review pass on a generated MUD spec.

        Args:
            swc_name:           SWC name for context
            asil:               ASIL level (affects safety checks)
            req_ids:            Requirement IDs that must be covered
            requirements_text:  Full raw architectural requirements
            mud_spec_markdown:  The MUD spec to be reviewed
            temperature:        AI sampling temperature
            iteration:          Which generation round this review is for (1-based)

        Returns:
            SpecReviewResult with approved flag, coverage%, full issue list, and counts.
        """
        # Truncate inputs so the reviewer prompt stays within 7b model context limits.
        # The reviewer only needs enough to assess coverage + identify structural issues.
        _MAX_REQ_CHARS = 3000
        _MAX_SPEC_CHARS = 4000
        req_text_trimmed = (
            requirements_text[:_MAX_REQ_CHARS] + "\n…[truncated]"
            if len(requirements_text) > _MAX_REQ_CHARS else requirements_text
        )
        spec_trimmed = (
            mud_spec_markdown[:_MAX_SPEC_CHARS] + "\n…[truncated]"
            if len(mud_spec_markdown) > _MAX_SPEC_CHARS else mud_spec_markdown
        )

        user_prompt = _REVIEW_USER_PROMPT_TMPL.format(
            swc_name=swc_name,
            asil=asil,
            req_ids=", ".join(req_ids),
            requirements_text=req_text_trimmed,
            mud_spec_markdown=spec_trimmed,
        )

        # Use the reviewer backend (deepseek-r1 or similar reasoning model) so that
        # coverage scoring and issue detection are handled by a model that reasons well.
        backend = self._orchestrator._get_reviewer_backend()
        logger.info(
            "review_spec: using backend=%s for %s (iter=%d), prompt=%d chars",
            backend.backend_name, swc_name, iteration, len(user_prompt),
        )
        response = await backend.generate(
            system_prompt=_REVIEW_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=2048,
            response_format="json",   # ← review always returns structured JSON
        )

        logger.info(
            "review_spec: raw response %d chars for %s: %s…",
            len(response.content), swc_name, response.content[:200].replace("\n", " "),
        )
        return self._parse_review(response.content, iteration=iteration)

    async def regenerate_spec(
        self,
        swc_name: str,
        asil: str,
        requirements_text: str,
        current_spec_markdown: str,
        review: SpecReviewResult,
        temperature: float = 0.05,
        progress_callback=None,
    ) -> str:
        """Regenerate an improved MUD spec by fixing all issues from the review report.

        This implements Stage 2c of the enhanced workflow. The AI receives:
          - The current (imperfect) MUD spec
          - The full structured review report (all errors, warnings, suggestions)
          - The original requirements for context

        It produces a new, improved MUD spec that fixes every issue.

        Args:
            swc_name:               SWC name
            asil:                   ASIL level
            requirements_text:      Full raw requirements
            current_spec_markdown:  The MUD spec produced in the previous iteration
            review:                 SpecReviewResult from review_spec() on current spec
            temperature:            AI sampling temperature
            progress_callback:      Optional callable(dict) for SSE progress events

        Returns:
            Improved MUD spec as a Markdown string.
        """
        if progress_callback:
            progress_callback({
                "stage": "mud_regen",
                "message": (
                    f"Regenerating MUD spec (iteration {review.iteration + 1}) — "
                    f"fixing {review.error_count} error(s), {review.warning_count} warning(s)…"
                ),
                "progress": 10,
                "iteration": review.iteration + 1,
            })

        # Build human-readable issue blocks
        by_sev = review.issues_by_severity()

        def _fmt_issues(issues: list[ReviewIssue]) -> str:
            if not issues:
                return "  (none)"
            return "\n".join(
                f"  [{i.section}] {i.message}" for i in issues
            )

        errors_text      = _fmt_issues(by_sev.get("error", []))
        warnings_text    = _fmt_issues(by_sev.get("warning", []))
        suggestions_text = (
            "\n".join(f"  - {s}" for s in review.suggestions)
            if review.suggestions else "  (none)"
        )
        uncovered_req_ids_text = (
            ", ".join(review.uncovered_req_ids)
            if review.uncovered_req_ids else "  (none — all requirements covered)"
        )
        coverage_gaps_text = (
            "\n".join(f"  - {g}" for g in review.coverage_gaps)
            if review.coverage_gaps else "  (none)"
        )

        user_prompt = _REGEN_USER_PROMPT_TMPL.format(
            swc_name=swc_name,
            asil=asil,
            iteration=review.iteration + 1,
            approved=review.approved,
            coverage_pct=review.coverage_pct,
            error_count=review.error_count,
            warning_count=review.warning_count,
            suggestion_count=len(review.suggestions),
            errors_text=errors_text,
            warnings_text=warnings_text,
            suggestions_text=suggestions_text,
            uncovered_count=len(review.uncovered_req_ids),
            uncovered_req_ids_text=uncovered_req_ids_text,
            coverage_gaps_text=coverage_gaps_text,
            requirements_text=requirements_text,
            mud_spec_markdown=current_spec_markdown,
        )

        backend = self._orchestrator._get_backend()

        # ── Token-streaming regeneration ─────────────────────────────────────
        regen_iter = review.iteration + 1
        chunks: list[str] = []
        char_count = 0
        last_progress_chars = 0

        try:
            logger.info("regenerate_spec: starting for %s (asil=%s, iter=%s)", swc_name, asil, regen_iter)
            async for chunk in backend.generate_stream(
                system_prompt=_REGEN_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=7168,
            ):
                chunks.append(chunk)
                char_count += len(chunk)

                if progress_callback and (char_count - last_progress_chars) >= 400:
                    last_progress_chars = char_count
                    partial = "".join(chunks)
                    partial_display = re.sub(
                        r"<think>.*?</think>", "", partial, flags=re.DOTALL
                    ).strip()
                    progress_callback({
                        "stage": "mud_regen",
                        "message": f"Regenerating… {char_count:,} chars",
                        "progress": min(88, 10 + char_count // 80),
                        "iteration": regen_iter,
                        "partial_content": partial_display,
                    })

        except Exception as exc:
            logger.warning(
                "MudSpecGenerator: regen streaming failed (%s), falling back", exc
            )
            if progress_callback:
                progress_callback({
                    "stage": "mud_regen",
                    "message": "Waiting for full response…",
                    "progress": 15,
                    "iteration": regen_iter,
                })
            logger.warning("regenerate_spec: streaming failed for %s — fallback to blocking generate(). Reason: %s", swc_name, exc)
            response = await backend.generate(
                system_prompt=_REGEN_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=7168,
                response_format="text",   # ← Markdown output, never JSON mode
            )
            chunks = [response.content]

        if progress_callback:
            progress_callback({
                "stage": "mud_regen",
                "message": f"Regeneration complete (iteration {regen_iter})",
                "progress": 92,
                "iteration": regen_iter,
            })

        raw = "".join(chunks).strip()
        spec_md = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        if spec_md.startswith("```"):
            spec_md = re.sub(r"^```[a-z]*\n?", "", spec_md)
            spec_md = re.sub(r"\n?```$", "", spec_md)

        logger.info(
            "MudSpecGenerator: regenerated spec for %s (iteration %d) → %d chars",
            swc_name, regen_iter, len(spec_md),
        )
        return spec_md

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_review(self, raw: str, iteration: int = 1) -> SpecReviewResult:
        """Parse JSON review result from AI response.

        Tries multiple extraction strategies in order:
        1. Strip <think> blocks and code fences, then find outermost {...}
        2. Search for every {...} candidate and try parsing each
        3. If all fail, return a synthetic minimal review so regeneration can still proceed
        """
        if not raw or not raw.strip():
            logger.warning("MudSpecGenerator: empty review response")
            return self._fallback_review(raw, iteration, "AI returned an empty review response")

        # Step 1: clean up the raw response
        # Strip reasoning model think-blocks (backup — cloud_backend already strips them,
        # but the reviewer_backend may use a different code path)
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        # Strip markdown code fences
        cleaned = re.sub(r"```(?:json)?", "", cleaned).strip().rstrip("`").strip()

        # Step 2: try finding the outermost { ... } block
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            candidate = cleaned[start:end]
            try:
                data = json.loads(candidate)
                logger.info(
                    "MudSpecGenerator: review parsed OK — approved=%s coverage=%s issues=%d",
                    data.get("approved"), data.get("coverage_pct"), len(data.get("issues", [])),
                )
                result = SpecReviewResult.from_dict(data, raw=raw, iteration=iteration)
                # Ensure there are always some concrete suggestions for the regeneration step
                if not result.suggestions:
                    result.suggestions = self._auto_suggestions(result)
                return result
            except json.JSONDecodeError:
                pass

        # Step 3: try each {...} substring in the response (handles nested/multiple objects)
        for m in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", cleaned, re.DOTALL):
            try:
                data = json.loads(m.group(0))
                if isinstance(data, dict) and "approved" in data:
                    logger.info(
                        "MudSpecGenerator: review parsed from inner JSON — coverage=%s",
                        data.get("coverage_pct"),
                    )
                    result = SpecReviewResult.from_dict(data, raw=raw, iteration=iteration)
                    if not result.suggestions:
                        result.suggestions = self._auto_suggestions(result)
                    return result
            except json.JSONDecodeError:
                continue

        # Step 4: try to recover partial fields via regex
        logger.warning(
            "MudSpecGenerator: could not parse review JSON — using regex fallback. Raw:\n%s",
            raw[:500],
        )
        coverage_m = re.search(r'"coverage_pct"\s*:\s*(\d+)', cleaned)
        approved_m = re.search(r'"approved"\s*:\s*(true|false)', cleaned, re.IGNORECASE)
        coverage_pct = int(coverage_m.group(1)) if coverage_m else 20
        approved = approved_m.group(1).lower() == "true" if approved_m else False

        return SpecReviewResult(
            approved=approved,
            coverage_pct=coverage_pct,
            issues=[ReviewIssue("warning", "review",
                "AI review response could not be fully parsed — partial data recovered")],
            suggestions=[
                "Ensure Section 7 has numbered functional steps for every runnable in Section 3",
                "Verify all port names follow PP_/RP_ convention with physical signal ranges",
                "Check that ASIL-C/D runnables have SAFE_STATE values and DEM event IDs in Section 6",
            ],
            raw_response=raw,
            iteration=iteration,
        )

    @staticmethod
    def _fallback_review(raw: str, iteration: int, reason: str) -> "SpecReviewResult":
        """Return a safe minimal review so the pipeline can still regenerate."""
        return SpecReviewResult(
            approved=False,
            coverage_pct=0,
            issues=[ReviewIssue("error", "review", reason)],
            suggestions=[
                "Ensure Section 7 has numbered functional steps for every runnable in Section 3",
                "Verify all port names follow PP_/RP_ convention with physical signal ranges",
                "Add DEM event IDs and SAFE_STATE descriptions to Section 6 for ASIL runnables",
            ],
            raw_response=raw or "",
            iteration=iteration,
        )

    @staticmethod
    def _auto_suggestions(result: "SpecReviewResult") -> list[str]:
        """Generate concrete suggestions from issues when the AI omitted the field."""
        suggestions = []
        for issue in result.issues:
            if issue.severity in ("error", "warning"):
                suggestions.append(f"Fix [{issue.section}]: {issue.message}")
        # Always add a minimum set so the regen prompt has something to act on
        if not suggestions:
            suggestions = [
                "Ensure Section 7 has numbered functional steps for every runnable",
                "Verify port naming conventions (PP_/RP_) and add physical units to all ranges",
            ]
        return suggestions[:5]  # cap at 5
