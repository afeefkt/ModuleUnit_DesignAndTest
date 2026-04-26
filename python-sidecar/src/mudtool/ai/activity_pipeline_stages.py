"""Multi-stage activity-diagram generation pipeline.

Mirrors the design of ``mud_pipeline_stages.MudSpecPipeline`` but emits
``ActivityDiagram`` objects instead of MUD-spec Markdown.  Replaces the
single AI call that asks the model to produce every runnable's diagram
in one giant ``{"diagrams":[…]}`` response (which overwhelms 7B models
on 8 GB GPUs and frequently returns ``nodes:[]``) with five focused
stages:

  Stage 1 — Skeleton (deepseek-r1:7b recommended)
    One small JSON call: extract the runnable list + per-runnable key
    steps + entry/exit hints.  Tiny output, fast on a reasoning model.

  Stage 2 — Cross-reference map (Python, no AI)
    Build a producer/consumer map for IRVs and DEM events from the
    parsed MudActivityContext so Stage 4 can flag coherence problems.

  Stage 3 — Per-runnable diagram (qwen2.5-coder:7b recommended)
    Loop runnables.  For each: ONE focused prompt with that runnable's
    Section 7 pseudo-code + the AUTOSAR/node-type rules from the legacy
    activity_diagram.yaml.  Output: a single ActivityDiagram JSON
    (no ``{"diagrams":[…]}`` wrapper).  Each call is ≤1.5 k tokens of
    input → 7B handles reliably.

  Stage 4 — Reviewer pass (deepseek-r1:7b recommended)
    Send compact summaries of all N drafts back to a reasoning model
    with the cross-ref map.  Reviewer flags missing initial/final,
    missing exception edges around Rte_IWrite_*/Dem_*, decision
    diamonds without both branches, IRV producer/consumer mismatches.
    Returns simple patches applied deterministically in Python.

  Stage 5 — Deterministic repair + provenance stamp
    Reuses the orchestrator's _repair_activity_diagram path
    (initial/final injection).  Stamps each diagram with backend +
    prompt-hash provenance.

Usage (from AIOrchestrator.generate_diagram):

    pipeline = ActivityPipeline(
        backend=generator_backend,
        skeleton_backend=skeleton_backend,
        reviewer_backend=reviewer_backend,
        progress_callback=cb,
    )
    diagrams = await pipeline.run(
        mud_activity_context=mac,
        module_context="SWC_Foo",
        requirements=requirements,
        activity_label_style="pseudocode",
    )
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

from mudtool.ai.mud_activity_context import (
    MudActivityContext,
    RunnableContext,
    synthesize_activity_diagrams_from_context,
)
from mudtool.generator.mermaid_exporter import MermaidExporter
from mudtool.models.json_uml import ActivityDiagram, DiagramType
from mudtool.validation.mermaid_linter import MermaidLinter


# ── JSON extraction helper (mirrors mud_pipeline_stages._extract_json) ────────

def _extract_json(raw: str) -> Any:
    """Parse the AI's JSON reply, tolerating <think> blocks and ``` fences."""
    if not raw:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    cleaned = re.sub(r"```(?:json)?", "", cleaned).strip().rstrip("`").strip()

    # Try the outermost {…} first
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end])
        except json.JSONDecodeError:
            pass

    # Fallback: try array
    start = cleaned.find("[")
    end = cleaned.rfind("]") + 1
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end])
        except json.JSONDecodeError:
            pass

    return None


# ── Edge cleanup helper ───────────────────────────────────────────────────────

def _scrub_orphan_edges(diagram: dict, runnable_name: str = "") -> None:
    """Repair / drop edges whose source/target don't match any node id, then
    auto-fill missing branches on decision nodes with <2 outgoing edges.

    Repair strategy for orphan refs:
      1. exact id match
      2. exact lowercased node-name match
      3. **substring** match (e.g. ``RP_IgnitionStatus`` → node named
         ``RP_IgnitionStatus == ON``)
      4. token-prefix match (first identifier in the name)
    If none match the edge is dropped.

    Decision branch auto-fill:
      For every node with node_type=='decision' that has <2 outgoing edges
      after orphan scrubbing, synthesise an ``[else]`` edge to the next
      successor (next node in source order, or the diagram's final node).
      Mutates ``diagram`` in place.
    """
    nodes = diagram.get("nodes") or []
    edges = diagram.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return

    # ── Build lookups ────────────────────────────────────────────────────
    valid_ids: set[str] = set()
    name_to_id: dict[str, str] = {}
    name_pairs: list[tuple[str, str]] = []   # (lowered_name, id) — for substring match
    final_id: Optional[str] = None
    nodes_by_id: dict[str, dict] = {}
    node_order_index: dict[str, int] = {}
    for idx, n in enumerate(nodes):
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if not nid:
            continue
        valid_ids.add(nid)
        nodes_by_id[nid] = n
        node_order_index[nid] = idx
        nm = (n.get("name") or "").strip().lower()
        if nm:
            name_to_id.setdefault(nm, nid)
            name_pairs.append((nm, nid))
        if (n.get("node_type") or "").lower() == "final" and final_id is None:
            final_id = nid

    def _first_token(s: str) -> str:
        # Pull the leading identifier out of "RP_IgnitionStatus == ON"
        s = s.strip()
        if not s:
            return ""
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s)
        return (m.group(0) if m else "").lower()

    def _resolve(ref: str) -> Optional[str]:
        if not ref:
            return None
        if ref in valid_ids:
            return ref
        key = ref.strip().lower().replace("-", "_")
        if not key:
            return None
        if key in name_to_id:
            return name_to_id[key]
        # Case-insensitive id match
        for vid in valid_ids:
            if vid.lower() == key:
                return vid
        # Substring match: ref appears inside a node name
        for nm, nid in name_pairs:
            if key in nm:
                return nid
        # Token-prefix match: ref equals the first identifier in some node name
        for nm, nid in name_pairs:
            if _first_token(nm) == key:
                return nid
        return None

    # ── Scrub edges ──────────────────────────────────────────────────────
    cleaned: list[dict] = []
    dropped = 0
    repaired = 0
    for e in edges:
        if not isinstance(e, dict):
            continue
        orig_src = e.get("source", "")
        orig_tgt = e.get("target", "")
        src = _resolve(orig_src)
        tgt = _resolve(orig_tgt)
        if src and tgt and src != tgt:
            if src != orig_src or tgt != orig_tgt:
                repaired += 1
                e["source"] = src
                e["target"] = tgt
            cleaned.append(e)
        else:
            # No match, or repair would produce a self-loop → drop
            dropped += 1
    diagram["edges"] = cleaned

    # ── Auto-fill missing decision branches ──────────────────────────────
    branches_added = 0
    out_count: dict[str, int] = {}
    for e in cleaned:
        s = e.get("source")
        if s:
            out_count[s] = out_count.get(s, 0) + 1
    next_eid = max(
        (int(re.search(r"\d+", e.get("id", "E_0")).group(0))
         for e in cleaned if isinstance(e.get("id"), str) and re.search(r"\d+", e.get("id"))),
        default=len(cleaned),
    )

    for n in nodes:
        if not isinstance(n, dict):
            continue
        if (n.get("node_type") or "").lower() != "decision":
            continue
        nid = n.get("id")
        if not nid:
            continue
        if out_count.get(nid, 0) >= 2:
            continue
        # Pick a successor: the next node in source order that isn't this
        # one, isn't already the existing branch target, and isn't itself
        # a decision (avoid chains of empty diamonds).  Fallback to final.
        existing_targets = {
            e.get("target") for e in cleaned if e.get("source") == nid
        }
        successor: Optional[str] = None
        my_idx = node_order_index.get(nid, -1)
        for cand in nodes:
            if not isinstance(cand, dict):
                continue
            cid = cand.get("id")
            if not cid or cid == nid or cid in existing_targets:
                continue
            if node_order_index.get(cid, -1) <= my_idx:
                continue
            ctype = (cand.get("node_type") or "").lower()
            if ctype == "decision":
                continue
            successor = cid
            break
        if successor is None and final_id and final_id != nid and final_id not in existing_targets:
            successor = final_id
        if successor is None:
            continue
        next_eid += 1
        cleaned.append({
            "id": f"E_{next_eid:02d}",
            "source": nid,
            "target": successor,
            "guard": "[else]",
        })
        out_count[nid] = out_count.get(nid, 0) + 1
        branches_added += 1

    diagram["edges"] = cleaned

    if dropped or repaired or branches_added:
        logger.info(
            "[Activity Pipeline/cleanup] %s: repaired=%d, dropped=%d, "
            "decision_branches_added=%d",
            runnable_name or diagram.get("name", "?"),
            repaired,
            dropped,
            branches_added,
        )


# ── Prompt templates ──────────────────────────────────────────────────────────

_SKELETON_SYSTEM = """You are an AUTOSAR software architect.

TASK: From the MUD specification block below, extract a JSON skeleton
listing every runnable and its key control-flow steps.  The skeleton
will be used downstream to generate one activity flowchart per runnable.

Output STRICT JSON only — no prose, no markdown fences, no <think>.
Begin with { and end with }.

JSON SCHEMA:
{
  "runnables": [
    {
      "name": "RE_…",                         // exact name from MUD
      "trigger": "10ms" or "Init" or "OnEvent",
      "asil": "QM" | "A" | "B" | "C" | "D",
      "entry_hint": "Start" or "Start (10ms)",
      "exit_hint": "End",
      "key_steps": [                          // 4–10 entries, each one short C-like phrase
        "Read PP_Torque",
        "Validate range",
        "Compute assist",
        "Write PP_Output",
        "Dem_SetEventStatus on fault"
      ],
      "writes_irvs": ["irv_…"],               // [] if none
      "reads_irvs":  ["irv_…"],
      "raises_dem":  ["DTC_…"]                // DEM events the runnable may report
    }
  ]
}

RULES:
  - Use ONLY runnable names that appear in the MUD spec.
  - Do NOT invent runnables.
  - key_steps must be ordered (entry → exit).
  - Write every guard/validation/check step as "if <C-expression>" so the
    downstream classifier can emit a decision diamond.
      WRONG: "Validate torque range"   →   RIGHT: "if l_f32Torque > TORQUE_MAX"
      WRONG: "Check speed valid"       →   RIGHT: "if l_f32Speed < SPEED_MIN"
  - Write RTE reads  as: "Rte_Read_RP_<Port>(&l_var)"
  - Write RTE writes as: "Rte_Write_PP_<Port>(&l_var)"
  - Write DEM calls  as: "Dem_SetEventStatus(<DTC>, FAILED)"
  - If the MUD pseudo-code has guards / decisions, include them as steps
    starting with "if" exactly.
  - If unsure of a field, return [] or "" rather than guessing.
"""


_SKELETON_USER_TMPL = """SWC: {swc_name}

{mud_block}

Return the JSON skeleton.  Output ONLY JSON.
"""


_RUNNABLE_SYSTEM = """You are an AUTOSAR software engineer.  Generate ONE
ActivityDiagram JSON for the single runnable supplied.  Style: C
pseudocode — node labels are C expressions, not English sentences.

Output STRICT JSON only — a single ActivityDiagram object (NOT a
{{"diagrams":[…]}} wrapper).  No prose, no markdown fences, no <think>.

NODE TYPES:
  initial       — name "Start" or "Start (10ms)"; first node only.
  final         — name "End"; last node.
  call          — RTE call signature, e.g. "Rte_Read_RP_Speed(&l_f32V)".
                  Set rte_call, port, element.
  action        — C assignment, e.g. "l_f32Out = l_f32K * l_f32In".
  decision      — C boolean expression, e.g. "l_f32V > LIMIT".
                  MUST have ≥2 outgoing edges with guards "[…]".
  merge         — name "merge", joins two decision branches.
  function_call — helper call with return var.  Set callee.
  exception     — DEM/fault report, e.g.
                  "Dem_SetEventStatus(DTC_X, DEM_EVENT_STATUS_FAILED)".

ID FORMAT — STRICT:
  - Node IDs MUST match the regex ^N_[0-9]+$  (e.g. N_01, N_02, N_15).
  - Edge IDs MUST match ^E_[0-9]+[a-z]?$  (e.g. E_01, E_03a).
  - DO NOT use semantic IDs like "current_mode", "inputs_valid", "start_node".
  - Every edge.source and edge.target MUST equal the id of a node listed in
    nodes[].  If you mention an entity that is not yet a node, FIRST add a
    node for it, THEN reference its N_xx id in edges[].
  - Before emitting JSON, mentally check: every edge.source is in nodes[].id
    and every edge.target is in nodes[].id.

Guards: "[l_f32V > LIMIT]".

EVERY node must have: id, name, node_type, trace_reqs (≥1 entry),
description (3–10 words), confidence (numeric 0.0–1.0; do NOT use words
like "high"/"medium"/"low").

STANDARD FLOW: INITIAL → CALL(reads) → DECISION(validate)
            → ACTION/FUNCTION_CALL(compute) → CALL(writes) → FINAL
Aim for 5–15 nodes.

OUTPUT SCHEMA (single object — NO outer wrapper):
{{
  "diagram_type": "activity",
  "name": "RE_Name Code Flow",
  "owner_swc": "SWC_…",
  "owner_runnable": "RE_…",
  "source_requirements": ["REQ-…"],
  "nodes": [ … ],
  "edges": [ … ],
  "sub_diagrams": []
}}
"""


_RUNNABLE_USER_TMPL = """Generate the activity flowchart for ONE runnable.

SWC: {swc_name}
RUNNABLE: {runnable_name}
TRIGGER: {trigger}
ASIL: {asil}
LABEL STYLE: {label_style}

KEY STEPS (from skeleton):
{key_steps_block}

NUMBERED PSEUDO-CODE FROM MUD SECTION 7:
{pseudo_code}

CANONICAL CFG SCAFFOLD (use this exact topology and these exact node ids / edge ids):
{cfg_scaffold}

ARCHITECTURAL REQUIREMENTS (use these IDs in trace_reqs):
{requirements_block}

Produce ONE ActivityDiagram JSON object for runnable {runnable_name}.
The CFG scaffold is authoritative for topology:
  - keep the same nodes[] ids, edge ids, edge source/target pairs, and branch count
  - you may enrich node names, descriptions, confidence, rte_call, port, element,
    callee, and edge guards
  - do NOT invent extra semantic edge endpoints like "vehicleSpeed", "true",
    "RP_IgnitionStatus", "abs", or signal names as source/target
Map each numbered pseudo-code step to ONE node:
  - "Rte_Read…" / "Rte_Write…"  → call node
  - "if X" / "Validate X"        → decision node (with both branches)
  - "Dem_SetEventStatus…"        → exception node
  - assignments / computations    → action node
  - helper / sub-function call    → function_call node

Add "Start" (initial) at the top and "End" (final) at the bottom.

Output ONLY the JSON object.  No text before or after.

CONCRETE ONE-SHOT EXAMPLE (6-node pattern — replace names/ids with actual runnable content):
{{
  "diagram_type": "activity",
  "name": "RE_TorqueCtrl Code Flow",
  "owner_swc": "SWC_Eps",
  "owner_runnable": "RE_TorqueCtrl",
  "source_requirements": ["REQ-01"],
  "nodes": [
    {{"id":"N_01","name":"Start","node_type":"initial","trace_reqs":["REQ-01"],"description":"Entry 10ms","confidence":0.95}},
    {{"id":"N_02","name":"Rte_Read_RP_Torque(&l_f32T)","node_type":"call","rte_call":"Rte_Read","port":"RP_Torque","element":"Torque","trace_reqs":["REQ-01"],"description":"Read torque sensor","confidence":0.95}},
    {{"id":"N_03","name":"l_f32T > TORQUE_MAX","node_type":"decision","trace_reqs":["REQ-01"],"description":"Range check","confidence":0.9}},
    {{"id":"N_04","name":"Dem_SetEventStatus(DTC_Torque, DEM_EVENT_STATUS_FAILED)","node_type":"exception","trace_reqs":["REQ-01"],"description":"Report fault","confidence":0.9}},
    {{"id":"N_05","name":"Rte_Write_PP_TorqueOut(&l_f32Out)","node_type":"call","rte_call":"Rte_Write","port":"PP_TorqueOut","element":"TorqueOut","trace_reqs":["REQ-01"],"description":"Write output","confidence":0.95}},
    {{"id":"N_06","name":"End","node_type":"final","trace_reqs":["REQ-01"],"description":"Exit","confidence":0.95}}
  ],
  "edges": [
    {{"id":"E_01","source":"N_01","target":"N_02"}},
    {{"id":"E_02","source":"N_02","target":"N_03"}},
    {{"id":"E_03","source":"N_03","target":"N_04","guard":"[l_f32T > TORQUE_MAX]"}},
    {{"id":"E_04","source":"N_03","target":"N_05","guard":"[else]"}},
    {{"id":"E_05","source":"N_04","target":"N_06"}},
    {{"id":"E_06","source":"N_05","target":"N_06"}}
  ],
  "sub_diagrams": []
}}
"""


_REVIEWER_SYSTEM = """You are an AUTOSAR design reviewer.  You receive
N draft activity diagrams (one per runnable) plus a cross-reference map
of which runnables read/write each IRV.

Your job: identify concrete issues and emit a JSON patch list.
Focus on these classes of problems:
  1. Missing initial or final node.
  2. A "Rte_IWrite_*" / "Rte_Write_*" / "Dem_*" node with no exception edge.
  3. A decision node with fewer than 2 outgoing edges.
  4. IRV mismatch: a runnable reads an IRV that no other runnable writes.
  5. Duplicate node IDs within one diagram.

Output STRICT JSON only:
{
  "issues": [
    {"runnable": "RE_…", "severity": "warn|error", "message": "…"}
  ],
  "patches": [
    {"runnable": "RE_…", "op": "add_initial"},
    {"runnable": "RE_…", "op": "add_final"}
  ]
}

Patch ops supported (use only these — anything else is ignored):
  add_initial   — insert a Start node at the top
  add_final     — insert an End node at the bottom

Be conservative: if unsure, log it as an issue without a patch.
Output ONLY JSON, no prose, no <think>.
"""


# ── ActivityPipeline class ────────────────────────────────────────────────────

class ActivityPipeline:
    """5-stage activity flowchart generator.

    Mirrors :class:`mudtool.ai.mud_pipeline_stages.MudSpecPipeline` so the
    user-visible progress events look identical:
      ``[Activity Pipeline] Stage 1/5 — extracting activity skeleton…``
      ``[Activity Pipeline] Stage 3/5 — diagram for RE_Init…``
      ``[Activity Pipeline] Complete — N diagrams, M nodes total``

    Returns a list of dicts shaped like the AI's per-diagram payload —
    the orchestrator validates them with ``ActivityDiagram.model_validate``
    and runs its existing ``_repair_activity_diagram`` repair so the
    pipeline is a drop-in replacement for the legacy single AI call.
    """

    def __init__(
        self,
        backend,
        skeleton_backend=None,
        reviewer_backend=None,
        progress_callback=None,
    ):
        self._backend = backend
        self._skeleton_backend = skeleton_backend or backend
        self._reviewer_backend = reviewer_backend or backend
        self._progress = progress_callback

    def _emit(self, message: str, progress: int = 0, **extra) -> None:
        if self._progress:
            try:
                self._progress({
                    "stage": "activity_pipeline",
                    "message": message,
                    "progress": progress,
                    **extra,
                })
            except Exception:
                pass
        logger.info(message)

    # ─── Public entry point ────────────────────────────────────────────────

    async def run(
        self,
        mud_activity_context: Any,
        module_context: Optional[str],
        requirements,
        activity_label_style: str = "pseudocode",
        temperature: float = 0.1,
    ) -> list[dict]:
        """Run all 5 stages and return validated diagram dicts.

        Returns an empty list if the skeleton stage fails so the caller
        can fall back to the legacy single-call path.
        """
        if mud_activity_context is None or not getattr(
            mud_activity_context, "runnables", None
        ):
            logger.info("[Activity Pipeline] no runnables in MUD context — skipping")
            return []

        swc_name = getattr(mud_activity_context, "swc_name", None) or (module_context or "")

        # ── Stage 1: Skeleton ──────────────────────────────────────────────
        self._emit(
            f"[Activity Pipeline] Stage 1/5 — extracting activity skeleton for {swc_name}…",
            10,
        )
        skeleton = await self._stage1_skeleton(mud_activity_context, swc_name, temperature)
        if not skeleton or not skeleton.get("runnables"):
            # Fall back to MUD context directly — every runnable becomes a
            # skeleton entry built from the parsed RunnableContext.
            logger.warning(
                "[Activity Pipeline] Stage 1 skeleton empty — synthesising from MUD context"
            )
            skeleton = self._synthesise_skeleton(mud_activity_context)
            if not skeleton["runnables"]:
                self._emit("[Activity Pipeline] Stage 1 failed — no runnables", 0)
                return []

        runnables = skeleton["runnables"]
        self._emit(
            f"[Activity Pipeline] Stage 1 complete — {len(runnables)} runnables identified",
            20,
        )

        # ── Stage 2: Cross-reference map ───────────────────────────────────
        xref = self._stage2_xref(runnables, mud_activity_context)
        logger.info(
            "[Activity Pipeline] Stage 2 xref: %d IRV producers, %d DEM raisers",
            len(xref["irv_writers"]),
            len(xref["dem_raisers"]),
        )

        # ── Stage 3: Per-runnable diagrams ─────────────────────────────────
        drafts: list[dict] = []
        total = len(runnables)
        for idx, sk_run in enumerate(runnables, 1):
            rname = sk_run.get("name") or f"RE_{idx}"
            self._emit(
                f"[Activity Pipeline] Stage 3/5 — diagram for {rname}…",
                20 + int(50 * idx / max(total, 1)),
            )
            draft = await self._stage3_runnable(
                sk_run,
                mud_activity_context,
                swc_name,
                requirements,
                activity_label_style,
                temperature,
            )
            if draft:
                drafts.append(draft)
            else:
                logger.warning(
                    "[Activity Pipeline] Stage 3 returned no diagram for %s", rname
                )

        if not drafts:
            self._emit("[Activity Pipeline] Stage 3 produced 0 diagrams — falling back", 0)
            return []

        # ── Stage 4: Reviewer pass ─────────────────────────────────────────
        self._emit(
            f"[Activity Pipeline] Stage 4/5 — reviewer pass (cross-runnable, {len(drafts)} drafts)…",
            78,
        )
        try:
            patches, issues = await self._stage4_review(drafts, xref, temperature)
            if issues:
                logger.warning(
                    "[Activity Pipeline] Reviewer flagged %d issue(s):\n  %s",
                    len(issues),
                    "\n  ".join(f"{i.get('runnable','?')}: {i.get('message','')}" for i in issues[:10]),
                )
        except Exception as exc:
            logger.warning("[Activity Pipeline] Stage 4 reviewer failed: %s", exc)
            patches = []

        # ── Stage 5: Deterministic repair + provenance ─────────────────────
        self._emit(
            "[Activity Pipeline] Stage 5/5 — deterministic repair + provenance…",
            90,
        )
        finalised = self._stage5_finalise(drafts, patches)

        total_nodes = sum(len(d.get("nodes", [])) for d in finalised)
        # Collect per-runnable provenance modes for the summary event
        prov_summary = {
            d.get("owner_runnable") or d.get("name", "?"): (
                d.get("provenance", {}).get("provenance_mode", "?")
            )
            for d in finalised
        }
        modes_str = ", ".join(
            f"{r}: {m}" for r, m in list(prov_summary.items())[:8]
        )
        self._emit(
            f"[Activity Pipeline] Complete — {len(finalised)} diagrams, "
            f"{total_nodes} nodes total | {modes_str}",
            100,
            quality_summary=prov_summary,
        )
        return finalised

    # ─── Stage 1 ──────────────────────────────────────────────────────────

    async def _stage1_skeleton(
        self,
        mud_activity_context,
        swc_name: str,
        temperature: float,
    ) -> Optional[dict]:
        try:
            mud_block = mud_activity_context.to_prompt_block()
        except Exception as exc:
            logger.warning("Could not render MUD block: %s", exc)
            return None

        # Cap the MUD block — Stage 1 only needs an overview
        if len(mud_block) > 6000:
            mud_block = mud_block[:6000] + "\n... [truncated for skeleton stage]"

        user_prompt = _SKELETON_USER_TMPL.format(
            swc_name=swc_name or "unknown",
            mud_block=mud_block,
        )

        backend = self._skeleton_backend
        backend_name = getattr(backend, "backend_name", "?")
        logger.info(
            "[Activity Pipeline/Stage1] using backend %s for %s", backend_name, swc_name
        )

        try:
            response = await backend.generate(
                system_prompt=_SKELETON_SYSTEM,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=2048,
                response_format="json",
            )
        except TypeError:
            # Some backends don't accept response_format kwarg
            response = await backend.generate(
                system_prompt=_SKELETON_SYSTEM,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.warning("[Activity Pipeline/Stage1] backend error: %s", exc)
            return None

        skeleton = _extract_json(response.content)
        if not isinstance(skeleton, dict):
            logger.warning(
                "[Activity Pipeline/Stage1] Failed to extract JSON from response: %s…",
                (response.content or "")[:300],
            )
            return None
        skeleton.setdefault("runnables", [])
        return skeleton

    @staticmethod
    def _synthesise_skeleton(mud_activity_context) -> dict:
        """Fall-back: build skeleton entries from the parsed MUD context."""
        runnables: list[dict] = []
        for r in getattr(mud_activity_context, "runnables", []) or []:
            steps: list[str] = []
            if getattr(r, "functional_description", ""):
                for ln in r.functional_description.splitlines():
                    s = ln.strip()
                    if s:
                        # strip leading numbering like "1." / "1)" / "- "
                        s = re.sub(r"^\s*(?:\d+[\.\)]|\-|\*)\s+", "", s)
                        steps.append(s[:120])
            runnables.append({
                "name": r.name,
                "trigger": getattr(r, "trigger", ""),
                "asil": getattr(r, "asil", ""),
                "entry_hint": "Start",
                "exit_hint": "End",
                "key_steps": steps[:12],
                "writes_irvs": [],
                "reads_irvs": [],
                "raises_dem": [],
            })
        return {"runnables": runnables}

    # ─── Stage 2 ──────────────────────────────────────────────────────────

    @staticmethod
    def _stage2_xref(runnables: list[dict], mud_activity_context=None) -> dict:
        """Build IRV and DEM cross-reference dicts for the reviewer.

        Primary source: the skeleton AI's ``writes_irvs`` / ``reads_irvs`` /
        ``raises_dem`` fields.  These are often ``[]`` because 7B models
        frequently omit them.

        Fallback: deterministically scan ``mud_activity_context.rte_calls``
        (already parsed by ``build_mud_activity_context`` from the raw
        markdown) to populate IRV writer/reader maps.  This guarantees the
        Stage 4 reviewer receives useful cross-reference data even when the
        skeleton model returns empty lists.
        """
        irv_writers: dict[str, list[str]] = {}
        irv_readers: dict[str, list[str]] = {}
        dem_raisers: dict[str, list[str]] = {}
        for r in runnables:
            rname = r.get("name", "")
            for irv in r.get("writes_irvs") or []:
                irv_writers.setdefault(irv, []).append(rname)
            for irv in r.get("reads_irvs") or []:
                irv_readers.setdefault(irv, []).append(rname)
            for dem in r.get("raises_dem") or []:
                dem_raisers.setdefault(dem, []).append(rname)

        # Fallback: parse rte_calls from MudActivityContext when AI returned nothing
        if not irv_writers and not irv_readers and mud_activity_context is not None:
            for call in getattr(mud_activity_context, "rte_calls", []) or []:
                m = re.search(r"Rte_IWrite_(\w+)", call)
                if m:
                    irv_writers.setdefault(m.group(1), ["(auto-detected)"])
                m = re.search(r"Rte_IRead_(\w+)", call)
                if m:
                    irv_readers.setdefault(m.group(1), ["(auto-detected)"])
            # Attribute DEM events from per-runnable pseudo-code
            for r in getattr(mud_activity_context, "runnables", []) or []:
                rname = getattr(r, "name", "")
                desc = getattr(r, "functional_description", "") or ""
                for dtc in re.findall(r"Dem_(?:SetEventStatus|ReportErrorStatus)\s*\(\s*(\w+)", desc):
                    dem_raisers.setdefault(dtc, []).append(rname)

        return {
            "irv_writers": irv_writers,
            "irv_readers": irv_readers,
            "dem_raisers": dem_raisers,
        }

    # ─── Stage 3 ──────────────────────────────────────────────────────────

    async def _stage3_runnable(
        self,
        sk_run: dict,
        mud_activity_context,
        swc_name: str,
        requirements,
        activity_label_style: str,
        temperature: float,
    ) -> Optional[dict]:
        rname = sk_run.get("name") or "RE_Unknown"

        # Find the matching RunnableContext for full pseudo-code
        pseudo_code = ""
        for r in getattr(mud_activity_context, "runnables", []) or []:
            if r.name == rname:
                pseudo_code = (r.functional_description or "").strip() or (r.summary or "")
                break
        if not pseudo_code:
            # fall back to the skeleton's key_steps
            pseudo_code = "\n".join(
                f"{i+1}. {s}" for i, s in enumerate(sk_run.get("key_steps") or [])
            )

        # Cap pseudo-code to keep prompt small
        if len(pseudo_code) > 2500:
            pseudo_code = pseudo_code[:2500] + "\n... [truncated]"

        key_steps_block = "\n".join(
            f"  {i+1}. {s}" for i, s in enumerate(sk_run.get("key_steps") or [])
        ) or "  (none — derive from pseudo-code)"
        req_ids = [getattr(req, "req_id", "") for req in requirements or [] if getattr(req, "req_id", "")]
        cfg_scaffold_obj = self._build_cfg_scaffold(
            mud_activity_context=mud_activity_context,
            sk_run=sk_run,
            swc_name=swc_name,
            pseudo_code=pseudo_code,
            req_ids=req_ids,
        )
        cfg_scaffold = (
            json.dumps(cfg_scaffold_obj, ensure_ascii=False, indent=2)
            if cfg_scaffold_obj
            else "  (no deterministic scaffold available)"
        )

        # Compact requirements list with IDs only
        req_lines: list[str] = []
        for req in requirements or []:
            rid = getattr(req, "req_id", None)
            title = getattr(req, "title", "")
            if rid:
                if title:
                    req_lines.append(f"  - {rid}: {title}")
                else:
                    req_lines.append(f"  - {rid}")
        requirements_block = "\n".join(req_lines[:30]) or "  (none provided)"

        user_prompt = _RUNNABLE_USER_TMPL.format(
            swc_name=swc_name or "unknown",
            runnable_name=rname,
            trigger=sk_run.get("trigger", "") or "n/a",
            asil=sk_run.get("asil", "") or "QM",
            label_style=activity_label_style,
            key_steps_block=key_steps_block,
            pseudo_code=pseudo_code or "(no pseudo-code; produce a minimal Start/End diagram)",
            cfg_scaffold=cfg_scaffold,
            requirements_block=requirements_block,
        )

        backend = self._backend
        backend_name = getattr(backend, "backend_name", "?")

        try:
            response = await backend.generate(
                system_prompt=_RUNNABLE_SYSTEM,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=4096,
                response_format="json",
            )
        except TypeError:
            response = await backend.generate(
                system_prompt=_RUNNABLE_SYSTEM,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=4096,
            )
        except Exception as exc:
            logger.warning("[Activity Pipeline/Stage3] backend error for %s: %s", rname, exc)
            return None

        diagram = _extract_json(response.content)
        # Some models return {"diagrams":[…]} despite instructions — unwrap
        if isinstance(diagram, dict) and "diagrams" in diagram:
            diags = diagram.get("diagrams") or []
            diagram = diags[0] if diags else None
        if not isinstance(diagram, dict):
            logger.warning(
                "[Activity Pipeline/Stage3] no JSON diagram for %s: %s",
                rname, (response.content or "")[:200],
            )
            return self._finalize_cfg_fallback(
                cfg_scaffold_obj,
                rname,
                swc_name,
                backend_name,
                response,
                reason="ai_no_json",
            )

        # Stamp identity fields the orchestrator expects
        diagram["diagram_type"] = "activity"
        diagram.setdefault("owner_swc", swc_name or "")
        diagram.setdefault("owner_runnable", rname)
        diagram.setdefault("name", f"{rname} Code Flow")
        diagram.setdefault("nodes", [])
        diagram.setdefault("edges", [])
        diagram.setdefault("sub_diagrams", [])

        # ── Deterministic cleanup: drop orphan edges + repair semantic IDs ──
        # Local 7B models occasionally emit edges referencing semantic IDs
        # (e.g. "current_mode") that don't match any node.  Rather than let
        # those propagate as Mermaid lint warnings, scrub them here.
        _scrub_orphan_edges(diagram, rname)
        if cfg_scaffold_obj:
            diagram = self._overlay_ai_on_cfg(cfg_scaffold_obj, diagram)
            if self._diagram_has_cfg_breakage(diagram, rname):
                logger.warning(
                    "[Activity Pipeline/Stage3] %s failed CFG/mermaid checks; using deterministic scaffold",
                    rname,
                )
                return self._finalize_cfg_fallback(
                    cfg_scaffold_obj,
                    rname,
                    swc_name,
                    backend_name,
                    response,
                    reason="cfg_rebuild",
                )
        # Store backend hint so the orchestrator can record provenance
        diagram.setdefault("_pipeline_backend", backend_name)
        diagram.setdefault("_pipeline_model", getattr(response, "model", backend_name))
        diagram.setdefault("_pipeline_latency_ms", getattr(response, "latency_ms", 0))
        if cfg_scaffold_obj:
            diagram["_pipeline_canonical"] = copy.deepcopy(cfg_scaffold_obj)
        return diagram

    # ─── Stage 4 ──────────────────────────────────────────────────────────

    async def _stage4_review(
        self,
        drafts: list[dict],
        xref: dict,
        temperature: float,
    ) -> tuple[list[dict], list[dict]]:
        """Ask reviewer for issues + patches.  Returns (patches, issues)."""

        # Compact the drafts so the reviewer prompt stays small
        compact = []
        for d in drafts:
            compact.append({
                "runnable": d.get("owner_runnable") or d.get("name"),
                "node_count": len(d.get("nodes", [])),
                "node_types": sorted({
                    (n.get("node_type") or "").lower()
                    for n in d.get("nodes", [])
                    if isinstance(n, dict)
                }),
                "decision_branch_counts": [
                    sum(1 for e in d.get("edges", []) if e.get("source") == n.get("id"))
                    for n in d.get("nodes", [])
                    if isinstance(n, dict) and (n.get("node_type") or "").lower() == "decision"
                ],
                "node_names": [n.get("name", "") for n in d.get("nodes", []) if isinstance(n, dict)],
            })

        user_prompt = (
            "DRAFT DIAGRAMS (compact form):\n"
            + json.dumps(compact, ensure_ascii=False, indent=2)
            + "\n\nCROSS-REFERENCE MAP:\n"
            + json.dumps(xref, ensure_ascii=False, indent=2)
            + "\n\nReturn the JSON {issues, patches}."
        )

        backend = self._reviewer_backend
        try:
            response = await backend.generate(
                system_prompt=_REVIEWER_SYSTEM,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=2048,
                response_format="json",
            )
        except TypeError:
            response = await backend.generate(
                system_prompt=_REVIEWER_SYSTEM,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=2048,
            )

        review = _extract_json(response.content) or {}
        if not isinstance(review, dict):
            return ([], [])
        issues = review.get("issues") if isinstance(review.get("issues"), list) else []
        patches = review.get("patches") if isinstance(review.get("patches"), list) else []
        return (patches, issues)

    # ─── Stage 5 ──────────────────────────────────────────────────────────

    @staticmethod
    def _stage5_finalise(drafts: list[dict], patches: list[dict]) -> list[dict]:
        """Apply reviewer patches deterministically + stamp provenance."""
        by_name: dict[str, dict] = {}
        for d in drafts:
            key = d.get("owner_runnable") or d.get("name") or ""
            by_name[key] = d

        for patch in patches or []:
            if not isinstance(patch, dict):
                continue
            target = patch.get("runnable")
            op = (patch.get("op") or "").lower()
            if not target or target not in by_name:
                continue
            d = by_name[target]
            nodes = d.setdefault("nodes", [])
            edges = d.setdefault("edges", [])

            if op == "add_initial":
                if not any(
                    isinstance(n, dict) and (n.get("node_type") or "").lower() == "initial"
                    for n in nodes
                ):
                    new_id = "N_START"
                    nodes.insert(0, {
                        "id": new_id, "name": "Start",
                        "node_type": "initial", "trace_reqs": [],
                        "confidence": 0.5,
                        "description": "Auto-inserted entry point",
                    })
                    if nodes[1:] and isinstance(nodes[1], dict) and nodes[1].get("id"):
                        edges.insert(0, {
                            "id": "E_START",
                            "source": new_id,
                            "target": nodes[1]["id"],
                        })
            elif op == "add_final":
                if not any(
                    isinstance(n, dict) and (n.get("node_type") or "").lower() == "final"
                    for n in nodes
                ):
                    new_id = "N_END"
                    nodes.append({
                        "id": new_id, "name": "End",
                        "node_type": "final", "trace_reqs": [],
                        "confidence": 0.5,
                        "description": "Auto-inserted exit point",
                    })
                    if nodes[:-1] and isinstance(nodes[-2], dict) and nodes[-2].get("id"):
                        edges.append({
                            "id": "E_END",
                            "source": nodes[-2]["id"],
                            "target": new_id,
                        })

        # Stamp provenance hash + version + quality metrics on every diagram
        finalised: list[dict] = []
        for d in drafts:
            canonical = d.get("_pipeline_canonical")
            candidate = d
            runnable_name = d.get("owner_runnable") or d.get("name") or ""

            # Determine provenance mode before any mutation
            if canonical and ActivityPipeline._diagram_has_cfg_breakage(d, runnable_name):
                candidate = copy.deepcopy(canonical)
                candidate["_pipeline_backend"] = d.get("_pipeline_backend", "activity_pipeline")
                candidate["_pipeline_model"] = d.get("_pipeline_model", d.get("_pipeline_backend", "activity_pipeline"))
                candidate["_pipeline_latency_ms"] = d.get("_pipeline_latency_ms", 0)
                provenance_mode = "cfg_restored"
            elif d.get("provenance", {}).get("prompt_version", "").startswith("activity_pipeline_cfg"):
                provenance_mode = "canonical_only"
            elif any(
                isinstance(patch, dict) and patch.get("runnable") == runnable_name
                for patch in patches or []
            ):
                provenance_mode = "reviewer_patched"
            else:
                provenance_mode = "ai_enriched"

            d = candidate
            backend_name = d.pop("_pipeline_backend", "activity_pipeline")
            model = d.pop("_pipeline_model", backend_name)
            latency = d.pop("_pipeline_latency_ms", 0)
            d.pop("_pipeline_canonical", None)

            # Compute per-runnable quality metrics
            node_dicts = [n for n in d.get("nodes", []) if isinstance(n, dict)]
            edge_dicts = [e for e in d.get("edges", []) if isinstance(e, dict)]
            out_edges: dict[str, int] = {}
            for e in edge_dicts:
                s = e.get("source")
                if s:
                    out_edges[s] = out_edges.get(s, 0) + 1
            in_edges: dict[str, int] = {}
            for e in edge_dicts:
                t = e.get("target")
                if t:
                    in_edges[t] = in_edges.get(t, 0) + 1
            initial_ids = {n.get("id") for n in node_dicts if (n.get("node_type") or "").lower() == "initial"}
            unreachable_count = sum(
                1 for n in node_dicts
                if n.get("id") not in initial_ids
                and in_edges.get(n.get("id"), 0) == 0
            )
            quality_metrics = {
                "node_count": len(node_dicts),
                "decision_count": sum(1 for n in node_dicts if (n.get("node_type") or "").lower() == "decision"),
                "merge_count": sum(1 for n in node_dicts if (n.get("node_type") or "").lower() == "merge"),
                "guarded_edge_count": sum(1 for e in edge_dicts if e.get("guard")),
                "unreachable_count": unreachable_count,
                "provenance_mode": provenance_mode,
            }

            prov = d.get("provenance")
            if not isinstance(prov, dict):
                prov = {}
                d["provenance"] = prov
            prov.setdefault("ai_model", model)
            prov.setdefault("backend", backend_name)
            prov.setdefault("prompt_version", "activity_pipeline_v1")
            prov.setdefault("confidence", 0.85)
            prov.setdefault("generation_time_ms", latency)
            prov["provenance_mode"] = provenance_mode
            prov["quality_metrics"] = quality_metrics
            prov_hash = hashlib.sha256(
                f"{d.get('name')}|{len(d.get('nodes', []))}|{int(time.time())}".encode()
            ).hexdigest()[:12]
            prov.setdefault("prompt_hash", prov_hash)
            finalised.append(d)
        return finalised

    def _build_cfg_scaffold(
        self,
        mud_activity_context,
        sk_run: dict,
        swc_name: str,
        pseudo_code: str,
        req_ids: list[str],
    ) -> Optional[dict]:
        runnable = RunnableContext(
            name=sk_run.get("name") or "RE_Unknown",
            trigger=sk_run.get("trigger", "") or "",
            asil=sk_run.get("asil", "") or "",
            summary="",
            functional_description=pseudo_code or "",
        )
        ctx = MudActivityContext(
            swc_name=swc_name or getattr(mud_activity_context, "swc_name", "") or "",
            runnables=[runnable],
            rte_calls=list(getattr(mud_activity_context, "rte_calls", []) or []),
            helper_functions=list(getattr(mud_activity_context, "helper_functions", []) or []),
            raw_markdown="",
        )
        diagrams = synthesize_activity_diagrams_from_context(ctx, req_ids)
        if not diagrams:
            return None
        return diagrams[0].model_dump(mode="json")

    @staticmethod
    def _finalize_cfg_fallback(
        cfg_scaffold_obj: Optional[dict],
        rname: str,
        swc_name: str,
        backend_name: str,
        response,
        reason: str,
    ) -> Optional[dict]:
        if not cfg_scaffold_obj:
            return None
        diagram = copy.deepcopy(cfg_scaffold_obj)
        diagram["diagram_type"] = "activity"
        diagram.setdefault("owner_swc", swc_name or "")
        diagram.setdefault("owner_runnable", rname)
        diagram.setdefault("name", f"{rname} Code Flow")
        diagram["_pipeline_backend"] = backend_name
        diagram["_pipeline_model"] = getattr(response, "model", backend_name)
        diagram["_pipeline_latency_ms"] = getattr(response, "latency_ms", 0)
        diagram["_pipeline_canonical"] = copy.deepcopy(cfg_scaffold_obj)
        if not isinstance(diagram.get("provenance"), dict):
            diagram["provenance"] = {}
        diagram["provenance"]["prompt_version"] = f"activity_pipeline_cfg_{reason}"
        return diagram

    @staticmethod
    def _overlay_ai_on_cfg(cfg_scaffold_obj: dict, ai_diagram: dict) -> dict:
        """Merge AI-enriched content (names, guards, rte metadata) onto the
        deterministic scaffold topology.

        Three-tier node matching (in priority order):
          1. Exact ID match  — ``N_01`` == ``N_01``
          2. List-index + same node_type  — positional alignment for clean outputs
          3. Position within same-type subsequence — catches models that use
             ``N_1`` / ``N_A`` / random IDs but emit nodes in the right order.

        This ensures AI-provided names, guard text, rte_call metadata, and
        confidence values are never silently discarded even when the model
        ignores the requested ``N_xx`` ID format.
        """
        from collections import defaultdict

        merged = copy.deepcopy(cfg_scaffold_obj)
        ai_nodes = ai_diagram.get("nodes") if isinstance(ai_diagram.get("nodes"), list) else []

        # Strategy 1 lookup: exact id
        ai_by_id = {
            str(node.get("id")): node
            for node in ai_nodes
            if isinstance(node, dict) and node.get("id")
        }

        # Strategy 3 lookup: per-type ordered list (Nth decision → Nth decision)
        ai_by_type_pos: dict[str, list] = defaultdict(list)
        for ai_node in ai_nodes:
            if isinstance(ai_node, dict):
                ai_by_type_pos[(ai_node.get("node_type") or "").lower()].append(ai_node)
        type_pos_counters: dict[str, int] = defaultdict(int)

        merged_nodes = merged.get("nodes", [])
        for idx, node in enumerate(merged_nodes):
            if not isinstance(node, dict):
                continue
            ntype = (node.get("node_type") or "").lower()

            # Strategy 1: exact id
            ai_node = ai_by_id.get(node.get("id"))

            # Strategy 2: list index with same node_type
            if ai_node is None and idx < len(ai_nodes) and isinstance(ai_nodes[idx], dict):
                if (ai_nodes[idx].get("node_type") or "").lower() == ntype:
                    ai_node = ai_nodes[idx]

            # Strategy 3: Nth occurrence of same node_type
            if ai_node is None:
                pos = type_pos_counters[ntype]
                peers = ai_by_type_pos[ntype]
                if pos < len(peers):
                    ai_node = peers[pos]

            type_pos_counters[ntype] += 1

            if not ai_node:
                continue

            # Enrich scalar fields from AI
            for key in ("description", "confidence", "callee"):
                value = ai_node.get(key)
                if value not in (None, "", []):
                    node[key] = value

            # Fill missing RTE metadata from AI
            for key in ("rte_call", "port", "element"):
                if not node.get(key):
                    value = ai_node.get(key)
                    if value not in (None, "", []):
                        node[key] = value

            # Use AI name when it is more specific (longer), but never shorten
            # a good Rte_/Dem_ scaffold name to a vague AI phrase.
            ai_name = (ai_node.get("name") or "").strip()
            scaffold_name = str(node.get("name", ""))
            is_rte_scaffold = scaffold_name.startswith(("Rte_", "Dem_"))
            is_rte_ai = ai_name.startswith(("Rte_", "Dem_"))
            if ntype not in {"initial", "final", "merge"} and ai_name:
                if is_rte_scaffold and not is_rte_ai:
                    # Keep the precise Rte_/Dem_ scaffold name — AI shortened it
                    pass
                elif len(ai_name) >= len(scaffold_name) // 2:
                    node["name"] = ai_name

            if ai_node.get("trace_reqs"):
                node["trace_reqs"] = ai_node["trace_reqs"]

        # Overlay edge guards — try exact (src,tgt) match first, then
        # positional match by source-node type-sequence index.
        ai_edges = ai_diagram.get("edges") if isinstance(ai_diagram.get("edges"), list) else []
        ai_edge_pairs = {
            (str(edge.get("source")), str(edge.get("target"))): edge
            for edge in ai_edges
            if isinstance(edge, dict) and edge.get("source") and edge.get("target")
        }

        # Also build a per-source-decision ordered list of AI edges so we can
        # match guards positionally when IDs differ.
        ai_edges_by_src: dict[str, list] = defaultdict(list)
        for edge in ai_edges:
            if isinstance(edge, dict) and edge.get("source"):
                ai_edges_by_src[str(edge["source"])].append(edge)
        scaffold_edge_src_counters: dict[str, int] = defaultdict(int)

        for edge in merged.get("edges", []):
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("source") or "")
            tgt = str(edge.get("target") or "")

            # Strategy 1: exact (src, tgt) pair
            ai_edge = ai_edge_pairs.get((src, tgt))

            # Strategy 2: Nth outgoing edge from the same source node
            if ai_edge is None and src:
                pos = scaffold_edge_src_counters[src]
                src_ai_edges = ai_edges_by_src.get(src, [])
                if pos < len(src_ai_edges):
                    ai_edge = src_ai_edges[pos]
            scaffold_edge_src_counters[src] += 1

            if ai_edge:
                # Prefer AI guard when it is semantically richer than the
                # scaffold's generic [true]/[false].
                ai_guard = (ai_edge.get("guard") or "").strip()
                cur_guard = (edge.get("guard") or "").strip()
                if ai_guard and ai_guard not in ("[true]", "[false]", "[loop]", "[else]"):
                    edge["guard"] = ai_guard
                elif ai_guard and not cur_guard:
                    edge["guard"] = ai_guard
                if not ai_guard and ai_edge.get("label"):
                    edge.setdefault("label", ai_edge["label"])

        merged["sub_diagrams"] = cfg_scaffold_obj.get("sub_diagrams", [])
        merged.setdefault("source_requirements", ai_diagram.get("source_requirements", cfg_scaffold_obj.get("source_requirements", [])))
        merged.setdefault("owner_swc", ai_diagram.get("owner_swc", cfg_scaffold_obj.get("owner_swc", "")))
        merged.setdefault("owner_runnable", ai_diagram.get("owner_runnable", cfg_scaffold_obj.get("owner_runnable", "")))
        merged.setdefault("name", ai_diagram.get("name", cfg_scaffold_obj.get("name", "")))
        return merged

    @staticmethod
    def _diagram_has_cfg_breakage(diagram: dict, runnable_name: str) -> bool:
        try:
            model = ActivityDiagram.model_validate({**diagram, "diagram_type": "activity"})
            mermaid_text = MermaidExporter().export_diagram(model)
        except Exception:
            return True
        node_dicts = [node for node in diagram.get("nodes", []) if isinstance(node, dict)]
        decision_count = sum(1 for node in node_dicts if (node.get("node_type") or "").lower() == "decision")
        merge_count = sum(1 for node in node_dicts if (node.get("node_type") or "").lower() == "merge")
        # ── Check 1: decision nodes missing outgoing branches ────────────────
        # Count decisions that have < 2 outgoing edges — genuinely broken
        # (missing an [else] or second branch).  Note: sequential independent
        # guards (2+ decisions, no merge) are valid — do NOT flag those.
        out_edges_count: dict[str, int] = {}
        in_edges_count: dict[str, int] = {}
        for e in (diagram.get("edges") or []):
            if not isinstance(e, dict):
                continue
            s = e.get("source")
            t = e.get("target")
            if s:
                out_edges_count[s] = out_edges_count.get(s, 0) + 1
            if t:
                in_edges_count[t] = in_edges_count.get(t, 0) + 1
        decisions_missing_branch = sum(
            1 for n in node_dicts
            if (n.get("node_type") or "").lower() == "decision"
            and out_edges_count.get(n.get("id"), 0) < 2
        )
        if decisions_missing_branch > 0:
            return True

        # ── Check 2: unreachable nodes ────────────────────────────────────────
        # Any non-initial node that has zero incoming edges is unreachable —
        # the AI invented an orphan node or connected it only via a dropped edge.
        initial_ids = {
            n.get("id") for n in node_dicts
            if (n.get("node_type") or "").lower() == "initial"
        }
        unreachable = [
            n.get("id") for n in node_dicts
            if n.get("id") not in initial_ids
            and in_edges_count.get(n.get("id"), 0) == 0
        ]
        if unreachable:
            logger.info(
                "[Activity Pipeline/breakage] %s: %d unreachable node(s): %s",
                runnable_name, len(unreachable), unreachable[:5],
            )
            return True
        for node in node_dicts:
            if (node.get("node_type") or "").lower() != "call":
                continue
            name = (node.get("name") or "").strip()
            rte_call = (node.get("rte_call") or "").strip()
            if name.startswith("Rte_") and (not rte_call or not rte_call.startswith("Rte_")):
                return True
        lint = MermaidLinter().lint(
            mermaid_text,
            DiagramType.ACTIVITY,
            diagram_key=runnable_name or diagram.get("name", ""),
        )
        if lint.errors:
            return True
        branch_warnings = [
            warning for warning in lint.warnings
            if "Decision node" in warning or "branching paths may be missing" in warning
        ]
        return bool(branch_warnings)
