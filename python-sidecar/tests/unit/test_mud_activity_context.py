from mudtool.ai.mud_activity_context import (
    _parse_numbered_step_entries,
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
    assert diagram.nodes[2].name == "assist = EPS_CalcAssistTorque(...)"
    assert diagram.sub_diagrams == []


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
    assert any("brakeRequest > threshold" in guard for guard in guards)
    assert "[else]" in guards


def test_synthesize_activity_diagrams_from_context_skips_merge_when_only_one_branch_continues():
    markdown = """
# MUD Spec: SWC_Guard

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Guard | Cyclic | 10 ms | ASIL-B | Guard return |

## 7. Functional Description
### RE_Guard
1. If inputInvalid
1.1. Rte_Write(PP_Status, 0)
1.2. return
2. Else
2.1. Rte_Write(PP_Status, 1)
3. End If
4. Rte_Write(PP_Result, result)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_Guard")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-106"])[0]

    merge_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.MERGE]
    merge_names = {n.name for n in merge_nodes}

    assert "Merge" not in merge_names
    assert any((n.name or "").strip().lower() == "return" for n in diagram.nodes)


def test_synthesize_activity_diagrams_from_context_skips_merge_when_all_branches_terminate():
    markdown = """
# MUD Spec: SWC_Terminal

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Terminal | Cyclic | 10 ms | ASIL-B | Both branches terminate |

## 7. Functional Description
### RE_Terminal
1. If faultActive
1.1. Dem_ReportErrorStatus(Event_Fault, DEM_EVENT_STATUS_FAILED)
1.2. return
2. Else
2.1. Rte_Write(PP_Status, 1)
2.2. return
3. End If
"""

    context = build_mud_activity_context(markdown, module_context="SWC_Terminal")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-107"])[0]

    merge_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.MERGE]

    assert not any(n.name == "Merge" for n in merge_nodes)
    assert sum(1 for n in diagram.nodes if (n.name or "").strip().lower() == "return") == 2


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


def test_synthesize_activity_diagrams_from_context_emits_helper_subdiagram_when_helper_repeats():
    markdown = """
# MUD Spec: SWC_Filter

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Filter | Cyclic | 10 ms | ASIL-B | Repeated helper use |

## 7. Functional Description
### RE_Filter
1. filteredA = ApplyFilter(rawA)
2. filteredB = ApplyFilter(rawB)
3. Rte_Write(PP_FilteredA, filteredA)
"""

    context = build_mud_activity_context(markdown, module_context="SWC_Filter")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-105"])[0]

    assert diagram.sub_diagrams
    assert diagram.sub_diagrams[0].function_name == "ApplyFilter"


def test_parse_numbered_step_entries_expands_c_style_pseudocode_blocks():
    text = """
1. Guard: mode check:
   if (RP_IgnitionStatus == false) {
       Rte_IWrite(PP_MotorCurrentDemand, 0);
       return;
   }
2. Write PP_ output:
   if (motorTemperature > 120) {
       Rte_IWrite(PP_EPSStatus, 3);
   } else if (assistDemand > 50) {
       Rte_IWrite(PP_EPSStatus, 2);
   } else {
       Rte_IWrite(PP_EPSStatus, 1);
   }
"""
    steps = _parse_numbered_step_entries(text)

    kinds = [step.kind for step in steps]
    texts = [step.text for step in steps]

    assert "if" in kinds
    assert "else_if" in kinds
    assert "else" in kinds
    assert any("Rte_IWrite(PP_EPSStatus, 3)" in text for text in texts)
    assert any(step.depth > 1 for step in steps)


def test_synthesize_activity_diagrams_from_context_builds_branching_from_c_style_section7_blocks():
    markdown = """
# MUD Spec: SWC_ElectricPowerSteering

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_ControlTorque | Cyclic | 5 ms | ASIL-D | Main EPS control loop |

## 7. Functional Description
### RE_ControlTorque
1. Guard: mode check:
   if (RP_IgnitionStatus == false) {
       Rte_IWrite(PP_MotorCurrentDemand, 0);
       Rte_IWrite(PP_EPSStatus, 0);
       return;
   }
2. Core computation step:
   if (assistDemand > 100) {
       assistDemand = 100;
   }
   if (assistDemand < -100) {
       assistDemand = -100;
   }
3. Write PP_ output:
   if (motorTemperature > 120) {
       Rte_IWrite(PP_EPSStatus, 3);
   } else if (assistDemand > 50) {
       Rte_IWrite(PP_EPSStatus, 2);
   } else {
       Rte_IWrite(PP_EPSStatus, 1);
   }
"""
    context = build_mud_activity_context(markdown, module_context="SWC_ElectricPowerSteering")

    assert context.has_structured_flow_source is True

    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-201"])[0]
    decision_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.DECISION]
    merge_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.MERGE]
    guards = {edge.guard for edge in diagram.edges if edge.guard}

    assert len(decision_nodes) >= 3
    assert len(merge_nodes) >= 3
    assert any("motorTemperature > 120" in guard for guard in guards)
    assert "[else]" in guards


def test_synthesize_activity_diagrams_from_context_normalizes_rte_iread_iwrite_and_return():
    markdown = """
# MUD Spec: SWC_Stream

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Stream | Cyclic | 5 ms | ASIL-B | Stream flow |

## 7. Functional Description
### RE_Stream
1. Guard: check status:
   if (Rte_IRead(RP_IgnitionStatus) == false) {
       Rte_IWrite(PP_EPSStatus, 0);
       return;
   }
2. Continue:
   Rte_IWrite(PP_AssistLevel, assistLevel);
"""
    context = build_mud_activity_context(markdown, module_context="SWC_Stream")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-301"])[0]

    call_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.CALL]
    decision_nodes = [n for n in diagram.nodes if n.node_type == ActivityNodeType.DECISION]
    return_nodes = [n for n in diagram.nodes if (n.name or "").strip().lower() == "return"]
    final_id = next(n.id for n in diagram.nodes if n.node_type == ActivityNodeType.FINAL)

    assert any(n.rte_call == "Rte_IRead" for n in diagram.nodes if getattr(n, "rte_call", None))
    assert any(n.rte_call == "Rte_IWrite" for n in call_nodes)
    assert any(n.rte_call == "Rte_IRead" for n in decision_nodes)
    assert return_nodes
    assert any(edge.source == return_nodes[0].id and edge.target == final_id for edge in diagram.edges)
