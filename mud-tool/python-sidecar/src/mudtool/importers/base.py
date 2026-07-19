"""Base importer interface and common utilities."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from mudtool.models.requirements import (
    ASILLevel,
    Priority,
    Requirement,
    RequirementSet,
    RequirementStatus,
    RequirementType,
)

logger = logging.getLogger(__name__)


class ImportResult(BaseModel):
    """Result of an import operation."""
    requirement_set: RequirementSet
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    rows_processed: int = 0
    rows_skipped: int = 0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.requirement_set.count > 0


# Default column name mappings for Polarion/DOORS Excel exports
DEFAULT_COLUMN_MAPPING: dict[str, list[str]] = {
    "req_id": ["Req_ID", "req_id", "ID", "Requirement ID", "ReqID", "Work Item ID"],
    "title": ["Title", "title", "Name", "Requirement Title", "Summary"],
    "description": ["Description", "description", "Text", "Requirement Text", "Content"],
    "parent_id": ["Parent_ID", "parent_id", "Parent", "Parent ID", "Parent Work Item"],
    "req_type": ["Type", "type", "req_type", "Requirement Type", "Category"],
    "safety_level": ["ASIL", "asil", "Safety", "Safety Level", "safety_level"],
    "priority": ["Priority", "priority", "Importance"],
    "status": ["Status", "status", "State", "Lifecycle"],
    "module_hint": ["Module_Hint", "module_hint", "Module", "Component", "Target Module"],
    "notes": ["Notes", "notes", "Comments", "Remarks", "Additional Info"],
}


class BaseImporter(ABC):
    """Abstract base class for requirement importers."""

    def __init__(self, column_mapping: Optional[dict[str, str]] = None):
        """Initialize with optional custom column mapping.

        Args:
            column_mapping: Optional dict mapping canonical field names to source column names.
                           If None, auto-detection is used.
        """
        self.column_mapping = column_mapping or {}
        self._warnings: list[str] = []
        self._errors: list[str] = []

    @abstractmethod
    def import_file(self, file_path: Path) -> ImportResult:
        """Import requirements from a file.

        Args:
            file_path: Path to the input file.

        Returns:
            ImportResult containing the requirement set and any issues.
        """
        ...

    @abstractmethod
    def supports_format(self, file_path: Path) -> bool:
        """Check if this importer supports the given file format."""
        ...

    def _detect_column(self, header: str) -> Optional[str]:
        """Auto-detect which canonical field a column header maps to.

        Args:
            header: The column header from the source file.

        Returns:
            Canonical field name or None if no match found.
        """
        header_clean = header.strip()

        # Check custom mapping first
        for field, source_col in self.column_mapping.items():
            if header_clean.lower() == source_col.lower():
                return field

        # Check default mappings
        for field, aliases in DEFAULT_COLUMN_MAPPING.items():
            for alias in aliases:
                if header_clean.lower() == alias.lower():
                    return field

        return None

    def _parse_req_type(self, value: str) -> RequirementType:
        """Parse requirement type string to enum."""
        mapping = {
            "functional": RequirementType.FUNCTIONAL,
            "func": RequirementType.FUNCTIONAL,
            "interface": RequirementType.INTERFACE,
            "iface": RequirementType.INTERFACE,
            "timing": RequirementType.TIMING,
            "time": RequirementType.TIMING,
            "safety": RequirementType.SAFETY,
            "constraint": RequirementType.CONSTRAINT,
            "non-functional": RequirementType.CONSTRAINT,
        }
        return mapping.get(value.strip().lower(), RequirementType.FUNCTIONAL)

    def _parse_asil(self, value: str) -> Optional[ASILLevel]:
        """Parse ASIL level string to enum."""
        if not value or not value.strip():
            return None
        mapping = {
            "qm": ASILLevel.QM,
            "asil-a": ASILLevel.ASIL_A,
            "asil_a": ASILLevel.ASIL_A,
            "a": ASILLevel.ASIL_A,
            "asil-b": ASILLevel.ASIL_B,
            "asil_b": ASILLevel.ASIL_B,
            "b": ASILLevel.ASIL_B,
            "asil-c": ASILLevel.ASIL_C,
            "asil_c": ASILLevel.ASIL_C,
            "c": ASILLevel.ASIL_C,
            "asil-d": ASILLevel.ASIL_D,
            "asil_d": ASILLevel.ASIL_D,
            "d": ASILLevel.ASIL_D,
        }
        return mapping.get(value.strip().lower())

    def _parse_priority(self, value: str) -> Priority:
        """Parse priority string to enum."""
        mapping = {
            "must": Priority.MUST,
            "must have": Priority.MUST,
            "high": Priority.MUST,
            "should": Priority.SHOULD,
            "should have": Priority.SHOULD,
            "medium": Priority.SHOULD,
            "could": Priority.COULD,
            "could have": Priority.COULD,
            "low": Priority.COULD,
            "won't": Priority.WONT,
            "wont": Priority.WONT,
            "won't have": Priority.WONT,
        }
        return mapping.get(value.strip().lower(), Priority.SHOULD)

    def _parse_status(self, value: str) -> RequirementStatus:
        """Parse status string to enum."""
        mapping = {
            "draft": RequirementStatus.DRAFT,
            "new": RequirementStatus.DRAFT,
            "approved": RequirementStatus.APPROVED,
            "accepted": RequirementStatus.APPROVED,
            "implemented": RequirementStatus.IMPLEMENTED,
            "done": RequirementStatus.IMPLEMENTED,
            "verified": RequirementStatus.VERIFIED,
            "tested": RequirementStatus.VERIFIED,
        }
        return mapping.get(value.strip().lower(), RequirementStatus.DRAFT)

    def _build_requirement(self, row_data: dict[str, str], row_num: int) -> Optional[Requirement]:
        """Build a Requirement from a mapped row dict.

        Args:
            row_data: Dict of canonical field name -> value.
            row_num: Row number for error reporting.

        Returns:
            Requirement or None if row is invalid.
        """
        req_id = row_data.get("req_id", "").strip()
        title = row_data.get("title", "").strip()
        description = row_data.get("description", "").strip()

        # Validate required fields
        if not req_id:
            self._warnings.append(f"Row {row_num}: Missing Req_ID, skipping")
            return None
        if not title:
            self._warnings.append(f"Row {row_num}: Missing Title for {req_id}, using ID as title")
            title = req_id
        if not description:
            self._warnings.append(
                f"Row {row_num}: Missing Description for {req_id}, using title"
            )
            description = title

        try:
            return Requirement(
                req_id=req_id,
                title=title,
                description=description,
                parent_id=row_data.get("parent_id", "").strip() or None,
                req_type=self._parse_req_type(row_data.get("req_type", "functional")),
                safety_level=self._parse_asil(row_data.get("safety_level", "")),
                priority=self._parse_priority(row_data.get("priority", "should")),
                status=self._parse_status(row_data.get("status", "draft")),
                module_hint=row_data.get("module_hint", "").strip() or None,
                notes=row_data.get("notes", "").strip() or None,
                source=row_data.get("source", "").strip() or None,
            )
        except Exception as e:
            self._errors.append(f"Row {row_num}: Failed to parse requirement {req_id}: {e}")
            return None
