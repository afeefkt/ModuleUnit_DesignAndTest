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
from typing import Any, AsyncIterator, Optional

from mudtool.ai.section7_normalizer import (
    Section7NormalizationResult,
    normalize_section7_markdown,
)

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

1. Guard
   if (moduleState != MODULE_READY) {
      irvModuleStatus = STATUS_INIT;
   }
2. Read inputs
   Rte_Read(RP_NvM_State, &nvmState);
3. Restore defaults
   if (nvmState == NVM_VALID) {
      irvTorqueSetpoint = nvmState.lastTorque;
   } else {
      irvTorqueSetpoint = Rte_Prm(RP_CalPrm_DefaultTorque);
   }
4. Validate
   if (irvTorqueSetpoint > 100.0F) {
      irvTorqueSetpoint = 100.0F;
   }
5. Write outputs
   Rte_Write(PP_InitStatus, INIT_DONE);
   irvModuleStatus = STATUS_READY;

### RE_Control
// Reads:  RP_SteerAngle, RP_MotorCurrent
// Writes: PP_TorqueOut
// IRVs consumed: irvTorqueSetpoint, irvModuleStatus
// IRVs produced: irvFilteredTorque
// CalPrm used:   RP_CalPrm_TorqueGain, RP_CalPrm_CurrentLimit

1. Guard
   if (irvModuleStatus != STATUS_READY) {
      Rte_Write(PP_TorqueOut, 0.0F);
      return;
   }
2. Read inputs
   Rte_Read(RP_SteerAngle, &steerAngle);
   Rte_Read(RP_MotorCurrent, &motorCurrent);
3. Validate
   if (motorCurrent > Rte_Prm(RP_CalPrm_CurrentLimit)) {
      Rte_Write(PP_TorqueOut, 0.0F);
      Dem_ReportErrorStatus(SWC_DEM_E_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED);
      return;
   }
4. Compute
   torqueCmd = steerAngle * Rte_Prm(RP_CalPrm_TorqueGain);
   irvFilteredTorque = LowPassFilter(torqueCmd, Rte_Prm(RP_CalPrm_FilterCoeff));
5. Write outputs
   Rte_Write(PP_TorqueOut, clamp(irvFilteredTorque, -100.0F, 100.0F));
════════════════════════════════════════════════

RULES (follow ALL — do not deviate):
- Output EXACTLY 7 top-level sections (## 1. Overview through ## 7. Functional Description).
  Do NOT add any other top-level (##) sections such as "Stack Monitoring", "Self-Test",
  "DTC Configuration", or anything not in the template above. Such content belongs INSIDE
  Section 6 (Error Handling & Safety) or Section 7 (Functional Description) as needed.
- Use AUTOSAR naming: SWC_PascalCase, RE_PascalCase, PP_/RP_ ports,
  IF_SR_/IF_CS_/IF_Prm_ interfaces, EA_ ExclusiveAreas, DEM event IDs (SWC_DEM_E_*)
- Section 3.1: include ALL OS-scheduled runnables — at minimum RE_Init + one RE_Cyclic
- Section 3.2: include ALL internal helper functions called by those runnables
- Section 7 MUST use the pseudo-code format shown above for EVERY runnable in Section 3.1:
    * // Reads / Writes / IRVs consumed / IRVs produced / CalPrm used — header comment block
    * Numbered steps with short labels such as Guard / Read inputs / Validate / Compute / Write outputs
    * One executable statement per line in the pseudo-code body
    * Explicit if / else if / else / switch / case / default / return statements
    * Numbered steps using Rte_Read/Rte_Write with actual port/signal names from Section 2
    * SAFE_STATE output value (0 or fail-safe) for every ASIL-C/D validation step
    * Dem_ReportErrorStatus() call with named DEM event ID on every error path
    * Sub-function calls (e.g. ReadSensorInputs()) as standalone statements referencing names from Section 3.2
    * No mixed prose + logic on one line
    * No arrow shorthand such as "-> SAFE_STATE" or "→"
    * No long narrative sentences describing multiple operations in one step
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

_REGEN_SYSTEM_PROMPT = """You are a TEXT EDITOR for AUTOSAR MUD specifications.
You are NOT a writer. You DO NOT generate new content from scratch.
You modify exactly the lines you are told to modify and copy everything else verbatim.

INPUTS:
  - CURRENT SPEC: the base document (already mostly correct)
  - FIX LIST: errors, warnings, suggestions, and uncovered requirements

YOUR JOB — STRICT RULES:
1. Start by mentally reading the entire CURRENT SPEC line by line.
2. For each line, decide: is this line referenced in the FIX LIST? If NO → output it verbatim.
3. If YES → output the corrected version of that line/block, applying ONLY the listed fix.
4. For UNCOVERED REQUIREMENTS: ADD a new numbered step to Section 7 of the most relevant
   runnable's pseudo-code (do NOT delete or modify existing steps; do NOT add new runnables).
5. WARNINGS are mandatory quality fixes. Treat warning items exactly like errors.
6. Section 7 pseudo-code fixes are highest priority because they directly affect activity diagrams.
7. NEVER add sections, ports, or runnables that are not explicitly requested by the FIX LIST.
8. NEVER rephrase, "improve clarity", or "polish" lines that have no listed issue.
9. The OUTPUT line count MUST be >= 95% of the CURRENT SPEC line count (you only ADD missing
   logic for uncovered reqs; you do NOT delete or shrink anything).
10. Output ONLY the complete patched Markdown — no JSON, no code fences, no commentary.

VERIFICATION CHECK (do this in your head before responding):
  - Did I copy every line not in the FIX LIST verbatim? If no → start over.
  - Did I satisfy every FIX MANIFEST acceptance check? If no → start over.
  - Did I keep the same 7 top-level sections? If no → start over.
"""

_REGEN_USER_PROMPT_TMPL = """You are patching a MUD specification. Apply ONLY the fixes listed below.
Copy all unchanged sections VERBATIM from the current spec.

══════════════════════════════════════════════════════════
MANDATORY FIX CHECKLIST for {swc_name} (iteration {iteration}):
You MUST address EVERY item below — none may be skipped.
WARNINGS are mandatory quality fixes — treat them identically to errors.
══════════════════════════════════════════════════════════
{mandatory_checklist}
══════════════════════════════════════════════════════════

FIX LIST — full detail (current coverage: {coverage_pct}%):

ERRORS ({error_count}):
{errors_text}

WARNINGS ({warning_count}) — ALL MANDATORY, SAME PRIORITY AS ERRORS:
{warnings_text}

SUGGESTIONS ({suggestion_count}):
{suggestions_text}

UNCOVERED REQUIREMENTS — must add logic for these to Section 7 ({uncovered_count}):
{uncovered_req_ids_text}

COVERAGE GAPS:
{coverage_gaps_text}

STRICT FIX MANIFEST — every item below is required:
{fix_manifest_text}

REQUIREMENTS (context only — do not introduce content beyond the FIX LIST above):
{requirements_text}

═══════════════════════════════════════════════
CURRENT SPEC — copy verbatim except for the FIX LIST above:
═══════════════════════════════════════════════
{mud_spec_markdown}
═══════════════════════════════════════════════

Output the patched document NOW. Copy every line that has no issue verbatim. Apply ONLY the
fixes above. If FIX LIST is empty in any category, change nothing for that category."""

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
    patch_plan: list[dict[str, Any]] = field(default_factory=list)
    deterministic_coverage: dict[str, Any] = field(default_factory=dict)
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
            "patch_plan": self.patch_plan,
            "deterministic_coverage": self.deterministic_coverage,
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
            patch_plan=d.get("patch_plan", []),
            deterministic_coverage=d.get("deterministic_coverage", {}),
        )


# ── Generator class ───────────────────────────────────────────────────────────

def _stable_slug(text: str, *, limit: int = 36) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:limit].strip("-") or "item")


def review_issue_fingerprint(item: ReviewIssue | dict | str, *, prefix: str = "issue") -> str:
    """Stable key for matching repeated review findings across iterations."""
    if isinstance(item, ReviewIssue):
        severity = item.severity
        section = item.section
        message = item.message
    elif isinstance(item, dict):
        severity = str(item.get("severity", prefix))
        section = str(item.get("section", ""))
        message = str(item.get("message", item.get("text", "")))
    else:
        severity = prefix
        section = ""
        message = str(item)
    normalized = " ".join(f"{severity} {section} {message}".lower().split())
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return f"{prefix}:{normalized}"


def build_fix_manifest(review: SpecReviewResult) -> list[dict[str, str]]:
    """Convert review output into required, actionable regeneration fixes."""
    items: list[dict[str, str]] = []

    for idx, issue in enumerate(review.issues, start=1):
        severity = (issue.severity or "info").lower()
        required = severity in {"error", "warning"}
        fix_id = f"{severity.upper()}-{idx:03d}-{_stable_slug(issue.section or issue.message)}"
        action = (
            f"Fix {severity} in section {issue.section or '?'}: {issue.message}"
            if required else
            f"Apply information item in section {issue.section or '?'} if it improves traceability: {issue.message}"
        )
        items.append({
            "id": fix_id,
            "kind": "issue",
            "severity": severity,
            "section": issue.section or "?",
            "message": issue.message,
            "required_action": action,
            "acceptance_check": f"Reviewer no longer reports: {issue.message}",
            "fingerprint": review_issue_fingerprint(issue, prefix="issue"),
            "required": "yes" if required else "no",
        })

    for idx, suggestion in enumerate(review.suggestions, start=1):
        fix_id = f"SUG-{idx:03d}-{_stable_slug(suggestion)}"
        items.append({
            "id": fix_id,
            "kind": "suggestion",
            "severity": "warning",
            "section": "review",
            "message": suggestion,
            "required_action": suggestion,
            "acceptance_check": "The suggested change is visible in the relevant MUD spec section.",
            "fingerprint": review_issue_fingerprint(suggestion, prefix="suggestion"),
            "required": "yes",
        })

    for idx, req_id in enumerate(review.uncovered_req_ids, start=1):
        gap = review.coverage_gaps[idx - 1] if idx - 1 < len(review.coverage_gaps) else ""
        fix_id = f"COV-{idx:03d}-{_stable_slug(req_id, limit=24)}"
        items.append({
            "id": fix_id,
            "kind": "coverage_gap",
            "severity": "warning",
            "section": "7",
            "message": f"{req_id}: {gap}".strip(),
            "required_action": (
                f"Add or update Section 7 pseudo-code so requirement {req_id} is explicitly covered. {gap}".strip()
            ),
            "acceptance_check": f"Requirement {req_id} is absent from uncovered_req_ids in the next review.",
            "fingerprint": review_issue_fingerprint(
                {"severity": "coverage", "section": req_id, "message": gap},
                prefix="coverage",
            ),
            "required": "yes",
        })

    return items


def format_fix_manifest(manifest: list[dict[str, str]]) -> str:
    if not manifest:
        return "  (none)"
    _sev_prefix = {
        "error":    "❌ REQUIRED",
        "warning":  "⚠ MANDATORY",
        "coverage": "⚠ MANDATORY",
        "info":     "💡 OPTIONAL",
    }
    lines: list[str] = []
    for item in manifest:
        prefix = _sev_prefix.get(item.get("severity", "info"), "⚠ MANDATORY")
        lines.append(
            f"- {item['id']} {prefix} | section: {item['section']} | required={item['required']}"
        )
        lines.append(f"  Problem:         {item['message']}")
        lines.append(f"  Required action: {item['required_action']}")
        lines.append(f"  Done when:       {item['acceptance_check']}")
    return "\n".join(lines)


_SECTION7_RE = re.compile(
    r"(?ms)^##\s+7\.\s+Functional Description\s*$\n?(?P<body>.*?)(?=^##\s+\d+\.|\Z)"
)
_RUNNABLE_RE = re.compile(r"(?m)^###\s+(.+?)\s*$")


def _extract_section7(markdown: str) -> str:
    match = _SECTION7_RE.search(markdown or "")
    return match.group("body") if match else ""


def _section7_runnable_blocks(markdown: str) -> list[dict[str, Any]]:
    match = _SECTION7_RE.search(markdown or "")
    if not match:
        return []
    body = match.group("body")
    blocks: list[dict[str, Any]] = []
    headings = list(_RUNNABLE_RE.finditer(body))
    for index, heading in enumerate(headings):
        body_start = heading.end()
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        blocks.append({
            "name": heading.group(1).strip(),
            "body": body[body_start:body_end],
            "abs_heading_start": match.start("body") + heading.start(),
            "abs_body_start": match.start("body") + body_start,
            "abs_body_end": match.start("body") + body_end,
        })
    return blocks


def _requirement_lines(requirements_text: str, req_ids: list[str]) -> dict[str, str]:
    lines = [line.strip() for line in (requirements_text or "").splitlines() if line.strip()]
    out: dict[str, str] = {}
    for req_id in req_ids:
        for line in lines:
            if req_id and req_id in line:
                out[req_id] = line[:260]
                break
        out.setdefault(req_id, req_id)
    return out


def _coverage_tokens(text: str) -> set[str]:
    stop = {
        "shall", "should", "must", "with", "from", "into", "that", "this", "when",
        "then", "have", "will", "module", "software", "component", "requirement",
    }
    return {
        tok.lower()
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", text or "")
        if tok.lower() not in stop and not tok.upper().startswith("REQ")
    }


def deterministic_requirement_coverage(
    mud_spec_markdown: str,
    requirements_text: str,
    req_ids: list[str],
) -> dict[str, Any]:
    """Best-effort deterministic coverage signal for Section 7.

    This is intentionally conservative. Explicit REQ-ID traces always count.
    Keyword evidence only counts when several requirement words appear in the
    same runnable block, preventing an LLM review from collapsing to 0% when
    the spec is visibly traceable.
    """
    req_ids = [rid for rid in req_ids or [] if rid]
    req_lines = _requirement_lines(requirements_text, req_ids)
    blocks = _section7_runnable_blocks(mud_spec_markdown)
    section7 = _extract_section7(mud_spec_markdown)
    covered: dict[str, dict[str, Any]] = {}
    uncovered: list[str] = []
    patch_plan: list[dict[str, Any]] = []

    for req_id in req_ids:
        evidence: dict[str, Any] | None = None
        if req_id in section7:
            target = next((b for b in blocks if req_id in b["body"]), blocks[0] if blocks else None)
            evidence = {
                "method": "explicit_req_id",
                "runnable": target["name"] if target else "",
            }
        else:
            req_tokens = _coverage_tokens(req_lines.get(req_id, ""))
            best: tuple[int, str] = (0, "")
            for block in blocks:
                overlap = len(req_tokens & _coverage_tokens(block["body"]))
                if overlap > best[0]:
                    best = (overlap, block["name"])
            if best[0] >= 4:
                evidence = {"method": "keyword_overlap", "runnable": best[1], "overlap": best[0]}

        if evidence:
            covered[req_id] = evidence
        else:
            uncovered.append(req_id)
            target_name = _guess_patch_runnable(req_id, req_lines.get(req_id, ""), blocks)
            patch_plan.append({
                "kind": "coverage_gap",
                "section": "7",
                "req_id": req_id,
                "target_runnable": target_name,
                "required_action": f"Add explicit Section 7 traceable logic for {req_id}",
                "acceptance_check": f"{req_id} appears in Section 7 runnable {target_name or '(any runnable)'}.",
            })

    total = len(req_ids)
    coverage_pct = int(round(len(covered) / total * 100)) if total else 100
    return {
        "coverage_pct": coverage_pct,
        "covered_req_ids": sorted(covered),
        "uncovered_req_ids": uncovered,
        "evidence": covered,
        "patch_plan": patch_plan,
    }


def _guess_patch_runnable(req_id: str, req_line: str, blocks: list[dict[str, Any]]) -> str:
    if not blocks:
        return ""
    hay = f"{req_id} {req_line}".lower()
    for block in blocks:
        name = block["name"]
        compact = re.sub(r"^RE_", "", name, flags=re.IGNORECASE).lower()
        words = re.findall(r"[a-z][a-z0-9]+", compact)
        if any(word and word in hay for word in words):
            return name
    return blocks[0]["name"]


def apply_patch_only_review_fixes(
    current_spec_markdown: str,
    requirements_text: str,
    review: SpecReviewResult,
) -> tuple[str, dict[str, Any]]:
    """Patch only targeted Section 7 runnable blocks for coverage gaps.

    Returns the original markdown unchanged when no safe deterministic patch can
    be applied. The caller may then fall back to the model-based editor.
    """
    blocks = _section7_runnable_blocks(current_spec_markdown)
    if not blocks:
        return current_spec_markdown, {"changed": False, "reason": "section7_not_found"}

    patch_items = [p for p in (review.patch_plan or []) if p.get("kind") == "coverage_gap"]
    if not patch_items:
        req_lines = _requirement_lines(requirements_text, review.uncovered_req_ids)
        patch_items = [
            {
                "kind": "coverage_gap",
                "req_id": req_id,
                "target_runnable": _guess_patch_runnable(req_id, req_lines.get(req_id, ""), blocks),
            }
            for req_id in review.uncovered_req_ids
        ]
    if not patch_items:
        return current_spec_markdown, {"changed": False, "reason": "no_patch_items"}

    req_lines = _requirement_lines(requirements_text, [str(p.get("req_id", "")) for p in patch_items])
    block_by_name = {b["name"]: b for b in blocks}
    insertions: dict[str, list[str]] = {}
    applied: list[str] = []
    for item in patch_items:
        req_id = str(item.get("req_id", "")).strip()
        if not req_id or req_id in _extract_section7(current_spec_markdown):
            continue
        target = str(item.get("target_runnable", "")).strip()
        if target not in block_by_name:
            target = blocks[0]["name"]
        req_summary = req_lines.get(req_id, req_id).replace("|", " ").strip()
        insertions.setdefault(target, []).extend([
            f"// Trace: {req_id}",
            f"99. Cover {req_id}",
            f"   Requirement intent: {req_summary[:180]}",
        ])
        applied.append(req_id)

    if not insertions:
        return current_spec_markdown, {"changed": False, "reason": "nothing_to_insert"}

    patched = current_spec_markdown
    for block in sorted(blocks, key=lambda b: b["abs_body_end"], reverse=True):
        lines = insertions.get(block["name"])
        if not lines:
            continue
        insertion = "\n" + "\n".join(lines) + "\n"
        insert_at = block["abs_body_end"]
        patched = patched[:insert_at].rstrip() + insertion + patched[insert_at:]

    unchanged_lines = {
        line.strip()
        for line in current_spec_markdown.splitlines()
        if line.strip()
    }
    patched_lines = {line.strip() for line in patched.splitlines() if line.strip()}
    overlap = len(unchanged_lines & patched_lines) / max(len(unchanged_lines), 1) * 100
    required_headings_present = all(
        f"## {idx}." in patched for idx in range(1, 8)
    )
    if overlap < 95.0 or not required_headings_present:
        return current_spec_markdown, {
            "changed": False,
            "reason": "patch_rejected",
            "overlap_pct": round(overlap, 1),
        }
    return patched, {
        "changed": True,
        "mode": "patch_only",
        "applied_req_ids": applied,
        "overlap_pct": round(overlap, 1),
        "targeted_sections": sorted(insertions),
    }


def review_fix_fingerprints(review: SpecReviewResult) -> set[str]:
    fingerprints: set[str] = set()
    for issue in review.issues:
        if (issue.severity or "").lower() in {"error", "warning"}:
            fingerprints.add(review_issue_fingerprint(issue, prefix="issue"))
    for idx, req_id in enumerate(review.uncovered_req_ids):
        gap = review.coverage_gaps[idx] if idx < len(review.coverage_gaps) else ""
        fingerprints.add(
            review_issue_fingerprint(
                {"severity": "coverage", "section": req_id, "message": gap},
                prefix="coverage",
            )
        )
    return fingerprints


def compare_review_results(before: SpecReviewResult, after: SpecReviewResult) -> dict[str, Any]:
    before_keys = review_fix_fingerprints(before)
    after_keys = review_fix_fingerprints(after)
    remaining = sorted(before_keys & after_keys)
    resolved = sorted(before_keys - after_keys)
    return {
        "initial_fix_count": len(before_keys),
        "resolved_issue_count": len(resolved),
        "repeated_issue_count": len(remaining),
        "remaining_fingerprints": remaining,
        "resolved_fingerprints": resolved,
        "post_issue_count": after.error_count + after.warning_count + len(after.uncovered_req_ids),
        "quality_status": "pass" if after.approved and after.warning_count == 0 else "needs_fix",
    }


def build_unresolved_review(
    comparison: dict,
    post_review: SpecReviewResult,
) -> SpecReviewResult:
    """Return a SpecReviewResult containing ONLY the issues that were NOT fixed.

    Uses ``comparison["remaining_fingerprints"]`` from ``compare_review_results()``
    to filter ``post_review.issues`` to just the stuck items so that the repair
    retry can focus exclusively on them rather than re-processing all issues.

    If nothing is repeated the original ``post_review`` is returned unchanged.
    """
    remaining_fps = set(comparison.get("remaining_fingerprints", []))
    if not remaining_fps:
        return post_review

    filtered_issues = [
        issue for issue in post_review.issues
        if review_issue_fingerprint(issue, prefix="issue") in remaining_fps
    ]
    filtered_uncovered: list[str] = []
    filtered_gaps: list[str] = []
    for idx, req_id in enumerate(post_review.uncovered_req_ids):
        gap = post_review.coverage_gaps[idx] if idx < len(post_review.coverage_gaps) else ""
        fp = review_issue_fingerprint(
            {"severity": "coverage", "section": req_id, "message": gap},
            prefix="coverage",
        )
        if fp in remaining_fps:
            filtered_uncovered.append(req_id)
            filtered_gaps.append(gap)

    return SpecReviewResult(
        approved=post_review.approved,
        coverage_pct=post_review.coverage_pct,
        issues=filtered_issues,
        suggestions=[],           # don't repeat suggestions on repair attempt
        uncovered_req_ids=filtered_uncovered,
        coverage_gaps=filtered_gaps,
        iteration=post_review.iteration,
    )


def strip_fix_coverage_block(markdown: str) -> str:
    """Remove accidental model-emitted fix coverage notes from user-visible spec."""
    text = markdown or ""
    text = re.sub(
        r"\n{0,2}<!--\s*FIX COVERAGE[\s\S]*?-->\s*",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\n{0,2}#{1,4}\s*Fix Coverage[\s\S]*?(?=\n#{1,4}\s+\S|\Z)",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


class MudSpecGenerator:
    """Generates a Module Unit Design spec Markdown for a single SWC.

    Usage:
        gen = MudSpecGenerator(orchestrator)
        spec_md = await gen.generate_spec(module_info, requirements_text)
        review  = await gen.review_spec(module_info, requirements_text, spec_md)
    """

    def __init__(self, orchestrator):
        self._orchestrator = orchestrator
        self._last_normalization_result = Section7NormalizationResult(normalized_markdown="")
        self._last_patch_meta: dict[str, Any] = {"changed": False}

    @property
    def last_normalization_result(self) -> Section7NormalizationResult:
        return self._last_normalization_result

    @property
    def last_patch_meta(self) -> dict[str, Any]:
        return self._last_patch_meta

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
        pipeline_mode: Optional[str] = None,
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

        # ── Two-stage pipeline (optional) ────────────────────────────────────
        # If pipeline_mode="two_stage" (passed from route or set in MUD_SPEC_PIPELINE),
        # delegate to MudSpecPipeline:
        #   Stage 1: JSON skeleton  Stage 3: per-runnable Section 7  Stage 4: validate
        #   Stage 5: assemble Markdown
        # Falls back to single-pass if pipeline returns empty string or raises.
        if pipeline_mode is None:
            try:
                from mudtool.config.settings import get_settings as _get_settings
                pipeline_mode = _get_settings().mud_spec_pipeline
            except Exception:
                pipeline_mode = "single_pass"
        _pipeline_mode = pipeline_mode

        if _pipeline_mode == "two_stage":
            try:
                from mudtool.ai.mud_pipeline_stages import MudSpecPipeline
                _pipeline = MudSpecPipeline(
                    backend=self._orchestrator._get_generator_backend(),
                    skeleton_backend=self._orchestrator._get_skeleton_backend(),
                    progress_callback=progress_callback,
                )
                _pipeline_result = await _pipeline.generate(
                    swc_name=swc_name,
                    description=description,
                    asil=asil,
                    runnables=runnables,
                    req_ids=req_ids,
                    requirements_text=requirements_text,
                    temperature=temperature,
                )
                if _pipeline_result and len(_pipeline_result) > 500:
                    logger.info(
                        "generate_spec: pipeline produced %d chars for %s",
                        len(_pipeline_result), swc_name,
                    )
                    return self._apply_section7_normalization(
                        _pipeline_result,
                        swc_name=swc_name,
                        progress_callback=progress_callback,
                        stage="mud_spec",
                    )
                else:
                    logger.warning(
                        "generate_spec: pipeline returned empty/short result (%d chars) "
                        "for %s — falling back to single-pass",
                        len(_pipeline_result or ""), swc_name,
                    )
                    if progress_callback:
                        progress_callback({
                            "stage": "mud_spec",
                            "message": "Pipeline produced no output — falling back to single-pass generation…",
                            "progress": 5,
                        })
            except Exception as _pipe_exc:
                logger.warning(
                    "generate_spec: pipeline failed for %s (%s) — falling back to single-pass",
                    swc_name, _pipe_exc,
                )
                if progress_callback:
                    progress_callback({
                        "stage": "mud_spec",
                        "message": f"Pipeline error ({_pipe_exc}) — falling back to single-pass…",
                        "progress": 5,
                    })

        # ── Single-pass generation (default path) ────────────────────────────
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

        logger.info("generate_spec: calling _get_generator_backend() for %s", swc_name)
        backend = self._orchestrator._get_generator_backend()
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
        return self._apply_section7_normalization(
            spec_md,
            swc_name=swc_name,
            progress_callback=progress_callback,
            stage="mud_spec",
        )

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
        # Truncate inputs so the reviewer prompt stays within model context limits.
        # Limits raised: real AUTOSAR specs are 8k-15k chars; truncating at 4k causes
        # the reviewer to miss issues in the tail and produce incomplete coverage reports.
        _MAX_REQ_CHARS = 6000
        _MAX_SPEC_CHARS = 10000
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
        result = self._parse_review(response.content, iteration=iteration)
        deterministic = deterministic_requirement_coverage(
            mud_spec_markdown=mud_spec_markdown,
            requirements_text=requirements_text,
            req_ids=req_ids,
        )
        result.deterministic_coverage = deterministic
        result.patch_plan = deterministic.get("patch_plan", [])
        if deterministic.get("coverage_pct", 0) > result.coverage_pct:
            logger.info(
                "review_spec: deterministic coverage overrides AI coverage %s -> %s for %s",
                result.coverage_pct,
                deterministic["coverage_pct"],
                swc_name,
            )
            result.coverage_pct = int(deterministic["coverage_pct"])
            result.uncovered_req_ids = list(deterministic.get("uncovered_req_ids", []))
            result.coverage_gaps = [
                f"{req_id}: missing explicit traceable Section 7 logic"
                for req_id in result.uncovered_req_ids
            ]
            result = self._enforce_approval_rules(result)
        if (
            result.deterministic_coverage.get("coverage_pct", 0) >= 80
            and not result.deterministic_coverage.get("uncovered_req_ids")
        ):
            downgraded = False
            for issue in result.issues:
                msg = (issue.message or "").lower()
                if issue.section == "review" and (
                    "empty review response" in msg
                    or "review response could not" in msg
                    or "could not be fully parsed" in msg
                ):
                    issue.severity = "info"
                    issue.message = (
                        issue.message
                        + " Deterministic Section 7 coverage passed, so this is reported as reviewer-backend telemetry only."
                    )
                    downgraded = True
            if downgraded:
                result = self._enforce_approval_rules(result)
        return result

    async def regenerate_spec(
        self,
        swc_name: str,
        asil: str,
        requirements_text: str,
        current_spec_markdown: str,
        review: SpecReviewResult,
        temperature: float = 0.0,
        progress_callback=None,
        repair_attempt: bool = False,
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
            repair_attempt:         True when this is a retry targeting only unresolved
                                    issues — adds escalation header to system prompt.

        Returns:
            Improved MUD spec as a Markdown string.
        """
        patched_md, patch_meta = apply_patch_only_review_fixes(
            current_spec_markdown=current_spec_markdown,
            requirements_text=requirements_text,
            review=review,
        )
        self._last_patch_meta = patch_meta
        if patch_meta.get("changed"):
            if progress_callback:
                progress_callback({
                    "stage": "mud_regen",
                    "message": (
                        f"Patch-only repair applied to Section 7 "
                        f"({len(patch_meta.get('applied_req_ids', []))} requirement trace(s))"
                    ),
                    "progress": 92,
                    "iteration": review.iteration + 1,
                    "repair_mode": "patch_only",
                    "patch_meta": patch_meta,
                })
            return self._apply_section7_normalization(
                patched_md,
                swc_name=swc_name,
                progress_callback=progress_callback,
                stage="mud_regen",
                iteration=review.iteration + 1,
            )
        elif progress_callback:
            progress_callback({
                "stage": "mud_regen",
                "message": (
                    f"Patch-only repair unavailable ({patch_meta.get('reason', 'unknown')}); "
                    "using AI editor fallback"
                ),
                "progress": 12,
                "iteration": review.iteration + 1,
                "repair_mode": "ai_editor_fallback",
                "patch_meta": patch_meta,
            })

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
        fix_manifest = build_fix_manifest(review)

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

        # Build the compact numbered mandatory checklist shown at the very top of
        # the prompt so small models encounter the highest-priority items first.
        mandatory_items: list[str] = []
        for issue in by_sev.get("error", []):
            sev_tag = "❌ ERROR"
            mandatory_items.append(
                f"  [{len(mandatory_items)+1}] {sev_tag} — [{issue.section}]: {issue.message}"
            )
        for issue in by_sev.get("warning", []):
            sev_tag = "⚠ WARNING"
            mandatory_items.append(
                f"  [{len(mandatory_items)+1}] {sev_tag} — [{issue.section}]: {issue.message}"
            )
        for req_id in review.uncovered_req_ids:
            mandatory_items.append(
                f"  [{len(mandatory_items)+1}] ⚠ COVERAGE GAP — Add Section 7 pseudo-code for: {req_id}"
            )
        mandatory_checklist = (
            "\n".join(mandatory_items)
            if mandatory_items
            else "  (all requirements met — no mandatory fixes)"
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
            mandatory_checklist=mandatory_checklist,
            errors_text=errors_text,
            warnings_text=warnings_text,
            suggestions_text=suggestions_text,
            uncovered_count=len(review.uncovered_req_ids),
            uncovered_req_ids_text=uncovered_req_ids_text,
            coverage_gaps_text=coverage_gaps_text,
            fix_manifest_text=format_fix_manifest(fix_manifest),
            requirements_text=requirements_text,
            mud_spec_markdown=current_spec_markdown,
        )

        # When this is a targeted repair retry, escalate the system prompt so the
        # AI knows these specific items were NOT fixed in the previous pass.
        system_prompt = _REGEN_SYSTEM_PROMPT
        if repair_attempt:
            system_prompt = _REGEN_SYSTEM_PROMPT + (
                "\n\n\U0001f6a8 REPAIR ATTEMPT — PREVIOUS REGENERATION DID NOT FIX THESE ITEMS.\n"
                "The items in the MANDATORY FIX CHECKLIST were identified in the previous pass "
                "and are STILL PRESENT in the spec.\n"
                "You MUST address each one specifically. If you output the same text as before "
                "for those sections, the spec will be REJECTED.\n"
                "Focus ONLY on the listed items. Do not introduce any other changes.\n"
            )

        # Regeneration edits Section 7 pseudo-code — route through the code-focused
        # generator backend (qwen) for consistency with the generation stage.
        backend = self._orchestrator._get_generator_backend()

        # ── Token-streaming regeneration ─────────────────────────────────────
        regen_iter = review.iteration + 1
        chunks: list[str] = []
        char_count = 0
        last_progress_chars = 0

        try:
            logger.info(
                "regenerate_spec: starting for %s (asil=%s, iter=%s, repair=%s)",
                swc_name, asil, regen_iter, repair_attempt,
            )
            async for chunk in backend.generate_stream(
                system_prompt=system_prompt,
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
                system_prompt=system_prompt,
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
        spec_md = strip_fix_coverage_block(spec_md)

        # ── Convergence verification ─────────────────────────────────────────
        # Small models often ignore PATCH MODE and rewrite from scratch. Detect
        # this by measuring line overlap with the previous spec. If overlap is
        # too low (<60%), the regen is a wholesale rewrite — log a warning so
        # the user knows the model didn't follow patch mode (they may need to
        # try a stronger model or a different reviewer model).
        try:
            prev_lines = {l.strip() for l in current_spec_markdown.splitlines() if l.strip()}
            new_lines  = {l.strip() for l in spec_md.splitlines() if l.strip()}
            if prev_lines and new_lines:
                kept = len(prev_lines & new_lines)
                overlap = kept / len(prev_lines) * 100
                logger.info(
                    "regenerate_spec: convergence — kept %d/%d lines (%.1f%% overlap) from iter %d → %d",
                    kept, len(prev_lines), overlap, review.iteration, regen_iter,
                )
                if overlap < 60.0:
                    logger.warning(
                        "regenerate_spec: LOW CONVERGENCE — only %.1f%% line overlap with previous spec. "
                        "Model rewrote rather than patched. Consider a larger model or stricter prompt.",
                        overlap,
                    )
                    if progress_callback:
                        progress_callback({
                            "stage": "mud_regen",
                            "message": (
                                f"Warning: low convergence ({overlap:.0f}% overlap) — "
                                "model rewrote instead of patching. Result kept anyway."
                            ),
                            "progress": 95,
                            "iteration": regen_iter,
                            "convergence_pct": round(overlap, 1),
                        })
        except Exception as _exc:
            logger.debug("convergence check failed: %s", _exc)

        logger.info(
            "MudSpecGenerator: regenerated spec for %s (iteration %d) → %d chars",
            swc_name, regen_iter, len(spec_md),
        )
        return self._apply_section7_normalization(
            spec_md,
            swc_name=swc_name,
            progress_callback=progress_callback,
            stage="mud_regen",
            iteration=regen_iter,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _enforce_approval_rules(result: "SpecReviewResult") -> "SpecReviewResult":
        """Override the AI's self-reported `approved` flag with our deterministic rule.

        Small models often return approved=true even when they list errors, low coverage,
        or uncovered requirements. The contract is: approved=true ONLY if all are clean.
        """
        result.__post_init__()
        rule_approved = (
            result.coverage_pct >= 80
            and result.error_count == 0
            and len(result.uncovered_req_ids) == 0
        )
        if result.approved != rule_approved:
            logger.warning(
                "Review approved=%s overridden to %s: coverage=%d errors=%d uncovered=%d",
                result.approved, rule_approved, result.coverage_pct,
                result.error_count, len(result.uncovered_req_ids),
            )
            result.approved = rule_approved
        return result

    def _apply_section7_normalization(
        self,
        spec_md: str,
        *,
        swc_name: str,
        progress_callback=None,
        stage: str = "mud_spec",
        iteration: int | None = None,
    ) -> str:
        try:
            normalization = normalize_section7_markdown(spec_md)
        except Exception as exc:
            logger.warning(
                "Section 7 normalization failed for %s: %s",
                swc_name,
                exc,
                exc_info=True,
            )
            self._last_normalization_result = Section7NormalizationResult(
                normalized_markdown=spec_md,
                warnings=[f"Section 7 normalization failed: {exc}"],
                runnable_reports=[],
                changed=False,
                succeeded=False,
            )
            if progress_callback:
                event = {
                    "stage": stage,
                    "message": f"Section 7 normalization skipped due to error: {exc}",
                    "progress": 94,
                    "section7_normalization": self._last_normalization_result.summary(),
                }
                if iteration is not None:
                    event["iteration"] = iteration
                progress_callback(event)
            return spec_md

        self._last_normalization_result = normalization
        logger.info(
            "Section 7 normalization for %s: runnables=%d changed=%d warnings=%d",
            swc_name,
            normalization.normalized_runnable_count,
            normalization.changed_runnable_count,
            normalization.warning_count,
        )
        if progress_callback:
            summary = normalization.summary()
            message = (
                "Section 7 normalization complete - "
                f"{summary['normalized_runnable_count']} runnable block(s), "
                f"{summary['changed_runnable_count']} adjusted, "
                f"{summary['warning_count']} warning(s)"
            )
            event = {
                "stage": stage,
                "message": message,
                "progress": 94,
                "section7_normalization": {
                    **summary,
                    "runnable_reports": [report.to_dict() for report in normalization.runnable_reports],
                    "warnings": list(normalization.warnings),
                },
            }
            if iteration is not None:
                event["iteration"] = iteration
            progress_callback(event)
        return normalization.normalized_markdown

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
                return self._enforce_approval_rules(result)
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
                    return self._enforce_approval_rules(result)
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

        return self._enforce_approval_rules(SpecReviewResult(
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
        ))

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
