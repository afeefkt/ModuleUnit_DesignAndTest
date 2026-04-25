from mudtool.ai.mud_activity_context import build_mud_activity_context


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
