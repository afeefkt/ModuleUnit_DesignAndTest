"""Importer factory - auto-detects format and returns appropriate importer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from mudtool.importers.base import BaseImporter, ImportResult
from mudtool.importers.csv_importer import CSVImporter
from mudtool.importers.excel_importer import ExcelImporter
from mudtool.importers.markdown_importer import MarkdownImporter
from mudtool.importers.text_importer import TextImporter

logger = logging.getLogger(__name__)

# Ordered list of importers to try
_IMPORTERS: list[type[BaseImporter]] = [
    ExcelImporter,
    CSVImporter,
    TextImporter,
    MarkdownImporter,
]


class ImporterFactory:
    """Factory for creating the appropriate importer based on file extension."""

    @staticmethod
    def get_importer(
        file_path: Path,
        column_mapping: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> BaseImporter:
        """Get the appropriate importer for a given file.

        Args:
            file_path: Path to the requirement file.
            column_mapping: Optional custom column mapping.
            **kwargs: Additional arguments passed to the importer constructor.

        Returns:
            Configured importer instance.

        Raises:
            ValueError: If no importer supports the file format.
        """
        for importer_cls in _IMPORTERS:
            importer = importer_cls(column_mapping=column_mapping, **kwargs)
            if importer.supports_format(file_path):
                logger.info(
                    f"Using {importer_cls.__name__} for {file_path.suffix} file"
                )
                return importer

        raise ValueError(
            f"Unsupported file format: {file_path.suffix}. "
            f"Supported: .xlsx, .xls, .csv, .txt, .md"
        )

    @staticmethod
    def import_file(
        file_path: str | Path,
        column_mapping: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> ImportResult:
        """Convenience method: auto-detect format and import requirements.

        Args:
            file_path: Path to the requirement file.
            column_mapping: Optional custom column mapping.

        Returns:
            ImportResult with parsed requirements.
        """
        path = Path(file_path)

        if not path.exists():
            from mudtool.models.requirements import RequirementSet
            return ImportResult(
                requirement_set=RequirementSet(source_file=str(path)),
                errors=[f"File not found: {path}"],
            )

        importer = ImporterFactory.get_importer(path, column_mapping, **kwargs)
        return importer.import_file(path)
