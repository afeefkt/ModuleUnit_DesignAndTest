"""Read the evidence of a run: coverage numbers, per-test results, and a ZIP of it all."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

_SKIP_SUFFIXES = {".o", ".gcda", ".gcno", ".d"}
_SKIP_NAMES = {"run_tests"}


def _pct(hit: int, found: int) -> float | None:
    return round(100.0 * hit / found, 1) if found else None


def coverage_summary(coverage_info: Path) -> dict[str, Any]:
    """Sum the lcov ``LF/LH`` (lines), ``BRF/BRH`` (branches), ``FNF/FNH`` (functions) records."""
    totals = {"LF": 0, "LH": 0, "BRF": 0, "BRH": 0, "FNF": 0, "FNH": 0}
    files = 0
    if not Path(coverage_info).is_file():
        return {}
    for line in Path(coverage_info).read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("SF:"):
            files += 1
            continue
        key, _, value = line.partition(":")
        if key in totals and value.strip().isdigit():
            totals[key] += int(value)
    return {
        "files": files,
        "lines_found": totals["LF"], "lines_hit": totals["LH"], "line_pct": _pct(totals["LH"], totals["LF"]),
        "branches_found": totals["BRF"], "branches_hit": totals["BRH"], "branch_pct": _pct(totals["BRH"], totals["BRF"]),
        "functions_found": totals["FNF"], "functions_hit": totals["FNH"], "function_pct": _pct(totals["FNH"], totals["FNF"]),
    }


def junit_cases(xml_path: Path) -> list[dict[str, Any]]:
    """One row per ``<testcase>``: name, group, time, status (passed/failed/error/skipped), message."""
    if not Path(xml_path).is_file():
        return []
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return []
    rows: list[dict[str, Any]] = []
    for case in root.iter("testcase"):
        status, message = "passed", ""
        for tag, label in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
            child = case.find(tag)
            if child is not None:
                status = label
                message = (child.get("message") or child.text or "").strip()
                break
        rows.append({
            "group": case.get("classname", ""),
            "test": case.get("name", ""),
            "time_s": float(case.get("time") or 0),
            "status": status,
            "message": message,
        })
    return rows


def zip_run(run_folder: Path) -> bytes:
    """ZIP of a run's evidence (inputs, designs, code, tests, reports) without build objects."""
    run_folder = Path(run_folder)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(run_folder.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix in _SKIP_SUFFIXES or path.name in _SKIP_NAMES:
                continue
            zf.write(path, Path(run_folder.name) / path.relative_to(run_folder))
    return buf.getvalue()


def to_windows_path(path: Path | str) -> str:
    """``/mnt/d/x/y`` -> ``D:\\x\\y`` (other paths are returned unchanged)."""
    s = str(path)
    if s.startswith("/mnt/") and len(s) > 6 and s[6] == "/":
        return f"{s[5].upper()}:" + s[6:].replace("/", "\\")
    return s
