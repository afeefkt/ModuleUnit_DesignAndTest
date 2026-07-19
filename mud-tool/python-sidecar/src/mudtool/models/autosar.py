"""AUTOSAR-specific data models.

These are first-class AUTOSAR entities, not generic UML with stereotypes.
They form the core domain model used by the AI, generator, and validator.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class TriggerType(str, Enum):
    """Runnable entity trigger types in AUTOSAR."""
    INIT = "init"
    CYCLIC = "cyclic"
    ON_DATA_RECEPTION = "on_data_reception"
    ON_MODE_SWITCH = "on_mode_switch"


class PortDirection(str, Enum):
    """Port direction in AUTOSAR."""
    PROVIDED = "provided"   # P-Port: sends data / offers service
    REQUIRED = "required"   # R-Port: receives data / consumes service


class SWCType(str, Enum):
    """Software component types in AUTOSAR."""
    APPLICATION = "application"
    SENSOR_ACTUATOR = "sensor_actuator"
    SERVICE = "service"
    COMPOSITION = "composition"


class DataTypeCategory(str, Enum):
    """AUTOSAR data type categories."""
    PRIMITIVE = "primitive"
    ARRAY = "array"
    RECORD = "record"
    ENUM = "enum"


class RTECallType(str, Enum):
    """AUTOSAR RTE API call types used in sequence diagrams."""
    RTE_READ = "Rte_Read"
    RTE_WRITE = "Rte_Write"
    RTE_CALL = "Rte_Call"
    RTE_RESULT = "Rte_Result"
    RTE_IREAD = "Rte_IRead"
    RTE_IWRITE = "Rte_IWrite"
    RTE_SEND = "Rte_Send"
    RTE_RECEIVE = "Rte_Receive"
    RTE_MODE_SWITCH = "Rte_Switch"


class InterfaceType(str, Enum):
    """AUTOSAR interface communication patterns."""
    SENDER_RECEIVER = "sender_receiver"
    CLIENT_SERVER = "client_server"


# ──────────────────────────────────────────────
# Data Types
# ──────────────────────────────────────────────

class DataType(BaseModel):
    """AUTOSAR data type definition."""
    name: str
    category: DataTypeCategory = DataTypeCategory.PRIMITIVE
    base_type: Optional[str] = Field(None, description="Base type (uint8, float32, etc.)")
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    unit: Optional[str] = None
    array_size: Optional[int] = Field(None, description="Size for array types")
    fields: Optional[list[DataType]] = Field(None, description="Fields for record types")
    enum_values: Optional[list[str]] = Field(None, description="Values for enum types")


# ──────────────────────────────────────────────
# Interfaces
# ──────────────────────────────────────────────

class DataElement(BaseModel):
    """A data element within a Sender-Receiver interface."""
    name: str
    data_type: str = Field(..., description="Reference to DataType name")
    init_value: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None


class OperationArgument(BaseModel):
    """An argument of a Client-Server operation."""
    name: str
    data_type: str
    direction: str = Field("in", description="in | out | inout")
    description: Optional[str] = None


class Operation(BaseModel):
    """An operation in a Client-Server interface."""
    name: str
    arguments: list[OperationArgument] = Field(default_factory=list)
    return_type: Optional[str] = None
    description: Optional[str] = None


class SenderReceiverInterface(BaseModel):
    """AUTOSAR Sender-Receiver communication interface."""
    name: str
    data_elements: list[DataElement] = Field(default_factory=list)
    description: Optional[str] = None


class ClientServerInterface(BaseModel):
    """AUTOSAR Client-Server communication interface."""
    name: str
    operations: list[Operation] = Field(default_factory=list)
    description: Optional[str] = None


# ──────────────────────────────────────────────
# Ports
# ──────────────────────────────────────────────

class Port(BaseModel):
    """An AUTOSAR port (P-Port or R-Port) on an SWC."""
    name: str
    direction: PortDirection
    interface_ref: str = Field(..., description="Reference to interface name")
    interface_type: InterfaceType = InterfaceType.SENDER_RECEIVER
    com_spec: Optional[dict] = Field(None, description="Communication specification details")
    description: Optional[str] = None


# ──────────────────────────────────────────────
# Runnables
# ──────────────────────────────────────────────

class DataAccess(BaseModel):
    """A data access point for a runnable entity."""
    port_ref: str
    element_ref: str
    access_type: str = Field("read", description="read | write | readwrite")


class Runnable(BaseModel):
    """An AUTOSAR Runnable Entity - executable unit within an SWC."""
    name: str
    trigger: TriggerType = TriggerType.CYCLIC
    period_ms: Optional[float] = Field(
        None,
        description="Period in ms for cyclic runnables",
        gt=0,
    )
    accesses: list[DataAccess] = Field(
        default_factory=list,
        description="Port/element access declarations",
    )
    description: Optional[str] = None
    trace_reqs: list[str] = Field(
        default_factory=list,
        description="Requirement IDs this runnable traces to",
    )


# ──────────────────────────────────────────────
# Software Components
# ──────────────────────────────────────────────

class ApplicationSWC(BaseModel):
    """AUTOSAR Application Software Component - primary building block."""
    name: str
    swc_type: SWCType = SWCType.APPLICATION
    ports: list[Port] = Field(default_factory=list)
    runnables: list[Runnable] = Field(default_factory=list)
    internal_data: list[DataType] = Field(
        default_factory=list,
        description="Internal data types / inter-runnable variables",
    )
    description: Optional[str] = None
    trace_reqs: list[str] = Field(
        default_factory=list,
        description="Requirement IDs this SWC traces to",
    )

    def get_provided_ports(self) -> list[Port]:
        return [p for p in self.ports if p.direction == PortDirection.PROVIDED]

    def get_required_ports(self) -> list[Port]:
        return [p for p in self.ports if p.direction == PortDirection.REQUIRED]

    def get_runnable_by_trigger(self, trigger: TriggerType) -> list[Runnable]:
        return [r for r in self.runnables if r.trigger == trigger]


# ──────────────────────────────────────────────
# Mode Declaration
# ──────────────────────────────────────────────

class ModeDeclarationGroup(BaseModel):
    """AUTOSAR mode declaration group for state-based behavior."""
    name: str
    modes: list[str] = Field(
        default_factory=list,
        description="Mode literals (e.g., STARTUP, RUNNING, SHUTDOWN)",
    )
    initial_mode: Optional[str] = None
    description: Optional[str] = None


# ──────────────────────────────────────────────
# RTE Calls (used in sequence diagrams)
# ──────────────────────────────────────────────

class RTECall(BaseModel):
    """An AUTOSAR RTE API call used in sequence diagram messages."""
    call_type: RTECallType
    port_ref: str = Field(..., description="Port name reference")
    element_ref: str = Field(..., description="Data element or operation name")
    description: Optional[str] = None
