"""Tests for the multi-level validation engine."""

import pytest

from mudtool.config.settings import Settings
from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityNode,
    ActivityNodeType,
    ClassDiagram,
    ClassElement,
    ClassOperation,
    ComponentDiagram,
    ComponentElement,
    Connector,
    GenerationResult,
    Lifeline,
    Message,
    PortElement,
    Provenance,
    SequenceDiagram,
    State,
    StateMachineDiagram,
    Transition,
    DiagramType,
)
from mudtool.models.requirements import Priority, Requirement, RequirementType
from mudtool.validation.structural_validator import StructuralValidator
from mudtool.validation.autosar_validator import AUTOSARValidator
from mudtool.validation.consistency_validator import ConsistencyValidator
from mudtool.validation.engine import ValidationEngine
from mudtool.validation.structural_precheck import StructuralPreCheck
from mudtool.ai.orchestrator import AIOrchestrator


class TestStructuralValidator:
    def test_valid_sequence_diagram(self, sample_sequence_diagram):
        result = GenerationResult(diagrams=[sample_sequence_diagram])
        validator = StructuralValidator()
        report = validator.validate(result)

        assert report.error_count == 0

    def test_orphan_lifeline(self):
        """Lifeline with no messages should produce a warning."""
        diagram = SequenceDiagram(
            name="test",
            lifelines=[
                Lifeline(id="ll_1", name="SWC_A"),
                Lifeline(id="ll_2", name="SWC_B"),
                Lifeline(id="ll_3", name="SWC_Orphan"),
            ],
            messages=[
                Message(id="m1", **{"from": "ll_1", "to": "ll_2"}, rte_call="Rte_Write"),
            ],
        )
        result = GenerationResult(diagrams=[diagram])
        report = StructuralValidator().validate(result)

        warnings = [i for i in report.issues if i.element_name == "SWC_Orphan"
                     or (i.element_id == "ll_3")]
        assert len(warnings) >= 1

    def test_invalid_message_reference(self):
        """Message referencing non-existent lifeline should be an error."""
        diagram = SequenceDiagram(
            name="test",
            lifelines=[Lifeline(id="ll_1", name="SWC_A")],
            messages=[
                Message(id="m1", **{"from": "ll_1", "to": "ll_999"}, rte_call="Rte_Write"),
            ],
        )
        result = GenerationResult(diagrams=[diagram])
        report = StructuralValidator().validate(result)

        assert report.error_count >= 1

    def test_state_machine_no_initial(self):
        """State machine without initial state should error."""
        diagram = StateMachineDiagram(
            name="test",
            states=[
                State(id="s_1", name="RUNNING"),
                State(id="s_2", name="SHUTDOWN"),
            ],
            transitions=[],
        )
        result = GenerationResult(diagrams=[diagram])
        report = StructuralValidator().validate(result)

        errors = [i for i in report.issues if i.rule_id == "STR-006"]
        assert len(errors) >= 1

    def test_state_machine_multiple_initials(self):
        """State machine with multiple initial states should error."""
        diagram = StateMachineDiagram(
            name="test",
            states=[
                State(id="s_0", name="INIT1", is_initial=True),
                State(id="s_1", name="INIT2", is_initial=True),
            ],
            transitions=[],
        )
        result = GenerationResult(diagrams=[diagram])
        report = StructuralValidator().validate(result)

        assert report.error_count >= 1


class TestStructuralPreCheck:
    def test_sequence_requires_two_swcs_and_blocks_generation(self):
        requirements = [
            Requirement(
                req_id="REQ-ARCH-1001",
                title="EPS torque publish",
                description=(
                    "SWC_ElectricPowerSteering shall send steering torque via "
                    "PP_Torque using IF_SR_Torque."
                ),
                req_type=RequirementType.FUNCTIONAL,
                priority=Priority.MUST,
            ),
            Requirement(
                req_id="REQ-ARCH-1002",
                title="EPS torque compute",
                description=(
                    "SWC_ElectricPowerSteering shall compute assist torque in "
                    "RE_Main every 10 ms."
                ),
                req_type=RequirementType.FUNCTIONAL,
                priority=Priority.MUST,
            ),
        ]

        result = StructuralPreCheck().check(requirements, DiagramType.SEQUENCE)

        assert result.blocked is True
        assert any("at least 2 lifelines" in gap for gap in result.gaps)

    def test_activity_repair_recurses_into_sub_diagrams(self):
        orchestrator = AIOrchestrator.__new__(AIOrchestrator)
        child = ActivityDiagram(
            name="Helper",
            function_name="EPS_Helper",
            nodes=[
                ActivityNode(id="N_01", name="l_x = 1", node_type=ActivityNodeType.ACTION),
            ],
            edges=[],
        )
        parent = ActivityDiagram(
            name="Parent",
            owner_swc="SWC_Test",
            owner_runnable="RE_Test",
            nodes=[
                ActivityNode(id="N_10", name="l_y = EPS_Helper()", node_type=ActivityNodeType.FUNCTION_CALL, callee="EPS_Helper"),
            ],
            edges=[],
            sub_diagrams=[child],
        )

        repaired = orchestrator._repair_activity_diagram(parent, ["REQ-ARCH-1001"])

        assert any(n.node_type == ActivityNodeType.INITIAL for n in repaired.nodes)
        assert any(n.node_type == ActivityNodeType.FINAL for n in repaired.nodes)
        assert any(n.node_type == ActivityNodeType.INITIAL for n in repaired.sub_diagrams[0].nodes)
        assert any(n.node_type == ActivityNodeType.FINAL for n in repaired.sub_diagrams[0].nodes)


class TestAUTOSARValidator:
    @pytest.fixture
    def validator(self, test_settings):
        return AUTOSARValidator(test_settings)

    def test_valid_sequence(self, validator, sample_sequence_diagram):
        result = GenerationResult(diagrams=[sample_sequence_diagram])
        report = validator.validate(result)

        # Should pass basic AUTOSAR checks
        assert report.error_count == 0

    def test_invalid_rte_call(self, validator):
        """Invalid RTE call type should produce an error."""
        diagram = SequenceDiagram(
            name="test",
            lifelines=[
                Lifeline(id="ll_1", name="SWC_A"),
                Lifeline(id="ll_2", name="SWC_B"),
            ],
            messages=[
                Message(id="m1", **{"from": "ll_1", "to": "ll_2"},
                        rte_call="Rte_Invalid", port="PP_Data"),
            ],
        )
        result = GenerationResult(diagrams=[diagram])
        report = validator.validate(result)

        errors = [i for i in report.issues if i.rule_id == "AUT-008"]
        assert len(errors) >= 1

    def test_read_on_pport_error(self, validator):
        """Rte_Read on a P-Port should produce AUT-001 error."""
        diagram = SequenceDiagram(
            name="test",
            lifelines=[
                Lifeline(id="ll_1", name="SWC_A"),
                Lifeline(id="ll_2", name="SWC_B"),
            ],
            messages=[
                Message(id="m1", **{"from": "ll_1", "to": "ll_2"},
                        rte_call="Rte_Read", port="PP_WrongPort"),
            ],
        )
        result = GenerationResult(diagrams=[diagram])
        report = validator.validate(result)

        errors = [i for i in report.issues if i.rule_id == "AUT-001"]
        assert len(errors) >= 1

    def test_cyclic_without_period(self, validator):
        """Cyclic runnable without period_ms should produce AUT-004 error."""
        diagram = ClassDiagram(
            name="test",
            classes=[ClassElement(
                id="c1", name="SWC_Test", stereotype="ApplicationSWC",
                operations=[
                    ClassOperation(
                        name="RE_Main", trigger_type="cyclic",
                        period_ms=None, trace_reqs=["REQ-ARCH-0001"],
                    ),
                ],
                trace_reqs=["REQ-ARCH-0001"],
            )],
        )
        result = GenerationResult(diagrams=[diagram])
        report = validator.validate(result)

        errors = [i for i in report.issues if i.rule_id == "AUT-004"]
        assert len(errors) >= 1

    def test_requirement_coverage(self, validator, sample_generation_result):
        """Check requirement coverage analysis."""
        all_reqs = ["REQ-ARCH-0142", "REQ-ARCH-0143", "REQ-ARCH-0300",
                     "REQ-ARCH-0301", "REQ-ARCH-9999"]
        report = validator.validate(sample_generation_result, all_reqs)

        coverage_issues = [i for i in report.issues if i.rule_id == "AUT-010"]
        assert len(coverage_issues) >= 1  # REQ-ARCH-9999 is uncovered


class TestConsistencyValidator:
    def test_consistent_diagrams(self, sample_generation_result):
        validator = ConsistencyValidator()
        report = validator.validate(sample_generation_result)

        # No errors expected for well-formed sample
        assert report.error_count == 0


class TestValidationEngine:
    def test_full_validation(self, test_settings, sample_generation_result):
        engine = ValidationEngine(test_settings)
        report = engine.validate(
            sample_generation_result,
            requirement_ids=["REQ-ARCH-0142", "REQ-ARCH-0143",
                             "REQ-ARCH-0300", "REQ-ARCH-0301"],
        )

        # Should complete without crash
        assert report.diagrams_checked >= 3
        assert report.elements_checked > 0

    def test_skip_autosar_pass_in_generic_mode(self, test_settings):
        engine = ValidationEngine(test_settings)
        diagram = SequenceDiagram(
            name="test",
            lifelines=[
                Lifeline(id="ll_1", name="ModuleA"),
                Lifeline(id="ll_2", name="ModuleB"),
            ],
            messages=[
                Message(
                    id="m1",
                    **{"from": "ll_1", "to": "ll_2"},
                    rte_call="Rte_Invalid",
                    port="PP_Data",
                ),
            ],
        )
        result = GenerationResult(diagrams=[diagram])
        report = engine.validate(
            result,
            requirement_ids=["REQ-001"],
            autosar_compliant=False,
        )
        assert not any(i.rule_id.startswith("AUT-") for i in report.issues)
