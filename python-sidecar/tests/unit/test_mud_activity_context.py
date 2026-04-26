from mudtool.ai.mud_activity_context import (
    build_mud_activity_context,
    synthesize_activity_diagrams_from_context,
)
from mudtool.models.json_uml import ActivityNodeType


def test_build_mud_activity_context_extracts_runnables_and_flow():
    markdown = """
# MUD Spec: SWC_ElectricPowerSteering

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_ControlTorque | cyclic | 10 ms | ASIL-B | Main EPS loop |

## 7. Functional Description
### RE_ControlTorque
Rte_Read_RP_SteerTorque_Torque(&l_f32DriverTorque)
Rte_Read_RP_VehicleSpeed_Speed(&l_f32Speed)
l_f32AssistTorque = EPS_CalcAssistTorque(l_f32DriverTorque, l_f32Speed)
Rte_Write_PP_AssistTorque_Torque(l_f32AssistTorque)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_ElectricPowerSteering")

    assert context.swc_name == "SWC_ElectricPowerSteering"
    assert context.has_usable_flow_source is True
    assert [r.name for r in context.runnables] == ["RE_ControlTorque"]
    assert "EPS_CalcAssistTorque" in context.helper_functions
    block = context.to_prompt_block()
    assert "AUTHORITATIVE MUD FLOW SOURCE" in block
    assert "RE_ControlTorque" in block
    assert "Rte_Read_RP_SteerTorque_Torque" in block


def test_build_mud_activity_context_handles_numbered_subheadings():
    markdown = """
# MUD Spec: SWC_ElectricPowerSteering

## 3. Runnables
### 3.1 Main Runnables (OS-scheduled via AUTOSAR RTE)
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_ControlTorque | Cyclic | 5 ms | ASIL-D | Main EPS control loop |

## 7. Functional Description
### RE_ControlTorque
// Reads: RP_VehicleSpeed
1. Rte_Read(RP_VehicleSpeed, &speed)
2. assist = EPS_CalcAssistTorque(speed)
3. Rte_Write(PP_AssistTorque, assist)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_ElectricPowerSteering")

    assert context.runnables[0].name == "RE_ControlTorque"
    assert context.runnables[0].period == "5 ms"
    assert context.has_structured_flow_source is True


def test_synthesize_activity_diagrams_from_context_uses_section7_steps():
    markdown = """
# MUD Spec: SWC_ElectricPowerSteering

## 3. Runnables
### 3.1 Main Runnables (OS-scheduled via AUTOSAR RTE)
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_ControlTorque | Cyclic | 5 ms | ASIL-D | Main EPS control loop |

## 7. Functional Description
### RE_ControlTorque
// Reads: RP_VehicleSpeed
1. Rte_Read(RP_VehicleSpeed, &speed)
2. assist = EPS_CalcAssistTorque(speed)
3. Rte_Write(PP_AssistTorque, assist)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_ElectricPowerSteering")
    diagrams = synthesize_activity_diagrams_from_context(context, ["REQ-001"])

    assert len(diagrams) == 1
    diagram = diagrams[0]
    assert diagram.owner_swc == "SWC_ElectricPowerSteering"
    assert diagram.owner_runnable == "RE_ControlTorque"
    assert len(diagram.nodes) == 5
    assert diagram.nodes[1].node_type.value == "call"
    assert diagram.nodes[2].node_type.value == "function_call"
    assert diagram.sub_diagrams


def test_synthesize_activity_diagrams_from_context_builds_if_else_branching():
    markdown = """
# MUD Spec: SWC_BrakeAssist

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Control | Cyclic | 10 ms | ASIL-C | Branching flow |

## 7. Functional Description
### RE_Control
1. If brakeRequest > threshold
1.1. Rte_Write(PP_BrakeAssistCmd, TRUE)
2. Else
2.1. Dem_ReportErrorStatus(Event_BrakeAssist, DEM_EVENT_STATUS_FAILED)
3. End If
4. Rte_Write(PP_Status, status)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_BrakeAssist")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-101"])[0]

    decision_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.DECISION]
    merge_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.MERGE]
    exception_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.EXCEPTION]
    guards = {edge.guard for edge in diagram.edges if edge.guard}

    assert len(decision_nodes) == 1
    assert merge_nodes
    assert exception_nodes
    assert "[true]" in guards
    assert "[false]" in guards


def test_synthesize_activity_diagrams_from_context_builds_nested_condition():
    markdown = """
# MUD Spec: SWC_Traction

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Traction | Cyclic | 10 ms | ASIL-C | Nested flow |

## 7. Functional Description
### RE_Traction
1. If wheelSlipDetected
1.1. If vehicleStable
1.1.1. ApplyTractionControl()
1.2. Else
1.2.1. Dem_ReportErrorStatus(Event_Stability, DEM_EVENT_STATUS_FAILED)
2. End If
3. Rte_Write(PP_TractionStatus, tractionStatus)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_Traction")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-102"])[0]

    assert sum(1 for n in diagram.nodes if n.node_type == ActivityNodeType.DECISION) >= 2
    assert sum(1 for n in diagram.nodes if n.node_type == ActivityNodeType.MERGE) >= 2


def test_synthesize_activity_diagrams_from_context_builds_while_loop_back_edge():
    markdown = """
# MUD Spec: SWC_Watchdog

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Watchdog | Cyclic | 5 ms | ASIL-B | Loop flow |

## 7. Functional Description
### RE_Watchdog
1. While retryCount < 3
1.1. Rte_Read(RP_Status, &status)
2. End While
3. Rte_Write(PP_Result, status)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_Watchdog")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-103"])[0]

    decisions = [n for n in diagram.nodes if n.node_type == ActivityNodeType.DECISION]
    assert decisions
    loop_id = decisions[0].id
    assert any(edge.target == loop_id and edge.source != "N_00" for edge in diagram.edges)
    assert any(edge.source == loop_id and edge.guard == "[done]" for edge in diagram.edges)


def test_synthesize_activity_diagrams_from_context_builds_for_each_loop_and_helper_subdiagram():
    markdown = """
# MUD Spec: SWC_Diagnostics

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Diag | Cyclic | 20 ms | ASIL-B | Helper in loop |

## 7. Functional Description
### RE_Diag
1. For each DTC entry
1.1. EvaluateDtc(entry)
2. End For
3. Rte_Write(PP_DiagStatus, diagStatus)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_Diagnostics")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-104"])[0]

    assert any(n.node_type == ActivityNodeType.DECISION for n in diagram.nodes)
    assert diagram.sub_diagrams
    assert diagram.sub_diagrams[0].function_name == "EvaluateDtc"
