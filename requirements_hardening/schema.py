"""Canonical requirement schema and small shared helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

REQUIREMENT_TYPES = {"functional", "interface", "timing", "safety", "constraint"}
ASIL_LEVELS = {"QM", "ASIL-A", "ASIL-B", "ASIL-C", "ASIL-D"}
PRIORITIES = {"must", "should", "could", "won't"}
STATUSES = {"draft", "review", "approved", "rejected", "deprecated"}
LEVELS = {"stakeholder", "system", "software", "unit"}
VERIFICATION_METHODS = {"test", "analysis", "review", "inspection"}

# Fields every hardened requirement must carry. Values may be empty only when
# the field is explicitly listed in ``open_issues`` and the reviewer accepts it.
REQUIRED_FIELDS = [
    "id",
    "version",
    "title",
    "statement",
    "type",
    "level",
    "status",
    "verification_method",
    "acceptance_criteria",
    "provenance",
    "links",
    "change_history",
]


def blank_requirement() -> dict[str, Any]:
    """Return an empty canonical requirement."""
    return {
        "id": "",
        "version": "0.1.0",
        "title": "",
        "statement": "",
        "rationale": "",
        "source": "",
        "owner": "requirements-engineering",
        "level": "software",
        "type": "functional",
        "parent_ids": [],
        "child_ids": [],
        "allocated_to": "",
        "asil": "QM",
        "safety_goal_id": "",
        "ftti_ms": None,
        "safe_state": "",
        "verification_method": "review",
        "acceptance_criteria": {
            "given": "",
            "when": "",
            "then": "",
            "inputs": [],
            "expected_outputs": [],
            "tolerance": "",
            "boundary_values": [],
        },
        "interfaces": [],
        "timing": {},
        "modes": [],
        "fault_reaction": "",
        "calibration_params": [],
        "assumptions": [],
        "constraints": [],
        "open_issues": [],
        "links": {"design": [], "test": [], "code": [], "standards": []},
        "provenance": {
            "source_file": "",
            "source_row": 0,
            "original_id": "",
            "input_hash": "",
            "generated_by": "requirements_hardening",
        },
        "change_history": [],
        "original": {},
        "notes": "",
        "design_notes": "",
        "implementation_constraint": False,
        "constraint_rationale": "",
    }


def canonical_type(value: str) -> str:
    v = (value or "").strip().lower()
    aliases = {
        "architecture": "functional",
        "function": "functional",
        "interface": "interface",
        "timing": "timing",
        "safety": "safety",
        "constraint": "constraint",
        "non-functional": "constraint",
        "nonfunctional": "constraint",
    }
    return aliases.get(v, "functional")


def canonical_asil(value: str) -> str:
    v = (value or "QM").strip().upper().replace("_", "-")
    if v in {"ASILA", "ASIL-A"}:
        return "ASIL-A"
    if v in {"ASILB", "ASIL-B"}:
        return "ASIL-B"
    if v in {"ASILC", "ASIL-C"}:
        return "ASIL-C"
    if v in {"ASILD", "ASIL-D"}:
        return "ASIL-D"
    if v in {"QM", ""}:
        return "QM"
    return v


def canonical_priority(value: str) -> str:
    v = (value or "must").strip().lower()
    return v if v in PRIORITIES else "must"


def canonical_status(value: str) -> str:
    v = (value or "draft").strip().lower()
    return v if v in STATUSES else "draft"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", (value or "").replace("\r", " ").replace("\n", " ")).strip()
    return text


def ensure_sentence(text: str) -> str:
    text = clean_text(text)
    if text and text[-1] not in ".!?":
        text += "."
    return text


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text or "")


def id_matches(value: str) -> bool:
    return bool(re.match(r"^[A-Z]+-(?:[A-Z]+-)*\d+$", value or ""))


def sort_key(requirement: dict[str, Any]) -> tuple[str, int, str]:
    rid = requirement.get("id", "")
    m = re.match(r"^([A-Z]+-[A-Z]+-)(\d+)$", rid)
    if m:
        return (m.group(1), int(m.group(2)), rid)
    return (rid, 0, rid)
