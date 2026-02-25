"""Plain text requirement importer.

Format: One requirement per line as: [REQ_ID] | [Type] | [Description]
Minimal parsing overhead for fast AI pipeline testing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from mudtool.importers.base import BaseImporter, ImportResult
from mudtool.models.requirements import RequirementSet

logger = logging.getLogger(__name__)


class TextImporter(BaseImporter):
    """Import requirements from plain text files.

    Supports two formats:
    1. Pipe-delimited: REQ_ID | Type | Description
    2. Simple: REQ_ID: Description (type defaults to functional)
    """

    def __init__(self, column_mapping: Optional[dict[str, str]] = None):
        super().__init__(column_mapping)

    def supports_format(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".txt"

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
                    source_file=str(file_path), source_format="txt"
                ),
                errors=[f"Failed to read text file: {e}"],
            )

        for line_num, line in enumerate(text.splitlines(), start=1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#") or line.startswith("//"):
                continue

            rows_processed += 1
            row_data: dict[str, str] = {}

            if "|" in line:
                # Pipe-delimited format: REQ_ID | Type | Description [| Priority] [| ASIL]
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    row_data["req_id"] = parts[0]
                    row_data["req_type"] = parts[1]
                    row_data["description"] = parts[2]
                    row_data["title"] = parts[2][:100]  # Use first 100 chars as title

                    if len(parts) >= 4:
                        row_data["priority"] = parts[3]
                    if len(parts) >= 5:
                        row_data["safety_level"] = parts[4]
                    if len(parts) >= 6:
                        row_data["module_hint"] = parts[5]
                else:
                    self._warnings.append(
                        f"Line {line_num}: Expected at least 3 pipe-delimited fields"
                    )
                    rows_skipped += 1
                    continue

            elif ":" in line:
                # Simple format: REQ_ID: Description
                colon_idx = line.index(":")
                row_data["req_id"] = line[:colon_idx].strip()
                desc = line[colon_idx + 1:].strip()
                row_data["description"] = desc
                row_data["title"] = desc[:100]
                row_data["req_type"] = "functional"
                row_data["priority"] = "should"
            else:
                self._warnings.append(f"Line {line_num}: Unrecognized format, skipping")
                rows_skipped += 1
                continue

            req = self._build_requirement(row_data, line_num)
            if req:
                requirements.append(req)
            else:
                rows_skipped += 1

        req_set = RequirementSet(
            requirements=requirements,
            source_file=str(file_path),
            source_format="txt",
        )

        logger.info(f"Text imported {len(requirements)} requirements from {file_path.name}")

        return ImportResult(
            requirement_set=req_set,
            warnings=self._warnings,
            errors=self._errors,
            rows_processed=rows_processed,
            rows_skipped=rows_skipped,
        )
