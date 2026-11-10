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


class _FailingBackend:
    async def generate(self, **kwargs):
        raise ConnectionError("All connection attempts failed")


class _FailingOrchestrator:
    def _get_backend(self):
        return _FailingBackend()


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


AEB_TEXT = """[REQ-1] (functional) Architecture
  Description: The feature is composed of SWC_A and SWC_B.
[REQ-2] (functional) A runnable
  Description: SWC_A shall run RE_DoA every 10 ms.
[REQ-3] (functional) B runnable
  Description: SWC_B shall run RE_DoB every 20 ms.
"""


@pytest.mark.asyncio
async def test_free_text_evidence_does_not_give_every_swc_every_runnable_and_requirement():
    """The chain sends "[ID] (type) title / Description" text, not CSV rows. For several SWCs the
    text evidence then gave EVERY component ALL runnables and ALL requirement IDs. Seen on the AEB
    set: SWC_AEB_BrakeActuator was planned with 2 runnables by the model and reached the spec with
    9 (object fusion, driver warning …) and all 120 requirements."""
    planner = ModulePlanner(_FakeOrchestrator(["""
        {"modules": [
          {"swc_name": "SWC_A", "runnables": ["RE_DoA"], "req_ids": ["REQ-2"]},
          {"swc_name": "SWC_B", "runnables": ["RE_DoB"], "req_ids": ["REQ-3"]}]}"""]))

    result = await planner.plan_modules(AEB_TEXT, temperature=0.1)

    by_name = {m.swc_name: m for m in result.modules}
    assert by_name["SWC_A"].runnables == ["RE_DoA"] and by_name["SWC_A"].req_ids == ["REQ-2"]
    assert by_name["SWC_B"].runnables == ["RE_DoB"] and by_name["SWC_B"].req_ids == ["REQ-3"]


@pytest.mark.asyncio
async def test_module_planner_falls_back_when_backend_connection_fails():
    planner = ModulePlanner(_FailingOrchestrator())

    result = await planner.plan_modules(EPS_CSV, temperature=0.1)

    assert len(result.modules) == 1
    module = result.modules[0]
    assert module.swc_name == "SWC_ElectricPowerSteering"
    assert module.asil == "ASIL-D"
    assert "RE_ControlTorque" in module.runnables
    assert "All connection attempts failed" in result.raw_response


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
