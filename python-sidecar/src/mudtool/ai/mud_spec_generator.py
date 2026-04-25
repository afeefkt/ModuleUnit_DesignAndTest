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
| PP_xxx | IF_SR_xxx | DE_xxx | float32 | 0–100 Nm | 10 ms | ... |

### 2.2 Required Ports (R-Ports)
| Port Name | Interface | Data Element | Data Type | Range / Unit | Provider | Description |
|-----------|-----------|--------------|-----------|--------------|----------|-------------|
| RP_xxx | IF_SR_xxx | DE_xxx | float32 | –100 to 100 | SWC_xxx | ... |

### 2.3 Calibration Ports (CalPrm)
| Port Name | Interface | Data Type | Default | Range | Description |
|-----------|-----------|-----------|---------|-------|-------------|
| RP_CalPrm_xxx | IF_Prm_xxx | float32 | 1.0 | 0.5–2.0 | Gain parameter |

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Init | init | — | QM | Initialise state |
| RE_xxx | cyclic | 10 ms | ASIL-D | Main control loop |

## 4. Inter-Runnable Variables (IRV)
| IRV Name | Data Type | Producer Runnable | Consumer Runnable | ExclusiveArea? | Description |
|----------|-----------|-------------------|-------------------|----------------|-------------|
| irvXxx | float32 | RE_Compute | RE_Output | EA_XxxData | Shared torque value |

## 5. Data Types
| Type Name | Base Type | Range | Unit | Description |
|-----------|-----------|-------|------|-------------|
| Xxx_t | float32 | 0–360 | deg | Rotor angle |

## 6. Error Handling & Safety
<Describe ASIL decomposition, DEM event IDs, safe-state outputs, redundancy requirements>

## 7. Functional Description
### RE_Init
<Step-by-step description of what this runnable does>

### RE_xxx
<Step-by-step description>
════════════════════════════════════════════════

RULES:
- Use AUTOSAR naming: SWC_PascalCase, RE_PascalCase, PP_/RP_ ports, IF_SR_/IF_CS_/IF_Prm_ interfaces
- Signal ranges must use engineering units where known (Nm, deg, m/s, %)
- Every CalPrm must have a default value and valid range
- ASIL-C/D runnables must note safe-state output values in Section 6
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
Your task is to read a MUD spec and check it against the original requirements.

Evaluate:
1. COMPLETENESS — are all req_ids covered? Are all runnables listed?
2. INTERFACE CORRECTNESS — do port names follow PP_/RP_ convention?
3. DATA TYPES — are all signals typed with physical ranges?
4. SAFETY — for ASIL-C/D: is SAFE_STATE described? DEM event IDs present?
5. IRV / EXCLUSIVE AREA — is every multi-task IRV protected by an ExclusiveArea?
6. CALPRM — does every calibration parameter have a default and range?

Return a JSON review result:
{
  "approved": true | false,
  "coverage_pct": 85,
  "issues": [
    {
      "severity": "error | warning | info",
      "section": "2.1 | 3 | 4 | ...",
      "message": "Description of the issue"
    }
  ],
  "suggestions": ["Suggestion 1", "Suggestion 2"]
}
Output ONLY valid JSON — no markdown, no prose."""

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

_REGEN_SYSTEM_PROMPT = """You are an expert AUTOSAR software architect.
You are given a MUD (Module Unit Design) specification that has been reviewed by a QA
reviewer. Your task is to produce an IMPROVED version of the document that fixes every
issue and implements every suggestion listed in the review report.

REGENERATION RULES:
1. Fix ALL issues marked "error" — they are mandatory.
2. Fix ALL issues marked "warning" — they are strongly recommended.
3. Apply ALL suggestions from the review report.
4. Preserve every correct element from the original spec — do not remove good content.
5. Keep the EXACT same 7-section Markdown structure as the original.
6. Add missing ports, runnables, IRVs, CalPrm, ExclusiveAreas, DEM event IDs as required.
7. For ASIL-C/D: if SAFE_STATE or DEM reporting is missing, add it to Section 6.
8. If a signal range was missing, add engineering-unit ranges (Nm, deg, m/s, %).
9. Output ONLY the improved Markdown document — no JSON, no code fences, no commentary.
"""

_REGEN_USER_PROMPT_TMPL = """Improve this MUD specification by fixing all issues listed
in the review report below.

═══════════════════════════════════════════════
MODULE: {swc_name}   |   ASIL: {asil}
ITERATION: {iteration}
═══════════════════════════════════════════════

REVIEW REPORT (fix every item):
Approved: {approved}
Coverage: {coverage_pct}%

ERRORS to fix ({error_count}):
{errors_text}

WARNINGS to fix ({warning_count}):
{warnings_text}

SUGGESTIONS to apply ({suggestion_count}):
{suggestions_text}

═══════════════════════════════════════════════
ORIGINAL ARCHITECTURAL REQUIREMENTS (context):
{requirements_text}

═══════════════════════════════════════════════
CURRENT MUD SPECIFICATION (iteration {iteration} — improve this):
{mud_spec_markdown}

Output the complete improved MUD specification document now.
Fix every error and warning. Apply every suggestion. Preserve all correct content."""

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
        temperature: float = 0.25,
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
        user_prompt = _REVIEW_USER_PROMPT_TMPL.format(
            swc_name=swc_name,
            asil=asil,
            req_ids=", ".join(req_ids),
            requirements_text=requirements_text,
            mud_spec_markdown=mud_spec_markdown,
        )

        backend = self._orchestrator._get_backend()
        response = await backend.generate(
            system_prompt=_REVIEW_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=2048,
            response_format="json",   # ← review always returns structured JSON
        )

        return self._parse_review(response.content, iteration=iteration)

    async def regenerate_spec(
        self,
        swc_name: str,
        asil: str,
        requirements_text: str,
        current_spec_markdown: str,
        review: SpecReviewResult,
        temperature: float = 0.2,
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
        """Parse JSON review result from AI response."""
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("MudSpecGenerator: no JSON in review response")
            return SpecReviewResult(
                approved=False,
                coverage_pct=0,
                issues=[ReviewIssue("error", "review", "AI did not return a valid review JSON")],
                raw_response=raw,
            )

        try:
            data = json.loads(cleaned[start:end])
        except json.JSONDecodeError as exc:
            logger.error("MudSpecGenerator: review JSON parse error: %s", exc)
            return SpecReviewResult(
                approved=False,
                coverage_pct=0,
                issues=[ReviewIssue("error", "review", f"JSON parse error: {exc}")],
                raw_response=raw,
                iteration=iteration,
            )

        return SpecReviewResult.from_dict(data, raw=raw, iteration=iteration)
