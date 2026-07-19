"""Skill loader — full-document injection for activity diagram system prompts.

Skills in data/skills/ are NOT chunked (unlike guidelines RAG).
The entire skill block is prepended to the system prompt so procedural
rules (M1-M10, pattern templates) stay coherent for qwen2.5-coder:7b.
"""

from __future__ import annotations

from pathlib import Path

from mudtool.config.settings import Settings


class SkillLoader:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._skills_dir = settings.get_skills_dir()

    def load_skill(self, filename: str) -> str:
        """Return full contents of a skill file, stripping YAML frontmatter."""
        path = self._skills_dir / filename
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        # Strip YAML frontmatter (---...---)
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3:].lstrip("\n")
        return text

    def build_activity_skill_block(self) -> str:
        """Return a condensed JSON-rule injection block for activity diagram prompts.

        Reinforces the critical JSON output fields that qwen2.5-coder:7b most often
        omits or gets wrong, based on observed failure patterns:
          - Missing owner_swc / owner_runnable → AUT-007 validation failure
          - Missing initial/final nodes → STR-020 validation failure
          - Decision nodes without guards → invalid diagram structure
          - Node IDs not following N_XX format → parser rejection
        """
        if not (self._skills_dir / "MUD_SKILL_CORE.md").exists():
            return ""

        block = """### AUTOSAR ACTIVITY DIAGRAM — CRITICAL JSON RULES (verify before output)

OUTPUT FORMAT: Pure JSON only. No markdown. No explanation. No ```json fences.

MANDATORY FIELDS on every diagram object:
  "owner_swc"      : "SWC_<Name>"   ← REQUIRED or AUT-007 validation fails
  "owner_runnable" : "RE_<Name>"    ← REQUIRED or AUT-007 validation fails

MANDATORY NODES — every diagram MUST contain both:
  {"id":"N_01","name":"Start","node_type":"initial",...}   ← first node
  {"id":"N_XX","name":"End",  "node_type":"final",  ...}   ← last node

NODE ID FORMAT: N_01, N_02, N_03 ... (two-digit, zero-padded)
EDGE ID FORMAT: E_01, E_02 ... or E_03a/E_03b for decision branches

DECISION NODE RULE: every "node_type":"decision" MUST have >=2 outgoing edges,
  each with a "guard" field: {"guard":"[condition_true]"} and {"guard":"[condition_false]"}

STANDARD FLOW: initial → call(Rte_Read) → decision(validate) → action(compute) → call(Rte_Write) → final

AUTOSAR NAMING:
  owner_swc       → SWC_PascalCase   (e.g. "SWC_ElectricPowerSteering")
  owner_runnable  → RE_PascalCase    (e.g. "RE_ControlTorque")
  port field      → PP_ or RP_ prefix (e.g. "PP_AssistTorque", "RP_VehicleSpeed")
  node names      → C pseudocode     (e.g. "Rte_Read_RP_Speed_Val(&l_f32Speed)")
"""
        return block
