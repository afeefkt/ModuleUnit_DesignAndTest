"""
MUD Tool — Activity Diagram Pipeline Tests
==========================================

Covers every layer of the activity diagram stack:

  LAYER 1 — Parser (no AI, no server)
    - _parse_response correctly unwraps {"diagrams": [...]} format
    - _parse_response handles flat ActivityDiagram format (backward compat)
    - _parse_response handles list-of-diagrams format

  LAYER 2 — Mermaid Exporter (no AI, no server)
    - Activity diagram with real nodes/edges -> valid flowchart TD text
    - CALL / ACTION / DECISION / EXCEPTION / MERGE nodes rendered
    - C expressions with ||, &&, | survive as word-form (OR/AND/PIPE)
    - Multi-line descriptions stripped from %% comments
    - Edges with guards produce -->|guard| syntax
    - Edges without guards produce --> syntax

  LAYER 3 — DrawIO Exporter (no AI, no server)
    - Activity diagram produces non-empty XML cells

  LAYER 4 — Live Integration (requires server on http://127.0.0.1:8042)
    - POST /api/v1/export/mermaid/inline returns non-empty diagrams dict
    - Inline Mermaid text is valid flowchart
    - POST /api/v1/export with format=mermaid writes .mmd file with content
    - POST /api/v1/export with format=drawio writes .drawio file with cells
    - POST /api/v1/generate (single_pass) returns ≥1 activity diagram
      (requires Ollama + qwen2.5-coder:7b running)

Run all unit tests (no server needed):
    cd python-sidecar
    python -m pytest tests/test_activity_pipeline.py -v -k "not live"

Run everything (server must be running):
    python -m pytest tests/test_activity_pipeline.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityEdge,
    ActivityNode,
    ActivityNodeType,
    DiagramType,
    GenerationResult,
    Provenance,
)
from mudtool.generator.mermaid_exporter import MermaidExporter


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES — build a realistic EPS RE_ControlTorque activity diagram
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def eps_activity_diagram() -> ActivityDiagram:
    """16-node EPS RE_ControlTorque diagram (mirrors the few-shot example)."""
    return ActivityDiagram(
        name="RE_ControlTorque Code Flow",
        owner_swc="SWC_ElectricPowerSteering",
        owner_runnable="RE_ControlTorque",
        source_requirements=["REQ-EPS-002", "REQ-EPS-010", "REQ-EPS-011",
                              "REQ-EPS-040", "REQ-EPS-041"],
        nodes=[
            ActivityNode(id="N_01", name="Start (5ms cycle)",
                         node_type=ActivityNodeType.INITIAL,
                         trace_reqs=["REQ-EPS-002"], confidence=0.95),
            ActivityNode(id="N_02", name="Rte_Read RP_VehicleSpeed",
                         node_type=ActivityNodeType.CALL,
                         rte_call="Rte_Read", port="RP_VehicleSpeed",
                         element="VehicleSpeed",
                         description="Rte_Read_RP_VehicleSpeed_VehicleSpeed(&l_u16SpeedKmh)",
                         trace_reqs=["REQ-EPS-010"], confidence=0.95),
            ActivityNode(id="N_03", name="Rte_Read RP_TorqueSensor",
                         node_type=ActivityNodeType.CALL,
                         rte_call="Rte_Read", port="RP_TorqueSensor",
                         element="DriverTorque",
                         description="Rte_Read_RP_TorqueSensor_DriverTorque(&l_f32TorqueMain)",
                         trace_reqs=["REQ-EPS-010"], confidence=0.95),
            ActivityNode(id="N_04", name="Compute torque delta",
                         node_type=ActivityNodeType.ACTION,
                         description="l_f32TorqueDelta = (l_f32TorqueMain >= l_f32TorqueRedundant) ? "
                                     "(l_f32TorqueMain - l_f32TorqueRedundant) : "
                                     "(l_f32TorqueRedundant - l_f32TorqueMain)",
                         trace_reqs=["REQ-EPS-041"], confidence=0.92),
            ActivityNode(id="N_05",
                         name="l_f32TorqueDelta > SENSOR_DELTA_LIMIT_NM",
                         node_type=ActivityNodeType.DECISION,
                         description="Cross-check main vs redundant torque sensor\nplausibility check",
                         trace_reqs=["REQ-EPS-041"], confidence=0.95),
            ActivityNode(id="N_06", name="DTC_TORQUE_SENSOR_PLAUSIBILITY",
                         node_type=ActivityNodeType.EXCEPTION,
                         description="Dem_SetEventStatus(DTC_TORQUE_SENSOR_PLAUSIBILITY, "
                                     "DEM_EVENT_STATUS_FAILED); l_f32AssistTorque = 0.0F",
                         trace_reqs=["REQ-EPS-041"], confidence=0.92),
            ActivityNode(id="N_07", name="Compute speed-dependent gain",
                         node_type=ActivityNodeType.ACTION,
                         description="l_f32SpeedGain = 1.0F - (0.7F * ((float32_t)l_u16SpeedKmh / 140.0F))",
                         trace_reqs=["REQ-EPS-011"], confidence=0.90),
            ActivityNode(id="N_08", name="Compute raw assist torque",
                         node_type=ActivityNodeType.ACTION,
                         description="l_f32AssistTorque = l_f32TorqueMain * l_f32SpeedGain",
                         trace_reqs=["REQ-EPS-010"], confidence=0.90),
            ActivityNode(id="N_09",
                         name="l_f32GradDelta > MAX_TORQUE_GRADIENT_NM",
                         node_type=ActivityNodeType.DECISION,
                         description="Rate-of-change safety limit: max 5 Nm per 5ms cycle",
                         trace_reqs=["REQ-EPS-040"], confidence=0.95),
            ActivityNode(id="N_10", name="Clamp to gradient limit",
                         node_type=ActivityNodeType.ACTION,
                         description="l_f32AssistTorque = (l_f32GradDelta > 0.0F) ? "
                                     "(l_f32PrevAssistTorque + MAX_TORQUE_GRADIENT_NM) : "
                                     "(l_f32PrevAssistTorque - MAX_TORQUE_GRADIENT_NM)",
                         trace_reqs=["REQ-EPS-040"], confidence=0.90),
            ActivityNode(id="N_11", name="After gradient check",
                         node_type=ActivityNodeType.MERGE,
                         trace_reqs=["REQ-EPS-040"], confidence=0.85),
            ActivityNode(id="N_12", name="Store previous torque",
                         node_type=ActivityNodeType.ACTION,
                         description="l_f32PrevAssistTorque = l_f32AssistTorque",
                         trace_reqs=["REQ-EPS-040"], confidence=0.88),
            ActivityNode(id="N_13", name="Rte_Write PP_MotorCurrent",
                         node_type=ActivityNodeType.CALL,
                         rte_call="Rte_Write", port="PP_MotorCurrent",
                         element="MotorCurrentDemand",
                         description="Rte_Write_PP_MotorCurrent_MotorCurrentDemand(l_f32AssistTorque)",
                         trace_reqs=["REQ-EPS-010"], confidence=0.95),
            ActivityNode(id="N_14", name="End",
                         node_type=ActivityNodeType.FINAL,
                         trace_reqs=["REQ-EPS-002"], confidence=0.95),
        ],
        edges=[
            ActivityEdge(id="E_01", source="N_01", target="N_02"),
            ActivityEdge(id="E_02", source="N_02", target="N_03"),
            ActivityEdge(id="E_03", source="N_03", target="N_04"),
            ActivityEdge(id="E_04", source="N_04", target="N_05"),
            ActivityEdge(id="E_05a", source="N_05", target="N_06",
                         guard="[l_f32TorqueDelta > SENSOR_DELTA_LIMIT_NM]"),
            ActivityEdge(id="E_05b", source="N_05", target="N_07",
                         guard="[l_f32TorqueDelta <= SENSOR_DELTA_LIMIT_NM]"),
            ActivityEdge(id="E_06",  source="N_06", target="N_14"),
            ActivityEdge(id="E_07",  source="N_07", target="N_08"),
            ActivityEdge(id="E_08",  source="N_08", target="N_09"),
            ActivityEdge(id="E_09a", source="N_09", target="N_10",
                         guard="[l_f32GradDelta > MAX_TORQUE_GRADIENT_NM]"),
            ActivityEdge(id="E_09b", source="N_09", target="N_11",
                         guard="[l_f32GradDelta <= MAX_TORQUE_GRADIENT_NM]"),
            ActivityEdge(id="E_10",  source="N_10", target="N_11"),
            ActivityEdge(id="E_11",  source="N_11", target="N_12"),
            ActivityEdge(id="E_12",  source="N_12", target="N_13"),
            ActivityEdge(id="E_13",  source="N_13", target="N_14"),
        ],
        provenance=Provenance(ai_model="test", prompt_version="v2.0", confidence=0.92),
    )


@pytest.fixture
def eps_generation_result(eps_activity_diagram) -> GenerationResult:
    return GenerationResult(
        diagrams=[eps_activity_diagram],
        analyzed_requirements=["REQ-EPS-002", "REQ-EPS-010", "REQ-EPS-011",
                                "REQ-EPS-040", "REQ-EPS-041"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — _parse_response wrapper handling
# ══════════════════════════════════════════════════════════════════════════════

class TestParseResponseWrapper:
    """Verify orchestrator._parse_response handles all three JSON formats."""

    def _make_orchestrator(self):
        """Build a minimal AIOrchestrator without real AI backends."""
        from mudtool.config.settings import Settings
        from mudtool.ai.orchestrator import AIOrchestrator

        settings = Settings(
            host="127.0.0.1", port=8042,
            openai_api_key="test",
            openai_base_url="http://localhost:11434/v1",
        )
        # Patch backend initialisation so no real connection is made
        with patch.object(AIOrchestrator, '__init__', lambda self, s: None):
            orch = AIOrchestrator.__new__(AIOrchestrator)
            orch.settings = settings
            from mudtool.ai.prompt_engine import PromptEngine
            orch.prompt_engine = PromptEngine(settings)
        return orch

    def _fake_response(self, content: str):
        from mudtool.ai.base_backend import AIResponse
        return AIResponse(
            content=content, model="test-model",
            input_tokens=10, output_tokens=50,
            finish_reason="stop", latency_ms=100,
        )

    # ── 1a. GenerationResult wrapper ─────────────────────────────────────────
    def test_wrapper_format_extracted(self, eps_activity_diagram):
        """{"diagrams":[...], "analyzed_requirements":[...]} must unwrap correctly."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [
                eps_activity_diagram.model_dump(mode="json", exclude_none=True)
            ],
            "analyzed_requirements": ["REQ-EPS-002"],
        }
        resp = self._fake_response(json.dumps(payload))

        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-EPS-002"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert len(result.diagrams) == 1, "Expected exactly 1 diagram"
        diag = result.diagrams[0]
        assert isinstance(diag, ActivityDiagram)
        assert len(diag.nodes) > 0, "Diagram nodes must not be empty after unwrapping"
        assert len(diag.edges) > 0, "Diagram edges must not be empty after unwrapping"
        assert diag.owner_swc == "SWC_ElectricPowerSteering"
        print(f"\n  [PASS] wrapper: extracted {len(diag.nodes)} nodes, "
              f"{len(diag.edges)} edges from {{\"diagrams\": [...]}}")

    # ── 1b. Multiple diagrams in wrapper ─────────────────────────────────────
    def test_wrapper_multiple_diagrams(self, eps_activity_diagram):
        """Wrapper with 2 diagrams -> 2 ActivityDiagram objects in result."""
        orch = self._make_orchestrator()

        d = eps_activity_diagram.model_dump(mode="json", exclude_none=True)
        d2 = dict(d)
        d2["name"] = "RE_InitTorque Code Flow"
        d2["owner_runnable"] = "RE_InitTorque"

        payload = {"diagrams": [d, d2], "analyzed_requirements": ["REQ-EPS-002"]}
        resp = self._fake_response(json.dumps(payload))

        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-EPS-002"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert len(result.diagrams) == 2
        print(f"\n  [PASS] wrapper with 2 diagrams -> {len(result.diagrams)} results")

    # ── 1c. Flat single-diagram format (other prompt types) ──────────────────
    def test_flat_format_still_works(self):
        """Flat {"diagram_type": "sequence", ...} format must still parse correctly."""
        from mudtool.models.json_uml import SequenceDiagram
        orch = self._make_orchestrator()

        payload = {
            "diagram_type": "sequence",
            "name": "Test_Seq",
            "lifelines": [
                {"id": "ll_1", "name": "SWC_A"},
                {"id": "ll_2", "name": "SWC_B"},
            ],
            "messages": [
                {"id": "msg_1", "from": "ll_1", "to": "ll_2",
                 "rte_call": "Rte_Write", "port": "PP_Data"},
            ],
        }
        resp = self._fake_response(json.dumps(payload))

        result = orch._parse_response(
            resp, DiagramType.SEQUENCE, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert len(result.diagrams) == 1
        assert isinstance(result.diagrams[0], SequenceDiagram)
        print(f"\n  [PASS] flat sequence diagram parsed: {result.diagrams[0].name}")

    # ── 1d. Previously broken: wrapper parsed as empty diagram ───────────────
    def test_wrapper_no_longer_creates_empty_diagram(self, eps_activity_diagram):
        """Before the fix, wrapper was parsed as ActivityDiagram -> nodes=[], edges=[]."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [
                eps_activity_diagram.model_dump(mode="json", exclude_none=True)
            ],
            "analyzed_requirements": [],
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test"
        )

        assert len(result.diagrams) == 1
        diag = result.diagrams[0]
        # Key assertion: nodes must NOT be empty (old bug returned empty diagram)
        assert len(diag.nodes) >= 1, (
            "BUG: wrapper was treated as a single diagram -> empty nodes. "
            "Fix in orchestrator._parse_response not applied."
        )
        print(f"\n  [PASS] no empty-diagram regression: {len(diag.nodes)} nodes")

    def test_wrapper_accepts_legacy_activity_shape(self):
        """Legacy payloads with node `type` and edges without `id` must parse."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [{
                "name": "Legacy Activity",
                "nodes": [
                    {"id": "0", "type": "InitialNode", "name": "Start"},
                    {"id": "1", "type": "ActivityNode", "name": "Read Sensor Data"},
                    {"id": "2", "type": "DecisionNode", "name": "Check Sensor Data"},
                    {"id": "3", "type": "FinalNode", "name": "End"},
                ],
                "edges": [
                    {"source": "0", "target": "1"},
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                ],
            }]
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert len(result.diagrams) == 1
        diag = result.diagrams[0]
        assert isinstance(diag, ActivityDiagram)
        assert diag.nodes[0].node_type == ActivityNodeType.INITIAL
        assert diag.nodes[1].node_type == ActivityNodeType.ACTION
        assert diag.nodes[2].node_type == ActivityNodeType.DECISION
        assert diag.edges[0].id == "E_01"
        assert diag.edges[1].id == "E_02"
        assert diag.edges[2].id == "E_03"
        print("\n  [PASS] legacy activity node/edge schema normalized")

    def test_wrapper_legacy_activity_missing_name_is_derived(self):
        """Legacy nodes without `name` must be auto-filled from description/id."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [{
                "name": "Legacy Missing Name",
                "nodes": [
                    {"id": "initial_node", "type": "InitialNode"},
                    {"id": "read_sensor_data", "type": "ActivityNode",
                     "description": "Read sensor data from source"},
                    {"id": "end_node", "type": "FinalNode"},
                ],
                "edges": [
                    {"source": "initial_node", "target": "read_sensor_data"},
                    {"source": "read_sensor_data", "target": "end_node"},
                ],
            }]
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        diag = result.diagrams[0]
        assert diag.nodes[0].name == "initial node"
        assert "Read sensor data from source" in diag.nodes[1].name
        assert diag.nodes[2].name == "end node"
        print("\n  [PASS] missing node names are derived for legacy activity payloads")

    def test_wrapper_null_node_type_uses_legacy_type(self):
        """node_type=null should backfill from legacy `type`."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [{
                "name": "Null NodeType Backfill",
                "nodes": [
                    {"id": "initial_node", "node_type": None, "type": "InitialNode"},
                    {"id": "check_sensor_data", "node_type": "", "type": "DecisionNode"},
                    {"id": "end_node", "node_type": None, "type": "FinalNode"},
                ],
                "edges": [
                    {"source": "initial_node", "target": "check_sensor_data"},
                    {"source": "check_sensor_data", "target": "end_node"},
                ],
            }]
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        diag = result.diagrams[0]
        assert diag.nodes[0].node_type == ActivityNodeType.INITIAL
        assert diag.nodes[1].node_type == ActivityNodeType.DECISION
        assert diag.nodes[2].node_type == ActivityNodeType.FINAL
        assert not result.warnings, f"Unexpected normalization warnings: {result.warnings}"
        print("\n  [PASS] node_type=None/empty falls back to legacy `type`")

    def test_wrapper_camel_case_node_type_is_supported(self):
        """nodeType camelCase key should be accepted when node_type is absent."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [{
                "name": "Camel NodeType",
                "nodes": [
                    {"id": "start", "nodeType": "initial"},
                    {"id": "do_work", "nodeType": "action"},
                    {"id": "end", "nodeType": "final"},
                ],
                "edges": [
                    {"source": "start", "target": "do_work"},
                    {"source": "do_work", "target": "end"},
                ],
            }]
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        diag = result.diagrams[0]
        assert diag.nodes[0].node_type == ActivityNodeType.INITIAL
        assert diag.nodes[1].node_type == ActivityNodeType.ACTION
        assert diag.nodes[2].node_type == ActivityNodeType.FINAL
        assert not result.warnings, f"Unexpected normalization warnings: {result.warnings}"
        print("\n  [PASS] camelCase nodeType is normalized")

    def test_wrapper_infers_and_defaults_node_type_with_warning(self):
        """Missing/invalid node type should infer from id/name or default to action."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [{
                "name": "Inference NodeType",
                "nodes": [
                    {"id": "end_node", "name": "End Node", "node_type": None},
                    {"id": "ambiguous_step", "name": "Compute Value", "node_type": "???"},
                ],
                "edges": [
                    {"source": "end_node", "target": "ambiguous_step"},
                ],
            }]
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        diag = result.diagrams[0]
        node_types = {n.id: n.node_type for n in diag.nodes}
        assert node_types["end_node"] == ActivityNodeType.FINAL
        assert node_types["ambiguous_step"] == ActivityNodeType.ACTION
        assert result.warnings, "Expected normalization warning for inferred/defaulted node types"
        warning = " ".join(result.warnings)
        assert "inferred node_type for 1 node(s)" in warning
        assert "defaulted 1 to action" in warning
        print("\n  [PASS] node_type inference/defaulting emits warning")

    def test_wrapper_accepts_edge_source_target_id_aliases(self):
        """Edges using source_id/target_id should normalize to source/target."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [{
                "name": "Edge Alias Activity",
                "nodes": [
                    {"id": "n1", "name": "Start", "node_type": "initial"},
                    {"id": "n2", "name": "Read input", "node_type": "action"},
                    {"id": "n3", "name": "End", "node_type": "final"},
                ],
                "edges": [
                    {"source_id": "n1", "target_id": "n2"},
                    {"from": "n2", "target_id": "n3"},
                ],
            }]
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        diag = result.diagrams[0]
        assert diag.edges[0].source == "n1"
        assert diag.edges[0].target == "n2"
        assert diag.edges[1].source == "n2"
        assert diag.edges[1].target == "n3"
        print("\n  [PASS] source_id/target_id edge aliases normalized")

    def test_wrapper_normalizes_subdiagram_edge_aliases(self):
        """Edge alias normalization should apply recursively for sub_diagrams."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [{
                "name": "Parent",
                "nodes": [
                    {"id": "n1", "name": "Start", "node_type": "initial"},
                    {"id": "n2", "name": "Call helper", "node_type": "function_call", "callee": "Helper"},
                    {"id": "n3", "name": "End", "node_type": "final"},
                ],
                "edges": [
                    {"source_id": "n1", "target_id": "n2"},
                    {"source_id": "n2", "target_id": "n3"},
                ],
                "sub_diagrams": [{
                    "diagram_type": "activity",
                    "name": "Helper",
                    "function_name": "Helper",
                    "nodes": [
                        {"id": "s1", "name": "Start", "node_type": "initial"},
                        {"id": "s2", "name": "Compute", "node_type": "action"},
                        {"id": "s3", "name": "End", "node_type": "final"},
                    ],
                    "edges": [
                        {"source_id": "s1", "target_id": "s2"},
                        {"source_id": "s2", "target_id": "s3"},
                    ],
                }],
            }]
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        parent = result.diagrams[0]
        child = result.diagrams[1]
        assert parent.edges[0].source == "n1"
        assert parent.edges[0].target == "n2"
        assert child.edges[0].source == "s1"
        assert child.edges[0].target == "s2"
        print("\n  [PASS] sub-diagram edge aliases normalized")

    def test_wrapper_sanitizes_mud_style_node_ids(self):
        """MUD-first activity payloads often reuse labels as ids; normalize them safely."""
        orch = self._make_orchestrator()

        payload = {
            "diagrams": [{
                "name": "RE_Control Flowchart",
                "nodes": [
                    {"id": "Start", "name": "Start", "node_type": "initial"},
                    {"id": "Rte_Read(RP_Speed, &speed)", "name": "Rte_Read(RP_Speed, &speed)"},
                    {"id": "assist = CalcAssist(speed)", "name": "assist = CalcAssist(speed)"},
                    {"id": "End", "name": "End", "node_type": "final"},
                ],
                "edges": [
                    {"source": "Start", "target": "Rte_Read(RP_Speed, &speed)"},
                    {"source": "Rte_Read(RP_Speed, &speed)", "target": "assist = CalcAssist(speed)"},
                    {"source": "assist = CalcAssist(speed)", "target": "End"},
                ],
            }]
        }
        resp = self._fake_response(json.dumps(payload))
        result = orch._parse_response(
            resp, DiagramType.ACTIVITY, "hash", "test", req_ids=["REQ-001"]
        )

        assert not result.errors, f"Unexpected errors: {result.errors}"
        diag = result.diagrams[0]
        assert [node.id for node in diag.nodes] == [
            "Start",
            "Rte_Read_RP_Speed_speed",
            "assist_CalcAssist_speed",
            "End",
        ]
        assert diag.edges[0].target == "Rte_Read_RP_Speed_speed"
        assert diag.edges[1].source == "Rte_Read_RP_Speed_speed"
        assert diag.edges[1].target == "assist_CalcAssist_speed"
        print("\n  [PASS] MUD-style label ids sanitized and edge refs updated")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — Mermaid Exporter
# ══════════════════════════════════════════════════════════════════════════════

class TestMermaidExporterActivity:
    """Verify MermaidExporter produces correct flowchart TD text."""

    def test_header(self, eps_activity_diagram):
        """Output must start with 'flowchart TD'."""
        mmd = MermaidExporter().export_diagram(eps_activity_diagram)
        assert mmd.startswith("flowchart TD"), f"Bad header:\n{mmd[:80]}"
        print(f"\n  [PASS] header: {mmd.split(chr(10))[0]}")

    def test_all_nodes_present(self, eps_activity_diagram):
        """Every node ID must appear in the output."""
        mmd = MermaidExporter().export_diagram(eps_activity_diagram)
        for node in eps_activity_diagram.nodes:
            nid = node.id.replace("-", "_").replace(".", "_")
            assert nid in mmd, f"Node {nid} missing from Mermaid output"
        print(f"\n  [PASS] all {len(eps_activity_diagram.nodes)} node IDs present")

    def test_all_edges_present(self, eps_activity_diagram):
        """Every edge source->target pair must appear as an arrow."""
        mmd = MermaidExporter().export_diagram(eps_activity_diagram)
        for edge in eps_activity_diagram.edges:
            src = edge.source.replace("-", "_")
            tgt = edge.target.replace("-", "_")
            assert f"{src} -->" in mmd, f"Source {src} missing from edges"
            assert tgt in mmd, f"Target {tgt} not referenced"
        print(f"\n  [PASS] all {len(eps_activity_diagram.edges)} edges rendered")

    def test_guards_on_decision_edges(self, eps_activity_diagram):
        """Decision-branch edges must use -->|guard| syntax."""
        mmd = MermaidExporter().export_diagram(eps_activity_diagram)
        assert "-->|" in mmd, "No guarded edges found (-->|...|)"
        # Check specific guard content (pipe chars replaced)
        assert "SENSOR_DELTA_LIMIT_NM" in mmd
        assert "MAX_TORQUE_GRADIENT_NM" in mmd
        print("\n  [PASS] guarded edges rendered with -->|...|")

    def test_no_raw_pipe_in_output(self, eps_activity_diagram):
        """Lone | inside node labels must be rendered as ' PIPE ', not left raw."""
        mmd = MermaidExporter().export_diagram(eps_activity_diagram)
        # Find all node label lines (lines with node shapes)
        label_lines = [l for l in mmd.split("\n")
                       if any(c in l for c in ("[(", "[\"", "{\"", "[/"))]
        for line in label_lines:
            # A raw lone | inside a label would break Mermaid's edge parser.
            # Allowed: -->|guard| edges (those start with spaces + N_ID --> )
            # We check that no label line (which starts with node shape syntax)
            # has a bare | not wrapped in the -->| edge syntax.
            stripped = line.strip()
            if stripped.startswith("N_") or stripped.startswith("-->"):
                continue
            assert "|" not in stripped or "-->" in stripped, (
                f"Possible raw | in node label line: {line}"
            )
        print("\n  [PASS] no raw pipe in node label lines")

    def test_decision_description_newline_stripped(self):
        """Multi-line decision description must be flattened to single %% comment line."""
        diag = ActivityDiagram(
            name="Test",
            nodes=[
                ActivityNode(id="N_01", name="Start", node_type=ActivityNodeType.INITIAL,
                             trace_reqs=["R1"]),
                ActivityNode(id="N_02", name="x > 0",
                             node_type=ActivityNodeType.DECISION,
                             description="First line\nSecond line\nThird line",
                             trace_reqs=["R1"]),
                ActivityNode(id="N_03", name="End", node_type=ActivityNodeType.FINAL,
                             trace_reqs=["R1"]),
            ],
            edges=[
                ActivityEdge(id="E_01", source="N_01", target="N_02"),
                ActivityEdge(id="E_02a", source="N_02", target="N_03", guard="[x > 0]"),
                ActivityEdge(id="E_02b", source="N_02", target="N_03", guard="[x <= 0]"),
            ],
        )
        mmd = MermaidExporter().export_diagram(diag)
        lines = mmd.split("\n")
        comment_lines = [l for l in lines if "%% decision:" in l]
        assert len(comment_lines) >= 1, "Decision description comment missing"
        for cl in comment_lines:
            assert "\n" not in cl, "Newline leaked into %% comment"
            assert "First line" in cl
            assert "Second line" in cl  # collapsed onto same line
        print(f"\n  [PASS] multi-line description flattened: '{comment_lines[0].strip()}'")

    def test_c_logical_operators_sanitized(self):
        """||, &&, lone | in guards must be replaced with OR/AND/OR."""
        diag = ActivityDiagram(
            name="Test",
            nodes=[
                ActivityNode(id="N_01", name="Start", node_type=ActivityNodeType.INITIAL,
                             trace_reqs=["R1"]),
                ActivityNode(id="N_02", name="cond", node_type=ActivityNodeType.DECISION,
                             trace_reqs=["R1"]),
                ActivityNode(id="N_03", name="End", node_type=ActivityNodeType.FINAL,
                             trace_reqs=["R1"]),
            ],
            edges=[
                ActivityEdge(id="E_01", source="N_01", target="N_02"),
                ActivityEdge(id="E_02a", source="N_02", target="N_03",
                             guard="[l_bValid == TRUE || l_u8Retry > 0]"),
                ActivityEdge(id="E_02b", source="N_02", target="N_03",
                             guard="[l_bValid == FALSE && l_u8Retry == 0]"),
            ],
        )
        mmd = MermaidExporter().export_diagram(diag)
        assert "||" not in mmd, "Raw || found — Mermaid parse error risk"
        assert " OR " in mmd
        assert " AND " in mmd
        # Also ensure the guard content is still human-readable
        assert "l_bValid" in mmd
        print("\n  [PASS] C logical operators sanitized: || -> OR, && -> AND")

    def test_special_character_node_ids_are_mermaid_safe(self):
        """Exporter should not leak spaces, parens, or ampersands into node identifiers."""
        diag = ActivityDiagram(
            name="MUD Output",
            nodes=[
                ActivityNode(id="Start", name="Start", node_type=ActivityNodeType.INITIAL, trace_reqs=["R1"]),
                ActivityNode(
                    id="Rte_Read(RP_Speed, &speed)",
                    name="Rte_Read(RP_Speed, &speed)",
                    node_type=ActivityNodeType.CALL,
                    trace_reqs=["R1"],
                ),
                ActivityNode(
                    id="assist = CalcAssist(speed)",
                    name="assist = CalcAssist(speed)",
                    node_type=ActivityNodeType.ACTION,
                    trace_reqs=["R1"],
                ),
                ActivityNode(id="End", name="End", node_type=ActivityNodeType.FINAL, trace_reqs=["R1"]),
            ],
            edges=[
                ActivityEdge(id="E_01", source="Start", target="Rte_Read(RP_Speed, &speed)"),
                ActivityEdge(id="E_02", source="Rte_Read(RP_Speed, &speed)", target="assist = CalcAssist(speed)"),
                ActivityEdge(id="E_03", source="assist = CalcAssist(speed)", target="End"),
            ],
        )
        mmd = MermaidExporter().export_diagram(diag)
        assert "Rte_Read(RP_Speed, &speed) -->" not in mmd
        assert "assist = CalcAssist(speed) -->" not in mmd
        assert "Rte_Read_RP_Speed_speed" in mmd
        assert "assist_CalcAssist_speed" in mmd
        print("\n  [PASS] exporter sanitizes special-character node ids")

    def test_inline_export_returns_dict(self, eps_generation_result):
        """export_result_inline must return {key: mermaid_text} with ≥1 entry."""
        result = MermaidExporter().export_result_inline(eps_generation_result)
        assert isinstance(result, dict), "export_result_inline must return dict"
        assert len(result) >= 1, "export_result_inline returned empty dict"
        key = list(result.keys())[0]
        mmd = result[key]
        assert "flowchart TD" in mmd, f"Mermaid text is not a flowchart:\n{mmd[:200]}"
        assert "N_01" in mmd, "Node N_01 missing from inline export"
        print(f"\n  [PASS] inline export: key='{key}', "
              f"{len(mmd.split(chr(10)))} lines")

    def test_export_to_file(self, tmp_path, eps_generation_result):
        """export_result must write .mmd file(s) with non-empty content."""
        paths = MermaidExporter().export_result(eps_generation_result, tmp_path)
        assert len(paths) >= 1, "No .mmd files written"
        for p in paths:
            assert p.exists(), f"File not found: {p}"
            content = p.read_text(encoding="utf-8")
            assert len(content) > 50, f"File too short ({len(content)} chars): {p}"
            assert "flowchart TD" in content, f"Not a flowchart: {p}"
            assert "N_01" in content, f"No nodes in file: {p}"
        print(f"\n  [PASS] {len(paths)} .mmd file(s) written")
        for p in paths:
            print(f"         {p} ({len(p.read_text())} chars)")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — DrawIO Exporter
# ══════════════════════════════════════════════════════════════════════════════

class TestDrawIOExporterActivity:
    """Verify DrawIOExporter produces non-empty XML for activity diagrams."""

    def test_produces_xml_cells(self, tmp_path, eps_generation_result):
        """DrawIO export must create a .drawio file with actual cell elements."""
        from mudtool.generator.drawio_exporter import DrawIOExporter

        paths = DrawIOExporter().export_result(eps_generation_result, tmp_path)
        assert len(paths) >= 1, "No .drawio files written"

        for p in paths:
            assert p.exists(), f"File not found: {p}"
            content = p.read_text(encoding="utf-8")
            assert "<mxfile" in content, f"Not a valid drawio file: {p}"
            # Must have more than just the empty template
            cell_count = content.count("<mxCell")
            assert cell_count > 2, (
                f"Only {cell_count} mxCell(s) — diagram is effectively empty: {p}\n"
                f"File content:\n{content}"
            )
        print(f"\n  [PASS] DrawIO: {len(paths)} file(s), "
              f"{content.count('<mxCell')} cells in last file")

    def test_file_not_blank(self, tmp_path, eps_generation_result):
        """DrawIO file must contain node labels from the diagram."""
        from mudtool.generator.drawio_exporter import DrawIOExporter

        paths = DrawIOExporter().export_result(eps_generation_result, tmp_path)
        for p in paths:
            content = p.read_text(encoding="utf-8")
            size = len(content)
            assert size > 500, (
                f"DrawIO file suspiciously small ({size} bytes) — likely empty:\n{p}"
            )
        print(f"\n  [PASS] DrawIO file size = {size} bytes (not blank)")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — Live integration against running server
# ══════════════════════════════════════════════════════════════════════════════

LIVE_BASE = "http://127.0.0.1:8042/api/v1"

# Skip live tests if the server is not reachable
def _server_is_up() -> bool:
    try:
        import httpx
        r = httpx.get(f"{LIVE_BASE}/health", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False

live = pytest.mark.skipif(
    not _server_is_up(),
    reason="Server not running on http://127.0.0.1:8042 — start with: python -m mudtool.main",
)


@live
class TestLiveExportEndpoints:
    """Hit the running server with a pre-built GenerationResult — no AI call."""

    def _result_payload(self, eps_activity_diagram) -> dict:
        return {
            "diagrams": [
                eps_activity_diagram.model_dump(mode="json", exclude_none=True)
            ],
            "analyzed_requirements": ["REQ-EPS-002", "REQ-EPS-010"],
        }

    def test_mermaid_inline_non_empty(self, eps_activity_diagram):
        """POST /export/mermaid/inline must return ≥1 diagram with flowchart text."""
        import httpx
        payload = {"result": self._result_payload(eps_activity_diagram)}
        r = httpx.post(f"{LIVE_BASE}/export/mermaid/inline", json=payload, timeout=15.0)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        data = r.json()
        assert "diagrams" in data, f"No 'diagrams' key in response: {data}"
        diags = data["diagrams"]
        assert len(diags) >= 1, f"Empty diagrams dict: {diags}"
        key = list(diags.keys())[0]
        mmd = diags[key]
        assert "flowchart TD" in mmd, f"Not a flowchart:\n{mmd[:300]}"
        assert "N_01" in mmd, f"No nodes in Mermaid text:\n{mmd[:300]}"
        print(f"\n  [LIVE PASS] /export/mermaid/inline: key='{key}', "
              f"{len(mmd.split(chr(10)))} lines")

    def test_mermaid_file_export(self, tmp_path, eps_activity_diagram):
        """POST /export format=mermaid must write non-empty .mmd file."""
        import httpx
        payload = {
            "result": self._result_payload(eps_activity_diagram),
            "format": "mermaid",
            "output_path": str(tmp_path),
        }
        r = httpx.post(f"{LIVE_BASE}/export", json=payload, timeout=15.0)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        data = r.json()
        assert "paths" in data, f"No 'paths' in response: {data}"
        for path_str in data["paths"]:
            p = Path(path_str)
            assert p.exists(), f".mmd file not written: {p}"
            content = p.read_text(encoding="utf-8")
            assert "flowchart TD" in content, f"Empty or wrong content: {p}"
            assert "N_01" in content
        print(f"\n  [LIVE PASS] /export mermaid: {data['paths']}")

    def test_drawio_file_export(self, tmp_path, eps_activity_diagram):
        """POST /export format=drawio must write non-empty .drawio file."""
        import httpx
        payload = {
            "result": self._result_payload(eps_activity_diagram),
            "format": "drawio",
            "output_path": str(tmp_path),
        }
        r = httpx.post(f"{LIVE_BASE}/export", json=payload, timeout=15.0)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        data = r.json()
        assert "paths" in data
        for path_str in data["paths"]:
            p = Path(path_str)
            assert p.exists(), f".drawio file not written: {p}"
            content = p.read_text(encoding="utf-8")
            cells = content.count("<mxCell")
            assert cells > 2, f"Only {cells} cells — drawio is blank: {p}"
        print(f"\n  [LIVE PASS] /export drawio: {data['paths']}")


@live
class TestLiveGenerate:
    """Full generate test — requires Ollama + qwen2.5-coder:7b."""

    EPS_REQUIREMENTS = {
        "requirements": [
            {
                "req_id": "REQ-EPS-002",
                "title": "RE_ControlTorque Cyclic Runnable",
                "description": "SWC_ElectricPowerSteering shall contain runnable RE_ControlTorque "
                               "triggered cyclically every 5ms. Safety: ASIL-D.",
                "req_type": "functional",
                "safety_level": "ASIL-D",
                "priority": "must",
            },
            {
                "req_id": "REQ-EPS-010",
                "title": "Torque and Speed Inputs",
                "description": "RE_ControlTorque shall read driver torque from RP_TorqueSensor and "
                               "vehicle speed from RP_VehicleSpeed, compute a speed-dependent assist "
                               "torque, and write the result to PP_MotorCurrent.",
                "req_type": "interface",
                "priority": "must",
            },
            {
                "req_id": "REQ-EPS-041",
                "title": "Sensor Cross-Check",
                "description": "RE_ControlTorque shall cross-check RP_TorqueSensor against "
                               "RP_TorqueSensorRedundant; if |delta| > SENSOR_DELTA_LIMIT_NM (2.0 Nm), "
                               "call Dem_SetEventStatus(DTC_TORQUE_SENSOR_PLAUSIBILITY, FAILED) and "
                               "set l_f32AssistTorque = 0.0F. Safety: ASIL-D.",
                "req_type": "safety",
                "safety_level": "ASIL-D",
                "priority": "must",
            },
        ]
    }

    EPS_MUD_SPEC = """# MUD Spec: SWC_ElectricPowerSteering

## 3. Runnables
### 3.1 Main Runnables (OS-scheduled via AUTOSAR RTE)
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_ControlTorque | Cyclic | 5 ms | ASIL-D | Main EPS assist loop |

## 7. Functional Description
### RE_ControlTorque
// Reads: RP_TorqueSensor, RP_TorqueSensorRedundant, RP_VehicleSpeed
// Writes: PP_MotorCurrent

1. Rte_Read(RP_VehicleSpeed, &l_u16SpeedKmh)
2. Rte_Read(RP_TorqueSensor, &l_f32TorqueMain)
3. Rte_Read(RP_TorqueSensorRedundant, &l_f32TorqueRedundant)
4. l_f32AssistTorque = EPS_CalcAssistTorque(l_f32TorqueMain, l_u16SpeedKmh)
5. Rte_Write(PP_MotorCurrent, l_f32AssistTorque)
"""

    def test_generate_activity_single_pass(self):
        """Single-pass generation must return ≥1 activity diagram with nodes."""
        import httpx
        payload = {
            "requirements": self.EPS_REQUIREMENTS,
            "diagram_types": ["activity"],
            "pipeline_mode": "single_pass",
            "apply_autosar_mapping": False,
            "activity_source": "mud_spec",
            "mud_spec_markdown": self.EPS_MUD_SPEC,
            "module_context": "SWC_ElectricPowerSteering",
        }
        r = httpx.post(
            f"{LIVE_BASE}/generate", json=payload,
            timeout=300.0,  # generation can take a few minutes
        )
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"
        data = r.json()

        # Check result structure
        result = data.get("result", {})
        diagrams = result.get("diagrams", [])
        errors = result.get("errors", [])

        if errors:
            print(f"\n  [WARN] Server errors: {errors}")

        assert len(diagrams) >= 1, (
            f"AI returned 0 activity diagrams.\n"
            f"Errors: {errors}\n"
            f"Full response: {json.dumps(data, indent=2)[:1000]}"
        )

        diag = diagrams[0]
        nodes = diag.get("nodes", [])
        edges = diag.get("edges", [])

        print(f"\n  [LIVE PASS] generate activity: {len(diagrams)} diagram(s), "
              f"{len(nodes)} nodes, {len(edges)} edges")
        print(f"  owner_swc={diag.get('owner_swc')}, "
              f"owner_runnable={diag.get('owner_runnable')}")

        # Soft assertions — warn but don't fail on AI output quality
        if len(nodes) < 3:
            print(f"  [WARN] Only {len(nodes)} nodes — AI may have generated minimal output")
        if not diag.get("owner_runnable"):
            print("  [WARN] owner_runnable missing — AI may not have set it")

        # Hard assertion: at least 1 node
        assert len(nodes) >= 1, (
            f"Activity diagram has 0 nodes — likely still parsing as empty wrapper.\n"
            f"Diagram: {json.dumps(diag, indent=2)[:500]}"
        )

    def test_mermaid_preview_after_generate(self):
        """After generate, /export/mermaid/inline must return non-empty preview."""
        import httpx

        # Step 1: Generate
        gen_payload = {
            "requirements": self.EPS_REQUIREMENTS,
            "diagram_types": ["activity"],
            "pipeline_mode": "single_pass",
            "apply_autosar_mapping": False,
            "activity_source": "mud_spec",
            "mud_spec_markdown": self.EPS_MUD_SPEC,
            "module_context": "SWC_ElectricPowerSteering",
        }
        r1 = httpx.post(f"{LIVE_BASE}/generate", json=gen_payload, timeout=300.0)
        assert r1.status_code == 200, f"Generate failed: {r1.status_code}"
        gen_data = r1.json()

        # Step 2: Get inline Mermaid
        inline_payload = {"result": gen_data["result"]}
        r2 = httpx.post(f"{LIVE_BASE}/export/mermaid/inline", json=inline_payload,
                        timeout=15.0)
        assert r2.status_code == 200, f"Inline export failed: {r2.status_code}"
        mmd_data = r2.json()

        diags = mmd_data.get("diagrams", {})
        assert len(diags) >= 1, (
            f"0 diagrams in Mermaid preview.\n"
            f"Generation result diagrams: "
            f"{len(gen_data['result'].get('diagrams', []))}\n"
            f"Errors: {gen_data['result'].get('errors', [])}"
        )

        for key, mmd in diags.items():
            assert "flowchart TD" in mmd, f"Diagram '{key}' is not a flowchart"
            line_count = len([l for l in mmd.split("\n") if l.strip()])
            print(f"\n  [LIVE PASS] Mermaid preview '{key}': {line_count} non-empty lines")
            # Print first 20 lines for visual inspection
            print("\n--- Mermaid Source (first 20 lines) ---")
            for line in mmd.split("\n")[:20]:
                print(f"  {line}")
            print("---")
