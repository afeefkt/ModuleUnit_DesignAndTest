"""Module Planner — analyses architectural requirements and extracts SWC modules.

Stage 1 of the enhanced MUD workflow:
  1. Receive all raw architectural requirements
  2. AI analyses requirements and plans module decomposition
  3. Returns a list of ModuleInfo objects for the user to choose from

After module selection, the user picks one module and proceeds to Stage 2
(MUD Spec Generation via MudSpecGenerator).
"""

from __future__ import annotations

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

REQUIREMENTS:
{requirements_text}

Return only valid JSON."""

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
        user_prompt = _USER_PROMPT_TMPL.format(requirements_text=requirements_text)

        response = await backend.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=4096,
            response_format="json",   # ← module plan is always structured JSON
        )

        return self._parse_response(response.content)

    def _parse_response(self, raw: str) -> PlanResult:
        """Extract JSON from the AI response and build PlanResult."""
        # Strip markdown code fences if the model wrapped the JSON
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

        # Find the outermost JSON object
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("ModulePlanner: no JSON object found in response")
            return PlanResult(modules=[], architecture_summary="", raw_response=raw)

        json_str = cleaned[start:end]
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error("ModulePlanner: JSON parse error: %s", exc)
            return PlanResult(modules=[], architecture_summary="", raw_response=raw)

        modules = [
            ModuleInfo.from_dict(m)
            for m in data.get("modules", [])
        ]
        summary = data.get("architecture_summary", "")

        logger.info("ModulePlanner: detected %d SWC modules", len(modules))
        return PlanResult(modules=modules, architecture_summary=summary, raw_response=raw)
