"""Data models for MUD Tool - Requirements, AUTOSAR entities, JSON-UML schemas."""

from mudtool.models.requirements import (
    Requirement,
    RequirementType,
    ASILLevel,
    Priority,
    RequirementStatus,
    RequirementSet,
)
from mudtool.models.autosar import (
    ApplicationSWC,
    Runnable,
    TriggerType,
    Port,
    PortDirection,
    SenderReceiverInterface,
    ClientServerInterface,
    DataElement,
    DataType,
    DataTypeCategory,
    Operation,
    OperationArgument,
    ModeDeclarationGroup,
    RTECall,
    RTECallType,
)
from mudtool.models.json_uml import (
    DiagramType,
    Lifeline,
    Message,
    State,
    Transition,
    ClassElement,
    ClassAttribute,
    ClassOperation,
    Association,
    ComponentElement,
    PortElement,
    Connector,
    Provenance,
    SequenceDiagram,
    StateMachineDiagram,
    ClassDiagram,
    ComponentDiagram,
    ActivityNodeType,
    ActivityNode,
    ActivityEdge,
    ActivityDiagram,
    GenerationResult,
)
from mudtool.models.validation import (
    ValidationSeverity,
    ValidationIssue,
    ValidationReport,
)

__all__ = [
    # Requirements
    "Requirement", "RequirementType", "ASILLevel", "Priority",
    "RequirementStatus", "RequirementSet",
    # AUTOSAR
    "ApplicationSWC", "Runnable", "TriggerType", "Port", "PortDirection",
    "SenderReceiverInterface", "ClientServerInterface", "DataElement",
    "DataType", "DataTypeCategory", "Operation", "OperationArgument",
    "ModeDeclarationGroup", "RTECall", "RTECallType",
    # JSON-UML
    "DiagramType", "Lifeline", "Message", "State", "Transition",
    "ClassElement", "ClassAttribute", "ClassOperation", "Association",
    "ComponentElement", "PortElement", "Connector", "Provenance",
    "SequenceDiagram", "StateMachineDiagram", "ClassDiagram", "ComponentDiagram",
    "ActivityNodeType", "ActivityNode", "ActivityEdge", "ActivityDiagram",
    "GenerationResult",
    # Validation
    "ValidationSeverity", "ValidationIssue", "ValidationReport",
]
