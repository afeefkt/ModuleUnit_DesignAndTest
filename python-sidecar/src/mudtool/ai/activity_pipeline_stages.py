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
from types import SimpleNamespace
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

══════════════════════════════════════════════════════════════════
AVAILABLE SIGNALS — USE THESE EXACT NAMES IN call/exception NODES
══════════════════════════════════════════════════════════════════
{signal_table}
══════════════════════════════════════════════════════════════════
IMPORTANT: copy the signatures above verbatim into your call nodes.
Do NOT paraphrase, abbreviate, or guess port names — use the exact
Rte_Read/Write/IRead/IWrite signatures shown. If a pseudo-code step
says "read vehicle speed", use the Read sig listed above for it.
══════════════════════════════════════════════════════════════════

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

GOLD-STANDARD EXAMPLE (11-node — shows port read, IRV read/write, CalPrm decision,
exception path, computation, second decision, merge, write, End):
{{
  "diagram_type": "activity",
  "name": "RE_SpeedMonitor Code Flow",
  "owner_swc": "SWC_VehicleSpeed",
  "owner_runnable": "RE_SpeedMonitor",
  "source_requirements": ["REQ-01", "REQ-02"],
  "nodes": [
    {{"id":"N_01","name":"Start","node_type":"initial","trace_reqs":["REQ-01"],"description":"Entry 10 ms cycle","confidence":0.95}},
    {{"id":"N_02","name":"Rte_Read_RP_VehicleSpeed(&l_f32Speed)","node_type":"call","rte_call":"Rte_Read","port":"RP_VehicleSpeed","element":"VehicleSpeed","trace_reqs":["REQ-01"],"description":"Read raw speed from sensor","confidence":0.95}},
    {{"id":"N_03","name":"Rte_IRead_IRV_PrevSpeed(&l_f32PrevSpd)","node_type":"call","rte_call":"Rte_IRead","port":"IRV_PrevSpeed","element":"PrevSpeed","trace_reqs":["REQ-01"],"description":"Read previous cycle speed IRV","confidence":0.95}},
    {{"id":"N_04","name":"(l_f32Speed >= 0.0F) && (l_f32Speed < CALPRM_SPEED_MAX)","node_type":"decision","trace_reqs":["REQ-01"],"description":"Validate speed in range","confidence":0.9}},
    {{"id":"N_05","name":"Dem_SetEventStatus(DTC_SpeedInvalid, DEM_EVENT_STATUS_FAILED)","node_type":"exception","trace_reqs":["REQ-02"],"description":"Report out-of-range fault","confidence":0.9}},
    {{"id":"N_06","name":"l_f32Delta = l_f32Speed - l_f32PrevSpd","node_type":"action","trace_reqs":["REQ-01"],"description":"Compute speed delta","confidence":0.95}},
    {{"id":"N_07","name":"l_f32Speed > CALPRM_SPEED_WARN","node_type":"decision","trace_reqs":["REQ-02"],"description":"Check warning threshold","confidence":0.9}},
    {{"id":"N_08","name":"Rte_Write_PP_SpeedWarning(TRUE)","node_type":"call","rte_call":"Rte_Write","port":"PP_SpeedWarning","element":"SpeedWarning","trace_reqs":["REQ-02"],"description":"Set warning flag","confidence":0.95}},
    {{"id":"N_09","name":"merge","node_type":"merge","trace_reqs":["REQ-01"],"description":"Rejoin after warning branch","confidence":0.99}},
    {{"id":"N_10","name":"Rte_IWrite_IRV_PrevSpeed(l_f32Speed)","node_type":"call","rte_call":"Rte_IWrite","port":"IRV_PrevSpeed","element":"PrevSpeed","trace_reqs":["REQ-01"],"description":"Store current speed for next cycle","confidence":0.95}},
    {{"id":"N_11","name":"End","node_type":"final","trace_reqs":["REQ-01"],"description":"Exit runnable","confidence":0.95}}
  ],
  "edges": [
    {{"id":"E_01","source":"N_01","target":"N_02","guard":""}},
    {{"id":"E_02","source":"N_02","target":"N_03","guard":""}},
    {{"id":"E_03","source":"N_03","target":"N_04","guard":""}},
    {{"id":"E_04","source":"N_04","target":"N_05","guard":"[else]"}},
    {{"id":"E_05","source":"N_04","target":"N_06","guard":"[(l_f32Speed >= 0.0F) && (l_f32Speed < CALPRM_SPEED_MAX)]"}},
    {{"id":"E_06","source":"N_05","target":"N_11","guard":""}},
    {{"id":"E_07","source":"N_06","target":"N_07","guard":""}},
    {{"id":"E_08","source":"N_07","target":"N_08","guard":"[l_f32Speed > CALPRM_SPEED_WARN]"}},
    {{"id":"E_09","source":"N_07","target":"N_09","guard":"[else]"}},
    {{"id":"E_10","source":"N_08","target":"N_09","guard":""}},
    {{"id":"E_11","source":"N_09","target":"N_10","guard":""}},
    {{"id":"E_12","source":"N_10","target":"N_11","guard":""}}
  ],
  "sub_diagrams": []
}}

STRICT FORMAT EXAMPLES — node names MUST follow these patterns (ZERO tolerance for English prose):

decision node names (C boolean expression only):
  YES  "l_f32Speed > LIMIT_HIGH"
  YES  "l_u8RetryCount < MAX_RETRIES"
  YES  "l_eMode == STATE_ACTIVE"
  YES  "(l_f32V > LO) && (l_f32V < HI)"
  NO   "Check if speed valid"                  (English prose)
  NO   "Validate torque range"                 (English prose)
  NO   "if l_f32Speed > LIMIT"                 (do NOT include 'if' keyword)

action node names (C assignment or atomic op):
  YES  "l_f32Out = l_f32K * l_f32In"
  YES  "l_u8Status = STATUS_OK"
  YES  "l_boolValid = (l_f32V < MAX)"
  NO   "Compute assist torque"                 (English prose)
  NO   "Set status to OK"                      (English prose)

call node names (AUTOSAR service signature):
  YES  "Rte_Read_RP_VehicleSpeed(&l_f32Speed)"
  YES  "Rte_Write_PP_AssistTorque(l_f32Out)"
  YES  "Dem_SetEventStatus(DEM_EVENT_FAULT, DEM_EVENT_STATUS_FAILED)"
  NO   "Read vehicle speed"                    (use Rte_Read signature)
  NO   "Rte_Read"                              (must include port and arg)

exception node names (Dem_/Det_ call):
  YES  "Dem_SetEventStatus(DTC_X, DEM_EVENT_STATUS_FAILED)"
  YES  "Det_ReportError(MODULE_ID, INSTANCE, API_ID, ERROR_CODE)"
  NO   "Report fault"                          (English prose)

LOCAL VARIABLE NAMING — must be l_<type><Name> (lowercase l, type prefix, PascalCase name):
  YES  l_f32Speed, l_u16Count, l_boolValid, l_eMode, l_i32Delta
  NO   speed, mySpeed, speedVar, theSpeed, f_speed

EDGE GUARDS — also C expressions only:
  YES  "[l_f32Speed > 100]", "[else]", "[default]", "[loop]"
  NO   "[if speed exceeds limit]", "[check valid]"

Before emitting JSON, scan EVERY node.name and EVERY edge.guard:
  - If a decision/guard contains English words (check/verify/validate/is/should/whether/when),
    REWRITE it as a C boolean expression using the local variables from the pseudo-code.
  - If a call name lacks the Rte_/Dem_ prefix with full signature, REWRITE.
  - If a local variable doesn't match l_<type><Name>, REWRITE.
  - If you cannot derive a valid C expression from the pseudo-code, set
    confidence < 0.5 and put a TODO marker in the description, but STILL
    write the name as a placeholder C expression (never English).
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
  6. A node typed "function_call" whose callee is a BSW/OS service (starts with WdgM_,
     Dem_, Det_, SchM_, Com_, NvM_, Os_, CanSM_, BswM_, Dcm_, Rte_). These are external
     service calls that never have sub-diagrams — they must be retyped to "action".
     Emit severity "error" with message: 'Node <id> "<name>": BSW callee "<callee>"
     must be node_type "action", not "function_call" (no sub-diagram exists for BSW
     services).'
  7. A non-initial node with zero incoming edges (unreachable / orphaned). This means
     the CFG has a broken bypass edge that skips over valid steps. Emit severity "warn"
     with message: 'Node <id> "<name>" is unreachable (no incoming edges) — a decision
     edge likely bypasses this node and must be rewired to it.'
  8. Pseudo-code purity: any decision node's name or any edge's guard contains English
     prose (words like check, verify, validate, is, are, whether, should, when, valid,
     invalid, ok) instead of a C boolean expression. ALSO any action node whose name
     is an English summary (no `=` and no recognizable C operator) when the source
     pseudo-code clearly contained C syntax. For each, emit a rename_node or
     change_guard patch with a rewritten C expression derived from the local
     variables used elsewhere in the same diagram. Severity "warn".

Output STRICT JSON only:
{
  "issues": [
    {"runnable": "RE_…", "severity": "warn|error", "message": "…"}
  ],
  "patches": [
    {"runnable": "RE_…", "op": "add_initial"},
    {"runnable": "RE_…", "op": "add_final"},
    {"runnable": "RE_…", "op": "rename_node",        "node_id": "N_03", "new_name": "Rte_Read_RP_Speed(&l_f32Speed)"},
    {"runnable": "RE_…", "op": "change_guard",       "edge_source": "N_04", "edge_target": "N_05", "new_guard": "[l_f32Speed > LIMIT]"},
    {"runnable": "RE_…", "op": "retype_node",        "node_id": "N_07", "new_type": "action"},
    {"runnable": "RE_…", "op": "add_exception_edge", "from_node": "N_09", "label": "E_NOT_OK"}
  ]
}

Patch ops supported (use only these — anything else is ignored):
  add_initial        — insert a Start node at the top
  add_final          — insert an End node at the bottom
  rename_node        — fix a node name; fields: node_id, new_name
  change_guard       — fix an edge guard; fields: edge_source, edge_target, new_guard
  retype_node        — correct a node's node_type; fields: node_id, new_type
                       valid types: action | call | function_call | decision | merge | exception | initial | final
  add_exception_edge — add a missing fault edge from a node to the diagram's final node
                       fields: from_node, label (the guard text, e.g. "E_NOT_OK")

For rule 6 (BSW callee typed as function_call): emit BOTH an issue AND a retype_node patch:
  {"runnable": "RE_…", "op": "retype_node", "node_id": "<id>", "new_type": "action"}

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

        # Surface inferred values so engineers can verify before Stage 3 commits to them
        assumptions = self._extract_assumptions(runnables)
        if assumptions:
            self._emit(
                f"[Activity Pipeline] Stage 1 inferred {len(assumptions)} value(s) from pseudo-code — verify in pipeline log",
                22,
                assumptions=assumptions,
                assumption_count=len(assumptions),
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
        fallback_records: list[dict[str, str]] = []
        total = len(runnables)
        for idx, sk_run in enumerate(runnables, 1):
            rname = sk_run.get("name") or f"RE_{idx}"
            backend_name = getattr(self._backend, "backend_name", "")
            enrichment_hint = ""
            if any(
                key in (backend_name or "").lower()
                for key in ("claude", "gpt-4", "gpt4", "gemini-1.5", "gemini-2", "o1", "o3", "o4")
            ):
                enrichment_hint = " [enrichment-only]"
            self._emit(
                f"[Activity Pipeline] Stage 3/5{enrichment_hint} — diagram for {rname}…",
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
                prov = draft.get("provenance") if isinstance(draft.get("provenance"), dict) else {}
                prompt_version = str(prov.get("prompt_version") or "")
                if prompt_version.startswith("activity_pipeline_cfg_"):
                    fallback_records.append({
                        "runnable": rname,
                        "reason": prompt_version.replace("activity_pipeline_cfg_", "", 1),
                    })
                drafts.append(draft)
            else:
                logger.warning(
                    "[Activity Pipeline] Stage 3 returned no diagram for %s", rname
                )
                fallback_records.append({"runnable": rname, "reason": "unavailable"})

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
        if fallback_records:
            for d in finalised:
                runnable = d.get("owner_runnable") or d.get("name", "")
                match = next((r for r in fallback_records if r["runnable"] == runnable), None)
                if match:
                    d.setdefault("warnings", []).append(
                        f"AI enrichment failed for {runnable}; deterministic CFG fallback used ({match['reason']})."
                    )

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
            fallback_records=fallback_records,
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

    @staticmethod
    def _extract_assumptions(runnables: list[dict]) -> list[dict]:
        """Extract inferred values from the Stage 1 skeleton for user visibility.

        Surfaces guard conditions, DEM events, and IRV references that the AI
        inferred from pseudo-code — so engineers can spot wrong guesses before
        diagram generation commits to them. Returned as a list of dicts emitted
        in the Stage 1 SSE payload.
        """
        assumptions: list[dict] = []
        for r in runnables:
            rname = r.get("name", "?")

            # Guard-like key steps (conditions the AI will use as decision guards)
            for step in r.get("key_steps", []):
                s = step.strip()
                if s.lower().startswith("if ") or any(op in s for op in ("==", "!=", ">", "<", ">=", "<=")):
                    assumptions.append({
                        "runnable": rname,
                        "field": "guard_condition",
                        "inferred_value": s,
                        "basis": "inferred from Section 7 pseudo-code",
                    })

            # DEM event IDs the AI found
            for dem in r.get("raises_dem", []):
                if dem:
                    assumptions.append({
                        "runnable": rname,
                        "field": "dem_event",
                        "inferred_value": dem,
                        "basis": "inferred from MUD spec DEM references",
                    })

            # IRV producer/consumer relationships
            for irv in r.get("reads_irvs", []):
                if irv:
                    assumptions.append({
                        "runnable": rname,
                        "field": "irv_read",
                        "inferred_value": irv,
                        "basis": "inferred from MUD spec IRV references",
                    })
            for irv in r.get("writes_irvs", []):
                if irv:
                    assumptions.append({
                        "runnable": rname,
                        "field": "irv_write",
                        "inferred_value": irv,
                        "basis": "inferred from MUD spec IRV references",
                    })

        return assumptions

    @staticmethod
    def _build_signal_table(
        sk_run: dict,
        pseudo_code: str,
        ctx_rte_calls: list[str],
    ) -> str:
        """Build a per-runnable available-signals table for Stage 3 injection.

        Combines three sources (priority order):
          1. Skeleton explicit port/IRV/DEM lists — most authoritative.
          2. Full Rte_ signatures extracted from the runnable's pseudo-code.
          3. Global ctx_rte_calls from MudActivityContext — SWC-wide fallback.

        The returned string is injected into _RUNNABLE_USER_TMPL's {signal_table}
        placeholder so Stage 3 uses exact port names instead of guessing.
        """
        lines: list[str] = []
        seen: set[str] = set()

        def _add(category: str, sig: str) -> None:
            sig = sig.strip()
            if sig and sig not in seen:
                seen.add(sig)
                lines.append(f"  {category:<14} {sig}")

        # ── 1. Skeleton explicit lists ────────────────────────────────────
        for p in sk_run.get("reads_ports") or []:
            p = p.strip()
            if p:
                sig = p if p.startswith("Rte_") else f"Rte_Read_{p}(&l_var)"
                _add("Read port:", sig)
        for p in sk_run.get("writes_ports") or []:
            p = p.strip()
            if p:
                sig = p if p.startswith("Rte_") else f"Rte_Write_{p}(l_var)"
                _add("Write port:", sig)
        for irv in sk_run.get("reads_irvs") or []:
            irv = irv.strip()
            if irv:
                sig = irv if irv.startswith("Rte_") else f"Rte_IRead_{irv}(&l_var)"
                _add("IRV read:", sig)
        for irv in sk_run.get("writes_irvs") or []:
            irv = irv.strip()
            if irv:
                sig = irv if irv.startswith("Rte_") else f"Rte_IWrite_{irv}(l_var)"
                _add("IRV write:", sig)
        for dem in sk_run.get("raises_dem") or []:
            dem = dem.strip()
            if dem:
                _add("DEM event:", f"Dem_SetEventStatus({dem}, DEM_EVENT_STATUS_FAILED)")

        # ── 2. Full signatures from runnable's pseudo-code ─────────────────
        _SIG_PAT = re.compile(
            r"\b(Rte_(?:Read|Write|IRead|IWrite|Call|Switch|Result)\w*\s*\([^)\n]{0,150}\))",
            re.IGNORECASE,
        )
        for m in _SIG_PAT.finditer(pseudo_code):
            sig = re.sub(r"\s+", " ", m.group(1)).strip()
            name_lower = sig.lower()
            if "iread" in name_lower:
                _add("IRV read:", sig)
            elif "iwrite" in name_lower:
                _add("IRV write:", sig)
            elif "read" in name_lower:
                _add("Read sig:", sig)
            elif "write" in name_lower:
                _add("Write sig:", sig)
            else:
                _add("Rte call:", sig)

        # ── 3. Global ctx_rte_calls — include calls that match pseudo-code ──
        pseudo_lower = pseudo_code.lower()
        for call in ctx_rte_calls or []:
            call = call.strip()
            m = re.search(r"Rte_(?:Read|Write|IRead|IWrite)_(\w+)", call, re.IGNORECASE)
            if not m:
                continue
            port_frag = m.group(1).lower()
            # Include if: port fragment is mentioned in pseudo-code, OR the SWC
            # is small enough (≤8 global calls) that showing all is useful.
            if port_frag in pseudo_lower or len(ctx_rte_calls) <= 8:
                name_lower = call.lower()
                if "iread" in name_lower:
                    _add("IRV read:", call)
                elif "iwrite" in name_lower:
                    _add("IRV write:", call)
                elif "read" in name_lower:
                    _add("Read sig:", call)
                elif "write" in name_lower:
                    _add("Write sig:", call)

        # ── 4. CalPrm constants mentioned in pseudo-code ───────────────────
        for calprm in sorted(set(re.findall(r"\bCALPRM_[A-Z][A-Z0-9_]+", pseudo_code))):
            _add("CalPrm:", calprm)

        if not lines:
            return "  (no signals detected — derive exact names from pseudo-code above)"
        return "\n".join(lines)

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

        # Build per-runnable signal table (Strategy 1 — exact port name injection).
        # This prevents the AI from guessing port names; it copies them verbatim.
        signal_table = self._build_signal_table(
            sk_run=sk_run,
            pseudo_code=pseudo_code,
            ctx_rte_calls=list(getattr(mud_activity_context, "rte_calls", None) or []),
        )

        backend = self._backend
        backend_name = getattr(backend, "backend_name", "?")
        is_high_end = any(
            key in (backend_name or "").lower()
            for key in ("claude", "gpt-4", "gpt4", "gemini-1.5", "gemini-2", "o1", "o3", "o4")
        )
        system_prompt = _RUNNABLE_SYSTEM
        if is_high_end and cfg_scaffold_obj:
            system_prompt = """You are enriching an AUTOSAR activity diagram.
The scaffold below is the canonical topology. Do not add, remove, or retype any node or edge.
For each node, improve only name, description, confidence, rte_call, port, element, and callee.
For each decision edge, improve only guard/label as a valid C boolean expression in brackets,
for example [l_f32Val > LIMIT] or [else].
Return the exact same ActivityDiagram JSON structure with the same topology and ids. Output JSON only."""
            logger.info("[Activity Pipeline/Stage3] %s using enrichment-only prompt for backend %s", rname, backend_name)

        user_prompt = _RUNNABLE_USER_TMPL.format(
            swc_name=swc_name or "unknown",
            runnable_name=rname,
            trigger=sk_run.get("trigger", "") or "n/a",
            asil=sk_run.get("asil", "") or "QM",
            label_style=activity_label_style,
            key_steps_block=key_steps_block,
            signal_table=signal_table,
            pseudo_code=pseudo_code or "(no pseudo-code; produce a minimal Start/End diagram)",
            cfg_scaffold=cfg_scaffold,
            requirements_block=requirements_block,
        )

        try:
            response = await backend.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=4096,
                response_format="json",
            )
        except TypeError:
            response = await backend.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=4096,
            )
        except Exception as exc:
            logger.warning("[Activity Pipeline/Stage3] backend error for %s: %s", rname, exc)
            return self._finalize_cfg_fallback(
                cfg_scaffold_obj,
                rname,
                swc_name,
                backend_name,
                SimpleNamespace(model=backend_name, latency_ms=0),
                reason="ai_backend_error",
            )

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
        self._normalize_activity_semantics(diagram)
        if cfg_scaffold_obj:
            diagram = self._overlay_ai_on_cfg(cfg_scaffold_obj, diagram)
            self._normalize_activity_semantics(diagram)
            self._repair_orphaned_nodes(diagram, rname)
            self._repair_decision_branches(diagram, rname)
            self._ensure_helper_subdiagrams(diagram, swc_name, rname, req_ids)
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

    @staticmethod
    def _normalize_activity_semantics(diagram: dict) -> None:
        """Normalize call-node semantics before AUTOSAR validation."""
        valid_rte_calls = {
            "Rte_Read", "Rte_Write", "Rte_Call", "Rte_Result",
            "Rte_IRead", "Rte_IWrite", "Rte_Send", "Rte_Receive", "Rte_Switch",
        }
        # BSW / OS service prefixes — these are external calls, never sub-diagrams.
        # Nodes typed as function_call with these callees are retyped to action so
        # the validator (STR-024) doesn't demand a matching sub-diagram for them.
        _BSW_PREFIXES = (
            "WdgM_", "Dem_", "Det_", "SchM_", "Com_", "NvM_", "Os_",
            "Rte_", "CanSM_", "LinSM_", "EthSM_", "BswM_", "Dcm_",
        )
        port_re = re.compile(r"^(?:RP|PP)_[A-Za-z][A-Za-z0-9_]*$")
        bool_expr_re = re.compile(r"[A-Za-z_]\w*\s*(?:==|!=|>=|<=|>|<)|&&|\|\|")
        for node in diagram.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            ntype = (node.get("node_type") or "").lower()

            # ── Pass 1: fix wrongly-typed CALL nodes ──────────────────────
            if ntype == "call":
                rte_call = (node.get("rte_call") or "").strip()
                name = (node.get("name") or "").strip()
                if bool_expr_re.search(name) and "Rte_" not in name and "Dem_" not in name:
                    node["node_type"] = "decision"
                    node.pop("rte_call", None)
                    node.pop("port", None)
                    node.pop("element", None)
                    continue
                if re.match(r"^[A-Za-z_]\w*\s*=\s*Rte_", name):
                    node["node_type"] = "action"
                    node.pop("rte_call", None)
                    node.pop("port", None)
                    node.pop("element", None)
                    continue
                if rte_call and rte_call not in valid_rte_calls:
                    node["node_type"] = "function_call"
                    node["callee"] = node.get("callee") or rte_call or name.split("(", 1)[0]
                    node.pop("rte_call", None)
                    node.pop("port", None)
                    node.pop("element", None)
                    continue
                port = (node.get("port") or "").strip()
                if port and not port_re.match(port):
                    if name.startswith("Rte_"):
                        node["node_type"] = "action"
                    node.pop("rte_call", None)
                    node.pop("port", None)

            # ── Pass 2: retype BSW/OS function_call nodes to action ───────
            # function_call requires a matching sub-diagram (STR-024).
            # External BSW service calls (WdgM_*, Dem_*, Det_*, etc.) are
            # leaf calls — they never have sub-diagrams within this component.
            elif ntype == "function_call":
                callee = (node.get("callee") or node.get("name") or "").strip()
                fn_name = callee.split("(", 1)[0].strip()
                if any(fn_name.startswith(prefix) for prefix in _BSW_PREFIXES):
                    node["node_type"] = "action"
                    node.pop("callee", None)
                    logger.debug(
                        "[Normalize] Retyped BSW function_call '%s' → action", fn_name
                    )

        for node in diagram.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            if (node.get("node_type") or "").lower() != "action":
                continue
            name = (node.get("name") or "").strip()
            if bool_expr_re.search(name) and "Rte_" not in name and "Dem_" not in name:
                node["node_type"] = "decision"
                logger.debug("[Normalize] Retyped condition action '%s' -> decision", name)

    @staticmethod
    def _ensure_helper_subdiagrams(diagram: dict, swc_name: str, runnable_name: str, req_ids: list[str]) -> None:
        sub_diagrams = diagram.setdefault("sub_diagrams", [])
        existing = {
            sub.get("function_name")
            for sub in sub_diagrams
            if isinstance(sub, dict) and sub.get("function_name")
        }
        for node in diagram.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            if (node.get("node_type") or "").lower() != "function_call":
                continue
            callee = (node.get("callee") or node.get("name") or "").split("(", 1)[0].strip()
            if not callee or callee in existing:
                continue
            sub_diagrams.append({
                "diagram_type": "activity",
                "name": f"{callee} Code Flow",
                "function_name": callee,
                "parent_diagram": f"{runnable_name} Code Flow",
                "owner_swc": swc_name or diagram.get("owner_swc") or "",
                "owner_runnable": runnable_name,
                "source_requirements": list(req_ids or diagram.get("source_requirements") or []),
                "nodes": [
                    {"id": "N_00", "name": "Start", "node_type": "initial", "trace_reqs": [], "confidence": 0.85, "description": f"Entry point for {callee}"},
                    {"id": "N_01", "name": f"{callee}(...)", "node_type": "action", "trace_reqs": list(req_ids or []), "confidence": 0.75, "description": f"Stub helper action for {callee}; detailed body not provided in MUD spec."},
                    {"id": "N_02", "name": "End", "node_type": "final", "trace_reqs": [], "confidence": 0.85, "description": f"Exit point for {callee}"},
                ],
                "edges": [
                    {"id": "E_01", "source": "N_00", "target": "N_01"},
                    {"id": "E_02", "source": "N_01", "target": "N_02"},
                ],
                "sub_diagrams": [],
            })
            existing.add(callee)

    @staticmethod
    def _repair_decision_branches(diagram: dict, runnable_name: str) -> None:
        nodes = [n for n in diagram.get("nodes") or [] if isinstance(n, dict) and n.get("id")]
        edges = diagram.setdefault("edges", [])
        if not nodes:
            return
        out_by_src: dict[str, list[dict]] = {}
        for edge in edges:
            if isinstance(edge, dict) and edge.get("source"):
                out_by_src.setdefault(edge["source"], []).append(edge)
        final_id = next(
            (n["id"] for n in nodes if (n.get("node_type") or "").lower() == "final"),
            nodes[-1]["id"],
        )
        for idx, node in enumerate(nodes):
            if (node.get("node_type") or "").lower() != "decision":
                continue
            outgoing = out_by_src.get(node["id"], [])
            if len(outgoing) >= 2:
                continue
            existing_targets = {
                edge.get("target")
                for edge in outgoing
                if isinstance(edge, dict) and edge.get("target")
            }
            target = final_id
            for later in nodes[idx + 1:]:
                if later["id"] != node["id"] and later["id"] not in existing_targets:
                    target = later["id"]
                    break
            if target in existing_targets and final_id not in existing_targets:
                target = final_id
            edge_id = f"E_AUTO_FALSE_{node['id']}"
            if any(isinstance(e, dict) and e.get("id") == edge_id for e in edges):
                continue
            edges.append({
                "id": edge_id,
                "source": node["id"],
                "target": target,
                "guard": "[else]",
            })
            logger.info("[DecisionRepair] %s: added else edge %s -> %s", runnable_name, node["id"], target)

    @staticmethod
    def _repair_orphaned_nodes(diagram: dict, runnable_name: str) -> None:
        """Stitch orphaned nodes (no incoming edges) into the nearest decision.

        When the AI generates a bypass edge from a decision directly to a late node
        (e.g. N_03→N_17 instead of N_03→N_07), valid intermediate nodes become
        unreachable. This repair:
          1. Identifies all non-INITIAL nodes with no incoming edges.
          2. For each such "orphaned chain head", finds the decision edge that bypasses
             it (i.e. a decision outgoing edge whose target is NOT in the orphaned set
             but SHOULD be, based on edge ordering).
          3. Rewires that edge to point to the orphaned chain head, and wires the
             chain tail to the original bypass target.

        Only applies when the orphaned count is ≤ 6 nodes (targeted repair, not bulk).
        """
        nodes: list[dict] = diagram.get("nodes") or []
        edges: list[dict] = diagram.get("edges") or []
        if not nodes or not edges:
            return

        node_ids = {n["id"] for n in nodes if isinstance(n, dict) and n.get("id")}
        node_by_id = {n["id"]: n for n in nodes if isinstance(n, dict) and n.get("id")}

        # Nodes with at least one incoming edge
        has_incoming = {e["target"] for e in edges if isinstance(e, dict) and e.get("target")}
        initial_ids = {
            n["id"] for n in nodes
            if isinstance(n, dict) and (n.get("node_type") or "").lower() == "initial"
        }

        orphaned_ids = (node_ids - has_incoming) - initial_ids
        if not orphaned_ids or len(orphaned_ids) > 6:
            return  # too many orphans → don't guess

        # Find the first node in the orphaned chain (has outgoing edges to known nodes)
        orphaned_sources = {
            e["source"] for e in edges
            if isinstance(e, dict) and e.get("source") in orphaned_ids
        }
        # Chain head = orphaned node that appears earliest among those with outgoing edges
        chain_heads = [
            n["id"] for n in nodes
            if isinstance(n, dict)
            and n.get("id") in orphaned_ids
            and n.get("id") in orphaned_sources
        ]
        if not chain_heads:
            return

        chain_head = chain_heads[0]

        # Chain tail = orphaned node with an outgoing edge to a non-orphaned node
        chain_tail = None
        bypass_target = None
        for e in edges:
            if not isinstance(e, dict):
                continue
            src = e.get("source")
            tgt = e.get("target")
            if src in orphaned_ids and tgt and tgt not in orphaned_ids:
                chain_tail = src
                bypass_target = tgt
                break

        if not chain_tail:
            return

        # Find the decision edge that bypasses the orphaned chain
        # (a decision → bypass_target edge where that same bypass_target equals
        # what the orphaned chain eventually connects to)
        for e in edges:
            if not isinstance(e, dict):
                continue
            src = e.get("source")
            tgt = e.get("target")
            src_node = node_by_id.get(src)
            if (
                src_node
                and (src_node.get("node_type") or "").lower() == "decision"
                and tgt == bypass_target
                and src not in orphaned_ids
            ):
                # Rewire: decision → chain_head (instead of bypass_target)
                logger.info(
                    "[RepairOrphan] %s: rewired decision edge %s→%s to %s→%s "
                    "(chain: %s→%s)",
                    runnable_name, src, tgt, src, chain_head, chain_head, bypass_target,
                )
                e["target"] = chain_head
                # The chain tail already points to bypass_target (from the edges above)
                return  # one repair per call

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

        backend = self._reviewer_backend
        reviewer_system = _REVIEWER_SYSTEM
        reviewer_name = getattr(backend, "backend_name", "")
        is_high_end_reviewer = any(
            key in (reviewer_name or "").lower()
            for key in ("claude", "gpt-4", "gpt4", "gemini-1.5", "gemini-2", "o1", "o3", "o4")
        )
        if is_high_end_reviewer:
            reviewer_system += """

Also flag:
- Guard labels that are English prose instead of C boolean expressions.
- Variable names not following l_f32/l_u8/l_b/l_u16 prefix convention.
- Missing Dem_SetEventStatus call after fault condition for ASIL-C/D runnables.
- RTE write calls missing a corresponding guard/validation step before them.
"""

        user_prompt = (
            "DRAFT DIAGRAMS (compact form):\n"
            + json.dumps(compact, ensure_ascii=False, indent=2)
            + "\n\nCROSS-REFERENCE MAP:\n"
            + json.dumps(xref, ensure_ascii=False, indent=2)
            + "\n\nReturn the JSON {issues, patches}."
        )
        try:
            response = await backend.generate(
                system_prompt=reviewer_system,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=2048,
                response_format="json",
            )
        except TypeError:
            response = await backend.generate(
                system_prompt=reviewer_system,
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

            elif op == "rename_node":
                node_id = patch.get("node_id")
                new_name = (patch.get("new_name") or "").strip()
                if node_id and new_name:
                    for n in nodes:
                        if isinstance(n, dict) and n.get("id") == node_id:
                            n["name"] = new_name
                            break

            elif op == "change_guard":
                src = patch.get("edge_source")
                tgt = patch.get("edge_target")
                new_guard = (patch.get("new_guard") or "").strip()
                if src and tgt and new_guard:
                    for e in edges:
                        if isinstance(e, dict) and e.get("source") == src and e.get("target") == tgt:
                            e["guard"] = new_guard
                            break

            elif op == "retype_node":
                node_id = patch.get("node_id")
                new_type = (patch.get("new_type") or "").strip().lower()
                _valid_types = {
                    "action", "call", "function_call", "decision",
                    "merge", "exception", "initial", "final", "fork", "join",
                }
                if node_id and new_type in _valid_types:
                    for n in nodes:
                        if isinstance(n, dict) and n.get("id") == node_id:
                            n["node_type"] = new_type
                            # BSW retyped to action — callee field no longer meaningful
                            if new_type == "action":
                                n.pop("callee", None)
                            break

            elif op == "add_exception_edge":
                from_node = patch.get("from_node")
                label = (patch.get("label") or "Error").strip()
                if from_node and any(
                    isinstance(n, dict) and n.get("id") == from_node for n in nodes
                ):
                    tgt = next(
                        (n["id"] for n in nodes
                         if isinstance(n, dict) and (n.get("node_type") or "").lower() == "final"),
                        None,
                    )
                    if tgt:
                        exc_edge_id = f"E_EXC_{from_node}"
                        already_exists = any(
                            isinstance(e, dict) and e.get("id") == exc_edge_id
                            for e in edges
                        )
                        if not already_exists:
                            edges.append({
                                "id": exc_edge_id,
                                "source": from_node,
                                "target": tgt,
                                "guard": f"[{label}]",
                            })

        # Stamp provenance hash + version + quality metrics on every diagram
        finalised: list[dict] = []
        for d in drafts:
            canonical = d.get("_pipeline_canonical")
            candidate = d
            runnable_name = d.get("owner_runnable") or d.get("name") or ""
            existing_provenance = d.get("provenance")
            if not isinstance(existing_provenance, dict):
                existing_provenance = {}

            # Determine provenance mode before any mutation
            if canonical and ActivityPipeline._diagram_has_cfg_breakage(d, runnable_name):
                candidate = copy.deepcopy(canonical)
                candidate["_pipeline_backend"] = d.get("_pipeline_backend", "activity_pipeline")
                candidate["_pipeline_model"] = d.get("_pipeline_model", d.get("_pipeline_backend", "activity_pipeline"))
                candidate["_pipeline_latency_ms"] = d.get("_pipeline_latency_ms", 0)
                provenance_mode = "cfg_restored"
            elif existing_provenance.get("prompt_version", "").startswith("activity_pipeline_cfg"):
                provenance_mode = "ai_failed_cfg_fallback"
            elif any(
                isinstance(patch, dict) and patch.get("runnable") == runnable_name
                for patch in patches or []
            ):
                provenance_mode = "reviewer_patched"
            else:
                provenance_mode = "ai_enriched"

            d = candidate
            ActivityPipeline._normalize_activity_semantics(d)
            ActivityPipeline._repair_decision_branches(d, runnable_name)
            ActivityPipeline._ensure_helper_subdiagrams(
                d,
                d.get("owner_swc", ""),
                runnable_name,
                list(d.get("source_requirements") or []),
            )
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

            # Use AI name only when it is comparably specific AND looks like
            # C syntax. Never let a vague English phrase from the AI overwrite
            # a precise scaffold-generated name (Rte_/Dem_/C-assignment/C-expr).
            ai_name = (ai_node.get("name") or "").strip()
            scaffold_name = str(node.get("name", ""))
            is_rte_scaffold = scaffold_name.startswith(("Rte_", "Dem_"))
            is_rte_ai = ai_name.startswith(("Rte_", "Dem_"))
            # AI name "looks like C" if it starts with an AUTOSAR service prefix
            # or contains an assignment / comparison / logical operator.
            ai_looks_c = bool(
                is_rte_ai
                or ai_name.startswith(("Sch_", "Det_", "WdgM_", "NvM_", "BswM_"))
                or re.search(r"[A-Za-z_]\w*\s*(?:=|>|<|==|!=|>=|<=|&&|\|\|)", ai_name)
            )
            if ntype not in {"initial", "final", "merge"} and ai_name:
                if is_rte_scaffold and not is_rte_ai:
                    # Keep the precise Rte_/Dem_ scaffold name — AI shortened it
                    pass
                elif len(ai_name) >= int(len(scaffold_name) * 0.8) and ai_looks_c:
                    node["name"] = ai_name
                # else: keep scaffold name — AI version is too short or too vague

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
        real_decision_ids = {
            n.get("id") for n in node_dicts
            if (n.get("node_type") or "").lower() == "decision"
        }
        has_merge = any(
            (n.get("node_type") or "").lower() == "merge"
            for n in node_dicts
        )
        if len(real_decision_ids) > 1 and not has_merge:
            return True
        # Multiple independent decisions can be valid without an explicit merge.
        # The real topology breakage is a decision with too few outgoing edges,
        # which is checked above per node.

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
        decision_warnings = [
            warning for warning in lint.warnings
            if "Decision node" in warning
            and "has only" in warning
            and "outgoing edge" in warning
            and any(f"'{did}'" in warning for did in real_decision_ids)
        ]
        return bool(decision_warnings)
