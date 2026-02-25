"""Validation result models."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""
    ERROR = "error"       # Must be fixed before commit
    WARNING = "warning"   # Can be accepted with acknowledgment
    INFO = "info"         # Suggestion for improvement


class ValidationIssue(BaseModel):
    """A single validation issue found during model checking."""
    rule_id: str = Field(..., description="Rule identifier (e.g., AUT-001)")
    severity: ValidationSeverity
    category: str = Field(..., description="Rule category (Port, Runnable, Interface, etc.)")
    message: str = Field(..., description="Human-readable issue description")
    element_id: Optional[str] = Field(None, description="ID of the offending model element")
    element_name: Optional[str] = Field(None, description="Name of the offending element")
    diagram_name: Optional[str] = Field(None, description="Diagram containing the issue")
    suggestion: Optional[str] = Field(None, description="Auto-fix suggestion if available")
    can_auto_fix: bool = Field(False, description="Whether an automatic fix is available")


class ValidationReport(BaseModel):
    """Complete validation report for a set of generated models."""
    issues: list[ValidationIssue] = Field(default_factory=list)
    diagrams_checked: int = 0
    elements_checked: int = 0
    passed: bool = Field(True, description="True if no ERROR-level issues")

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.INFO)

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.passed = False

    def get_errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    def get_warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def summary(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Validation {status}: {self.error_count} errors, "
            f"{self.warning_count} warnings, {self.info_count} info | "
            f"{self.diagrams_checked} diagrams, {self.elements_checked} elements checked"
        )
