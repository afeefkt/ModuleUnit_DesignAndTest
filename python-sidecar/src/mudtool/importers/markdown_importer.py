"""Markdown table requirement importer.

Parses markdown tables with the same column headers as the Excel template.
Useful for quick copy-paste from documentation or chat.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from mudtool.importers.base import BaseImporter, ImportResult
from mudtool.models.requirements import RequirementSet

logger = logging.getLogger(__name__)


class MarkdownImporter(BaseImporter):
    """Import requirements from Markdown table files."""

    def __init__(self, column_mapping: Optional[dict[str, str]] = None):
        super().__init__(column_mapping)

    def supports_format(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".md"

    def _parse_md_table_row(self, line: str) -> list[str]:
        """Parse a markdown table row into cell values."""
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        return [cell.strip() for cell in line.split("|")]

    def _is_separator_row(self, line: str) -> bool:
        """Check if a line is a markdown table separator (e.g., |---|---|)."""
        return bool(re.match(r"^\s*\|?[\s\-:]+(\|[\s\-:]+)*\|?\s*$", line))

    def import_file(self, file_path: Path) -> ImportResult:
        self._warnings = []
        self._errors = []
        requirements = []
        rows_processed = 0
        rows_skipped = 0

        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return ImportResult(
                requirement_set=RequirementSet(
                    source_file=str(file_path), source_format="md"
                ),
                errors=[f"Failed to read markdown file: {e}"],
            )

        lines = text.splitlines()

        # Find the table: look for a line with | characters followed by a separator
        table_start = -1
        headers: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if "|" in stripped and not self._is_separator_row(stripped):
                # Check if next line is a separator
                if i + 1 < len(lines) and self._is_separator_row(lines[i + 1]):
                    headers = self._parse_md_table_row(stripped)
                    table_start = i + 2  # Start after separator
                    break

        if table_start == -1 or not headers:
            return ImportResult(
                requirement_set=RequirementSet(
                    source_file=str(file_path), source_format="md"
                ),
                errors=["No markdown table found in file"],
            )

        # Build column mapping
        col_map: dict[int, str] = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            field = self._detect_column(header)
            if field:
                col_map[idx] = field

        if "req_id" not in set(col_map.values()):
            return ImportResult(
                requirement_set=RequirementSet(
                    source_file=str(file_path), source_format="md"
                ),
                errors=[f"Required column 'Req_ID' not found. Headers: {headers}"],
            )

        # Parse data rows
        for line_num in range(table_start, len(lines)):
            line = lines[line_num].strip()

            # Stop at empty line or non-table line
            if not line or "|" not in line:
                break

            if self._is_separator_row(line):
                continue

            rows_processed += 1
            cells = self._parse_md_table_row(line)
            row_data: dict[str, str] = {}

            for col_idx, value in enumerate(cells):
                if col_idx in col_map:
                    row_data[col_map[col_idx]] = value

            if not any(v.strip() for v in row_data.values()):
                rows_skipped += 1
                continue

            req = self._build_requirement(row_data, line_num + 1)
            if req:
                requirements.append(req)
            else:
                rows_skipped += 1

        req_set = RequirementSet(
            requirements=requirements,
            source_file=str(file_path),
            source_format="md",
        )

        logger.info(f"Markdown imported {len(requirements)} requirements from {file_path.name}")

        return ImportResult(
            requirement_set=req_set,
            warnings=self._warnings,
            errors=self._errors,
            rows_processed=rows_processed,
            rows_skipped=rows_skipped,
        )
