"""CSV requirement importer."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional

from mudtool.importers.base import BaseImporter, ImportResult
from mudtool.models.requirements import RequirementSet

logger = logging.getLogger(__name__)


class CSVImporter(BaseImporter):
    """Import requirements from CSV files.

    Same column structure as Excel template but as comma-separated values.
    """

    def __init__(
        self,
        column_mapping: Optional[dict[str, str]] = None,
        delimiter: str = ",",
        encoding: str = "utf-8",
    ):
        super().__init__(column_mapping)
        self.delimiter = delimiter
        self.encoding = encoding

    def supports_format(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".csv"

    def import_file(self, file_path: Path) -> ImportResult:
        self._warnings = []
        self._errors = []
        requirements = []
        rows_processed = 0
        rows_skipped = 0

        try:
            with open(file_path, "r", encoding=self.encoding, newline="") as f:
                # Sniff delimiter if not specified
                sample = f.read(4096)
                f.seek(0)

                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                    reader = csv.reader(f, dialect)
                except csv.Error:
                    reader = csv.reader(f, delimiter=self.delimiter)

                # Read header
                try:
                    headers = next(reader)
                except StopIteration:
                    return ImportResult(
                        requirement_set=RequirementSet(
                            source_file=str(file_path), source_format="csv"
                        ),
                        errors=["CSV file is empty"],
                    )

                headers = [h.strip() for h in headers]

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
                            source_file=str(file_path), source_format="csv"
                        ),
                        errors=[f"Required column 'Req_ID' not found. Headers: {headers}"],
                    )

                # Read data rows
                for row_num, row in enumerate(reader, start=2):
                    rows_processed += 1
                    row_data: dict[str, str] = {}

                    for col_idx, value in enumerate(row):
                        if col_idx in col_map:
                            row_data[col_map[col_idx]] = value.strip()

                    if not any(v.strip() for v in row_data.values()):
                        rows_skipped += 1
                        continue

                    req = self._build_requirement(row_data, row_num)
                    if req:
                        requirements.append(req)
                    else:
                        rows_skipped += 1

        except Exception as e:
            self._errors.append(f"Failed to read CSV file: {e}")

        req_set = RequirementSet(
            requirements=requirements,
            source_file=str(file_path),
            source_format="csv",
        )

        logger.info(
            f"CSV imported {len(requirements)} requirements "
            f"({rows_processed} rows, {rows_skipped} skipped)"
        )

        return ImportResult(
            requirement_set=req_set,
            warnings=self._warnings,
            errors=self._errors,
            rows_processed=rows_processed,
            rows_skipped=rows_skipped,
        )
