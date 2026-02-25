"""Validation Engine - orchestrates all three validation passes.

Pass 1: Structural (UML metamodel conformance)
Pass 2: AUTOSAR Rules (domain-specific validation)
Pass 3: Cross-Diagram Consistency
"""

from __future__ import annotations

import logging
from typing import Optional

from mudtool.config.settings import Settings
from mudtool.models.json_uml import GenerationResult
from mudtool.models.validation import ValidationReport
from mudtool.validation.autosar_validator import AUTOSARValidator
from mudtool.validation.consistency_validator import ConsistencyValidator
from mudtool.validation.structural_validator import StructuralValidator

logger = logging.getLogger(__name__)


class ValidationEngine:
    """Orchestrates multi-pass model validation.

    Runs three validation passes in sequence:
    1. Structural - UML metamodel conformance
    2. AUTOSAR - Domain-specific rules
    3. Consistency - Cross-diagram checks

    Results are merged into a single ValidationReport.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.structural = StructuralValidator()
        self.autosar = AUTOSARValidator(settings)
        self.consistency = ConsistencyValidator()

    def validate(
        self,
        result: GenerationResult,
        requirement_ids: Optional[list[str]] = None,
    ) -> ValidationReport:
        """Run all validation passes on a generation result.

        Args:
            result: The generation result to validate.
            requirement_ids: Optional list of all requirement IDs for coverage check.

        Returns:
            Combined ValidationReport from all passes.
        """
        combined = ValidationReport()

        # Pass 1: Structural
        logger.info("Validation Pass 1: Structural checks...")
        structural_report = self.structural.validate(result)
        self._merge_report(combined, structural_report)
        logger.info(f"  Structural: {structural_report.error_count} errors, "
                     f"{structural_report.warning_count} warnings")

        # Pass 2: AUTOSAR Rules
        logger.info("Validation Pass 2: AUTOSAR rules...")
        autosar_report = self.autosar.validate(result, requirement_ids)
        self._merge_report(combined, autosar_report)
        logger.info(f"  AUTOSAR: {autosar_report.error_count} errors, "
                     f"{autosar_report.warning_count} warnings")

        # Pass 3: Cross-Diagram Consistency
        logger.info("Validation Pass 3: Cross-diagram consistency...")
        consistency_report = self.consistency.validate(result)
        self._merge_report(combined, consistency_report)
        logger.info(f"  Consistency: {consistency_report.error_count} errors, "
                     f"{consistency_report.warning_count} warnings")

        logger.info(f"Validation complete: {combined.summary()}")
        return combined

    def _merge_report(self, target: ValidationReport, source: ValidationReport) -> None:
        """Merge source report into target."""
        for issue in source.issues:
            target.add_issue(issue)
        target.diagrams_checked += source.diagrams_checked
        target.elements_checked += source.elements_checked
