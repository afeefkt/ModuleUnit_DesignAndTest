"""Parse CSV/XLSX-ish requirement exports into the canonical schema."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from .schema import blank_requirement, canonical_asil, canonical_priority, canonical_status, canonical_type, clean_text, sha256_file

AEB_COLUMN_MAP = {
    "Object Identifier": "id",
    "Object Heading": "title",
    "Object Text": "statement",
    "Object Level": "object_level",
    "Allocated To": "allocated_to",
    "ASIL": "asil",
    "Priority": "priority",
    "Status": "status",
    "Type": "type",
    "Parent_ID": "parent_id",
    "Notes": "notes",
}

# Generic aliases (subset of mud-tool importers, kept local to avoid coupling).
GENERIC_ALIASES = {
    "id": ["req_id", "Req_ID", "ID", "Requirement ID", "Object Identifier", "Identifier"],
    "title": ["title", "Title", "Name", "Object Heading", "Summary"],
    "statement": ["description", "Description", "Object Text", "Text", "Statement"],
    "allocated_to": ["module_hint", "Allocated To", "Module", "Component", "Target Module"],
    "asil": ["ASIL", "asil", "Safety Level", "safety_level"],
    "priority": ["Priority", "priority", "Importance"],
    "status": ["Status", "status", "State"],
    "type": ["Type", "type", "req_type", "Requirement Type"],
    "parent_id": ["Parent_ID", "parent_id", "Parent", "Parent ID"],
    "notes": ["Notes", "notes", "Rationale", "Comments", "Remarks"],
    "object_level": ["Object Level", "Level"],
}


def _normalize_header(value: str) -> str:
    return re.sub(r"[\s_.\-]+", "", value or "").lower()


_LOOKUP: dict[str, str] = {}
for canonical, aliases in GENERIC_ALIASES.items():
    for alias in aliases:
        _LOOKUP[_normalize_header(alias)] = canonical


def _map_row(row: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in row.items():
        canonical = _LOOKUP.get(_normalize_header(key))
        if canonical and canonical not in out:
            out[canonical] = value
    return out


def _level_from_object_level(value: str) -> str:
    v = (value or "").strip()
    if v == "1":
        return "system"
    if v == "2":
        return "software"
    if v in {"3", "4"}:
        return "unit"
    return "software"


def extract_numbers(text: str) -> list[dict[str, Any]]:
    """Extract numeric thresholds with units from requirement text."""
    unit_pattern = r"(ms|s|km/h|m/s2|m/s²|m/s|bar|%|m|°C|V|A|Ah|N|Nm|objects?|cycles?)"
    matches = re.finditer(rf"(?<![\d.])(-?\d+(?:\.\d+)?)\s*{unit_pattern}", text or "", flags=re.IGNORECASE)
    out: list[dict[str, Any]] = []
    for m in matches:
        raw_value = m.group(1)
        unit = m.group(2)
        value = float(raw_value)
        out.append({"value": value, "unit": unit, "raw": m.group(0)})
    return out


def extract_period_ms(text: str) -> float | None:
    m = re.search(r"every\s+(\d+(?:\.\d+)?)\s*ms", text or "", flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*ms\s+cycle", text or "", flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def extract_runnables(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bRE_[A-Za-z0-9_]+\b", text or "")))


def extract_ports(text: str) -> list[str]:
    return sorted(set(re.findall(r"\b(?:RP|PP)_[A-Za-z0-9_]+\b", text or "")))


def extract_interfaces(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bIF_[A-Za-z0-9_]+\b", text or "")))


def extract_dtcs(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bDTC_[A-Za-z0-9_]+\b", text or "")))


def extract_standards(text: str) -> list[str]:
    refs = []
    for pattern, label in [
        (r"R152", "UNECE R152"),
        (r"ISO\s*26262", "ISO 26262"),
        (r"ISO\s*22839", "ISO 22839"),
        (r"FMVSS\s*127", "FMVSS 127"),
        (r"ASPICE|Automotive SPICE", "Automotive SPICE"),
        (r"ISO\s*21434", "ISO 21434"),
        (r"AUTOSAR", "AUTOSAR"),
    ]:
        if re.search(pattern, text or "", flags=re.IGNORECASE):
            refs.append(label)
    return refs


def parse_csv(path: str | Path) -> list[dict[str, Any]]:
    """Parse a CSV export into canonical requirement dictionaries."""
    path = Path(path)
    input_hash = sha256_file(path)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    requirements: list[dict[str, Any]] = []
    for index, raw in enumerate(rows, start=1):
        mapped = _map_row(raw)
        req = blank_requirement()
        req["id"] = clean_text(mapped.get("id", "")).upper().replace(" ", "-")
        req["title"] = clean_text(mapped.get("title", ""))
        req["statement"] = clean_text(mapped.get("statement", ""))
        req["type"] = canonical_type(mapped.get("type", "functional"))
        req["asil"] = canonical_asil(mapped.get("asil", "QM"))
        req["priority"] = canonical_priority(mapped.get("priority", "must"))
        req["status"] = canonical_status(mapped.get("status", "draft"))
        req["allocated_to"] = clean_text(mapped.get("allocated_to", ""))
        req["level"] = _level_from_object_level(mapped.get("object_level", "2"))
        parent = clean_text(mapped.get("parent_id", ""))
        req["parent_ids"] = [parent] if parent else []
        req["notes"] = clean_text(mapped.get("notes", ""))
        req["source"] = f"{path.name}:row{index}"
        req["provenance"] = {
            "source_file": str(path),
            "source_row": index,
            "original_id": req["id"],
            "input_hash": input_hash,
            "generated_by": "requirements_hardening.parser",
        }
        req["original"] = dict(raw)
        req["links"]["standards"] = extract_standards(req["statement"] + " " + req["notes"])
        req["links"]["design"] = extract_runnables(req["statement"])
        requirements.append(req)

    _attach_children(requirements)
    return requirements


def _attach_children(requirements: list[dict[str, Any]]) -> None:
    by_id = {r["id"]: r for r in requirements}
    for req in requirements:
        for parent in req.get("parent_ids", []):
            if parent in by_id:
                if req["id"] not in by_id[parent]["child_ids"]:
                    by_id[parent]["child_ids"].append(req["id"])


def parse_aeb(path: str | Path) -> list[dict[str, Any]]:
    """AEB-specific entry point (kept explicit for clarity)."""
    return parse_csv(path)


def parse_any(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_csv(path)
    raise ValueError(f"Unsupported requirement format for this MVP: {suffix}. Use CSV.")
