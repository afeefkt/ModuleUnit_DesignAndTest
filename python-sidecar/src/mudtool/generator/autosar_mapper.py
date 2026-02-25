"""AUTOSAR Mapper - enriches generic UML elements with AUTOSAR semantics.

Stage 4 of the pipeline: Post-Processing & AUTOSAR Mapping.

Responsibilities:
- Classes -> Application SWCs with correct swc_type
- Operations -> Runnables with correct trigger types
- Associations -> Port connections with proper direction and interface type
- Naming convention enforcement
- Data type mapping to AUTOSAR primitives
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from mudtool.config.settings import Settings
from mudtool.models.autosar import (
    ApplicationSWC,
    ClientServerInterface,
    DataAccess,
    DataElement,
    InterfaceType,
    Port,
    PortDirection,
    Runnable,
    SenderReceiverInterface,
    SWCType,
    TriggerType,
)
from mudtool.models.json_uml import (
    AnyDiagram,
    ClassDiagram,
    ClassElement,
    ComponentDiagram,
    ComponentElement,
    GenerationResult,
    Lifeline,
    Message,
    SequenceDiagram,
    StateMachineDiagram,
)

logger = logging.getLogger(__name__)


class AUTOSARMapper:
    """Maps generic UML/JSON-UML elements to AUTOSAR-specific constructs.

    This mapper enforces AUTOSAR semantics and naming conventions on
    AI-generated models before they undergo validation.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._swc_pattern = re.compile(settings.swc_naming_regex)
        self._runnable_pattern = re.compile(settings.runnable_naming_regex)
        self._port_pattern = re.compile(settings.port_naming_regex)

    def map_generation_result(self, result: GenerationResult) -> GenerationResult:
        """Apply AUTOSAR mapping to all diagrams in a generation result.

        This is the main entry point - call after AI generation, before validation.
        """
        mapped_diagrams = []
        for diagram in result.diagrams:
            try:
                mapped = self.map_diagram(diagram)
                mapped_diagrams.append(mapped)
            except Exception as e:
                logger.error(f"Failed to map diagram: {e}")
                result.warnings.append(f"AUTOSAR mapping failed for diagram: {e}")
                mapped_diagrams.append(diagram)  # Keep original

        result.diagrams = mapped_diagrams
        return result

    def map_diagram(self, diagram: AnyDiagram) -> AnyDiagram:
        """Map a single diagram to AUTOSAR semantics."""
        if isinstance(diagram, SequenceDiagram):
            return self._map_sequence_diagram(diagram)
        elif isinstance(diagram, StateMachineDiagram):
            return self._map_state_machine(diagram)
        elif isinstance(diagram, ClassDiagram):
            return self._map_class_diagram(diagram)
        elif isinstance(diagram, ComponentDiagram):
            return self._map_component_diagram(diagram)
        return diagram

    def _map_sequence_diagram(self, diagram: SequenceDiagram) -> SequenceDiagram:
        """Map sequence diagram elements to AUTOSAR semantics."""
        # Map lifelines to AUTOSAR SWCs
        for lifeline in diagram.lifelines:
            lifeline.name = self._enforce_swc_naming(lifeline.name)
            if not lifeline.type or lifeline.type == "Class":
                lifeline.type = "ApplicationSWC"
            if lifeline.runnable:
                lifeline.runnable = self._enforce_runnable_naming(lifeline.runnable)

        # Map messages to RTE calls
        for msg in diagram.messages:
            if msg.rte_call:
                msg.rte_call = self._normalize_rte_call(msg.rte_call)
            if msg.port:
                msg.port = self._enforce_port_naming(msg.port, is_provided=not msg.is_return)

            # Generate label from RTE call info
            if msg.rte_call and msg.port and msg.element and not msg.label:
                msg.label = f"{msg.rte_call}({msg.port}, {msg.element})"

        return diagram

    def _map_state_machine(self, diagram: StateMachineDiagram) -> StateMachineDiagram:
        """Map state machine elements to AUTOSAR mode management."""
        if diagram.owner_swc:
            diagram.owner_swc = self._enforce_swc_naming(diagram.owner_swc)

        # Ensure state names follow conventions (UPPER_CASE for modes)
        for state in diagram.states:
            if not state.is_initial and not state.is_final:
                # AUTOSAR mode names are typically UPPER_CASE
                if not state.name.isupper():
                    state.name = state.name.upper().replace(" ", "_")

        return diagram

    def _map_class_diagram(self, diagram: ClassDiagram) -> ClassDiagram:
        """Map class diagram elements to AUTOSAR SWCs."""
        for cls in diagram.classes:
            cls.name = self._enforce_swc_naming(cls.name)
            if not cls.stereotype:
                cls.stereotype = "ApplicationSWC"

            # Map operations to Runnables
            for op in cls.operations:
                op.name = self._enforce_runnable_naming(op.name)
                # Infer trigger type from name or description
                if not op.trigger_type:
                    op.trigger_type = self._infer_trigger_type(op.name, op.description)

        return diagram

    def _map_component_diagram(self, diagram: ComponentDiagram) -> ComponentDiagram:
        """Map component diagram elements to AUTOSAR architecture."""
        for comp in diagram.components:
            comp.name = self._enforce_swc_naming(comp.name)
            if not comp.stereotype:
                comp.stereotype = "ApplicationSWC"

            for port in comp.ports:
                is_provided = port.direction == "provided"
                port.name = self._enforce_port_naming(port.name, is_provided)

        return diagram

    # ──────────────────────────────────────────────
    # Naming Convention Enforcement
    # ──────────────────────────────────────────────

    def _enforce_swc_naming(self, name: str) -> str:
        """Ensure SWC name follows AUTOSAR convention: SWC_PascalCase."""
        if self._swc_pattern.match(name):
            return name

        # Strip common prefixes
        clean = name.replace("SWC_", "").replace("swc_", "")
        clean = clean.replace(" ", "_")

        # Convert to PascalCase
        parts = clean.split("_")
        pascal = "".join(p.capitalize() for p in parts if p)

        return f"SWC_{pascal}"

    def _enforce_runnable_naming(self, name: str) -> str:
        """Ensure Runnable name follows convention: RE_PascalCase."""
        if self._runnable_pattern.match(name):
            return name

        clean = name.replace("RE_", "").replace("re_", "")
        clean = clean.replace(" ", "_")

        parts = clean.split("_")
        pascal = "".join(p.capitalize() for p in parts if p)

        return f"RE_{pascal}"

    def _enforce_port_naming(self, name: str, is_provided: bool = True) -> str:
        """Ensure port name follows convention: PP_Name or RP_Name."""
        if self._port_pattern.match(name):
            return name

        # Remove existing prefixes
        clean = name
        for prefix in ("PP_", "RP_", "pp_", "rp_", "P_", "R_"):
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break

        clean = clean.replace(" ", "_")
        parts = clean.split("_")
        pascal = "".join(p.capitalize() for p in parts if p)

        prefix = "PP" if is_provided else "RP"
        return f"{prefix}_{pascal}"

    def _normalize_rte_call(self, rte_call: str) -> str:
        """Normalize RTE API call name."""
        mapping = {
            "rte_read": "Rte_Read",
            "rte_write": "Rte_Write",
            "rte_call": "Rte_Call",
            "rte_result": "Rte_Result",
            "rte_send": "Rte_Send",
            "rte_receive": "Rte_Receive",
            "rte_iread": "Rte_IRead",
            "rte_iwrite": "Rte_IWrite",
            "rte_switch": "Rte_Switch",
        }
        return mapping.get(rte_call.lower(), rte_call)

    def _infer_trigger_type(
        self, name: str, description: Optional[str] = None
    ) -> str:
        """Infer AUTOSAR runnable trigger type from name/description."""
        name_lower = name.lower()
        desc_lower = (description or "").lower()
        combined = f"{name_lower} {desc_lower}"

        if any(kw in combined for kw in ["init", "initialize", "startup", "setup"]):
            return TriggerType.INIT.value
        if any(kw in combined for kw in ["cyclic", "periodic", "cycle", "main"]):
            return TriggerType.CYCLIC.value
        if any(kw in combined for kw in ["receive", "reception", "on_data", "callback"]):
            return TriggerType.ON_DATA_RECEPTION.value
        if any(kw in combined for kw in ["mode", "switch", "transition"]):
            return TriggerType.ON_MODE_SWITCH.value

        return TriggerType.CYCLIC.value  # Default to cyclic

    # ──────────────────────────────────────────────
    # Extract AUTOSAR entities from diagrams
    # ──────────────────────────────────────────────

    def extract_swcs(self, result: GenerationResult) -> list[ApplicationSWC]:
        """Extract AUTOSAR SWC definitions from generated diagrams."""
        swc_map: dict[str, ApplicationSWC] = {}

        for diagram in result.diagrams:
            if isinstance(diagram, ClassDiagram):
                for cls in diagram.classes:
                    swc = self._class_to_swc(cls)
                    if swc.name in swc_map:
                        self._merge_swc(swc_map[swc.name], swc)
                    else:
                        swc_map[swc.name] = swc

            elif isinstance(diagram, ComponentDiagram):
                for comp in diagram.components:
                    swc = self._component_to_swc(comp)
                    if swc.name in swc_map:
                        self._merge_swc(swc_map[swc.name], swc)
                    else:
                        swc_map[swc.name] = swc

        return list(swc_map.values())

    def _class_to_swc(self, cls: ClassElement) -> ApplicationSWC:
        """Convert a class element to an ApplicationSWC."""
        runnables = []
        for op in cls.operations:
            trigger = TriggerType(op.trigger_type) if op.trigger_type else TriggerType.CYCLIC
            runnables.append(Runnable(
                name=op.name,
                trigger=trigger,
                period_ms=op.period_ms,
                description=op.description,
                trace_reqs=op.trace_reqs,
            ))

        return ApplicationSWC(
            name=cls.name,
            swc_type=self._infer_swc_type(cls.stereotype),
            runnables=runnables,
            trace_reqs=cls.trace_reqs,
        )

    def _component_to_swc(self, comp: ComponentElement) -> ApplicationSWC:
        """Convert a component element to an ApplicationSWC."""
        ports = []
        for p in comp.ports:
            ports.append(Port(
                name=p.name,
                direction=PortDirection.PROVIDED if p.direction == "provided" else PortDirection.REQUIRED,
                interface_ref=p.interface_ref or "UNDEFINED",
                interface_type=InterfaceType(p.interface_type) if p.interface_type else InterfaceType.SENDER_RECEIVER,
            ))

        return ApplicationSWC(
            name=comp.name,
            swc_type=self._infer_swc_type(comp.stereotype),
            ports=ports,
            trace_reqs=comp.trace_reqs,
        )

    def _infer_swc_type(self, stereotype: Optional[str]) -> SWCType:
        """Infer SWC type from stereotype."""
        if not stereotype:
            return SWCType.APPLICATION
        s = stereotype.lower()
        if "sensor" in s or "actuator" in s:
            return SWCType.SENSOR_ACTUATOR
        if "service" in s:
            return SWCType.SERVICE
        if "composition" in s:
            return SWCType.COMPOSITION
        return SWCType.APPLICATION

    def _merge_swc(self, target: ApplicationSWC, source: ApplicationSWC) -> None:
        """Merge source SWC info into target (combine ports, runnables, etc.)."""
        existing_port_names = {p.name for p in target.ports}
        for port in source.ports:
            if port.name not in existing_port_names:
                target.ports.append(port)

        existing_runnable_names = {r.name for r in target.runnables}
        for runnable in source.runnables:
            if runnable.name not in existing_runnable_names:
                target.runnables.append(runnable)

        for req_id in source.trace_reqs:
            if req_id not in target.trace_reqs:
                target.trace_reqs.append(req_id)
