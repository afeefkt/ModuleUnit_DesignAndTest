"""Tests for data models - Requirements, AUTOSAR entities, JSON-UML."""

import pytest

from mudtool.models.requirements import (
    ASILLevel,
    Priority,
    Requirement,
    RequirementSet,
    RequirementType,
)
from mudtool.models.autosar import (
    ApplicationSWC,
    DataElement,
    Port,
    PortDirection,
    Runnable,
    SenderReceiverInterface,
    SWCType,
    TriggerType,
)
from mudtool.models.json_uml import (
    DiagramType,
    Lifeline,
    Message,
    Provenance,
    SequenceDiagram,
)
from mudtool.models.validation import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)


class TestRequirementModel:
    def test_create_requirement(self):
        req = Requirement(
            req_id="REQ-ARCH-0001",
            title="Test Requirement",
            description="This is a test requirement",
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
        )
        assert req.req_id == "REQ-ARCH-0001"
        assert req.req_type == RequirementType.FUNCTIONAL
        assert req.safety_level is None

    def test_requirement_with_asil(self):
        req = Requirement(
            req_id="REQ-ARCH-0002",
            title="Safety Requirement",
            description="A safety-critical requirement",
            req_type=RequirementType.SAFETY,
            safety_level=ASILLevel.ASIL_D,
            priority=Priority.MUST,
        )
        assert req.safety_level == ASILLevel.ASIL_D

    def test_requirement_set_operations(self, sample_requirements):
        req_set = RequirementSet(requirements=sample_requirements)
        assert req_set.count == 4

        by_id = req_set.get_by_id("REQ-ARCH-0142")
        assert by_id is not None
        assert by_id.title == "Sensor Fusion Data Distribution"

        functional = req_set.get_functional()
        assert len(functional) == 2

        interface = req_set.get_interface()
        assert len(interface) == 1


class TestAUTOSARModels:
    def test_create_swc(self):
        swc = ApplicationSWC(
            name="SWC_SensorFusion",
            swc_type=SWCType.APPLICATION,
            ports=[
                Port(
                    name="PP_FusedData",
                    direction=PortDirection.PROVIDED,
                    interface_ref="IF_SR_FusedSensor",
                )
            ],
            runnables=[
                Runnable(
                    name="RE_FuseSensorData",
                    trigger=TriggerType.CYCLIC,
                    period_ms=10.0,
                )
            ],
        )
        assert swc.name == "SWC_SensorFusion"
        assert len(swc.ports) == 1
        assert len(swc.runnables) == 1
        assert len(swc.get_provided_ports()) == 1
        assert len(swc.get_required_ports()) == 0

    def test_sender_receiver_interface(self):
        iface = SenderReceiverInterface(
            name="IF_SR_FusedSensor",
            data_elements=[
                DataElement(name="DE_FusedOutput", data_type="FusedSensorType"),
            ],
        )
        assert len(iface.data_elements) == 1

    def test_runnable_triggers(self):
        init = Runnable(name="RE_Init", trigger=TriggerType.INIT)
        cyclic = Runnable(name="RE_Main", trigger=TriggerType.CYCLIC, period_ms=10.0)
        event = Runnable(name="RE_OnData", trigger=TriggerType.ON_DATA_RECEPTION)

        assert init.trigger == TriggerType.INIT
        assert cyclic.period_ms == 10.0
        assert event.trigger == TriggerType.ON_DATA_RECEPTION


class TestJSONUMLModels:
    def test_sequence_diagram(self, sample_sequence_diagram):
        diag = sample_sequence_diagram
        assert diag.diagram_type == DiagramType.SEQUENCE
        assert len(diag.lifelines) == 2
        assert len(diag.messages) == 1
        assert diag.provenance.confidence == 0.90

    def test_message_model(self):
        msg = Message(
            id="msg_1",
            **{"from": "ll_1", "to": "ll_2"},
            rte_call="Rte_Write",
            port="PP_Data",
            element="DE_Output",
            trace_req="REQ-ARCH-0001",
            confidence=0.9,
        )
        assert msg.from_lifeline == "ll_1"
        assert msg.to_lifeline == "ll_2"
        assert msg.rte_call == "Rte_Write"


class TestValidationModels:
    def test_validation_report(self):
        report = ValidationReport()
        assert report.passed is True
        assert report.error_count == 0

        report.add_issue(ValidationIssue(
            rule_id="AUT-001",
            severity=ValidationSeverity.ERROR,
            category="Port",
            message="Port mismatch",
        ))

        assert report.passed is False
        assert report.error_count == 1

        report.add_issue(ValidationIssue(
            rule_id="AUT-006",
            severity=ValidationSeverity.WARNING,
            category="Naming",
            message="Naming violation",
        ))

        assert report.warning_count == 1
        assert "FAILED" in report.summary()
