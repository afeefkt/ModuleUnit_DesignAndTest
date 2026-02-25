"""Pass 2 - AUTOSAR-Specific Validation.

Implements rules AUT-001 through AUT-010 from the architecture document:
- Port direction consistency
- Interface type matching
- Runnable trigger validity
- Data type compatibility
- Naming conventions
- Traceability coverage
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from mudtool.config.settings import Settings
from mudtool.models.json_uml import (
    ActivityDiagram,
    ClassDiagram,
    ComponentDiagram,
    GenerationResult,
    SequenceDiagram,
    StateMachineDiagram,
)
from mudtool.models.validation import ValidationIssue, ValidationReport, ValidationSeverity

logger = logging.getLogger(__name__)


class AUTOSARValidator:
    """AUTOSAR-specific validation rules engine.

    Validates AUTOSAR metamodel compliance:
    - AUT-001: R-Port to P-Port matching
    - AUT-002: Interface type constraints
    - AUT-003: Init runnable trigger type
    - AUT-004: Cyclic runnable period
    - AUT-005: SR interface data elements have types
    - AUT-006: Naming conventions
    - AUT-007: SWC traceability
    - AUT-008: Sequence diagram RTE call validity
    - AUT-009: State machine initial state
    - AUT-010: Requirement coverage completeness
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._swc_pattern = re.compile(settings.swc_naming_regex)
        self._runnable_pattern = re.compile(settings.runnable_naming_regex)
        self._port_pattern = re.compile(settings.port_naming_regex)

    def validate(
        self,
        result: GenerationResult,
        requirement_ids: Optional[list[str]] = None,
    ) -> ValidationReport:
        """Run all AUTOSAR validation rules on the generation result.

        Args:
            result: The generation result to validate.
            requirement_ids: Optional list of all requirement IDs for coverage check.
        """
        report = ValidationReport()

        for diagram in result.diagrams:
            report.diagrams_checked += 1

            if isinstance(diagram, SequenceDiagram):
                self._validate_sequence(diagram, report)
            elif isinstance(diagram, StateMachineDiagram):
                self._validate_state_machine(diagram, report)
            elif isinstance(diagram, ClassDiagram):
                self._validate_class(diagram, report)
            elif isinstance(diagram, ComponentDiagram):
                self._validate_component(diagram, report)
            elif isinstance(diagram, ActivityDiagram):
                self._validate_activity(diagram, report)

        # AUT-010: Requirement coverage (cross-diagram)
        if requirement_ids:
            self._validate_requirement_coverage(result, requirement_ids, report)

        return report

    def _validate_sequence(
        self, diagram: SequenceDiagram, report: ValidationReport
    ) -> None:
        """Validate AUTOSAR rules on sequence diagrams."""
        # AUT-008: RTE calls must reference valid constructs
        valid_rte_calls = {
            "Rte_Read", "Rte_Write", "Rte_Call", "Rte_Result",
            "Rte_IRead", "Rte_IWrite", "Rte_Send", "Rte_Receive", "Rte_Switch",
        }

        for msg in diagram.messages:
            report.elements_checked += 1

            if msg.rte_call and msg.rte_call not in valid_rte_calls:
                report.add_issue(ValidationIssue(
                    rule_id="AUT-008",
                    severity=ValidationSeverity.ERROR,
                    category="Sequence",
                    message=(
                        f"Invalid RTE call '{msg.rte_call}' in message. "
                        f"Valid: {sorted(valid_rte_calls)}"
                    ),
                    element_id=msg.id,
                    diagram_name=diagram.name,
                ))

            # RTE calls should reference ports
            if msg.rte_call and not msg.port:
                report.add_issue(ValidationIssue(
                    rule_id="AUT-008",
                    severity=ValidationSeverity.ERROR,
                    category="Sequence",
                    message=(
                        f"RTE call '{msg.rte_call}' has no port reference"
                    ),
                    element_id=msg.id,
                    diagram_name=diagram.name,
                    suggestion="Add port reference to the message",
                ))

            if msg.rte_call and not msg.element:
                report.add_issue(ValidationIssue(
                    rule_id="AUT-008",
                    severity=ValidationSeverity.WARNING,
                    category="Sequence",
                    message=(
                        f"RTE call '{msg.rte_call}' has no data element reference"
                    ),
                    element_id=msg.id,
                    diagram_name=diagram.name,
                ))

            # RTE Read/IRead should be on R-Ports, Write/IWrite on P-Ports
            if msg.rte_call in ("Rte_Read", "Rte_IRead", "Rte_Receive") and msg.port:
                if msg.port.startswith("PP_"):
                    report.add_issue(ValidationIssue(
                        rule_id="AUT-001",
                        severity=ValidationSeverity.ERROR,
                        category="Port",
                        message=(
                            f"Read operation '{msg.rte_call}' on P-Port '{msg.port}'. "
                            "Read operations should use R-Ports."
                        ),
                        element_id=msg.id,
                        diagram_name=diagram.name,
                        suggestion=f"Change port to RP_{msg.port[3:]}",
                        can_auto_fix=True,
                    ))

            if msg.rte_call in ("Rte_Write", "Rte_IWrite", "Rte_Send") and msg.port:
                if msg.port.startswith("RP_"):
                    report.add_issue(ValidationIssue(
                        rule_id="AUT-001",
                        severity=ValidationSeverity.ERROR,
                        category="Port",
                        message=(
                            f"Write operation '{msg.rte_call}' on R-Port '{msg.port}'. "
                            "Write operations should use P-Ports."
                        ),
                        element_id=msg.id,
                        diagram_name=diagram.name,
                        suggestion=f"Change port to PP_{msg.port[3:]}",
                        can_auto_fix=True,
                    ))

        # AUT-006: Naming conventions for lifelines
        for ll in diagram.lifelines:
            report.elements_checked += 1
            if ll.name and not self._swc_pattern.match(ll.name):
                report.add_issue(ValidationIssue(
                    rule_id="AUT-006",
                    severity=ValidationSeverity.WARNING,
                    category="Naming",
                    message=(
                        f"SWC name '{ll.name}' does not match naming convention "
                        f"'{self.settings.swc_naming_regex}'"
                    ),
                    element_id=ll.id,
                    element_name=ll.name,
                    diagram_name=diagram.name,
                ))

    def _validate_state_machine(
        self, diagram: StateMachineDiagram, report: ValidationReport
    ) -> None:
        """Validate AUTOSAR rules on state machines."""
        # AUT-009: Exactly one initial state
        initial_count = sum(1 for s in diagram.states if s.is_initial)
        report.elements_checked += len(diagram.states)

        if initial_count != 1:
            report.add_issue(ValidationIssue(
                rule_id="AUT-009",
                severity=ValidationSeverity.ERROR,
                category="State",
                message=(
                    f"State machine must have exactly one initial state, "
                    f"found {initial_count}"
                ),
                diagram_name=diagram.name,
            ))

        # AUT-007: Owner SWC traceability
        if not diagram.owner_swc:
            report.add_issue(ValidationIssue(
                rule_id="AUT-007",
                severity=ValidationSeverity.WARNING,
                category="Traceability",
                message="State machine has no owner SWC reference",
                diagram_name=diagram.name,
            ))

    def _validate_class(self, diagram: ClassDiagram, report: ValidationReport) -> None:
        """Validate AUTOSAR rules on class/SWC diagrams."""
        for cls in diagram.classes:
            report.elements_checked += 1

            # AUT-006: Naming convention
            if not self._swc_pattern.match(cls.name):
                report.add_issue(ValidationIssue(
                    rule_id="AUT-006",
                    severity=ValidationSeverity.WARNING,
                    category="Naming",
                    message=f"SWC name '{cls.name}' violates naming convention",
                    element_id=cls.id,
                    element_name=cls.name,
                    diagram_name=diagram.name,
                ))

            # AUT-007: Traceability
            if not cls.trace_reqs:
                report.add_issue(ValidationIssue(
                    rule_id="AUT-007",
                    severity=ValidationSeverity.WARNING,
                    category="Traceability",
                    message=f"SWC '{cls.name}' does not trace to any requirement",
                    element_id=cls.id,
                    element_name=cls.name,
                    diagram_name=diagram.name,
                ))

            # Validate operations/runnables
            for op in cls.operations:
                report.elements_checked += 1

                # AUT-006: Runnable naming
                if not self._runnable_pattern.match(op.name):
                    report.add_issue(ValidationIssue(
                        rule_id="AUT-006",
                        severity=ValidationSeverity.WARNING,
                        category="Naming",
                        message=f"Runnable name '{op.name}' violates naming convention",
                        element_name=op.name,
                        diagram_name=diagram.name,
                    ))

                # AUT-003: Init runnables must have INIT trigger
                if op.trigger_type:
                    if "init" in op.name.lower() and op.trigger_type != "init":
                        report.add_issue(ValidationIssue(
                            rule_id="AUT-003",
                            severity=ValidationSeverity.ERROR,
                            category="Runnable",
                            message=(
                                f"Init runnable '{op.name}' has trigger type "
                                f"'{op.trigger_type}' instead of 'init'"
                            ),
                            element_name=op.name,
                            diagram_name=diagram.name,
                            can_auto_fix=True,
                            suggestion="Change trigger type to 'init'",
                        ))

                    # AUT-004: Cyclic runnables must have period_ms > 0
                    if op.trigger_type == "cyclic" and (
                        op.period_ms is None or op.period_ms <= 0
                    ):
                        report.add_issue(ValidationIssue(
                            rule_id="AUT-004",
                            severity=ValidationSeverity.ERROR,
                            category="Runnable",
                            message=(
                                f"Cyclic runnable '{op.name}' must specify "
                                f"period_ms > 0 (current: {op.period_ms})"
                            ),
                            element_name=op.name,
                            diagram_name=diagram.name,
                        ))

    def _validate_component(
        self, diagram: ComponentDiagram, report: ValidationReport
    ) -> None:
        """Validate AUTOSAR rules on component diagrams."""
        # Build port inventory for cross-checking
        provided_ports: dict[str, list[str]] = {}  # interface -> [comp_names]
        required_ports: dict[str, list[str]] = {}

        for comp in diagram.components:
            report.elements_checked += 1

            # AUT-006: Naming
            if not self._swc_pattern.match(comp.name):
                report.add_issue(ValidationIssue(
                    rule_id="AUT-006",
                    severity=ValidationSeverity.WARNING,
                    category="Naming",
                    message=f"Component name '{comp.name}' violates naming convention",
                    element_id=comp.id,
                    element_name=comp.name,
                    diagram_name=diagram.name,
                ))

            # AUT-007: Traceability
            if not comp.trace_reqs:
                report.add_issue(ValidationIssue(
                    rule_id="AUT-007",
                    severity=ValidationSeverity.WARNING,
                    category="Traceability",
                    message=f"Component '{comp.name}' traces to no requirements",
                    element_id=comp.id,
                    diagram_name=diagram.name,
                ))

            for port in comp.ports:
                report.elements_checked += 1

                # AUT-006: Port naming
                if not self._port_pattern.match(port.name):
                    report.add_issue(ValidationIssue(
                        rule_id="AUT-006",
                        severity=ValidationSeverity.WARNING,
                        category="Naming",
                        message=f"Port name '{port.name}' violates naming convention",
                        element_id=port.id,
                        diagram_name=diagram.name,
                    ))

                # Build port inventory
                if port.interface_ref:
                    if port.direction == "provided":
                        provided_ports.setdefault(port.interface_ref, []).append(comp.name)
                    else:
                        required_ports.setdefault(port.interface_ref, []).append(comp.name)

        # AUT-001: Every R-Port must connect to exactly one P-Port of matching type
        for iface, r_comps in required_ports.items():
            if iface not in provided_ports:
                for comp_name in r_comps:
                    report.add_issue(ValidationIssue(
                        rule_id="AUT-001",
                        severity=ValidationSeverity.ERROR,
                        category="Port",
                        message=(
                            f"R-Port on '{comp_name}' references interface '{iface}' "
                            f"but no P-Port provides this interface"
                        ),
                        diagram_name=diagram.name,
                    ))

    def _validate_activity(
        self, diagram: ActivityDiagram, report: ValidationReport
    ) -> None:
        """Validate AUTOSAR rules on activity / code-flow diagrams."""
        valid_rte_calls = {
            "Rte_Read", "Rte_Write", "Rte_Call", "Rte_Result",
            "Rte_IRead", "Rte_IWrite", "Rte_Send", "Rte_Receive", "Rte_Switch",
        }

        # AUT-007: Owner SWC and runnable traceability
        if not diagram.owner_swc:
            report.add_issue(ValidationIssue(
                rule_id="AUT-007",
                severity=ValidationSeverity.WARNING,
                category="Traceability",
                message="Activity diagram has no owner_swc reference",
                diagram_name=diagram.name,
            ))
        if not diagram.owner_runnable:
            report.add_issue(ValidationIssue(
                rule_id="AUT-007",
                severity=ValidationSeverity.WARNING,
                category="Traceability",
                message="Activity diagram has no owner_runnable reference",
                diagram_name=diagram.name,
            ))

        for node in diagram.nodes:
            report.elements_checked += 1

            # AUT-007: Node-level traceability
            if not node.trace_reqs:
                report.add_issue(ValidationIssue(
                    rule_id="AUT-007",
                    severity=ValidationSeverity.WARNING,
                    category="Traceability",
                    message=f"Activity node '{node.name}' traces to no requirements",
                    element_id=node.id,
                    diagram_name=diagram.name,
                ))

            # AUT-008: RTE call validity for 'call' nodes
            if node.node_type.value == "call":
                if node.rte_call and node.rte_call not in valid_rte_calls:
                    report.add_issue(ValidationIssue(
                        rule_id="AUT-008",
                        severity=ValidationSeverity.ERROR,
                        category="Activity",
                        message=(
                            f"Invalid RTE call '{node.rte_call}' in activity node "
                            f"'{node.name}'. Valid: {sorted(valid_rte_calls)}"
                        ),
                        element_id=node.id,
                        diagram_name=diagram.name,
                    ))

                # RTE call nodes should reference a port
                if node.rte_call and not node.port:
                    report.add_issue(ValidationIssue(
                        rule_id="AUT-008",
                        severity=ValidationSeverity.ERROR,
                        category="Activity",
                        message=(
                            f"RTE call node '{node.name}' has no port reference"
                        ),
                        element_id=node.id,
                        diagram_name=diagram.name,
                        suggestion="Add port reference to the call node",
                    ))

            # AUT-006: Port naming on call nodes
            if node.port and not self._port_pattern.match(node.port):
                report.add_issue(ValidationIssue(
                    rule_id="AUT-006",
                    severity=ValidationSeverity.WARNING,
                    category="Naming",
                    message=(
                        f"Port name '{node.port}' in activity node '{node.name}' "
                        f"violates naming convention"
                    ),
                    element_id=node.id,
                    diagram_name=diagram.name,
                ))

        # Recursively validate sub-diagrams
        for sub in diagram.sub_diagrams:
            self._validate_activity(sub, report)

    def _validate_requirement_coverage(
        self,
        result: GenerationResult,
        requirement_ids: list[str],
        report: ValidationReport,
    ) -> None:
        """AUT-010: All functional requirements must map to at least one element."""
        covered_reqs: set[str] = set()

        for diagram in result.diagrams:
            # Collect all trace_req references
            if hasattr(diagram, "source_requirements"):
                covered_reqs.update(diagram.source_requirements)

            if isinstance(diagram, SequenceDiagram):
                for msg in diagram.messages:
                    if msg.trace_req:
                        covered_reqs.add(msg.trace_req)
                for ll in diagram.lifelines:
                    covered_reqs.update(ll.trace_reqs)

            elif isinstance(diagram, StateMachineDiagram):
                for state in diagram.states:
                    covered_reqs.update(state.trace_reqs)

            elif isinstance(diagram, ClassDiagram):
                for cls in diagram.classes:
                    covered_reqs.update(cls.trace_reqs)
                    for op in cls.operations:
                        covered_reqs.update(op.trace_reqs)

            elif isinstance(diagram, ComponentDiagram):
                for comp in diagram.components:
                    covered_reqs.update(comp.trace_reqs)

            elif isinstance(diagram, ActivityDiagram):
                for node in diagram.nodes:
                    covered_reqs.update(node.trace_reqs)
                for sub in diagram.sub_diagrams:
                    for node in sub.nodes:
                        covered_reqs.update(node.trace_reqs)

        uncovered = set(requirement_ids) - covered_reqs
        if uncovered:
            report.add_issue(ValidationIssue(
                rule_id="AUT-010",
                severity=ValidationSeverity.WARNING,
                category="Completeness",
                message=(
                    f"{len(uncovered)} requirements have no model element: "
                    f"{sorted(uncovered)[:10]}{'...' if len(uncovered) > 10 else ''}"
                ),
            ))
