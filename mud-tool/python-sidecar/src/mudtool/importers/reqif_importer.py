"""ReqIF importer (.reqif / .reqifz) — the exchange format DOORS, Polarion, Jama and others export.

Standard-library XML only. Each ``SPEC-OBJECT`` becomes a requirement; its attribute values
are mapped to the canonical fields by the attribute *definition's* long name, using the same
alias table as the CSV/Excel importers (so "ReqIF.ChapterName", "ReqIF.Text", "Object Text"
… are recognised). XHTML rich text is converted to plain text.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from mudtool.importers.base import BaseImporter, ImportResult, normalize_header
from mudtool.models.requirements import RequirementSet

logger = logging.getLogger(__name__)

# ReqIF built-in attribute names that the generic alias table does not know.
_REQIF_EXTRA = {
    "reqifchaptername": "title",
    "reqiftext": "description",
    "reqifname": "title",
    "reqifforeignid": "req_id",
    "reqifchapter": "title",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _all_text(elem: ET.Element) -> str:
    """Concatenate text of an element tree, turning block-level XHTML into line breaks."""
    parts: list[str] = []

    def walk(e: ET.Element) -> None:
        name = _local(e.tag)
        if name in ("br",):
            parts.append("\n")
        if e.text:
            parts.append(e.text)
        for child in e:
            walk(child)
            if child.tail:
                parts.append(child.tail)
        if name in ("p", "div", "li", "tr"):
            parts.append("\n")

    walk(elem)
    return "".join(parts)


class ReqIFImporter(BaseImporter):
    """Import requirements from a ReqIF file."""

    def __init__(self, column_mapping: Optional[dict[str, str]] = None, **_: object):
        super().__init__(column_mapping)

    def supports_format(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in (".reqif", ".reqifz")

    def _field_for(self, long_name: str) -> Optional[str]:
        norm = normalize_header(long_name)
        for field, source_col in self.column_mapping.items():
            if norm == normalize_header(source_col):
                return field
        return _REQIF_EXTRA.get(norm) or self._detect_column(long_name)

    def import_file(self, file_path: Path) -> ImportResult:
        self._warnings = []
        self._errors = []
        fmt = "reqif"
        try:
            if file_path.suffix.lower() == ".reqifz":
                with zipfile.ZipFile(file_path) as zf:
                    name = next((n for n in zf.namelist() if n.lower().endswith(".reqif")), None)
                    if not name:
                        raise ValueError("no .reqif file inside the archive")
                    root = ET.fromstring(zf.read(name))
            else:
                root = ET.fromstring(file_path.read_bytes())
        except Exception as e:  # noqa: BLE001
            return ImportResult(
                requirement_set=RequirementSet(source_file=str(file_path), source_format=fmt),
                errors=[f"Failed to read ReqIF file: {e}"],
            )

        # attribute-definition id -> long name, and enum value id -> label
        defs: dict[str, str] = {}
        enum_values: dict[str, str] = {}
        for elem in root.iter():
            name = _local(elem.tag)
            if name.startswith("ATTRIBUTE-DEFINITION") and elem.get("IDENTIFIER"):
                defs[elem.get("IDENTIFIER")] = elem.get("LONG-NAME") or elem.get("IDENTIFIER")
            elif name == "ENUM-VALUE" and elem.get("IDENTIFIER"):
                enum_values[elem.get("IDENTIFIER")] = elem.get("LONG-NAME") or ""

        requirements = []
        rows_processed = 0
        rows_skipped = 0
        for obj in (e for e in root.iter() if _local(e.tag) == "SPEC-OBJECT"):
            rows_processed += 1
            row: dict[str, str] = {}
            for value in obj.iter():
                vname = _local(value.tag)
                if not vname.startswith("ATTRIBUTE-VALUE"):
                    continue
                def_ref = next(
                    (r.text for r in value.iter() if _local(r.tag).startswith("ATTRIBUTE-DEFINITION") and r.text),
                    None,
                )
                field = self._field_for(defs.get(def_ref or "", ""))
                if not field:
                    continue
                if vname == "ATTRIBUTE-VALUE-XHTML":
                    text = _all_text(next((c for c in value if _local(c.tag) == "THE-VALUE"), value))
                elif vname == "ATTRIBUTE-VALUE-ENUMERATION":
                    text = ", ".join(
                        enum_values.get(r.text or "", r.text or "")
                        for r in value.iter() if _local(r.tag) == "ENUM-VALUE-REF"
                    )
                else:
                    text = value.get("THE-VALUE") or ""
                if text.strip() and not row.get(field):
                    row[field] = text.strip()
            if not row.get("req_id"):
                row["req_id"] = obj.get("IDENTIFIER") or f"REQ-{rows_processed:03d}"
            if not any(row.get(k) for k in ("title", "description")):
                rows_skipped += 1  # structural objects (folders/headings without text)
                continue
            req = self._build_requirement(row, rows_processed)
            if req:
                requirements.append(req)
            else:
                rows_skipped += 1

        if not requirements and not self._errors:
            self._errors.append("No requirements found in the ReqIF file")
        logger.info("ReqIF imported %d requirements (%d objects)", len(requirements), rows_processed)
        return ImportResult(
            requirement_set=RequirementSet(
                requirements=requirements, source_file=str(file_path), source_format=fmt,
            ),
            warnings=self._warnings,
            errors=self._errors,
            rows_processed=rows_processed,
            rows_skipped=rows_skipped,
        )
