"""JSON-UML schema models - the AI interchange format.

These models define the strict JSON schema that the AI produces and the generator
consumes. They enforce AUTOSAR semantics at the output level, reducing post-processing
errors. Each diagram type has its own schema.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, model_validator


class DiagramType(str, Enum):
    """Supported UML diagram types."""
    SEQUENCE = "sequence"
    STATE_MACHINE = "state_machine"
    CLASS = "class"
    COMPONENT = "component"
    ACTIVITY = "activity"


# ──────────────────────────────────────────────
# Provenance (attached to every AI output)
# ──────────────────────────────────────────────

class Provenance(BaseModel):
    """Provenance metadata tracking AI generation details."""
    ai_model: str = Field(..., description="AI model used (e.g., claude-sonnet-4-5)")
    prompt_version: str = Field(..., description="Prompt template version (e.g., seq-v3.2)")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    prompt_hash: Optional[str] = Field(None, description="SHA-256 hash of rendered prompt")
    generation_time_ms: Optional[int] = None
    backend: Optional[str] = Field(None, description="local or cloud")


# ──────────────────────────────────────────────
# Sequence Diagram Elements
# ──────────────────────────────────────────────

class Lifeline(BaseModel):
    """A lifeline in a sequence diagram - maps to an AUTOSAR SWC/Runnable."""
    id: str
    name: str = Field(..., description="SWC or module name")
    type: str = Field("ApplicationSWC", description="AUTOSAR entity type")
    runnable: Optional[str] = Field(None, description="Runnable entity name if applicable")
    stereotype: Optional[str] = None
    trace_reqs: list[str] = Field(default_factory=list)


class Fragment(BaseModel):
    """Combined fragment (alt, loop, opt, par) in sequence diagram."""
    fragment_type: str = Field(..., description="alt | loop | opt | par | break")
    condition: Optional[str] = Field(None, description="Guard condition")
    message_refs: list[str] = Field(default_factory=list, description="IDs of messages inside")


class Message(BaseModel):
    """A message in a sequence diagram - maps to an AUTOSAR RTE call."""
    id: str = Field(default="")
    from_lifeline: str = Field(..., alias="from", description="Source lifeline ID")
    to_lifeline: str = Field(..., alias="to", description="Target lifeline ID")
    label: Optional[str] = Field(None, description="Message label for display")
    rte_call: Optional[str] = Field(None, description="RTE API call type")
    port: Optional[str] = Field(None, description="Port name")
    element: Optional[str] = Field(None, description="Data element or operation name")
    is_return: bool = Field(False, description="Whether this is a return message")
    is_async: bool = Field(False, description="Whether this is asynchronous")
    sequence_number: Optional[int] = None
    trace_req: Optional[str] = Field(None, description="Requirement ID this message traces to")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    model_config = {"populate_by_name": True}


class SequenceDiagram(BaseModel):
    """Complete sequence diagram in JSON-UML format."""
    diagram_type: DiagramType = DiagramType.SEQUENCE
    name: str = Field("", description="Diagram name")
    description: Optional[str] = None
    source_requirements: list[str] = Field(default_factory=list)
    lifelines: list[Lifeline] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    fragments: list[Fragment] = Field(default_factory=list)
    provenance: Optional[Provenance] = None


# ──────────────────────────────────────────────
# State Machine Diagram Elements
# ──────────────────────────────────────────────

class StateAction(BaseModel):
    """An action within a state (entry, do, exit)."""
    action_type: str = Field(..., description="entry | do | exit")
    description: str = ""
    rte_call: Optional[str] = None


class State(BaseModel):
    """A state in a state machine diagram."""
    id: str
    name: str
    is_initial: bool = False
    is_final: bool = False
    state_type: str = Field("simple", description="simple | composite | submachine")
    actions: list[StateAction] = Field(default_factory=list)
    substates: list[State] = Field(default_factory=list)
    trace_reqs: list[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class Guard(BaseModel):
    """A guard condition on a transition."""
    condition: str
    description: Optional[str] = None


class Transition(BaseModel):
    """A transition between states."""
    id: str = ""
    source: str = Field(..., description="Source state ID")
    target: str = Field(..., description="Target state ID")
    trigger: Optional[str] = Field(None, description="Event that triggers transition")
    guard: Optional[Guard] = None
    action: Optional[str] = Field(None, description="Action performed during transition")
    trace_req: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class StateMachineDiagram(BaseModel):
    """Complete state machine diagram in JSON-UML format."""
    diagram_type: DiagramType = DiagramType.STATE_MACHINE
    name: str = ""
    description: Optional[str] = None
    source_requirements: list[str] = Field(default_factory=list)
    owner_swc: Optional[str] = Field(None, description="Owning SWC name")
    states: list[State] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)
    provenance: Optional[Provenance] = None


# ──────────────────────────────────────────────
# Class / Module Diagram Elements
# ──────────────────────────────────────────────

class Visibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    PACKAGE = "package"


class ClassAttribute(BaseModel):
    """An attribute of a class/SWC."""
    name: str
    data_type: str
    visibility: Visibility = Visibility.PRIVATE
    is_static: bool = False
    default_value: Optional[str] = None
    description: Optional[str] = None


class ClassOperation(BaseModel):
    """An operation/method of a class - maps to a Runnable."""
    name: str
    return_type: Optional[str] = None
    parameters: list[dict] = Field(default_factory=list)
    visibility: Visibility = Visibility.PUBLIC
    is_static: bool = False
    trigger_type: Optional[str] = Field(None, description="AUTOSAR trigger type if runnable")
    period_ms: Optional[float] = None
    description: Optional[str] = None
    trace_reqs: list[str] = Field(default_factory=list)


class ClassElement(BaseModel):
    """A class element in a class diagram - maps to an AUTOSAR SWC."""
    id: str
    name: str
    stereotype: Optional[str] = Field(None, description="AUTOSAR stereotype (ApplicationSWC, etc.)")
    attributes: list[ClassAttribute] = Field(default_factory=list)
    operations: list[ClassOperation] = Field(default_factory=list)
    trace_reqs: list[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class AssociationType(str, Enum):
    ASSOCIATION = "association"
    AGGREGATION = "aggregation"
    COMPOSITION = "composition"
    DEPENDENCY = "dependency"
    REALIZATION = "realization"


class Association(BaseModel):
    """An association between class elements."""
    id: str = ""
    source: str = Field(..., description="Source class ID")
    target: str = Field(..., description="Target class ID")
    association_type: AssociationType = AssociationType.ASSOCIATION
    source_role: Optional[str] = None
    target_role: Optional[str] = None
    source_multiplicity: Optional[str] = None
    target_multiplicity: Optional[str] = None
    label: Optional[str] = None
    port_info: Optional[dict] = Field(None, description="AUTOSAR port details if applicable")


class ClassDiagram(BaseModel):
    """Complete class/module diagram in JSON-UML format."""
    diagram_type: DiagramType = DiagramType.CLASS
    name: str = ""
    description: Optional[str] = None
    source_requirements: list[str] = Field(default_factory=list)
    classes: list[ClassElement] = Field(default_factory=list)
    associations: list[Association] = Field(default_factory=list)
    interfaces: list[dict] = Field(default_factory=list, description="Interface definitions")
    data_types: list[dict] = Field(default_factory=list, description="Data type definitions")
    provenance: Optional[Provenance] = None


# ──────────────────────────────────────────────
# Component / Package Diagram Elements
# ──────────────────────────────────────────────

class PortElement(BaseModel):
    """A port on a component."""
    id: str
    name: str
    direction: str = Field(..., description="provided | required")
    interface_ref: Optional[str] = None
    interface_type: Optional[str] = Field(None, description="sender_receiver | client_server")


class ComponentElement(BaseModel):
    """A component in a component diagram - maps to AUTOSAR SWC."""
    id: str
    name: str
    stereotype: Optional[str] = None
    ports: list[PortElement] = Field(default_factory=list)
    subcomponents: list[ComponentElement] = Field(default_factory=list)
    trace_reqs: list[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class Connector(BaseModel):
    """A connector between component ports."""
    id: str = ""
    source_component: str
    source_port: str
    target_component: str
    target_port: str
    interface_ref: Optional[str] = None
    label: Optional[str] = None


class ComponentDiagram(BaseModel):
    """Complete component/package diagram in JSON-UML format."""
    diagram_type: DiagramType = DiagramType.COMPONENT
    name: str = ""
    description: Optional[str] = None
    source_requirements: list[str] = Field(default_factory=list)
    components: list[ComponentElement] = Field(default_factory=list)
    connectors: list[Connector] = Field(default_factory=list)
    packages: list[dict] = Field(default_factory=list)
    provenance: Optional[Provenance] = None


# ──────────────────────────────────────────────
# Activity / Code-Flow Diagram Elements
# ──────────────────────────────────────────────

class ActivityNodeType(str, Enum):
    """Types of nodes in an activity / code-flow diagram."""
    INITIAL       = "initial"        # Start point — filled circle
    FINAL         = "final"          # End point — bulls-eye circle
    ACTION        = "action"         # Plain computation or assignment — rectangle
    CALL          = "call"           # RTE read / write / call / result — blue rectangle
    FUNCTION_CALL = "function_call"  # Call to private helper function — subroutine box
    DECISION      = "decision"       # if / switch condition — diamond
    FORK          = "fork"           # Parallel split — horizontal bar
    JOIN          = "join"           # Parallel merge — horizontal bar
    MERGE         = "merge"          # Condition merge without wait — rounded rect
    EXCEPTION     = "exception"      # Fault / error path entry — parallelogram


class ActivityNode(BaseModel):
    """A node in an activity diagram — maps to a code-level operation or decision."""
    id: str = Field(..., description="Unique node ID, e.g. N_01")
    name: str = Field(..., description="Short label displayed on the node")
    node_type: ActivityNodeType
    rte_call: Optional[str] = Field(None, description="RTE API, e.g. Rte_Read")
    port: Optional[str]     = Field(None, description="Port name, e.g. RP_VehicleSpeed")
    element: Optional[str]  = Field(None, description="Data element or operation name")
    callee: Optional[str]   = Field(None, description="For FUNCTION_CALL: name of the called function, e.g. EPS_CalcAssistTorque")
    description: Optional[str] = None
    trace_reqs: list[str]   = Field(default_factory=list)
    confidence: float        = Field(0.8, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: dict) -> dict:
        """Accept LLM variants: 'type'/'nodeType' → 'node_type', strip suffixes."""
        if not isinstance(data, dict):
            return data

        # Map type / nodeType → node_type if node_type is missing
        if "node_type" not in data:
            for alt_key in ("nodeType", "type"):
                if alt_key in data:
                    data["node_type"] = data.pop(alt_key)
                    break

        # Normalize node_type value: strip suffixes, lowercase, apply aliases
        raw = data.get("node_type")
        if isinstance(raw, str):
            norm = raw.strip().lower().replace("-", "_").replace(" ", "_")
            # Strip trailing _node / node suffix (e.g. InitialNode → initial)
            if norm.endswith("_node"):
                norm = norm[:-5]
            elif norm.endswith("node"):
                norm = norm[:-4]
            _ALIASES = {
                "activity": "action", "process": "action",
                "operation": "action", "step": "action",
                "functioncall": "function_call", "function": "function_call",
                "branch": "decision", "condition": "decision",
                "error": "exception", "fault": "exception",
                "start": "initial", "begin": "initial",
                "end": "final", "stop": "final", "terminate": "final",
            }
            norm = _ALIASES.get(norm, norm)
            data["node_type"] = norm

        # Derive name from label/title/description if missing
        if not data.get("name"):
            for alt in ("label", "title"):
                if data.get(alt):
                    data["name"] = data[alt]
                    break
            else:
                data.setdefault("name", data.get("description", "Node"))

        return data


_edge_counter = 0  # module-level counter for auto-generating edge IDs


def _next_edge_id() -> str:
    global _edge_counter
    _edge_counter += 1
    return f"E_{_edge_counter:02d}"


class ActivityEdge(BaseModel):
    """A directed edge between two activity nodes."""
    id: str = Field(default_factory=_next_edge_id, description="Unique edge ID, e.g. E_01")
    source: str = Field(..., description="Source ActivityNode.id")
    target: str = Field(..., description="Target ActivityNode.id")
    guard: Optional[str] = Field(None, description="Guard condition shown on arrow, e.g. [speed > 40]")
    label: Optional[str] = Field(None, description="Alternative edge label when no guard")

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: dict) -> dict:
        """Accept LLM variants: 'from'→'source', 'to'→'target', 'source_id'→'source'."""
        if not isinstance(data, dict):
            return data
        if "source" not in data:
            for alt in ("from", "source_id", "src"):
                if alt in data:
                    data["source"] = data.pop(alt)
                    break
        if "target" not in data:
            for alt in ("to", "target_id", "dst", "dest"):
                if alt in data:
                    data["target"] = data.pop(alt)
                    break
        return data


class ActivityDiagram(BaseModel):
    """Code-flow / activity diagram for a single AUTOSAR Runnable or private function."""
    diagram_type: DiagramType           = Field(DiagramType.ACTIVITY, frozen=True)
    name: str                           = Field("", description="Diagram name")
    description: Optional[str]         = None
    source_requirements: list[str]     = Field(default_factory=list)
    owner_swc: Optional[str]           = Field(None, description="Owning SWC, e.g. SWC_ElectricPowerSteering")
    owner_runnable: Optional[str]      = Field(None, description="Runnable modelled, e.g. RE_ControlTorque")
    function_name: Optional[str]       = Field(None, description="For sub-diagrams: the private function modelled, e.g. EPS_CalcAssistTorque")
    parent_diagram: Optional[str]      = Field(None, description="Parent diagram name this is a child of")
    nodes: list[ActivityNode]          = Field(default_factory=list)
    edges: list[ActivityEdge]          = Field(default_factory=list)
    sub_diagrams: list['ActivityDiagram'] = Field(default_factory=list, description="Child function flowcharts")
    provenance: Optional[Provenance]   = None


# ──────────────────────────────────────────────
# Union type for any diagram
# ──────────────────────────────────────────────

AnyDiagram = Union[SequenceDiagram, StateMachineDiagram, ClassDiagram, ComponentDiagram, ActivityDiagram]


class GenerationResult(BaseModel):
    """Result of an AI generation run, containing one or more diagrams."""
    diagrams: list[AnyDiagram] = Field(default_factory=list)
    analyzed_requirements: list[str] = Field(default_factory=list)
    module_assignments: Optional[dict[str, list[str]]] = Field(
        None,
        description="Module name -> list of requirement IDs",
    )
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    total_generation_time_ms: Optional[int] = None
