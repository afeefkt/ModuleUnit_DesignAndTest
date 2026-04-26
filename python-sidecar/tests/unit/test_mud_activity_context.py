from mudtool.ai.mud_activity_context import (
    build_mud_activity_context,
    synthesize_activity_diagrams_from_context,
)


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
