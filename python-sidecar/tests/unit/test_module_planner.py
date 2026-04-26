from __future__ import annotations

import pytest

from mudtool.ai.base_backend import AIResponse
from mudtool.ai.module_planner import ModulePlanner


class _FakeBackend:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    async def generate(self, **kwargs):
        content = self._responses.pop(0) if self._responses else ""
        return AIResponse(content=content, model="fake-model")


class _FakeOrchestrator:
    def __init__(self, responses: list[str]):
        self._backend = _FakeBackend(responses)

    def _get_backend(self):
        return self._backend


EPS_CSV = """req_id,title,description,req_type,safety_level,priority,module_hint,notes
REQ-EPS-001,EPS SWC Architecture,SWC_ElectricPowerSteering shall be implemented as an AUTOSAR ApplicationSWC,FUNCTIONAL,ASIL-D,MUST,SWC_ElectricPowerSteering,Single SWC owns all EPS application logic
REQ-EPS-002,Control Torque Runnable,RE_ControlTorque shall execute cyclically every 5 ms,TIMING,ASIL-D,MUST,SWC_ElectricPowerSteering,5ms control loop
REQ-EPS-003,Safety Monitor Runnable,RE_MonitorSafety shall execute cyclically every 10 ms,TIMING,ASIL-D,MUST,SWC_ElectricPowerSteering,10ms safety loop
REQ-EPS-004,Required Ports,SWC shall declare: RP_VehicleSpeed RP_IgnitionStatus PP_EPSStatus,INTERFACE,ASIL-D,MUST,SWC_ElectricPowerSteering,Port definitions
"""


@pytest.mark.asyncio
async def test_module_planner_recovers_from_empty_ai_output_using_requirement_evidence():
    planner = ModulePlanner(_FakeOrchestrator(["", ""]))

    result = await planner.plan_modules(EPS_CSV, temperature=0.1)

    assert len(result.modules) == 1
    module = result.modules[0]
    assert module.swc_name == "SWC_ElectricPowerSteering"
    assert module.asil == "ASIL-D"
    assert "RE_ControlTorque" in module.runnables
    assert "REQ-EPS-001" in module.req_ids
    assert module.port_count >= 3


@pytest.mark.asyncio
async def test_module_planner_repairs_partial_ai_module_with_requirement_evidence():
    planner = ModulePlanner(
        _FakeOrchestrator(
            [
                """
                {
                  "modules": [
                    {
                      "swc_name": "ElectricPowerSteering",
                      "description": "EPS logic",
                      "runnables": [],
                      "req_ids": [],
                      "port_count": 0,
                      "calprm_count": 0,
                      "complexity": "medium"
                    }
                  ]
                }
                """
            ]
        )
    )

    result = await planner.plan_modules(EPS_CSV, temperature=0.1)

    assert len(result.modules) == 1
    module = result.modules[0]
    assert module.swc_name == "SWC_ElectricPowerSteering"
    assert module.short_name == "electricPowerSteering"
    assert module.asil == "ASIL-D"
    assert "RE_ControlTorque" in module.runnables
    assert "RE_MonitorSafety" in module.runnables
    assert "REQ-EPS-002" in module.req_ids
    assert module.port_count >= 3
