---
name: autosar-activity
description: >
  How to author an AUTOSAR activity / Code-Flow diagram as JSON for the MUD_MUT pipeline.
  Use when designing a runnable's control flow (RTE reads/writes, decisions, calls) as an
  activity diagram. Triggers on: activity diagram, flowchart, code-flow, runnable design,
  Rte_Read, Rte_Write, decision node, SWC flow.
---

# AUTOSAR Activity Diagram JSON — authoring rules

You write an **activity diagram as one JSON object** describing a single runnable's control
flow. Output either a bare diagram object or a `{"diagrams": [ ... ]}` wrapper.

## Required shape

```json
{
  "diagram_type": "activity",
  "name": "RE_EstimateSOC_Flow",
  "owner_swc": "SWC_BatteryManagement",
  "owner_runnable": "RE_EstimateSOC",
  "source_requirements": ["REQ-BMS-002"],
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

## Node rules
- `id` — `N_01`, `N_02`, ... (two-digit, zero-padded, no spaces or special chars).
- `node_type` — one of: `initial`, `final`, `action`, `call`, `function_call`, `decision`,
  `fork`, `join`, `merge`, `exception`.
- `name` — short label.
  - `call` nodes use a C signature, e.g. `Rte_Read_RP_SOCVoltage_Val(&l_f32Volt)`.
  - `decision` nodes use a C boolean expression, e.g. `l_f32Volt > 1.5f` (never English prose).
- `call` nodes should also set `rte_call` (`Rte_Read` / `Rte_Write` / `Rte_Call`), `port`
  (prefix `RP_` or `PP_`), and `element`.
- Add `trace_reqs` (list of requirement IDs) to every node that implements a requirement.

## Edge rules
- `id` — `E_01`, `E_02`, ...
- `source` / `target` — existing node IDs.
- Every `decision` must have **≥ 2 outgoing edges**, each with a C-expression `guard`
  (e.g. `[l_f32Volt > 1.5f]`) or a generic `[else]` / `[true]` / `[false]`.

## Mandatory (validation fails without these)
1. Exactly ONE `initial` node and at least ONE `final` node.
2. Every edge references existing node IDs; every non-initial node is reachable from the initial node.
3. Every `decision` has ≥ 2 outgoing edges with guards.
4. Node IDs use the `N_XX` format.
5. `call` node names start with a BSW prefix (`Rte_`, `Dem_`, `NvM_`, `Sch_`, ...).
6. Decision names and edge guards are C expressions, not English prose.

## Minimal valid example

```json
{
  "diagrams": [
    {
      "diagram_type": "activity",
      "name": "RE_EstimateSOC_Flow",
      "owner_swc": "SWC_BatteryManagement",
      "owner_runnable": "RE_EstimateSOC",
      "source_requirements": ["REQ-BMS-002"],
      "nodes": [
        {"id": "N_01", "name": "Start", "node_type": "initial"},
        {"id": "N_02", "name": "Rte_Read_RP_SOCVoltage_Val(&l_f32Volt)", "node_type": "call",
         "rte_call": "Rte_Read", "port": "RP_SOCVoltage", "element": "Val", "trace_reqs": ["REQ-BMS-002"]},
        {"id": "N_03", "name": "l_f32Volt > 1.5f", "node_type": "decision"},
        {"id": "N_04", "name": "l_f32SOC = EKF_Predict()", "node_type": "action", "trace_reqs": ["REQ-BMS-002"]},
        {"id": "N_05", "name": "Rte_Write_PP_SOCPercent_Val(l_f32SOC)", "node_type": "call",
         "rte_call": "Rte_Write", "port": "PP_SOCPercent", "element": "Val", "trace_reqs": ["REQ-BMS-002"]},
        {"id": "N_06", "name": "End", "node_type": "final"}
      ],
      "edges": [
        {"id": "E_01", "source": "N_01", "target": "N_02"},
        {"id": "E_02", "source": "N_02", "target": "N_03"},
        {"id": "E_03", "source": "N_03", "target": "N_04", "guard": "[l_f32Volt > 1.5f]"},
        {"id": "E_04", "source": "N_03", "target": "N_05", "guard": "[else]"},
        {"id": "E_05", "source": "N_04", "target": "N_05"},
        {"id": "E_06", "source": "N_05", "target": "N_06"}
      ]
    }
  ]
}
```

## Deeper reference
For full AUTOSAR MUD rules (design patterns, naming cheat-sheet, ASIL checklist, RTE API
reference), read `inputs/skills/MUD_SKILL_CORE.md` and
`inputs/guidelines/MUD_SKILL_APPENDIX.md`. The rules above are the condensed subset
that local 7B models most often get wrong.
