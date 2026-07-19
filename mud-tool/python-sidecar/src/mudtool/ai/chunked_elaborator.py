"""Chunked Requirement Elaboration for Small Models (2–3B parameters).

Instead of asking the model to produce one large coherent document,
this module breaks elaboration into three small, constrained generation
calls and assembles the result with Python code.

Why chunked?
  A Qwen 2.5 2B model can reliably produce ~500 tokens of well-formed JSON
  in a single call.  Asking it to produce a 3000-word ARS document in one
  shot causes drift, repeated rows, and hallucinated table entries.

Generation stages (each ≤ 500 tokens output):
  Stage 1  — SWC identification
             Input : N requirements
             Output: JSON list  [{name, req_ids, purpose}]   ~100 tokens
             One AI call for the entire requirement set.

  Stage 2  — Port table per SWC
             Input : SWC name + its requirement texts
             Output: JSON list  [{port, direction, interface, data_type, desc}]
             One AI call per SWC.

  Stage 3  — Runnable list + pseudocode per SWC
             Input : SWC name + its requirement texts + ports (from stage 2)
             Output: JSON list  [{runnable, trigger, period_ms, pseudocode:[]}]
             One AI call per SWC.

  Stage 4  — Assembly (no AI)
             Python code assembles the stage 1–3 outputs into the same
             `elaborated_data` dict format produced by RequirementElaborator,
             so the rest of the pipeline (build_enriched_context, diagram
             generation) works without any changes.

Output dict is compatible with RequirementElaborator.elaborate():
  {
    "thinking":            ["Identified N SWCs: ...", ...],
    "architecture_summary": "...",
    "elaborated": [
        {"req_id": "REQ-001", "entities": {...}, "logic_flow": "...",
         "diagram_hints": {...}},
        ...
    ],
    # Extra keys with full structured data for MUD-doc assembly:
    "swc_list":      [{name, req_ids, purpose}],
    "swc_ports":     {"SWC_Name": [{port, direction, ...}]},
    "swc_runnables": {"SWC_Name": [{runnable, trigger, pseudocode:[]}]},
    "req_hash": "...", "parse_ok": true, "status": "ok",
    "source": "chunked_generation"
  }
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mudtool.ai.base_backend import BaseAIBackend
from mudtool.config.settings import Settings
from mudtool.models.requirements import Requirement

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "elaborated"


def _purge_stale_cache(keep: Path) -> None:
    """Delete all elaboration cache files except *keep*.

    Mirrors the function in elaborator.py — both elaborators share the same
    cache directory so cleanup from either one clears both single-shot and
    chunked stale files at once.
    """
    deleted = 0
    for old in _CACHE_DIR.glob("*.json"):
        if old == keep:
            continue
        try:
            old.unlink()
            deleted += 1
        except Exception as exc:
            logger.warning("Could not remove stale elaboration cache %s: %s", old.name, exc)
    if deleted:
        logger.info("Purged %d stale elaboration cache file(s) from %s", deleted, _CACHE_DIR)


# Maximum number of SWCs to process — caps AI call count on large requirement sets
_MAX_SWCS = 8
# Hard cap on output tokens per stage call — keeps small models in their reliable range
_STAGE1_MAX_TOKENS = 256
_STAGE2_MAX_TOKENS = 384
_STAGE3_MAX_TOKENS = 512


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(text: str) -> list | dict | None:
    """Extract the first valid JSON array or object from model output."""
    text = text.strip()
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        if start == -1:
            continue
        end = text.rfind(end_char)
        if end > start:
            try:
                return json.loads(text[start: end + 1])
            except json.JSONDecodeError:
                pass
    # Try markdown code block
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    return None


# ── Stage prompt builders ─────────────────────────────────────────────────────

def _stage1_prompts(requirements: list[Requirement]) -> tuple[str, str]:
    """Build (system, user) prompts for SWC identification."""
    system = (
        "You are an AUTOSAR software architect. "
        "Analyze requirements and identify the Software Components (SWCs) needed. "
        "Output ONLY a valid JSON array — no explanation, no markdown outside the JSON.\n\n"
        "Schema: [{\"name\": \"SWC_PascalCase\", \"req_ids\": [\"REQ-1\"], "
        "\"purpose\": \"one sentence\"}]"
    )
    reqs_text = "\n".join(
        f"[{r.req_id}] {r.title}: {r.description}" for r in requirements
    )
    user = (
        f"Requirements ({len(requirements)} total):\n{reqs_text}\n\n"
        f"Identify the AUTOSAR SWCs (max {_MAX_SWCS}). "
        "Return ONLY the JSON array."
    )
    return system, user


def _stage2_prompts(
    swc_name: str,
    swc_reqs: list[Requirement],
) -> tuple[str, str]:
    """Build (system, user) prompts for port table generation."""
    system = (
        "You are an AUTOSAR software architect. "
        "List the AUTOSAR ports for one SWC. "
        "Output ONLY a valid JSON array — no explanation, no markdown outside the JSON.\n\n"
        "Schema: [{\"port\": \"PP_PascalCase\", \"direction\": \"provided|required\", "
        "\"interface\": \"IF_SR_Name\", \"data_type\": \"uint8\", "
        "\"description\": \"what data flows\"}]"
    )
    reqs_text = "\n".join(
        f"[{r.req_id}] {r.title}: {r.description}" for r in swc_reqs
    )
    user = (
        f"SWC: {swc_name}\n"
        f"Requirements handled by this SWC:\n{reqs_text}\n\n"
        "List the AUTOSAR ports (Provided and Required). Return ONLY the JSON array."
    )
    return system, user


def _stage3_prompts(
    swc_name: str,
    swc_reqs: list[Requirement],
    ports: list[dict],
) -> tuple[str, str]:
    """Build (system, user) prompts for runnable + pseudocode generation."""
    system = (
        "You are an AUTOSAR software architect. "
        "List the Runnables for one SWC and write brief pseudocode for each. "
        "Output ONLY a valid JSON array — no explanation, no markdown outside the JSON.\n\n"
        "Schema: [{\"runnable\": \"RE_PascalCase\", "
        "\"trigger\": \"init|cyclic|on_data_reception\", "
        "\"period_ms\": 10, "
        "\"pseudocode\": [\"step 1 description\", \"step 2 description\"]}]\n"
        "period_ms is only relevant for cyclic trigger, use 0 otherwise."
    )
    reqs_text = "\n".join(
        f"[{r.req_id}] {r.title}: {r.description}" for r in swc_reqs
    )
    port_names = [p.get("port", "") for p in ports]
    port_summary = ", ".join(port_names) if port_names else "(none identified)"
    user = (
        f"SWC: {swc_name}\n"
        f"Ports: {port_summary}\n"
        f"Requirements:\n{reqs_text}\n\n"
        "List the Runnables with pseudocode steps (max 6 steps per runnable). "
        "Return ONLY the JSON array."
    )
    return system, user


# ── Fallback helpers (when a stage call fails) ────────────────────────────────

def _fallback_swc_list(requirements: list[Requirement]) -> list[dict]:
    """Infer a minimal SWC list from requirement module_hints or req_ids."""
    swcs: dict[str, list[str]] = {}
    for r in requirements:
        hint = (r.module_hint or "").strip()
        if hint and not hint.upper().startswith("SWC_"):
            # Normalise hint to SWC_PascalCase
            words = re.sub(r"[^a-zA-Z0-9 ]", " ", hint).split()
            hint = "SWC_" + "".join(w.capitalize() for w in words if w)
        key = hint if hint else "SWC_Main"
        swcs.setdefault(key, []).append(r.req_id)
    return [
        {"name": name, "req_ids": ids, "purpose": f"Handles {name} functionality"}
        for name, ids in swcs.items()
    ]


def _fallback_ports(swc_name: str) -> list[dict]:
    return [
        {
            "port": f"PP_{swc_name.replace('SWC_', '')}Out",
            "direction": "provided",
            "interface": f"IF_SR_{swc_name.replace('SWC_', '')}If",
            "data_type": "uint8",
            "description": f"Output data from {swc_name}",
        }
    ]


def _fallback_runnables(swc_name: str) -> list[dict]:
    short = swc_name.replace("SWC_", "")
    return [
        {
            "runnable": f"RE_{short}Init",
            "trigger": "init",
            "period_ms": 0,
            "pseudocode": ["Initialize internal state", "Configure ports"],
        },
        {
            "runnable": f"RE_{short}Process",
            "trigger": "cyclic",
            "period_ms": 10,
            "pseudocode": [
                "Read input data via Rte_Read",
                "Process data",
                "Write output via Rte_Write",
            ],
        },
    ]


# ── Main chunked elaborator class ─────────────────────────────────────────────

class ChunkedElaborator:
    """Elaborates requirements via small, reliable, chunked AI calls.

    Produces the same output format as RequirementElaborator so the
    rest of the pipeline (build_enriched_context, diagram generation)
    is completely unchanged.
    """

    def __init__(self, settings: Settings, backend: BaseAIBackend):
        self.settings = settings
        self.backend = backend

    @staticmethod
    def _compute_hash(requirements: list[Requirement]) -> str:
        text = "\n".join(
            f"{r.req_id}|{r.req_type.value}|{r.title}|{r.description}"
            for r in sorted(requirements, key=lambda r: r.req_id)
        )
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    @staticmethod
    def get_cache_path(req_hash: str) -> Path:
        return _CACHE_DIR / f"chunked_{req_hash}.json"

    def load_cached(self, requirements: list[Requirement]) -> Optional[dict]:
        req_hash = self._compute_hash(requirements)
        cache_path = self.get_cache_path(req_hash)
        if not cache_path.exists():
            return None
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if data.get("status") == "ok" and data.get("elaborated"):
                logger.info(f"Loaded chunked elaboration from cache: {cache_path}")
                data["source"] = "cache_hit"
                return data
        except Exception as exc:
            logger.warning(f"Failed to load chunked elaboration cache: {exc}")
        return None

    def _save_cache(self, data: dict) -> None:
        if data.get("status") != "ok":
            return
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = self.get_cache_path(data.get("req_hash", "unknown"))
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved chunked elaboration cache: {path}")
        # Purge stale files from previous imports so old data can't pollute future runs
        _purge_stale_cache(keep=path)

    # ── Stage runners ──────────────────────────────────────────────────────────

    async def _run_stage1(
        self,
        requirements: list[Requirement],
        progress_callback: Optional[callable],
    ) -> list[dict]:
        """Stage 1: Identify SWCs. Returns list of {name, req_ids, purpose}."""
        if progress_callback:
            progress_callback({
                "stage": "elaborate_chunk",
                "chunk": "stage1_swc_list",
                "message": f"Stage 1/3: Identifying SWCs from {len(requirements)} requirements...",
            })
        system, user = _stage1_prompts(requirements)
        try:
            response = await self.backend.generate(
                system_prompt=system,
                user_prompt=user,
                max_tokens=_STAGE1_MAX_TOKENS,
                temperature=0.1,  # very deterministic — SWC naming is constrained
            )
            parsed = _extract_json(response.content)
            if isinstance(parsed, list) and parsed:
                # Normalize: ensure each entry has required keys
                cleaned = []
                req_ids_all = {r.req_id for r in requirements}
                for item in parsed[:_MAX_SWCS]:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    if not name:
                        continue
                    # Enforce SWC_ prefix
                    if not name.startswith("SWC_"):
                        name = "SWC_" + name
                    # Filter req_ids to only valid ones
                    rids = [
                        rid for rid in item.get("req_ids", [])
                        if rid in req_ids_all
                    ]
                    cleaned.append({
                        "name": name,
                        "req_ids": rids,
                        "purpose": str(item.get("purpose", f"Handles {name} functionality"))[:200],
                    })
                if cleaned:
                    logger.info(f"Stage 1: identified {len(cleaned)} SWCs")
                    return cleaned
        except Exception as exc:
            logger.warning(f"Stage 1 AI call failed: {exc}; using fallback SWC list")
        fallback = _fallback_swc_list(requirements)
        logger.info(f"Stage 1: fallback produced {len(fallback)} SWCs")
        return fallback

    async def _run_stage2(
        self,
        swc_name: str,
        swc_reqs: list[Requirement],
        swc_index: int,
        total_swcs: int,
        progress_callback: Optional[callable],
    ) -> list[dict]:
        """Stage 2: Generate port table for one SWC."""
        if progress_callback:
            progress_callback({
                "stage": "elaborate_chunk",
                "chunk": f"stage2_ports_{swc_name}",
                "message": (
                    f"Stage 2/3: Generating ports for {swc_name} "
                    f"({swc_index}/{total_swcs})..."
                ),
            })
        system, user = _stage2_prompts(swc_name, swc_reqs)
        try:
            response = await self.backend.generate(
                system_prompt=system,
                user_prompt=user,
                max_tokens=_STAGE2_MAX_TOKENS,
                temperature=0.1,
            )
            parsed = _extract_json(response.content)
            if isinstance(parsed, list) and parsed:
                valid = [p for p in parsed if isinstance(p, dict) and p.get("port")]
                if valid:
                    logger.debug(f"Stage 2 {swc_name}: {len(valid)} ports")
                    return valid
        except Exception as exc:
            logger.warning(f"Stage 2 ({swc_name}) AI call failed: {exc}; using fallback")
        return _fallback_ports(swc_name)

    async def _run_stage3(
        self,
        swc_name: str,
        swc_reqs: list[Requirement],
        ports: list[dict],
        swc_index: int,
        total_swcs: int,
        progress_callback: Optional[callable],
    ) -> list[dict]:
        """Stage 3: Generate runnable list + pseudocode for one SWC."""
        if progress_callback:
            progress_callback({
                "stage": "elaborate_chunk",
                "chunk": f"stage3_runnables_{swc_name}",
                "message": (
                    f"Stage 3/3: Generating runnables for {swc_name} "
                    f"({swc_index}/{total_swcs})..."
                ),
            })
        system, user = _stage3_prompts(swc_name, swc_reqs, ports)
        try:
            response = await self.backend.generate(
                system_prompt=system,
                user_prompt=user,
                max_tokens=_STAGE3_MAX_TOKENS,
                temperature=0.15,
            )
            parsed = _extract_json(response.content)
            if isinstance(parsed, list) and parsed:
                valid = [
                    r for r in parsed
                    if isinstance(r, dict) and r.get("runnable")
                ]
                if valid:
                    # Normalise pseudocode to list[str]
                    for entry in valid:
                        pc = entry.get("pseudocode", [])
                        if isinstance(pc, str):
                            entry["pseudocode"] = [pc]
                        elif isinstance(pc, list):
                            entry["pseudocode"] = [str(s) for s in pc][:6]
                        else:
                            entry["pseudocode"] = []
                        # Ensure RE_ prefix
                        rname = str(entry.get("runnable", "")).strip()
                        if rname and not rname.startswith("RE_"):
                            entry["runnable"] = "RE_" + rname
                    logger.debug(f"Stage 3 {swc_name}: {len(valid)} runnables")
                    return valid
        except Exception as exc:
            logger.warning(f"Stage 3 ({swc_name}) AI call failed: {exc}; using fallback")
        return _fallback_runnables(swc_name)

    # ── Stage 4: Assembly (no AI) ──────────────────────────────────────────────

    @staticmethod
    def _assemble(
        requirements: list[Requirement],
        swc_list: list[dict],
        swc_ports: dict[str, list[dict]],
        swc_runnables: dict[str, list[dict]],
        req_hash: str,
    ) -> dict:
        """Assemble chunked outputs into the standard elaborated_data format.

        Produces the same dict shape as RequirementElaborator so
        build_enriched_context() and diagram generation need no changes.
        """
        req_map = {r.req_id: r for r in requirements}

        # Build elaborated[] by inverting swc_list: one entry per requirement
        elaborated: list[dict] = []
        covered_req_ids: set[str] = set()

        for swc in swc_list:
            swc_name = swc["name"]
            req_ids = swc.get("req_ids", [])
            ports = swc_ports.get(swc_name, [])
            runnables = swc_runnables.get(swc_name, [])

            port_names = [p["port"] for p in ports]
            runnable_names = [r["runnable"] for r in runnables]
            iface_names = list({
                p["interface"] for p in ports if p.get("interface")
            })

            # Build a logic_flow summary from pseudocode of the first runnable
            logic_flow = ""
            if runnables:
                first_steps = runnables[0].get("pseudocode", [])
                logic_flow = " → ".join(first_steps[:4])

            for req_id in req_ids:
                covered_req_ids.add(req_id)
                req = req_map.get(req_id)
                elaborated.append({
                    "req_id": req_id,
                    "entities": {
                        "swc": swc_name,
                        "runnables": runnable_names,
                        "ports": port_names,
                        "interfaces": iface_names,
                    },
                    "logic_flow": logic_flow,
                    "diagram_hints": {
                        "swc": swc_name,
                        "primary_runnable": runnable_names[0] if runnable_names else "",
                    },
                    "safety_level": (
                        req.safety_level.value
                        if req and req.safety_level
                        else "not_safety_relevant"
                    ),
                })

        # For requirements not assigned to any SWC, add a stub entry
        for req in requirements:
            if req.req_id not in covered_req_ids:
                elaborated.append({
                    "req_id": req.req_id,
                    "entities": {"swc": "", "runnables": [], "ports": [], "interfaces": []},
                    "logic_flow": "",
                    "diagram_hints": {},
                })

        # Build architecture_summary
        swc_names = [s["name"] for s in swc_list]
        architecture_summary = (
            f"System decomposed into {len(swc_list)} SWC(s): "
            + ", ".join(swc_names[:5])
            + (f" and {len(swc_names) - 5} more" if len(swc_names) > 5 else "")
            + "."
        )

        # Thinking log entries shown in UI
        thinking = [
            f"Stage 1: Identified {len(swc_list)} SWCs from "
            f"{len(requirements)} requirements: {', '.join(swc_names)}",
        ]
        for swc in swc_list:
            swc_name = swc["name"]
            ports = swc_ports.get(swc_name, [])
            runnables = swc_runnables.get(swc_name, [])
            thinking.append(
                f"Stage 2 {swc_name}: {len(ports)} port(s) → "
                + ", ".join(p["port"] for p in ports[:3])
            )
            thinking.append(
                f"Stage 3 {swc_name}: {len(runnables)} runnable(s) → "
                + ", ".join(r["runnable"] for r in runnables[:2])
            )

        return {
            "thinking": thinking,
            "architecture_summary": architecture_summary,
            "elaborated": elaborated,
            # Extra structured data for MUD-doc assembly
            "swc_list": swc_list,
            "swc_ports": swc_ports,
            "swc_runnables": swc_runnables,
            "req_hash": req_hash,
            "parse_ok": True,
            "status": "ok",
            "source": "chunked_generation",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "elaborated_count": len(elaborated),
            "quality_score": (
                len(covered_req_ids) / max(len(requirements), 1)
            ),
        }

    # ── Public API ─────────────────────────────────────────────────────────────

    async def elaborate(
        self,
        requirements: list[Requirement],
        progress_callback: Optional[callable] = None,
        force_refresh: bool = False,
    ) -> dict:
        """Elaborate requirements using chunked AI calls.

        Drop-in replacement for RequirementElaborator.elaborate().
        Each AI call targets ≤ 500 tokens of output; Python code assembles
        the results into the standard elaborated_data dict.
        """
        req_hash = self._compute_hash(requirements)

        # Check cache
        if not force_refresh:
            cached = self.load_cached(requirements)
            if cached:
                return cached

        logger.info(
            f"Starting chunked elaboration for {len(requirements)} requirements "
            f"(hash={req_hash})..."
        )

        # ── Stage 1: SWC identification ──────────────────────────────────────
        swc_list = await self._run_stage1(requirements, progress_callback)

        # Build req → SWC lookup for stages 2 & 3
        req_map = {r.req_id: r for r in requirements}
        # Distribute any unassigned requirements to the first SWC
        assigned_ids = {rid for swc in swc_list for rid in swc.get("req_ids", [])}
        unassigned = [r for r in requirements if r.req_id not in assigned_ids]
        if unassigned and swc_list:
            swc_list[0]["req_ids"] = list(set(swc_list[0]["req_ids"]) | {r.req_id for r in unassigned})
            logger.debug(
                f"Assigned {len(unassigned)} unassigned requirements to {swc_list[0]['name']}"
            )

        total_swcs = len(swc_list)
        swc_ports: dict[str, list[dict]] = {}
        swc_runnables: dict[str, list[dict]] = {}

        for idx, swc in enumerate(swc_list, start=1):
            swc_name = swc["name"]
            swc_req_ids = swc.get("req_ids", [])
            swc_reqs = [req_map[rid] for rid in swc_req_ids if rid in req_map]

            # Fallback: if no reqs assigned, use all requirements
            if not swc_reqs:
                swc_reqs = requirements

            # ── Stage 2: Port table ──────────────────────────────────────────
            ports = await self._run_stage2(
                swc_name, swc_reqs, idx, total_swcs, progress_callback
            )
            swc_ports[swc_name] = ports

            # ── Stage 3: Runnables + pseudocode ─────────────────────────────
            runnables = await self._run_stage3(
                swc_name, swc_reqs, ports, idx, total_swcs, progress_callback
            )
            swc_runnables[swc_name] = runnables

        # ── Stage 4: Assembly (no AI) ─────────────────────────────────────────
        result = self._assemble(
            requirements, swc_list, swc_ports, swc_runnables, req_hash
        )

        # Persist cache
        self._save_cache(result)

        logger.info(
            f"Chunked elaboration complete: {len(swc_list)} SWCs, "
            f"{len(result['elaborated'])} elaborated requirements, "
            f"quality={result['quality_score']:.2f}"
        )

        if progress_callback:
            progress_callback({
                "stage": "elaborate_complete",
                "swc_count": len(swc_list),
                "elaborated_count": len(result["elaborated"]),
                "message": (
                    f"Elaboration complete: {len(swc_list)} SWC(s), "
                    f"{len(result['elaborated'])} requirements processed."
                ),
            })

        return result
