"""Structural Pre-Check - runs BEFORE the AI draft stage.

Analyses the requirement set for a specific diagram type and identifies gaps
that would produce trivial or incorrect output. Results are injected into the
elaboration context as hints so the AI has concrete guidance.

Pipeline position:
    Import → Elaborate → [Structural Pre-check] → Draft → Critique → Refine
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from mudtool.models.json_uml import DiagramType
from mudtool.models.requirements import Requirement


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class PreCheckResult:
    """Outcome of a structural pre-check pass for one diagram type."""
    diagram_type: str
    gaps: list[str] = field(default_factory=list)
    # gaps   → injected into AI prompt as "PRE-CHECK HINTS" - specific missing info
    warnings: list[str] = field(default_factory=list)
    # warnings → non-blocking; logged + surfaced to user but generation continues
    suggestions: list[str] = field(default_factory=list)
    # suggestions → improvements the human can make to the requirements
    blocked: bool = False
    # blocked=True  → requirement set too sparse, generation will be skipped
    quality_score: float = 1.0
    # 0.0–1.0; computed from gap/warning penalties; < 0.4 triggers blocked=True

    def to_hint_block(self) -> str:
        """Format gaps as a hint block for injection into the generation prompt."""
        if not self.gaps:
            return ""
        lines = ["PRE-CHECK HINTS (must address in generated output):"]
        for gap in self.gaps:
            lines.append(f"  - {gap}")
        return "\n".join(lines)

    def to_summary(self) -> dict:
        return {
            "diagram_type": self.diagram_type,
            "blocked": self.blocked,
            "quality_score": round(self.quality_score, 2),
            "gap_count": len(self.gaps),
            "warning_count": len(self.warnings),
            "gaps": self.gaps,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


# ── Compiled patterns (module-level for reuse) ────────────────────────────────

_RTE_PATTERN = re.compile(
    r"\b(Rte_Read|Rte_Write|Rte_Call|Rte_Result)\b", re.IGNORECASE
)
_ACTION_PATTERN = re.compile(
    r"\b(if|condition|fault|error|check|compute|calculate|process|"
    r"update|send|receive|monitor|detect|handle|trigger)\b",
    re.IGNORECASE,
)
_SWC_PATTERN = re.compile(r"\bSWC_\w+", re.IGNORECASE)
_RUNNABLE_PATTERN = re.compile(r"\bRE_\w+")
_PORT_PATTERN = re.compile(r"\b(?:PP|RP)_\w+")
_COMMS_PATTERN = re.compile(
    r"\b(shall\s+send|shall\s+receive|interface|communicate|invoke|call|message)\b",
    re.IGNORECASE,
)
_STATE_PATTERN = re.compile(
    r"\b(state|mode|init(?:ial)?|active|idle|running|fault|shutdown|"
    r"lifecycle|degrad|standby)\b",
    re.IGNORECASE,
)
_TRANSITION_PATTERN = re.compile(
    r"\b(transition|switch|change|from\s+\w+\s+to|enter|exit|trigger|event)\b",
    re.IGNORECASE,
)
_FAULT_PATTERN = re.compile(
    r"\b(fault|error|fail(?:ure)?|degraded|exception|alarm|warning)\b",
    re.IGNORECASE,
)


# ── Pre-checker ───────────────────────────────────────────────────────────────

class StructuralPreCheck:
    """Analyses a requirement set before generation to identify completeness gaps."""

    _MIN_REQS: dict[DiagramType, int] = {
        DiagramType.ACTIVITY:      1,
        DiagramType.SEQUENCE:      2,
        DiagramType.STATE_MACHINE: 1,
        DiagramType.CLASS:         1,
        DiagramType.COMPONENT:     2,
    }

    def check(
        self,
        requirements: list[Requirement],
        diagram_type: DiagramType,
    ) -> PreCheckResult:
        """Run pre-check for a given diagram type.

        Returns a PreCheckResult with gaps/warnings and an overall quality_score.
        """
        result = PreCheckResult(diagram_type=diagram_type.value)

        # ── Minimum requirement count ─────────────────────────────────────────
        min_needed = self._MIN_REQS.get(diagram_type, 1)
        if len(requirements) < min_needed:
            result.blocked = True
            result.quality_score = 0.0
            result.gaps.append(
                f"Only {len(requirements)} requirement(s) provided - "
                f"{min_needed} minimum needed for a {diagram_type.value} diagram."
            )
            return result

        all_text = " ".join(
            f"{r.title or ''} {r.description or ''}" for r in requirements
        )

        # ── Type-specific checks ──────────────────────────────────────────────
        dispatch = {
            DiagramType.ACTIVITY:      self._check_activity,
            DiagramType.SEQUENCE:      self._check_sequence,
            DiagramType.STATE_MACHINE: self._check_state_machine,
            DiagramType.CLASS:         self._check_class,
            DiagramType.COMPONENT:     self._check_component,
        }
        checker = dispatch.get(diagram_type)
        if checker:
            result = checker(requirements, all_text, result)

        # ── Compute quality score from penalties ──────────────────────────────
        penalty = len(result.gaps) * 0.15 + len(result.warnings) * 0.05
        result.quality_score = max(0.0, round(1.0 - penalty, 2))
        if result.quality_score < 0.4:
            result.blocked = True

        return result

    # ── Activity ──────────────────────────────────────────────────────────────

    def _check_activity(
        self,
        reqs: list[Requirement],
        all_text: str,
        result: PreCheckResult,
    ) -> PreCheckResult:
        # Check for RTE calls or action verbs
        has_rte = bool(_RTE_PATTERN.search(all_text))
        has_actions = bool(_ACTION_PATTERN.search(all_text))
        if not has_rte and not has_actions:
            result.gaps.append(
                "No RTE calls (Rte_Read/Write) or action verbs detected - "
                "add Rte_Read/Rte_Write references and conditional logic "
                "(if/check/compute) to get meaningful activity nodes."
            )

        # Check for owning SWC name
        swc_names = _SWC_PATTERN.findall(all_text)
        if not swc_names:
            result.gaps.append(
                "No SWC_* component name found - include the owning SWC name "
                "(SWC_PascalCase) and its Runnable (RE_PascalCase) so the diagram "
                "can be correctly attributed."
            )
        else:
            # Check for runnable
            if not _RUNNABLE_PATTERN.search(all_text):
                result.warnings.append(
                    f"SWC '{swc_names[0]}' found but no RE_* runnable name detected - "
                    "add the runnable name for proper AUTOSAR naming."
                )

        # Check for port references
        if not _PORT_PATTERN.search(all_text):
            result.gaps.append(
                "No port names (PP_* or RP_*) detected - include port names so "
                "Rte_Read/Rte_Write nodes can reference correct AUTOSAR ports."
            )

        # Suggest fault handling if absent (produces richer branching)
        if not _FAULT_PATTERN.search(all_text):
            result.suggestions.append(
                "Adding fault/error-handling requirements would produce richer "
                "activity diagrams with decision branches (if/else diamonds)."
            )

        return result

    # ── Sequence ──────────────────────────────────────────────────────────────

    def _check_sequence(
        self,
        reqs: list[Requirement],
        all_text: str,
        result: PreCheckResult,
    ) -> PreCheckResult:
        if not _COMMS_PATTERN.search(all_text):
            result.gaps.append(
                "No communication keywords (shall send/receive, interface, port) - "
                "sequence diagrams need sender/receiver relationships. "
                "Add 'shall send' or 'shall receive' descriptions."
            )

        swc_names = list(set(_SWC_PATTERN.findall(all_text)))
        if len(swc_names) < 2:
            result.gaps.append(
                f"Only {len(swc_names)} distinct SWC_* component(s) found - "
                "sequence diagrams need at least 2 lifelines. "
                "Add requirements referencing a second SWC."
            )
            result.blocked = True

        if not _PORT_PATTERN.search(all_text):
            result.warnings.append(
                "No port names (PP_* / RP_*) detected - sequence messages will "
                "lack specific RTE port references."
            )

        return result

    # ── State Machine ─────────────────────────────────────────────────────────

    def _check_state_machine(
        self,
        reqs: list[Requirement],
        all_text: str,
        result: PreCheckResult,
    ) -> PreCheckResult:
        if not _STATE_PATTERN.search(all_text):
            result.gaps.append(
                "No state/mode keywords detected (init, active, fault, shutdown, etc.) - "
                "state machines need lifecycle or mode descriptions. "
                "Add requirement text about operating modes."
            )

        if not _TRANSITION_PATTERN.search(all_text):
            result.gaps.append(
                "No state transition cues found - add trigger events "
                "(PowerOn, SensorFailure, InitComplete) to produce meaningful transitions."
            )

        if not _SWC_PATTERN.search(all_text):
            result.warnings.append(
                "No SWC_* name detected - the AI will infer the owner SWC from context."
            )

        return result

    # ── Class ─────────────────────────────────────────────────────────────────

    def _check_class(
        self,
        reqs: list[Requirement],
        all_text: str,
        result: PreCheckResult,
    ) -> PreCheckResult:
        if not _SWC_PATTERN.search(all_text):
            result.gaps.append(
                "No SWC_* names detected - class diagrams need component names "
                "as class identifiers. Add SWC_PascalCase references."
            )

        if not _RUNNABLE_PATTERN.search(all_text):
            result.gaps.append(
                "No RE_* runnable names detected - add runnable names so "
                "the AI can generate class operations."
            )

        return result

    # ── Component ─────────────────────────────────────────────────────────────

    def _check_component(
        self,
        reqs: list[Requirement],
        all_text: str,
        result: PreCheckResult,
    ) -> PreCheckResult:
        if not _PORT_PATTERN.search(all_text):
            result.gaps.append(
                "No port names (PP_* / RP_*) detected - component diagrams need "
                "port topology. Add provided/required port references."
            )

        connector_keywords = re.compile(
            r"\b(connect(?:s|ed)?|interface|receive\s+from|send\s+to|communicate|linked)\b",
            re.IGNORECASE,
        )
        if not connector_keywords.search(all_text):
            result.gaps.append(
                "No inter-component connection language detected - add descriptions "
                "of which SWCs communicate with each other via which ports."
            )

        swc_names = list(set(_SWC_PATTERN.findall(all_text)))
        if len(swc_names) < 2:
            result.gaps.append(
                f"Only {len(swc_names)} SWC_* component(s) found - "
                "component diagrams need at least 2 components with connectors."
            )

        return result
