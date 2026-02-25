"""Pass 1 - Structural Validation.

UML metamodel conformance checks:
- Valid element types
- Correct multiplicities
- No orphan elements
- Required fields present
"""

from __future__ import annotations

import logging

from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityNodeType,
    AnyDiagram,
    ClassDiagram,
    ComponentDiagram,
    GenerationResult,
    SequenceDiagram,
    StateMachineDiagram,
)
from mudtool.models.validation import ValidationIssue, ValidationReport, ValidationSeverity

logger = logging.getLogger(__name__)


class StructuralValidator:
    """Validates UML metamodel conformance of generated diagrams."""

    def validate(self, result: GenerationResult) -> ValidationReport:
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

        return report

    def _validate_sequence(
        self, diagram: SequenceDiagram, report: ValidationReport
    ) -> None:
        """Validate sequence diagram structural integrity."""
        lifeline_ids = {ll.id for ll in diagram.lifelines}
        report.elements_checked += len(diagram.lifelines) + len(diagram.messages)

        # Check lifelines have names
        for ll in diagram.lifelines:
            if not ll.name:
                report.add_issue(ValidationIssue(
                    rule_id="STR-001",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Lifeline '{ll.id}' has no name",
                    element_id=ll.id,
                    diagram_name=diagram.name,
                ))

            if not ll.id:
                report.add_issue(ValidationIssue(
                    rule_id="STR-002",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message="Lifeline has no ID",
                    element_name=ll.name,
                    diagram_name=diagram.name,
                ))

        # Check messages reference valid lifelines
        for msg in diagram.messages:
            if msg.from_lifeline not in lifeline_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-003",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=(
                        f"Message references non-existent source lifeline "
                        f"'{msg.from_lifeline}'"
                    ),
                    element_id=msg.id,
                    diagram_name=diagram.name,
                    suggestion=f"Valid lifeline IDs: {sorted(lifeline_ids)}",
                ))

            if msg.to_lifeline not in lifeline_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-003",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=(
                        f"Message references non-existent target lifeline "
                        f"'{msg.to_lifeline}'"
                    ),
                    element_id=msg.id,
                    diagram_name=diagram.name,
                ))

            # Self-message check (warning, not error)
            if msg.from_lifeline == msg.to_lifeline and not msg.is_return:
                report.add_issue(ValidationIssue(
                    rule_id="STR-004",
                    severity=ValidationSeverity.INFO,
                    category="Structural",
                    message=f"Self-message detected on lifeline '{msg.from_lifeline}'",
                    element_id=msg.id,
                    diagram_name=diagram.name,
                ))

        # Check for orphan lifelines (no messages)
        referenced = set()
        for msg in diagram.messages:
            referenced.add(msg.from_lifeline)
            referenced.add(msg.to_lifeline)

        for ll in diagram.lifelines:
            if ll.id not in referenced:
                report.add_issue(ValidationIssue(
                    rule_id="STR-005",
                    severity=ValidationSeverity.WARNING,
                    category="Structural",
                    message=f"Lifeline '{ll.name}' ({ll.id}) has no messages",
                    element_id=ll.id,
                    diagram_name=diagram.name,
                ))

    def _validate_state_machine(
        self, diagram: StateMachineDiagram, report: ValidationReport
    ) -> None:
        """Validate state machine structural integrity."""
        state_ids = {s.id for s in diagram.states}
        report.elements_checked += len(diagram.states) + len(diagram.transitions)

        # Check for initial state
        initial_states = [s for s in diagram.states if s.is_initial]
        if len(initial_states) == 0:
            report.add_issue(ValidationIssue(
                rule_id="STR-006",
                severity=ValidationSeverity.ERROR,
                category="Structural",
                message="State machine has no initial state",
                diagram_name=diagram.name,
            ))
        elif len(initial_states) > 1:
            report.add_issue(ValidationIssue(
                rule_id="STR-006",
                severity=ValidationSeverity.ERROR,
                category="Structural",
                message=f"State machine has {len(initial_states)} initial states (must be exactly 1)",
                diagram_name=diagram.name,
            ))

        # Check states have names
        for state in diagram.states:
            if not state.name and not state.is_initial and not state.is_final:
                report.add_issue(ValidationIssue(
                    rule_id="STR-007",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"State '{state.id}' has no name",
                    element_id=state.id,
                    diagram_name=diagram.name,
                ))

        # Check transitions reference valid states
        for trans in diagram.transitions:
            if trans.source not in state_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-008",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Transition references non-existent source state '{trans.source}'",
                    element_id=trans.id,
                    diagram_name=diagram.name,
                ))
            if trans.target not in state_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-008",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Transition references non-existent target state '{trans.target}'",
                    element_id=trans.id,
                    diagram_name=diagram.name,
                ))

        # Check for unreachable states
        reachable = set()
        for trans in diagram.transitions:
            reachable.add(trans.target)
        for s in initial_states:
            reachable.add(s.id)

        for state in diagram.states:
            if state.id not in reachable and not state.is_initial:
                report.add_issue(ValidationIssue(
                    rule_id="STR-009",
                    severity=ValidationSeverity.WARNING,
                    category="Structural",
                    message=f"State '{state.name}' may be unreachable",
                    element_id=state.id,
                    diagram_name=diagram.name,
                ))

    def _validate_class(self, diagram: ClassDiagram, report: ValidationReport) -> None:
        """Validate class diagram structural integrity."""
        class_ids = {c.id for c in diagram.classes}
        report.elements_checked += len(diagram.classes) + len(diagram.associations)

        for cls in diagram.classes:
            if not cls.name:
                report.add_issue(ValidationIssue(
                    rule_id="STR-010",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Class '{cls.id}' has no name",
                    element_id=cls.id,
                    diagram_name=diagram.name,
                ))

            # Check for duplicate attribute names
            attr_names = [a.name for a in cls.attributes]
            if len(attr_names) != len(set(attr_names)):
                report.add_issue(ValidationIssue(
                    rule_id="STR-011",
                    severity=ValidationSeverity.WARNING,
                    category="Structural",
                    message=f"Class '{cls.name}' has duplicate attribute names",
                    element_id=cls.id,
                    diagram_name=diagram.name,
                ))

            # Check for duplicate operation names
            op_names = [o.name for o in cls.operations]
            if len(op_names) != len(set(op_names)):
                report.add_issue(ValidationIssue(
                    rule_id="STR-011",
                    severity=ValidationSeverity.WARNING,
                    category="Structural",
                    message=f"Class '{cls.name}' has duplicate operation names",
                    element_id=cls.id,
                    diagram_name=diagram.name,
                ))

        # Check associations
        for assoc in diagram.associations:
            if assoc.source not in class_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-012",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Association references non-existent source class '{assoc.source}'",
                    element_id=assoc.id,
                    diagram_name=diagram.name,
                ))
            if assoc.target not in class_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-012",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Association references non-existent target class '{assoc.target}'",
                    element_id=assoc.id,
                    diagram_name=diagram.name,
                ))

    def _validate_component(
        self, diagram: ComponentDiagram, report: ValidationReport
    ) -> None:
        """Validate component diagram structural integrity."""
        comp_ids = {c.id for c in diagram.components}
        report.elements_checked += len(diagram.components) + len(diagram.connectors)

        for comp in diagram.components:
            if not comp.name:
                report.add_issue(ValidationIssue(
                    rule_id="STR-013",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Component '{comp.id}' has no name",
                    element_id=comp.id,
                    diagram_name=diagram.name,
                ))

            # Check ports have valid direction
            for port in comp.ports:
                if port.direction not in ("provided", "required"):
                    report.add_issue(ValidationIssue(
                        rule_id="STR-014",
                        severity=ValidationSeverity.ERROR,
                        category="Structural",
                        message=(
                            f"Port '{port.name}' on '{comp.name}' has invalid "
                            f"direction '{port.direction}'"
                        ),
                        element_id=port.id,
                        diagram_name=diagram.name,
                    ))

        # Validate connectors
        for conn in diagram.connectors:
            if conn.source_component not in comp_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-015",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Connector references non-existent source '{conn.source_component}'",
                    element_id=conn.id,
                    diagram_name=diagram.name,
                ))
            if conn.target_component not in comp_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-015",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Connector references non-existent target '{conn.target_component}'",
                    element_id=conn.id,
                    diagram_name=diagram.name,
                ))

    def _validate_activity(
        self, diagram: ActivityDiagram, report: ValidationReport
    ) -> None:
        """Validate activity / code-flow diagram structural integrity."""
        node_ids = {n.id for n in diagram.nodes}
        report.elements_checked += len(diagram.nodes) + len(diagram.edges)

        # STR-020: Must have exactly 1 initial and ≥1 final node
        initial_nodes = [
            n for n in diagram.nodes
            if n.node_type == ActivityNodeType.INITIAL
        ]
        final_nodes = [
            n for n in diagram.nodes
            if n.node_type == ActivityNodeType.FINAL
        ]

        if len(initial_nodes) == 0:
            report.add_issue(ValidationIssue(
                rule_id="STR-020",
                severity=ValidationSeverity.ERROR,
                category="Structural",
                message="Activity diagram has no initial node",
                diagram_name=diagram.name,
            ))
        elif len(initial_nodes) > 1:
            report.add_issue(ValidationIssue(
                rule_id="STR-020",
                severity=ValidationSeverity.ERROR,
                category="Structural",
                message=f"Activity diagram has {len(initial_nodes)} initial nodes (must be exactly 1)",
                diagram_name=diagram.name,
            ))

        if len(final_nodes) == 0:
            report.add_issue(ValidationIssue(
                rule_id="STR-020",
                severity=ValidationSeverity.WARNING,
                category="Structural",
                message="Activity diagram has no final node",
                diagram_name=diagram.name,
            ))

        # STR-021: Decision nodes must have ≥2 outgoing edges
        outgoing_count: dict[str, int] = {}
        for edge in diagram.edges:
            outgoing_count[edge.source] = outgoing_count.get(edge.source, 0) + 1

        for node in diagram.nodes:
            if node.node_type == ActivityNodeType.DECISION:
                out = outgoing_count.get(node.id, 0)
                if out < 2:
                    report.add_issue(ValidationIssue(
                        rule_id="STR-021",
                        severity=ValidationSeverity.ERROR,
                        category="Structural",
                        message=(
                            f"Decision node '{node.name}' ({node.id}) has "
                            f"{out} outgoing edge(s), needs ≥2"
                        ),
                        element_id=node.id,
                        diagram_name=diagram.name,
                        suggestion="Every decision must branch into at least 2 paths",
                    ))

        # STR-022: Edge source and target must reference valid node IDs
        for edge in diagram.edges:
            if edge.source not in node_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-022",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Edge '{edge.id}' references non-existent source node '{edge.source}'",
                    element_id=edge.id,
                    diagram_name=diagram.name,
                ))
            if edge.target not in node_ids:
                report.add_issue(ValidationIssue(
                    rule_id="STR-022",
                    severity=ValidationSeverity.ERROR,
                    category="Structural",
                    message=f"Edge '{edge.id}' references non-existent target node '{edge.target}'",
                    element_id=edge.id,
                    diagram_name=diagram.name,
                ))

        # STR-023: Check for orphan nodes (not initial and not reachable)
        reachable: set[str] = set()
        for edge in diagram.edges:
            reachable.add(edge.target)
        for n in initial_nodes:
            reachable.add(n.id)

        for node in diagram.nodes:
            if node.id not in reachable and node.node_type != ActivityNodeType.INITIAL:
                report.add_issue(ValidationIssue(
                    rule_id="STR-023",
                    severity=ValidationSeverity.WARNING,
                    category="Structural",
                    message=f"Activity node '{node.name}' ({node.id}) may be unreachable",
                    element_id=node.id,
                    diagram_name=diagram.name,
                ))
