"""Shared test fixtures for the MUD Tool test suite."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from mudtool.config.settings import Settings
from mudtool.models.requirements import (
    ASILLevel,
    Priority,
    Requirement,
    RequirementSet,
    RequirementType,
)
from mudtool.models.json_uml import (
    DiagramType,
    Lifeline,
    Message,
    Provenance,
    SequenceDiagram,
    State,
    StateMachineDiagram,
    Transition,
    ClassDiagram,
    ClassElement,
    ClassOperation,
    ComponentDiagram,
    ComponentElement,
    PortElement,
    GenerationResult,
)


@pytest.fixture
def test_settings(tmp_path):
    """Create test settings with temporary directories."""
    os.environ["MUD_AI_BACKEND"] = "cloud"
    os.environ["MUD_ANTHROPIC_API_KEY"] = "test-key"

    settings = Settings(
        host="127.0.0.1",
        port=8042,
        debug=True,
        project_root=tmp_path,
        prompts_dir=tmp_path / "prompts",
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "test.sqlite",
    )
    (tmp_path / "prompts").mkdir(exist_ok=True)
    (tmp_path / "data").mkdir(exist_ok=True)
    return settings


@pytest.fixture
def sample_requirements() -> list[Requirement]:
    """Create sample AUTOSAR requirements for testing."""
    return [
        Requirement(
            req_id="REQ-ARCH-0142",
            title="Sensor Fusion Data Distribution",
            description=(
                "The SWC_SensorFusion shall distribute fused sensor data "
                "to all consuming components via Sender-Receiver interface "
                "with a cycle time of 10ms."
            ),
            req_type=RequirementType.FUNCTIONAL,
            safety_level=ASILLevel.ASIL_B,
            priority=Priority.MUST,
            module_hint="SWC_SensorFusion",
        ),
        Requirement(
            req_id="REQ-ARCH-0143",
            title="Vehicle Control Data Reception",
            description=(
                "SWC_VehicleControl shall receive fused sensor data from "
                "SWC_SensorFusion and process it in its cyclic runnable."
            ),
            req_type=RequirementType.INTERFACE,
            priority=Priority.MUST,
            module_hint="SWC_VehicleControl",
        ),
        Requirement(
            req_id="REQ-ARCH-0300",
            title="SWC Lifecycle Management",
            description=(
                "SWC_SensorFusion shall implement a lifecycle with Init, "
                "Running, and Shutdown states."
            ),
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
        ),
        Requirement(
            req_id="REQ-ARCH-0301",
            title="Error State Handling",
            description=(
                "SWC_SensorFusion shall transition to ERROR state on "
                "sensor communication failure and attempt recovery after 500ms."
            ),
            req_type=RequirementType.SAFETY,
            safety_level=ASILLevel.ASIL_B,
            priority=Priority.MUST,
        ),
    ]


@pytest.fixture
def sample_requirement_set(sample_requirements) -> RequirementSet:
    return RequirementSet(requirements=sample_requirements)


@pytest.fixture
def sample_sequence_diagram() -> SequenceDiagram:
    """Create a sample sequence diagram for testing."""
    return SequenceDiagram(
        name="SensorFusion_DataDistribution",
        source_requirements=["REQ-ARCH-0142", "REQ-ARCH-0143"],
        lifelines=[
            Lifeline(
                id="ll_1", name="SWC_SensorFusion",
                type="ApplicationSWC", runnable="RE_FuseSensorData",
                trace_reqs=["REQ-ARCH-0142"],
            ),
            Lifeline(
                id="ll_2", name="SWC_VehicleControl",
                type="ApplicationSWC", runnable="RE_ProcessSensorData",
                trace_reqs=["REQ-ARCH-0143"],
            ),
        ],
        messages=[
            Message(
                id="msg_1",
                **{"from": "ll_1", "to": "ll_2"},
                rte_call="Rte_Write", port="PP_FusedData",
                element="DE_FusedSensorOutput",
                trace_req="REQ-ARCH-0142",
                confidence=0.92,
            ),
        ],
        provenance=Provenance(
            ai_model="test-model", prompt_version="seq-v1.0", confidence=0.90,
        ),
    )


@pytest.fixture
def sample_state_machine() -> StateMachineDiagram:
    """Create a sample state machine diagram for testing."""
    return StateMachineDiagram(
        name="SWC_SensorFusion_Lifecycle",
        owner_swc="SWC_SensorFusion",
        source_requirements=["REQ-ARCH-0300", "REQ-ARCH-0301"],
        states=[
            State(id="s_0", name="INITIAL", is_initial=True),
            State(id="s_1", name="INIT", trace_reqs=["REQ-ARCH-0300"]),
            State(id="s_2", name="RUNNING", trace_reqs=["REQ-ARCH-0300"]),
            State(id="s_3", name="ERROR", trace_reqs=["REQ-ARCH-0301"]),
            State(id="s_4", name="SHUTDOWN", trace_reqs=["REQ-ARCH-0300"]),
        ],
        transitions=[
            Transition(id="t_1", source="s_0", target="s_1", trigger="PowerOn"),
            Transition(id="t_2", source="s_1", target="s_2", trigger="InitComplete"),
            Transition(id="t_3", source="s_2", target="s_3", trigger="SensorCommFailure",
                       trace_req="REQ-ARCH-0301"),
            Transition(id="t_4", source="s_3", target="s_2", trigger="RecoveryTimeout",
                       trace_req="REQ-ARCH-0301"),
            Transition(id="t_5", source="s_2", target="s_4", trigger="ShutdownRequest"),
        ],
        provenance=Provenance(
            ai_model="test-model", prompt_version="sm-v1.0", confidence=0.88,
        ),
    )


@pytest.fixture
def sample_class_diagram() -> ClassDiagram:
    """Create a sample class diagram for testing."""
    return ClassDiagram(
        name="SWC_SensorFusion_Design",
        source_requirements=["REQ-ARCH-0142"],
        classes=[
            ClassElement(
                id="cls_1", name="SWC_SensorFusion",
                stereotype="ApplicationSWC",
                operations=[
                    ClassOperation(
                        name="RE_InitFusion", trigger_type="init",
                        trace_reqs=["REQ-ARCH-0142"],
                    ),
                    ClassOperation(
                        name="RE_FuseSensorData", trigger_type="cyclic",
                        period_ms=10.0,
                        trace_reqs=["REQ-ARCH-0142"],
                    ),
                ],
                trace_reqs=["REQ-ARCH-0142"],
            ),
        ],
        provenance=Provenance(
            ai_model="test-model", prompt_version="cls-v1.0", confidence=0.90,
        ),
    )


@pytest.fixture
def sample_generation_result(
    sample_sequence_diagram, sample_state_machine, sample_class_diagram
) -> GenerationResult:
    """Create a sample generation result with multiple diagram types."""
    return GenerationResult(
        diagrams=[sample_sequence_diagram, sample_state_machine, sample_class_diagram],
        analyzed_requirements=["REQ-ARCH-0142", "REQ-ARCH-0143", "REQ-ARCH-0300", "REQ-ARCH-0301"],
    )
