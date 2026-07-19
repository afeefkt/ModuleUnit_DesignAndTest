"""Module Planner — analyses architectural requirements and extracts SWC modules.

Stage 1 of the enhanced MUD workflow:
  1. Receive all raw architectural requirements
  2. AI analyses requirements and plans module decomposition
  3. Returns a list of ModuleInfo objects for the user to choose from

After module selection, the user picks one module and proceeds to Stage 2
(MUD Spec Generation via MudSpecGenerator).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert AUTOSAR software architect.
Your task is to analyse a set of architectural requirements and produce a
structured module decomposition — one entry per Software Component (SWC).

DECOMPOSITION RULES — read carefully before responding:
1. Work at ARCHITECTURE level. Each SWC is a major functional domain
   (e.g. SWC_SpeedControl, SWC_CurrentControl, SWC_MotorMonitor).
   Sub-functions (overcurrent protection, overvoltage protection, stall
   detection, etc.) are RUNNABLES inside a parent SWC — NOT separate SWCs.

2. ❌ WRONG — over-decomposition (never do this):
     SWC_MtrMonOvercurrent, SWC_MtrMonOvervoltage, SWC_MtrMonOvertemp …
   ✅ CORRECT — one SWC, multiple runnables:
     SWC_MtrMon  with runnables [RE_OvercurrentProtection,
                                  RE_OvervoltageProtection,
                                  RE_OvertempProtection, …]

3. TARGET COUNT: aim for (total_requirements / 8) SWCs, rounded up.
   For ≤40 requirements: 2–6 SWCs.
   For 41–80 requirements: 4–10 SWCs.
   Never exceed 10 SWCs unless the requirements explicitly describe >10
   independent architectural components.

4. WHAT IS NOT A SWC — treat these as runnables or notes, never as new SWCs:
   - Coding/design constraints (no dynamic memory, MISRA rules, no globals)
     → add as a note; do NOT create a new SWC
   - Verification/test requirements (integration tests, test scenarios, coverage goals)
     → skip entirely; do NOT create a new SWC
   - Signal interface / connectivity specs (units, routing between SWCs)
     → add the ports to the relevant SWC; do NOT create a new SWC
   - Top-level architecture descriptions (closed-loop control chain, system flow)
     → use as context for decomposition; do NOT create SWC_ControlChain or SWC_System
   - Initialization patterns (initialize all integrators, set safe outputs on startup)
     → this is RE_Init inside each existing SWC; do NOT create SWC_Initialization

   A SWC must be an independently implementable unit with its own internal state
   and runnables. If a requirement only describes HOW other SWCs should behave
   (constraint, test, interface rule), it belongs inside those SWCs — not in a new one.

5. Use AUTOSAR SWC naming: SWC_PascalCase  (e.g. SWC_SensorFusion)

6. For each SWC extract:
   - short_name:    camelCase identifier  (e.g. sensorFusion)
   - description:   one sentence purpose
   - asil:          QM | ASIL-A | ASIL-B | ASIL-C | ASIL-D  (default QM)
   - runnables:     list of RE_ names — include ALL sub-functions as runnables
                    (e.g. ["RE_Init","RE_OvercurrentProtection","RE_FaultReport"])
   - req_ids:       list of requirement IDs that belong to this SWC
   - port_count:    estimated number of ports
   - calprm_count:  estimated number of calibration parameters
   - complexity:    low | medium | high

7. Output ONLY valid JSON — no markdown, no prose.

OUTPUT SCHEMA:
{
  "modules": [
    {
      "swc_name":    "SWC_Name",
      "short_name":  "swcShortName",
      "description": "One-sentence purpose",
      "asil":        "QM",
      "runnables":   ["RE_Init", "RE_Process"],
      "req_ids":     ["REQ-001", "REQ-002"],
      "port_count":  3,
      "calprm_count": 1,
      "complexity":  "medium"
    }
  ],
  "architecture_summary": "Brief paragraph summarising the overall system architecture"
}
"""

_USER_PROMPT_TMPL = """Analyse the following architectural requirements and return the
module decomposition JSON.

CONSTRAINT: {req_count} requirements total — target {target_swc_count} SWC(s).
Group sub-functions (protection types, control modes, diagnostic checks) as
RE_* runnables inside their parent SWC. Do NOT create a separate SWC for each
sub-function.

DETECTED HINTS (architecture-level SWCs only):
{evidence_summary}

REQUIREMENTS:
{requirements_text}

Return only valid JSON."""

_REQUIREMENT_ID_RE = re.compile(r"\b[A-Z]+(?:-[A-Z]+)*-\d+\b")
_SWC_RE = re.compile(r"\bSWC_[A-Za-z][A-Za-z0-9_]*\b")
_RUNNABLE_RE = re.compile(r"\bRE_[A-Za-z][A-Za-z0-9_]*\b")
_PORT_RE = re.compile(r"\b(?:RP|PP)_[A-Za-z0-9_]+\b")
_CALPRM_RE = re.compile(r"\bCalPrm_[A-Za-z0-9_]+\b", flags=re.IGNORECASE)

# Requirement types that should NOT generate a new SWC entry.
# These rows contribute ports/calprms to the existing module hint, but never
# cause a new SWC to be created from a Module_Hint=System or vague hint.
_NON_SWC_REQ_TYPES: frozenset[str] = frozenset({
    "constraint", "design_constraint", "implementation_constraint",
    "verification", "test", "testing", "validation",
    "interface", "connectivity", "signal_interface",
    "system", "architecture",            # top-level arch descriptions
})
_ASIL_ORDER = {"QM": 0, "ASIL-A": 1, "ASIL-B": 2, "ASIL-C": 3, "ASIL-D": 4}
_COMPLEXITY_ORDER = {"low": 0, "medium": 1, "high": 2}

# ── Data model ───────────────────────────────────────────────────────────────

@dataclass
class ModuleInfo:
    """Structured description of one SWC detected from architectural requirements."""
    swc_name: str
    short_name: str
    description: str
    asil: str = "QM"
    runnables: list[str] = field(default_factory=list)
    req_ids: list[str] = field(default_factory=list)
    port_count: int = 0
    calprm_count: int = 0
    complexity: str = "medium"

    def to_dict(self) -> dict:
        return {
            "swc_name": self.swc_name,
            "short_name": self.short_name,
            "description": self.description,
            "asil": self.asil,
            "runnables": self.runnables,
            "req_ids": self.req_ids,
            "port_count": self.port_count,
            "calprm_count": self.calprm_count,
            "complexity": self.complexity,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModuleInfo":
        return cls(
            swc_name=d.get("swc_name", "SWC_Unknown"),
            short_name=d.get("short_name", "unknown"),
            description=d.get("description", ""),
            asil=d.get("asil", "QM"),
            runnables=d.get("runnables", []),
            req_ids=d.get("req_ids", []),
            port_count=int(d.get("port_count", 0)),
            calprm_count=int(d.get("calprm_count", 0)),
            complexity=d.get("complexity", "medium"),
        )


@dataclass
class PlanResult:
    """Result returned by ModulePlanner.plan_modules()."""
    modules: list[ModuleInfo]
    architecture_summary: str = ""
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "modules": [m.to_dict() for m in self.modules],
            "architecture_summary": self.architecture_summary,
        }


# ── Planner class ────────────────────────────────────────────────────────────

class ModulePlanner:
    """Analyses architectural requirements and returns a list of SWC modules.

    Uses the active AI backend (cloud or local) via direct API call — does NOT
    use the diagram-generation pipeline.
    """

    def __init__(self, orchestrator):
        """
        Args:
            orchestrator: An initialised AIOrchestrator instance, used to access
                          the active backend and settings.
        """
        self._orchestrator = orchestrator

    async def plan_modules(
        self,
        requirements_text: str,
        temperature: float = 0.2,
    ) -> PlanResult:
        """Run AI module planning on the supplied requirements text.

        Args:
            requirements_text: Raw requirements as a single string (any format).
            temperature: Sampling temperature (lower = more deterministic).

        Returns:
            PlanResult with a list of ModuleInfo objects.
        """
        backend = self._orchestrator._get_backend()
        evidence_modules = _derive_modules_from_requirements_text(requirements_text)
        req_count = sum(len(m.req_ids) for m in evidence_modules.values()) or requirements_text.count("\n")
        target_swc_count = max(1, min(10, math.ceil(req_count / 8)))
        user_prompt = _USER_PROMPT_TMPL.format(
            requirements_text=requirements_text,
            evidence_summary=_build_evidence_summary(evidence_modules),
            req_count=req_count,
            target_swc_count=target_swc_count,
        )

        try:
            response = await backend.generate(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=4096,
                response_format="json",   # module plan is always structured JSON
            )
        except Exception as exc:
            logger.warning(
                "ModulePlanner: AI planning call failed (%s); using deterministic requirement evidence",
                exc,
            )
            return PlanResult(
                modules=_sort_modules(list(evidence_modules.values())),
                architecture_summary=_default_architecture_summary(evidence_modules),
                raw_response=str(exc),
            )

        plan = self._parse_response(response.content, evidence_modules)
        if plan.modules:
            return plan

        # Retry once with a smaller, evidence-anchored prompt when the first AI
        # answer is empty or malformed. This keeps planning AI-first but much
        # more resilient on smaller local models.
        retry_prompt = (
            "Return module decomposition JSON for the following AUTOSAR evidence.\n\n"
            f"{_build_evidence_summary(evidence_modules)}\n\n"
            "Use these exact SWC names, include matching RE_* runnables and req_ids, "
            "and return only valid JSON with top-level key 'modules'."
        )
        try:
            retry = await backend.generate(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=retry_prompt,
                temperature=min(temperature, 0.1),
                max_tokens=2048,
                response_format="json",
            )
        except Exception as exc:
            logger.warning(
                "ModulePlanner: AI planning retry failed (%s); using deterministic requirement evidence",
                exc,
            )
            return PlanResult(
                modules=_sort_modules(list(evidence_modules.values())),
                architecture_summary=(
                    plan.architecture_summary or _default_architecture_summary(evidence_modules)
                ),
                raw_response=response.content or str(exc),
            )
        repaired = self._parse_response(retry.content, evidence_modules)
        if repaired.modules:
            return repaired

        logger.warning(
            "ModulePlanner: AI planning returned no usable modules after retry; using deterministic requirement evidence"
        )
        return PlanResult(
            modules=_sort_modules(list(evidence_modules.values())),
            architecture_summary=(
                repaired.architecture_summary
                or plan.architecture_summary
                or _default_architecture_summary(evidence_modules)
            ),
            raw_response=retry.content or response.content,
        )

    def _parse_response(self, raw: str, evidence_modules: dict[str, ModuleInfo] | None = None) -> PlanResult:
        """Extract JSON from the AI response and build PlanResult."""
        evidence_modules = evidence_modules or {}
        json_str = _extract_json_payload(raw)
        if not json_str:
            logger.warning("ModulePlanner: no JSON payload found in response")
            return PlanResult(
                modules=[],
                architecture_summary=_default_architecture_summary(evidence_modules),
                raw_response=raw,
            )
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error("ModulePlanner: JSON parse error: %s", exc)
            return PlanResult(
                modules=[],
                architecture_summary=_default_architecture_summary(evidence_modules),
                raw_response=raw,
            )

        modules_raw: list[dict] = []
        summary = ""
        if isinstance(data, list):
            modules_raw = [m for m in data if isinstance(m, dict)]
        elif isinstance(data, dict):
            summary = str(data.get("architecture_summary", "") or "")
            for key in ("modules", "swcs", "components"):
                value = data.get(key)
                if isinstance(value, list):
                    modules_raw = [m for m in value if isinstance(m, dict)]
                    break

        ai_modules = [_module_from_ai_dict(m) for m in modules_raw]
        modules = _merge_ai_and_evidence(ai_modules, evidence_modules)
        modules = _consolidate_sub_swcs(modules)
        modules = _filter_weak_modules(modules)
        if not summary:
            summary = _default_architecture_summary({m.swc_name: m for m in modules})

        logger.info("ModulePlanner: detected %d SWC modules (after consolidation + filter)", len(modules))
        return PlanResult(modules=modules, architecture_summary=summary, raw_response=raw)


def _extract_json_payload(raw: str) -> str:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw or "").strip().rstrip("`").strip()
    candidates: list[tuple[int, int]] = []
    obj_start = cleaned.find("{")
    obj_end = cleaned.rfind("}") + 1
    if obj_start != -1 and obj_end > obj_start:
        candidates.append((obj_start, obj_end))
    arr_start = cleaned.find("[")
    arr_end = cleaned.rfind("]") + 1
    if arr_start != -1 and arr_end > arr_start:
        candidates.append((arr_start, arr_end))
    if not candidates:
        return ""
    start, end = min(candidates, key=lambda item: item[0])
    return cleaned[start:end]


def _module_from_ai_dict(data: dict) -> ModuleInfo:
    swc_name = _normalize_swc_name(
        str(
            data.get("swc_name")
            or data.get("name")
            or data.get("module_name")
            or data.get("component_name")
            or "SWC_Unknown"
        )
    )
    runnables = _dedupe_preserve_order(
        _normalize_runnables(data.get("runnables"))
        or _extract_runnables_from_text(" ".join(str(data.get(k, "")) for k in ("description", "summary", "title")))
    )
    req_ids = _dedupe_preserve_order(_extract_req_ids(data.get("req_ids")))
    asil = _normalize_asil(str(data.get("asil", "QM") or "QM"))
    complexity = _normalize_complexity(str(data.get("complexity", "medium") or "medium"))
    description = str(data.get("description", "") or "").strip()
    short_name = str(data.get("short_name", "") or "").strip() or _short_name_from_swc(swc_name)
    return ModuleInfo(
        swc_name=swc_name,
        short_name=short_name,
        description=description,
        asil=asil,
        runnables=runnables,
        req_ids=req_ids,
        port_count=_safe_int(data.get("port_count")),
        calprm_count=_safe_int(data.get("calprm_count")),
        complexity=complexity,
    )


def _merge_ai_and_evidence(
    ai_modules: list[ModuleInfo],
    evidence_modules: dict[str, ModuleInfo],
) -> list[ModuleInfo]:
    if not ai_modules:
        return _sort_modules(list(evidence_modules.values()))

    merged: dict[str, ModuleInfo] = {}
    single_evidence = next(iter(evidence_modules.values()), None) if len(evidence_modules) == 1 else None
    for ai in ai_modules:
        swc_name = ai.swc_name
        if (not swc_name or swc_name == "SWC_Unknown") and single_evidence:
            swc_name = single_evidence.swc_name
            ai.swc_name = swc_name
            ai.short_name = ai.short_name if ai.short_name != "unknown" else single_evidence.short_name
        evidence = evidence_modules.get(swc_name)
        merged[swc_name] = _combine_module_info(ai, evidence)

    for swc_name, evidence in evidence_modules.items():
        if swc_name not in merged:
            merged[swc_name] = evidence

    return _sort_modules(list(merged.values()))


def _combine_module_info(ai: ModuleInfo, evidence: ModuleInfo | None) -> ModuleInfo:
    if evidence is None:
        ai.short_name = ai.short_name or _short_name_from_swc(ai.swc_name)
        ai.description = ai.description or _default_module_description(ai.swc_name, ai.req_ids)
        ai.complexity = _normalize_complexity(ai.complexity)
        ai.asil = _normalize_asil(ai.asil)
        ai.runnables = _dedupe_preserve_order(ai.runnables)
        ai.req_ids = _dedupe_preserve_order(ai.req_ids)
        return ai
    return ModuleInfo(
        swc_name=evidence.swc_name if ai.swc_name == "SWC_Unknown" else ai.swc_name or evidence.swc_name,
        short_name=ai.short_name if ai.short_name and ai.short_name != "unknown" else evidence.short_name,
        description=ai.description or evidence.description,
        asil=_stronger_asil(ai.asil, evidence.asil),
        runnables=_dedupe_preserve_order(ai.runnables + evidence.runnables),
        req_ids=_dedupe_preserve_order(ai.req_ids + evidence.req_ids),
        port_count=max(ai.port_count, evidence.port_count),
        calprm_count=max(ai.calprm_count, evidence.calprm_count),
        complexity=_stronger_complexity(ai.complexity, evidence.complexity),
    )


def _derive_modules_from_requirements_text(requirements_text: str) -> dict[str, ModuleInfo]:
    rows = _parse_requirement_rows(requirements_text)
    if not rows:
        return _derive_modules_from_free_text(requirements_text)

    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        # Classify the requirement type — constraints, tests, and interface-only
        # requirements do NOT become new SWCs; they contribute to existing SWCs only.
        req_type = str(row.get("type", "") or "").strip().lower().replace(" ", "_").replace("-", "_")

        blob = " ".join(
            str(row.get(k, "") or "")
            for k in ("title", "description", "module_hint", "notes", "safety_level")
        )
        raw_hint = str(row.get("module_hint") or "").strip()
        swc_name = _normalize_swc_name(
            raw_hint or _first_match(_SWC_RE, blob) or "SWC_Main"
        )

        if req_type in _NON_SWC_REQ_TYPES:
            # Don't create a new SWC for this requirement type.
            # If a real SWC already exists for this module_hint, add the req_id there;
            # otherwise just skip it — it will be handled by the AI prompt context.
            req_id = str(row.get("req_id", "") or "").strip()
            if swc_name in grouped and req_id:
                grouped[swc_name]["req_ids"].append(req_id)  # type: ignore[index]
            logger.debug(
                "ModulePlanner: skipping req %s (type=%s) from SWC creation",
                str(row.get("req_id", "")), req_type,
            )
            continue

        entry = grouped.setdefault(
            swc_name,
            {
                "req_ids": [],
                "runnables": [],
                "port_names": set(),
                "calprm_names": set(),
                "titles": [],
                "asils": [],
            },
        )
        req_ids = entry["req_ids"]
        runnables = entry["runnables"]
        port_names = entry["port_names"]
        calprm_names = entry["calprm_names"]
        titles = entry["titles"]
        asils = entry["asils"]

        req_id = str(row.get("req_id", "") or "").strip()
        if req_id:
            req_ids.append(req_id)
        title = str(row.get("title", "") or "").strip()
        if title:
            titles.append(title)
        asil = _normalize_asil(str(row.get("safety_level", "") or "") or _first_match(re.compile(r"\bASIL-[A-D]\b|\bQM\b"), blob) or "QM")
        asils.append(asil)
        runnables.extend(_extract_runnables_from_text(blob))
        port_names.update(_PORT_RE.findall(blob))
        calprm_names.update(_CALPRM_RE.findall(blob))
        if "calibration parameter" in blob.lower():
            calprm_names.add("calibration_parameter")

    modules: dict[str, ModuleInfo] = {}
    for swc_name, entry in grouped.items():
        req_ids = _dedupe_preserve_order(entry["req_ids"])
        runnables = _dedupe_preserve_order(entry["runnables"])
        titles = entry["titles"]
        asils = entry["asils"]
        port_names = entry["port_names"]
        calprm_names = entry["calprm_names"]
        modules[swc_name] = ModuleInfo(
            swc_name=swc_name,
            short_name=_short_name_from_swc(swc_name),
            description=_derive_description_from_titles(swc_name, titles, req_ids),
            asil=_strongest_asil(asils),
            runnables=runnables,
            req_ids=req_ids,
            port_count=len(port_names),
            calprm_count=len(calprm_names),
            complexity=_derive_complexity(len(req_ids), len(runnables), len(port_names), len(calprm_names)),
        )
    return modules


def _derive_modules_from_free_text(requirements_text: str) -> dict[str, ModuleInfo]:
    req_ids = _dedupe_preserve_order(_REQUIREMENT_ID_RE.findall(requirements_text or ""))
    swc_names = _dedupe_preserve_order(_normalize_swc_name(name) for name in _SWC_RE.findall(requirements_text or ""))
    if not swc_names:
        swc_names = ["SWC_Main"]
    modules: dict[str, ModuleInfo] = {}
    all_runnables = _dedupe_preserve_order(_RUNNABLE_RE.findall(requirements_text or ""))
    asil = _strongest_asil(re.findall(r"\bASIL-[A-D]\b|\bQM\b", requirements_text or "", flags=re.IGNORECASE))
    port_count = len(set(_PORT_RE.findall(requirements_text or "")))
    calprm_names = set(_CALPRM_RE.findall(requirements_text or ""))
    if "calibration parameter" in (requirements_text or "").lower():
        calprm_names.add("calibration_parameter")
    for swc_name in swc_names:
        modules[swc_name] = ModuleInfo(
            swc_name=swc_name,
            short_name=_short_name_from_swc(swc_name),
            description=_default_module_description(swc_name, req_ids),
            asil=asil,
            runnables=all_runnables,
            req_ids=req_ids,
            port_count=port_count,
            calprm_count=len(calprm_names),
            complexity=_derive_complexity(len(req_ids), len(all_runnables), port_count, len(calprm_names)),
        )
    return modules


def _parse_requirement_rows(requirements_text: str) -> list[dict[str, str]]:
    text = (requirements_text or "").strip()
    if not text:
        return []
    first_line = text.splitlines()[0].lower()
    if "req_id" not in first_line or "," not in first_line:
        return []
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            if not row:
                continue
            normalized = {str(k or "").strip().lower(): str(v or "").strip() for k, v in row.items()}
            if normalized.get("req_id"):
                rows.append(normalized)
        return rows
    except csv.Error:
        return []


def _build_evidence_summary(evidence_modules: dict[str, ModuleInfo]) -> str:
    if not evidence_modules:
        return "- No deterministic hints extracted."
    lines: list[str] = []
    for module in _sort_modules(list(evidence_modules.values())):
        lines.append(
            f"- {module.swc_name} | asil={module.asil} | reqs={len(module.req_ids)} "
            f"| runnables={module.runnables[:8]} | ports={module.port_count} | calprms={module.calprm_count}"
        )
    return "\n".join(lines)


def _default_architecture_summary(evidence_modules: dict[str, ModuleInfo]) -> str:
    if not evidence_modules:
        return ""
    names = [m.swc_name for m in _sort_modules(list(evidence_modules.values()))]
    if len(names) == 1:
        return f"The requirements describe a single AUTOSAR software component: {names[0]}."
    return f"The requirements describe {len(names)} AUTOSAR software components: {', '.join(names)}."


_ORPHAN_KEYWORDS: frozenset[str] = frozenset({
    "test", "verif", "constraint", "avoid", "prevent", "ensure",
    "signal", "interface", "chain", "init", "system", "architecture",
})


def _name_similarity(a: str, b: str) -> int:
    """Count characters of common prefix between two SWC names (case-insensitive)."""
    a_norm = re.sub(r"^SWC_", "", a).lower()
    b_norm = re.sub(r"^SWC_", "", b).lower()
    count = 0
    for ca, cb in zip(a_norm, b_norm):
        if ca == cb:
            count += 1
        else:
            break
    return count


def _filter_weak_modules(modules: list[ModuleInfo]) -> list[ModuleInfo]:
    """Remove artifacts (0-req SWCs) and absorb 1-req non-functional orphans.

    A "non-functional orphan" is a SWC with only 1 requirement whose name or
    description contains constraint/test/interface keywords.  These are absorbed
    into the most name-similar real SWC so their req_id is not lost.
    """
    if len(modules) <= 2:
        return modules  # nothing to filter — keep all

    strong: list[ModuleInfo] = [m for m in modules if len(m.req_ids) >= 2]
    one_req: list[ModuleInfo] = [m for m in modules if len(m.req_ids) == 1]
    zero_req: list[ModuleInfo] = [m for m in modules if len(m.req_ids) == 0]

    for m in zero_req:
        logger.info("ModulePlanner: dropping %s (0 requirements — artifact)", m.swc_name)

    for orphan in one_req:
        label = (orphan.swc_name + " " + orphan.description).lower()
        is_non_functional = any(kw in label for kw in _ORPHAN_KEYWORDS)
        if not is_non_functional:
            strong.append(orphan)  # looks like a real SWC — keep it
            continue
        # Absorb into the most name-similar strong SWC
        best = max(strong, key=lambda m: _name_similarity(m.swc_name, orphan.swc_name), default=None)
        if best:
            best.req_ids = _dedupe_preserve_order(best.req_ids + orphan.req_ids)
            best.runnables = _dedupe_preserve_order(best.runnables + orphan.runnables)
            logger.info(
                "ModulePlanner: absorbed 1-req orphan %s → %s", orphan.swc_name, best.swc_name
            )
        else:
            strong.append(orphan)  # no good match — keep it rather than lose the req

    return _sort_modules(strong)


def _consolidate_sub_swcs(modules: list[ModuleInfo]) -> list[ModuleInfo]:
    """Merge over-decomposed sub-SWCs back into their architecture-level parent.

    When the AI produces SWC_MtrMonOvercurrent + SWC_MtrMonOvervoltage + …
    this function detects them by shared prefix and merges them into SWC_MtrMon,
    converting each child SWC into a runnable of the parent.

    A "parent" is the SWC whose name is a prefix of at least one sibling name.
    The merge only fires when a cluster of ≥3 SWCs share a common SWC_ prefix
    (to avoid merging genuinely independent SWCs that happen to share a word).
    """
    if len(modules) <= 4:
        return modules  # small result — nothing to consolidate

    # Build prefix groups: strip SWC_ then take the first PascalCase word
    def _parent_prefix(swc_name: str) -> str:
        base = re.sub(r"^SWC_", "", swc_name)
        # Split on PascalCase boundary: SWC_MtrMonOvercurrent → ["Mtr", "Mon", "Overcurrent"]
        parts = re.findall(r"[A-Z][a-z0-9]*", base)
        # Use first 1–2 parts as the canonical parent prefix
        return "SWC_" + "".join(parts[:2]) if len(parts) >= 2 else swc_name

    from collections import defaultdict
    prefix_groups: dict[str, list[ModuleInfo]] = defaultdict(list)
    for m in modules:
        prefix_groups[_parent_prefix(m.swc_name)].append(m)

    merged: list[ModuleInfo] = []
    for parent_name, group in prefix_groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue
        # Only merge when 2+ SWCs share the prefix AND the parent name differs
        # from each child — avoids merging unrelated short-prefix coincidences.
        if len(group) < 2:
            merged.extend(group)
            continue

        # Check if one of the group members IS already the parent (exact name match)
        exact_parent = next((m for m in group if m.swc_name == parent_name), None)

        # Merge all children into the parent (or build a new parent)
        combined_runnables: list[str] = []
        combined_req_ids: list[str] = []
        combined_port_count = 0
        combined_calprm_count = 0
        asils: list[str] = []
        descriptions: list[str] = []

        for child in group:
            # Convert the child SWC itself into a runnable name
            child_base = re.sub(r"^SWC_", "", child.swc_name)
            child_as_runnable = "RE_" + child_base
            if child_as_runnable not in combined_runnables:
                combined_runnables.append(child_as_runnable)
            combined_runnables.extend(child.runnables)
            combined_req_ids.extend(child.req_ids)
            combined_port_count += child.port_count
            combined_calprm_count += child.calprm_count
            asils.append(child.asil)
            if child.description:
                descriptions.append(child.description)

        combined_runnables = _dedupe_preserve_order(combined_runnables)
        combined_req_ids = _dedupe_preserve_order(combined_req_ids)

        base_module = exact_parent or group[0]
        description = (
            base_module.description
            or f"{parent_name} consolidates {len(group)} functional sub-components."
        )

        merged.append(ModuleInfo(
            swc_name=parent_name,
            short_name=_short_name_from_swc(parent_name),
            description=description,
            asil=_strongest_asil(asils),
            runnables=combined_runnables,
            req_ids=combined_req_ids,
            port_count=combined_port_count,
            calprm_count=combined_calprm_count,
            complexity=_derive_complexity(
                len(combined_req_ids),
                len(combined_runnables),
                combined_port_count,
                combined_calprm_count,
            ),
        ))
        logger.info(
            "ModulePlanner: consolidated %d sub-SWCs into %s (%d runnables)",
            len(group), parent_name, len(combined_runnables),
        )

    return _sort_modules(merged)


def _sort_modules(modules: list[ModuleInfo]) -> list[ModuleInfo]:
    return sorted(modules, key=lambda m: (-len(m.req_ids), m.swc_name))


def _normalize_swc_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return "SWC_Unknown"
    match = _SWC_RE.search(raw)
    if match:
        return match.group(0)
    if raw.upper().startswith("SWC_"):
        raw = raw[4:]
    words = re.findall(r"[A-Za-z0-9]+", raw)
    if not words:
        return "SWC_Unknown"
    return "SWC_" + "".join(word[:1].upper() + word[1:] for word in words)


def _short_name_from_swc(swc_name: str) -> str:
    base = re.sub(r"^SWC_", "", swc_name or "")
    parts = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z]|$)", base)
    if not parts:
        return "unknown"
    return parts[0].lower() + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _normalize_asil(value: str) -> str:
    raw = (value or "").strip().upper().replace("_", "-")
    if raw in _ASIL_ORDER:
        return raw
    if raw in {"A", "ASILA", "ASIL-A"}:
        return "ASIL-A"
    if raw in {"B", "ASILB", "ASIL-B"}:
        return "ASIL-B"
    if raw in {"C", "ASILC", "ASIL-C"}:
        return "ASIL-C"
    if raw in {"D", "ASILD", "ASIL-D"}:
        return "ASIL-D"
    return "QM"


def _strongest_asil(values: list[str]) -> str:
    normalized = [_normalize_asil(v) for v in values if v]
    if not normalized:
        return "QM"
    return max(normalized, key=lambda v: _ASIL_ORDER.get(v, 0))


def _stronger_asil(left: str, right: str) -> str:
    return _strongest_asil([left, right])


def _normalize_complexity(value: str) -> str:
    lowered = (value or "").strip().lower()
    return lowered if lowered in _COMPLEXITY_ORDER else "medium"


def _stronger_complexity(left: str, right: str) -> str:
    left_n = _normalize_complexity(left)
    right_n = _normalize_complexity(right)
    return left_n if _COMPLEXITY_ORDER[left_n] >= _COMPLEXITY_ORDER[right_n] else right_n


def _derive_complexity(req_count: int, runnable_count: int, port_count: int, calprm_count: int) -> str:
    score = req_count + (2 * runnable_count) + port_count + calprm_count
    if score >= 18:
        return "high"
    if score >= 8:
        return "medium"
    return "low"


def _normalize_runnables(value: object) -> list[str]:
    if isinstance(value, list):
        candidates = [str(v) for v in value]
    elif isinstance(value, str):
        candidates = re.split(r"[,;\n]", value)
    else:
        return []
    normalized = []
    for candidate in candidates:
        normalized.extend(_RUNNABLE_RE.findall(candidate))
    return _dedupe_preserve_order(normalized)


def _extract_runnables_from_text(text: str) -> list[str]:
    return _dedupe_preserve_order(_RUNNABLE_RE.findall(text or ""))


def _extract_req_ids(value: object) -> list[str]:
    if isinstance(value, list):
        parts = [str(v) for v in value]
    else:
        parts = [str(value or "")]
    req_ids: list[str] = []
    for part in parts:
        req_ids.extend(_REQUIREMENT_ID_RE.findall(part))
    return req_ids


def _derive_description_from_titles(swc_name: str, titles: list[str], req_ids: list[str]) -> str:
    for title in titles:
        cleaned = re.sub(r"\s+", " ", title).strip()
        if cleaned:
            return f"{swc_name} handles {cleaned[:1].lower() + cleaned[1:]}."
    return _default_module_description(swc_name, req_ids)


def _default_module_description(swc_name: str, req_ids: list[str]) -> str:
    return f"{swc_name} covers {len(req_ids)} requirement(s) from the imported architecture set."


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        value = (item or "").strip()
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text or "")
    return match.group(0) if match else ""


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
