from __future__ import annotations

import json

import pytest

from mudtool.ai.activity_pipeline_stages import ActivityPipeline
from mudtool.ai.base_backend import AIResponse
from mudtool.ai.mud_activity_context import MudActivityContext, RunnableContext
from mudtool.generator.mermaid_exporter import MermaidExporter
from mudtool.models.json_uml import ActivityDiagram, ActivityEdge, ActivityNode, ActivityNodeType
from mudtool.models.requirements import Priority, Requirement, RequirementStatus, RequirementType


class _FakeBackend:
    def __init__(self, payloads: list[dict | str]):
        self._payloads = list(payloads)
        self.backend_name = "fake"

    async def generate(self, **kwargs):
        payload = self._payloads.pop(0)
        content = payload if isinstance(payload, str) else json.dumps(payload)
        return AIResponse(content=content, model="fake-model", latency_ms=12)


def _make_requirement(req_id: str) -> Requirement:
    return Requirement(
        req_id=req_id,
        title=req_id,
        description=req_id,
        req_type=RequirementType.FUNCTIONAL,
        priority=Priority.MUST,
        status=RequirementStatus.APPROVED,
    )


def test_normalize_activity_semantics_reclassifies_non_rte_service_call():
    diagram = {
        "nodes": [
            {
                "id": "N_01",
                "name": "WdgM_UpdateAliveCounter(WDG_ENTITY_RE_Init)",
                "node_type": "call",
                "rte_call": "WdgM_UpdateAliveCounter",
                "port": "WDG_ENTITY_RE_Init",
            }
        ],
        "edges": [],
    }

    ActivityPipeline._normalize_activity_semantics(diagram)

    node = diagram["nodes"][0]
    assert node["node_type"] == "function_call"
    assert node["callee"] == "WdgM_UpdateAliveCounter"
    assert "rte_call" not in node
    assert "port" not in node


def test_normalize_activity_semantics_drops_local_variable_port_metadata():
    diagram = {
        "nodes": [
            {
                "id": "N_01",
                "name": "Rte_Read_irvTorqueSetpoint(&irvTorqueSetpoint)",
                "node_type": "call",
                "rte_call": "Rte_Read",
                "port": "irvTorqueSetpoint",
            }
        ],
        "edges": [],
    }

    ActivityPipeline._normalize_activity_semantics(diagram)

    node = diagram["nodes"][0]
    assert node["node_type"] == "action"
    assert "rte_call" not in node
    assert "port" not in node


def test_mermaid_activity_decision_edges_use_yes_no_labels():
    diagram = ActivityDiagram(
        name="RE_Decision Code Flow",
        nodes=[
            ActivityNode(id="N_00", name="Start", node_type=ActivityNodeType.INITIAL),
            ActivityNode(id="N_01", name="vehicleSpeed > 10", node_type=ActivityNodeType.DECISION),
            ActivityNode(id="N_02", name="High assist", node_type=ActivityNodeType.ACTION),
            ActivityNode(id="N_03", name="Low assist", node_type=ActivityNodeType.ACTION),
            ActivityNode(id="N_04", name="End", node_type=ActivityNodeType.FINAL),
        ],
        edges=[
            ActivityEdge(source="N_00", target="N_01"),
            ActivityEdge(source="N_01", target="N_02", guard="[vehicleSpeed > 10]"),
            ActivityEdge(source="N_01", target="N_03", guard="[false]"),
            ActivityEdge(source="N_02", target="N_04"),
            ActivityEdge(source="N_03", target="N_04"),
        ],
    )

    mermaid = MermaidExporter().export_diagram(diagram)

    assert mermaid.count("vehicleSpeed > 10") == 1
    assert "N_01 -->|Yes| N_02" in mermaid
    assert "N_01 -->|No| N_03" in mermaid
    assert "-->|vehicleSpeed" not in mermaid


def test_mermaid_activity_three_way_decision_edges_use_yes_case_no_labels():
    diagram = ActivityDiagram(
        name="RE_SwitchLikeDecision Code Flow",
        nodes=[
            ActivityNode(id="N_00", name="Start", node_type=ActivityNodeType.INITIAL),
            ActivityNode(id="N_01", name="torqueState", node_type=ActivityNodeType.DECISION),
            ActivityNode(id="N_02", name="Nominal path", node_type=ActivityNodeType.ACTION),
            ActivityNode(id="N_03", name="Limited path", node_type=ActivityNodeType.ACTION),
            ActivityNode(id="N_04", name="Fallback path", node_type=ActivityNodeType.ACTION),
            ActivityNode(id="N_05", name="End", node_type=ActivityNodeType.FINAL),
        ],
        edges=[
            ActivityEdge(source="N_00", target="N_01"),
            ActivityEdge(source="N_01", target="N_02", guard="[l_f32Torque < NOMINAL_LIMIT]"),
            ActivityEdge(source="N_01", target="N_03", guard="[l_f32Torque < MAX_LIMIT]"),
            ActivityEdge(source="N_01", target="N_04", guard="[default]"),
            ActivityEdge(source="N_02", target="N_05"),
            ActivityEdge(source="N_03", target="N_05"),
            ActivityEdge(source="N_04", target="N_05"),
        ],
    )

    mermaid = MermaidExporter().export_diagram(diagram)

    assert "N_01 -->|Yes| N_02" in mermaid
    assert "N_01 -->|Case 2| N_03" in mermaid
    assert "N_01 -->|No| N_04" in mermaid
    assert "-->|l_f32Torque" not in mermaid
    assert "-->|default|" not in mermaid


@pytest.mark.asyncio
async def test_stage3_runnable_rebuilds_invalid_ai_topology_from_cfg():
    pipeline = ActivityPipeline(
        backend=_FakeBackend(
            [
                {
                    "name": "RE_ControlTorque Code Flow",
                    "owner_swc": "SWC_ElectricPowerSteering",
                    "owner_runnable": "RE_ControlTorque",
                    "nodes": [
                        {"id": "N_00", "name": "Start", "node_type": "initial", "trace_reqs": ["REQ-1"], "description": "start", "confidence": 0.8},
                        {"id": "N_01", "name": "speed > 10", "node_type": "decision", "trace_reqs": ["REQ-1"], "description": "decision", "confidence": 0.8},
                        {"id": "N_02", "name": "End", "node_type": "final", "trace_reqs": ["REQ-1"], "description": "end", "confidence": 0.8},
                    ],
                    "edges": [
                        {"id": "E_01", "source": "N_00", "target": "N_01"},
                        {"id": "E_02", "source": "N_01", "target": "vehicleSpeed", "guard": "[true]"},
                    ],
                    "sub_diagrams": [],
                }
            ]
        ),
        skeleton_backend=_FakeBackend([]),
        reviewer_backend=_FakeBackend([]),
    )
    mud_ctx = MudActivityContext(
        swc_name="SWC_ElectricPowerSteering",
        runnables=[
            RunnableContext(
                name="RE_ControlTorque",
                trigger="5ms",
                asil="ASIL-D",
                functional_description="\n".join(
                    [
                        "1. If vehicleSpeed > 10",
                        "1.1. Rte_Write(PP_AssistLevel, HIGH)",
                        "2. Else",
                        "2.1. Rte_Write(PP_AssistLevel, LOW)",
                        "3. End If",
                    ]
                ),
            )
        ],
        rte_calls=[],
        helper_functions=[],
        raw_markdown="",
    )
    sk_run = {
        "name": "RE_ControlTorque",
        "trigger": "5ms",
        "asil": "ASIL-D",
        "key_steps": ["If vehicleSpeed > 10", "Write assist high", "Else", "Write assist low"],
    }

    result = await pipeline._stage3_runnable(
        sk_run=sk_run,
        mud_activity_context=mud_ctx,
        swc_name="SWC_ElectricPowerSteering",
        requirements=[_make_requirement("REQ-1")],
        activity_label_style="pseudocode",
        temperature=0.1,
    )

    assert result is not None
    node_ids = {node["id"] for node in result["nodes"]}
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in result["edges"])
    decision_ids = [node["id"] for node in result["nodes"] if node["node_type"] == "decision"]
    assert decision_ids
    for did in decision_ids:
        assert sum(1 for edge in result["edges"] if edge["source"] == did) >= 2


def test_stage5_finalise_rebuilds_from_canonical_when_lint_fails():
    canonical = {
        "diagram_type": "activity",
        "name": "RE_Test Code Flow",
        "owner_swc": "SWC_Test",
        "owner_runnable": "RE_Test",
        "source_requirements": ["REQ-1"],
        "nodes": [
            {"id": "N_00", "name": "Start", "node_type": "initial", "trace_reqs": ["REQ-1"], "description": "start", "confidence": 0.9},
            {"id": "N_01", "name": "x > 0", "node_type": "decision", "trace_reqs": ["REQ-1"], "description": "decision", "confidence": 0.9},
            {"id": "N_02", "name": "Then", "node_type": "action", "trace_reqs": ["REQ-1"], "description": "then", "confidence": 0.9},
            {"id": "N_03", "name": "Else", "node_type": "action", "trace_reqs": ["REQ-1"], "description": "else", "confidence": 0.9},
            {"id": "N_04", "name": "Merge", "node_type": "merge", "trace_reqs": ["REQ-1"], "description": "merge", "confidence": 0.9},
            {"id": "N_05", "name": "End", "node_type": "final", "trace_reqs": ["REQ-1"], "description": "end", "confidence": 0.9},
        ],
        "edges": [
            {"id": "E_01", "source": "N_00", "target": "N_01"},
            {"id": "E_02", "source": "N_01", "target": "N_02", "guard": "[true]"},
            {"id": "E_03", "source": "N_01", "target": "N_03", "guard": "[false]"},
            {"id": "E_04", "source": "N_02", "target": "N_04"},
            {"id": "E_05", "source": "N_03", "target": "N_04"},
            {"id": "E_06", "source": "N_04", "target": "N_05"},
        ],
        "sub_diagrams": [],
        "_pipeline_backend": "fake",
        "_pipeline_model": "fake-model",
        "_pipeline_latency_ms": 1,
    }
    broken = {
        **canonical,
        "edges": [
            {"id": "E_01", "source": "N_00", "target": "N_01"},
            {"id": "E_02", "source": "N_01", "target": "true", "guard": "[true]"},
        ],
        "_pipeline_canonical": canonical,
    }

    finalised = ActivityPipeline._stage5_finalise([broken], patches=[])

    assert len(finalised) == 1
    restored = finalised[0]
    assert all(edge["target"] != "true" for edge in restored["edges"])
    assert len([edge for edge in restored["edges"] if edge["source"] == "N_01"]) == 2


def test_stage5_finalise_recovers_when_provenance_is_none():
    draft = {
        "diagram_type": "activity",
        "name": "RE_Test Code Flow",
        "owner_swc": "SWC_Test",
        "owner_runnable": "RE_Test",
        "source_requirements": ["REQ-1"],
        "nodes": [
            {"id": "N_00", "name": "Start", "node_type": "initial", "trace_reqs": ["REQ-1"], "description": "start", "confidence": 0.9},
            {"id": "N_01", "name": "Do work", "node_type": "action", "trace_reqs": ["REQ-1"], "description": "work", "confidence": 0.9},
            {"id": "N_02", "name": "End", "node_type": "final", "trace_reqs": ["REQ-1"], "description": "end", "confidence": 0.9},
        ],
        "edges": [
            {"id": "E_01", "source": "N_00", "target": "N_01"},
            {"id": "E_02", "source": "N_01", "target": "N_02"},
        ],
        "sub_diagrams": [],
        "provenance": None,
        "_pipeline_backend": "fake",
        "_pipeline_model": "fake-model",
        "_pipeline_latency_ms": 12,
    }

    finalised = ActivityPipeline._stage5_finalise([draft], patches=[])

    assert len(finalised) == 1
    assert isinstance(finalised[0]["provenance"], dict)
    assert finalised[0]["provenance"]["ai_model"] == "fake-model"
    assert finalised[0]["provenance"]["backend"] == "fake"


def test_overlay_ai_on_cfg_preserves_canonical_rte_metadata():
    canonical = {
        "diagram_type": "activity",
        "name": "RE_ReadInputs Code Flow",
        "owner_swc": "SWC_Test",
        "owner_runnable": "RE_ReadInputs",
        "source_requirements": ["REQ-1"],
        "nodes": [
            {"id": "N_00", "name": "Start", "node_type": "initial", "trace_reqs": ["REQ-1"], "description": "start", "confidence": 0.9},
            {
                "id": "N_01",
                "name": "Rte_IRead(RP_IgnitionStatus)",
                "node_type": "call",
                "trace_reqs": ["REQ-1"],
                "description": "read ignition",
                "confidence": 0.9,
                "rte_call": "Rte_IRead",
                "port": "RP_IgnitionStatus",
                "element": "IgnitionStatus",
            },
            {"id": "N_02", "name": "End", "node_type": "final", "trace_reqs": ["REQ-1"], "description": "end", "confidence": 0.9},
        ],
        "edges": [
            {"id": "E_01", "source": "N_00", "target": "N_01"},
            {"id": "E_02", "source": "N_01", "target": "N_02"},
        ],
        "sub_diagrams": [],
    }
    ai_diagram = {
        "nodes": [
            {"id": "N_00", "name": "Start", "node_type": "initial"},
            {
                "id": "N_01",
                "name": "Read ignition state",
                "node_type": "call",
                "description": "AI wording",
                "confidence": 0.71,
                "rte_call": "IRead",
                "port": "wrongPort",
                "element": "wrongElement",
            },
            {"id": "N_02", "name": "End", "node_type": "final"},
        ],
        "edges": [],
    }

    merged = ActivityPipeline._overlay_ai_on_cfg(canonical, ai_diagram)
    call_node = next(node for node in merged["nodes"] if node["id"] == "N_01")

    assert call_node["description"] == "AI wording"
    assert call_node["confidence"] == 0.71
    assert call_node["rte_call"] == "Rte_IRead"
    assert call_node["port"] == "RP_IgnitionStatus"
    assert call_node["element"] == "IgnitionStatus"


def test_diagram_has_cfg_breakage_when_multiple_decisions_have_no_merge():
    diagram = {
        "diagram_type": "activity",
        "name": "RE_NoMerge Code Flow",
        "owner_swc": "SWC_Test",
        "owner_runnable": "RE_NoMerge",
        "source_requirements": ["REQ-1"],
        "nodes": [
            {"id": "N_00", "name": "Start", "node_type": "initial", "trace_reqs": ["REQ-1"], "description": "start", "confidence": 0.9},
            {"id": "N_01", "name": "a > 0", "node_type": "decision", "trace_reqs": ["REQ-1"], "description": "d1", "confidence": 0.9},
            {"id": "N_02", "name": "Then A", "node_type": "action", "trace_reqs": ["REQ-1"], "description": "then", "confidence": 0.9},
            {"id": "N_03", "name": "b > 0", "node_type": "decision", "trace_reqs": ["REQ-1"], "description": "d2", "confidence": 0.9},
            {"id": "N_04", "name": "Then B", "node_type": "action", "trace_reqs": ["REQ-1"], "description": "then", "confidence": 0.9},
            {"id": "N_05", "name": "End", "node_type": "final", "trace_reqs": ["REQ-1"], "description": "end", "confidence": 0.9},
        ],
        "edges": [
            {"id": "E_01", "source": "N_00", "target": "N_01"},
            {"id": "E_02", "source": "N_01", "target": "N_02", "guard": "[true]"},
            {"id": "E_03", "source": "N_01", "target": "N_03", "guard": "[false]"},
            {"id": "E_04", "source": "N_02", "target": "N_05"},
            {"id": "E_05", "source": "N_03", "target": "N_04", "guard": "[true]"},
            {"id": "E_06", "source": "N_03", "target": "N_05", "guard": "[false]"},
            {"id": "E_07", "source": "N_04", "target": "N_05"},
        ],
        "sub_diagrams": [],
    }

    assert ActivityPipeline._diagram_has_cfg_breakage(diagram, "RE_NoMerge")


def test_diagram_has_cfg_breakage_when_rte_call_is_not_normalized():
    diagram = {
        "diagram_type": "activity",
        "name": "RE_BadRte Code Flow",
        "owner_swc": "SWC_Test",
        "owner_runnable": "RE_BadRte",
        "source_requirements": ["REQ-1"],
        "nodes": [
            {"id": "N_00", "name": "Start", "node_type": "initial", "trace_reqs": ["REQ-1"], "description": "start", "confidence": 0.9},
            {
                "id": "N_01",
                "name": "Rte_IRead(RP_IgnitionStatus)",
                "node_type": "call",
                "trace_reqs": ["REQ-1"],
                "description": "read ignition",
                "confidence": 0.9,
                "rte_call": "IRead",
                "port": "RP_IgnitionStatus",
                "element": "IgnitionStatus",
            },
            {"id": "N_02", "name": "End", "node_type": "final", "trace_reqs": ["REQ-1"], "description": "end", "confidence": 0.9},
        ],
        "edges": [
            {"id": "E_01", "source": "N_00", "target": "N_01"},
            {"id": "E_02", "source": "N_01", "target": "N_02"},
        ],
        "sub_diagrams": [],
    }

    assert ActivityPipeline._diagram_has_cfg_breakage(diagram, "RE_BadRte")


def test_diagram_has_cfg_breakage_ignores_generic_branch_density_warning_for_single_decision():
    diagram = {
        "diagram_type": "activity",
        "name": "RE_SingleDecision Code Flow",
        "owner_swc": "SWC_Test",
        "owner_runnable": "RE_SingleDecision",
        "source_requirements": ["REQ-1"],
        "nodes": [
            {"id": "N_00", "name": "Start", "node_type": "initial", "trace_reqs": ["REQ-1"], "description": "start", "confidence": 0.9},
            {"id": "N_01", "name": "mode valid?", "node_type": "decision", "trace_reqs": ["REQ-1"], "description": "decision", "confidence": 0.9},
            {"id": "N_02", "name": "Initialize", "node_type": "action", "trace_reqs": ["REQ-1"], "description": "init", "confidence": 0.9},
            {"id": "N_03", "name": "Skip init", "node_type": "action", "trace_reqs": ["REQ-1"], "description": "skip", "confidence": 0.9},
            {"id": "N_04", "name": "Merge", "node_type": "merge", "trace_reqs": ["REQ-1"], "description": "merge", "confidence": 0.9},
            {"id": "N_05", "name": "Read 1", "node_type": "call", "trace_reqs": ["REQ-1"], "description": "r1", "confidence": 0.9, "rte_call": "Rte_Read"},
            {"id": "N_06", "name": "Read 2", "node_type": "call", "trace_reqs": ["REQ-1"], "description": "r2", "confidence": 0.9, "rte_call": "Rte_Read"},
            {"id": "N_07", "name": "Write", "node_type": "call", "trace_reqs": ["REQ-1"], "description": "w", "confidence": 0.9, "rte_call": "Rte_Write"},
            {"id": "N_08", "name": "End", "node_type": "final", "trace_reqs": ["REQ-1"], "description": "end", "confidence": 0.9},
        ],
        "edges": [
            {"id": "E_01", "source": "N_00", "target": "N_01"},
            {"id": "E_02", "source": "N_01", "target": "N_02", "guard": "[mode valid]"},
            {"id": "E_03", "source": "N_01", "target": "N_03", "guard": "[else]"},
            {"id": "E_04", "source": "N_02", "target": "N_04"},
            {"id": "E_05", "source": "N_03", "target": "N_04"},
            {"id": "E_06", "source": "N_04", "target": "N_05"},
            {"id": "E_07", "source": "N_05", "target": "N_06"},
            {"id": "E_08", "source": "N_06", "target": "N_07"},
            {"id": "E_09", "source": "N_07", "target": "N_08"},
        ],
        "sub_diagrams": [],
    }

    assert not ActivityPipeline._diagram_has_cfg_breakage(diagram, "RE_SingleDecision")
