"""Requirement data models for ingestion from ALM tools."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RequirementType(str, Enum):
    """Requirement classification types."""
    FUNCTIONAL = "functional"
    INTERFACE = "interface"
    TIMING = "timing"
    SAFETY = "safety"
    CONSTRAINT = "constraint"


class ASILLevel(str, Enum):
    """ASIL classification per ISO 26262."""
    QM = "QM"
    ASIL_A = "ASIL-A"
    ASIL_B = "ASIL-B"
    ASIL_C = "ASIL-C"
    ASIL_D = "ASIL-D"


class Priority(str, Enum):
    """MoSCoW priority classification."""
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "won't"


class RequirementStatus(str, Enum):
    """Requirement lifecycle status."""
    DRAFT = "draft"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"


class Requirement(BaseModel):
    """A single architecture requirement imported from ALM tool export.

    This is the canonical internal representation used throughout the pipeline.
    Mapped from Excel/CSV/TXT input formats.
    """
    req_id: str = Field(
        ...,
        description="Unique requirement identifier from ALM tool (e.g., REQ-ARCH-0142)",
        pattern=r"^[A-Z]+-[A-Z]+-\d+$",
    )
    title: str = Field(
        ...,
        description="Short requirement title",
        min_length=1,
        max_length=500,
    )
    description: str = Field(
        ...,
        description="Full requirement text - primary AI input",
        min_length=1,
    )
    parent_id: Optional[str] = Field(
        None,
        description="Parent requirement ID for hierarchy",
    )
    req_type: RequirementType = Field(
        ...,
        description="Requirement classification type",
    )
    safety_level: Optional[ASILLevel] = Field(
        None,
        description="ASIL classification if applicable",
    )
    priority: Priority = Field(
        ...,
        description="MoSCoW priority",
    )
    status: RequirementStatus = Field(
        RequirementStatus.DRAFT,
        description="Lifecycle status",
    )
    module_hint: Optional[str] = Field(
        None,
        description="Suggested target SWC/module name (optional AI hint)",
    )
    notes: Optional[str] = Field(
        None,
        description="Additional context for AI or reviewer",
    )
    source: Optional[str] = Field(
        None,
        description="Origin ALM tool and export timestamp",
    )
    imported_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this requirement was imported",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "req_id": "REQ-ARCH-0142",
            "title": "Sensor Fusion Data Distribution",
            "description": "The SWC shall distribute fused sensor data to all consuming components via Sender-Receiver interface with a cycle time of 10ms.",
            "parent_id": "REQ-ARCH-0100",
            "req_type": "functional",
            "safety_level": "ASIL-B",
            "priority": "must",
            "status": "approved",
            "module_hint": "SWC_SensorFusion",
            "notes": "Related to radar and camera fusion pipeline",
            "source": "Polarion:2026-02-10T14:30:00Z",
        }
    }}


class RequirementSet(BaseModel):
    """A collection of requirements imported together, forming the input to AI analysis."""
    requirements: list[Requirement] = Field(default_factory=list)
    source_file: Optional[str] = Field(None, description="Original file path")
    source_format: Optional[str] = Field(None, description="Detected format (xlsx, csv, txt, md)")
    import_timestamp: datetime = Field(default_factory=datetime.utcnow)
    column_mapping: Optional[dict[str, str]] = Field(
        None,
        description="Mapping from source column names to canonical field names",
    )

    @property
    def count(self) -> int:
        return len(self.requirements)

    def get_by_id(self, req_id: str) -> Optional[Requirement]:
        """Look up a requirement by ID."""
        for req in self.requirements:
            if req.req_id == req_id:
                return req
        return None

    def get_by_type(self, req_type: RequirementType) -> list[Requirement]:
        """Filter requirements by type."""
        return [r for r in self.requirements if r.req_type == req_type]

    def get_by_module_hint(self, module: str) -> list[Requirement]:
        """Filter requirements by module hint."""
        return [r for r in self.requirements if r.module_hint == module]

    def get_functional(self) -> list[Requirement]:
        """Get all functional requirements."""
        return self.get_by_type(RequirementType.FUNCTIONAL)

    def get_interface(self) -> list[Requirement]:
        """Get all interface requirements."""
        return self.get_by_type(RequirementType.INTERFACE)
