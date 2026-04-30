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
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert AUTOSAR software architect.
Your task is to analyse a set of architectural requirements and produce a
structured module decomposition — one entry per Software Component (SWC).

RULES:
1. Identify every distinct SWC mentioned or implied by the requirements.
2. Use AUTOSAR SWC naming: SWC_PascalCase  (e.g. SWC_SensorFusion)
3. For each SWC extract:
   - short_name:    camelCase identifier  (e.g. sensorFusion)
   - description:   one sentence purpose
   - asil:          QM | ASIL-A | ASIL-B | ASIL-C | ASIL-D  (default QM)
   - runnables:     list of RE_ names (e.g. ["RE_Init","RE_FuseSensorData"])
   - req_ids:       list of requirement IDs that belong to this SWC
   - port_count:    estimated number of ports
   - calprm_count:  estimated number of calibration parameters
   - complexity:    low | medium | high
4. Output ONLY valid JSON — no markdown, no prose.

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
module decomposition JSON:

DETECTED HINTS:
{evidence_summary}

REQUIREMENTS:
{requirements_text}

Return only valid JSON."""

_REQUIREMENT_ID_RE = re.compile(r"\b[A-Z]+(?:-[A-Z]+)*-\d+\b")
_SWC_RE = re.compile(r"\bSWC_[A-Za-z][A-Za-z0-9_]*\b")
_RUNNABLE_RE = re.compile(r"\bRE_[A-Za-z][A-Za-z0-9_]*\b")
_PORT_RE = re.compile(r"\b(?:RP|PP)_[A-Za-z0-9_]+\b")
_CALPRM_RE = re.compile(r"\bCalPrm_[A-Za-z0-9_]+\b", flags=re.IGNORECASE)
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
        user_prompt = _USER_PROMPT_TMPL.format(
            requirements_text=requirements_text,
            evidence_summary=_build_evidence_summary(evidence_modules),
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
        if not summary:
            summary = _default_architecture_summary({m.swc_name: m for m in modules})

        logger.info("ModulePlanner: detected %d SWC modules", len(modules))
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
        blob = " ".join(
            str(row.get(k, "") or "")
            for k in ("title", "description", "module_hint", "notes", "safety_level")
        )
        swc_name = _normalize_swc_name(
            str(row.get("module_hint") or "") or _first_match(_SWC_RE, blob) or "SWC_Main"
        )
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
