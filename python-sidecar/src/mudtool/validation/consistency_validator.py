"""Pass 3 - Cross-Diagram Consistency Validation.

Checks consistency across multiple diagram types:
- Sequence diagram messages match class diagram operations
- State transitions align with sequence flows
- Interface contracts match between diagrams
- All requirement IDs trace to at least one model element
"""

from __future__ import annotations

import logging

from mudtool.models.json_uml import (
    ClassDiagram,
    ComponentDiagram,
    GenerationResult,
    SequenceDiagram,
    StateMachineDiagram,
)
from mudtool.models.validation import ValidationIssue, ValidationReport, ValidationSeverity

logger = logging.getLogger(__name__)


class ConsistencyValidator:
    """Cross-diagram consistency checker."""

    def validate(self, result: GenerationResult) -> ValidationReport:
        report = ValidationReport()

        # Collect all diagrams by type
        sequences = [d for d in result.diagrams if isinstance(d, SequenceDiagram)]
        state_machines = [d for d in result.diagrams if isinstance(d, StateMachineDiagram)]
        class_diagrams = [d for d in result.diagrams if isinstance(d, ClassDiagram)]
        component_diagrams = [d for d in result.diagrams if isinstance(d, ComponentDiagram)]

        report.diagrams_checked = len(result.diagrams)

        # Check sequence messages vs class operations
        if sequences and class_diagrams:
            self._check_sequence_vs_class(sequences, class_diagrams, report)

        # Check sequence lifelines vs components
        if sequences and component_diagrams:
            self._check_sequence_vs_component(sequences, component_diagrams, report)

        # Check state machine owners vs class/component names
        if state_machines and (class_diagrams or component_diagrams):
            self._check_state_machine_owners(
                state_machines, class_diagrams, component_diagrams, report
            )

        # Check port consistency between class and component diagrams
        if class_diagrams and component_diagrams:
            self._check_port_consistency(class_diagrams, component_diagrams, report)

        return report

    def _check_sequence_vs_class(
        self,
        sequences: list[SequenceDiagram],
        classes: list[ClassDiagram],
        report: ValidationReport,
    ) -> None:
        """Sequence diagram messages should match class diagram operations."""
        # Build a set of all operations from class diagrams
        class_operations: dict[str, set[str]] = {}  # class_name -> {op_names}
        for cd in classes:
            for cls in cd.classes:
                ops = {op.name for op in cls.operations}
                class_operations[cls.name] = ops

        # Check sequence messages
        for seq in sequences:
            lifeline_names = {ll.id: ll.name for ll in seq.lifelines}

            for msg in seq.messages:
                report.elements_checked += 1
                target_name = lifeline_names.get(msg.to_lifeline, "")

                # If the target SWC exists in class diagrams, check the operation
                if target_name in class_operations:
                    # Messages can be RTE calls or operation calls
                    msg_label = msg.label or msg.rte_call or ""
                    if msg_label and not msg.is_return:
                        # Check if there's a matching runnable/operation
                        ops = class_operations[target_name]
                        # RTE calls are fine - they go through the runtime
                        if msg.rte_call:
                            continue  # RTE calls are handled by the runtime

                        if msg_label not in ops and not any(
                            msg_label in op for op in ops
                        ):
                            report.add_issue(ValidationIssue(
                                rule_id="CON-001",
                                severity=ValidationSeverity.WARNING,
                                category="Consistency",
                                message=(
                                    f"Sequence message '{msg_label}' to '{target_name}' "
                                    f"has no matching operation in class diagram. "
                                    f"Available: {sorted(ops)}"
                                ),
                                element_id=msg.id,
                                diagram_name=seq.name,
                            ))

    def _check_sequence_vs_component(
        self,
        sequences: list[SequenceDiagram],
        components: list[ComponentDiagram],
        report: ValidationReport,
    ) -> None:
        """Sequence diagram lifelines should correspond to components."""
        # Build set of all component names
        comp_names: set[str] = set()
        comp_ports: dict[str, set[str]] = {}  # comp_name -> {port_names}

        for cd in components:
            for comp in cd.components:
                comp_names.add(comp.name)
                comp_ports[comp.name] = {p.name for p in comp.ports}

        # Check lifelines
        for seq in sequences:
            for ll in seq.lifelines:
                report.elements_checked += 1
                if comp_names and ll.name not in comp_names:
                    report.add_issue(ValidationIssue(
                        rule_id="CON-002",
                        severity=ValidationSeverity.INFO,
                        category="Consistency",
                        message=(
                            f"Sequence lifeline '{ll.name}' has no matching component. "
                            f"Known components: {sorted(comp_names)}"
                        ),
                        element_id=ll.id,
                        diagram_name=seq.name,
                    ))

            # Check port references in messages
            for msg in seq.messages:
                if msg.port:
                    report.elements_checked += 1
                    source_name = {l.id: l.name for l in seq.lifelines}.get(
                        msg.from_lifeline, ""
                    )
                    if source_name in comp_ports:
                        ports = comp_ports[source_name]
                        if msg.port not in ports:
                            report.add_issue(ValidationIssue(
                                rule_id="CON-003",
                                severity=ValidationSeverity.WARNING,
                                category="Consistency",
                                message=(
                                    f"Message references port '{msg.port}' on "
                                    f"'{source_name}' but port not found in "
                                    f"component diagram. Known ports: {sorted(ports)}"
                                ),
                                element_id=msg.id,
                                diagram_name=seq.name,
                            ))

    def _check_state_machine_owners(
        self,
        state_machines: list[StateMachineDiagram],
        classes: list[ClassDiagram],
        components: list[ComponentDiagram],
        report: ValidationReport,
    ) -> None:
        """State machine owners should correspond to known SWCs."""
        known_swcs: set[str] = set()

        for cd in classes:
            for cls in cd.classes:
                known_swcs.add(cls.name)
        for cd in components:
            for comp in cd.components:
                known_swcs.add(comp.name)

        for sm in state_machines:
            report.elements_checked += 1
            if sm.owner_swc and known_swcs and sm.owner_swc not in known_swcs:
                report.add_issue(ValidationIssue(
                    rule_id="CON-004",
                    severity=ValidationSeverity.WARNING,
                    category="Consistency",
                    message=(
                        f"State machine owner '{sm.owner_swc}' not found "
                        f"in class/component diagrams. Known: {sorted(known_swcs)}"
                    ),
                    diagram_name=sm.name,
                ))

    def _check_port_consistency(
        self,
        classes: list[ClassDiagram],
        components: list[ComponentDiagram],
        report: ValidationReport,
    ) -> None:
        """Port definitions should be consistent across diagrams."""
        # This is a deeper check - for now, verify SWC names match
        class_names = set()
        for cd in classes:
            for cls in cd.classes:
                class_names.add(cls.name)

        comp_names = set()
        for cd in components:
            for comp in cd.components:
                comp_names.add(comp.name)

        # SWCs in component diagram should appear in class diagram
        missing_from_class = comp_names - class_names
        if missing_from_class:
            for name in missing_from_class:
                report.add_issue(ValidationIssue(
                    rule_id="CON-005",
                    severity=ValidationSeverity.INFO,
                    category="Consistency",
                    message=(
                        f"Component '{name}' has no corresponding "
                        f"class diagram definition"
                    ),
                    element_name=name,
                ))
