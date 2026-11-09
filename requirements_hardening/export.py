"""Export hardened requirements, test design and traceability artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _ac_text(ac: dict[str, Any]) -> str:
    return (
        f"GIVEN {ac.get('given', '')} "
        f"WHEN {ac.get('when', '')} "
        f"THEN {ac.get('then', '')} "
        f"TOLERANCE {ac.get('tolerance', '')}"
    ).strip()


def compatibility_rows(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for req in requirements:
        rows.append({
            "Object Identifier": req.get("id", ""),
            "Object Heading": req.get("title", ""),
            "Object Text": req.get("statement", ""),
            "Object Level": "1" if req.get("level") == "system" else "2",
            "Allocated To": req.get("allocated_to", ""),
            "ASIL": req.get("asil", "QM"),
            "Priority": req.get("priority", "must"),
            "Status": "draft" if req.get("status") == "review" else req.get("status", "draft"),
            "Type": req.get("type", "functional"),
            "Parent_ID": ", ".join(req.get("parent_ids", [])),
            "Notes": (req.get("notes", "") + f"; hardened={req.get('version', '0.1.0')}; verification={req.get('verification_method', '')}; test={','.join(req.get('links', {}).get('test', []))}").strip("; "),
        })
    return rows


def extended_rows(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for req in requirements:
        ac = req.get("acceptance_criteria") or {}
        rows.append({
            "id": req.get("id", ""),
            "version": req.get("version", ""),
            "title": req.get("title", ""),
            "statement": req.get("statement", ""),
            "type": req.get("type", ""),
            "level": req.get("level", ""),
            "status": req.get("status", ""),
            "allocated_to": req.get("allocated_to", ""),
            "asil": req.get("asil", ""),
            "priority": req.get("priority", ""),
            "parent_ids": ", ".join(req.get("parent_ids", [])),
            "verification_method": req.get("verification_method", ""),
            "given": ac.get("given", ""),
            "when": ac.get("when", ""),
            "then": ac.get("then", ""),
            "tolerance": ac.get("tolerance", ""),
            "test_ids": ", ".join(req.get("links", {}).get("test", [])),
            "design_links": ", ".join(req.get("links", {}).get("design", [])),
            "safety_goal_id": req.get("safety_goal_id", ""),
            "safe_state": req.get("safe_state", ""),
            "ftti_ms": req.get("ftti_ms", ""),
            "open_issues": " | ".join(req.get("open_issues", [])),
            "rationale": req.get("rationale", ""),
            "source": req.get("source", ""),
            "split_from": req.get("split_from", ""),
            "split_into": ", ".join(req.get("split_into", [])),
            "provenance_file": req.get("provenance", {}).get("source_file", ""),
            "provenance_row": req.get("provenance", {}).get("source_row", ""),
        })
    return rows


def test_design_rows(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for req in requirements:
        ac = req.get("acceptance_criteria") or {}
        boundary = "; ".join(
            f"{b.get('parameter')}: {', '.join(str(v) for v in b.get('values', []))}"
            for b in ac.get("boundary_values", [])
        )
        rows.append({
            "Test_ID": f"TD-{req.get('id', '')}",
            "Req_ID": req.get("id", ""),
            "Test_Type": req.get("verification_method", ""),
            "ASIL": req.get("asil", ""),
            "Given": ac.get("given", ""),
            "When": ac.get("when", ""),
            "Then": ac.get("then", ""),
            "Inputs": "; ".join(str(x) for x in ac.get("inputs", [])),
            "Expected_Outputs": "; ".join(str(x) for x in ac.get("expected_outputs", [])),
            "Tolerance": ac.get("tolerance", ""),
            "Boundary_Values": boundary,
            "Open_Issues": " | ".join(req.get("open_issues", [])),
        })
    return rows


def trace_rows(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for req in requirements:
        rows.append({
            "Req_ID": req.get("id", ""),
            "Parent_IDs": ", ".join(req.get("parent_ids", [])),
            "Allocated_To": req.get("allocated_to", ""),
            "Design_Links": ", ".join(req.get("links", {}).get("design", [])),
            "Test_IDs": ", ".join(req.get("links", {}).get("test", [])),
            "Split_From": req.get("split_from", ""),
            "Split_Into": ", ".join(req.get("split_into", [])),
            "Standards": ", ".join(req.get("links", {}).get("standards", [])),
            "Status": req.get("status", ""),
            "ASIL": req.get("asil", ""),
            "Verification": req.get("verification_method", ""),
        })
    return rows


def export_all(
    requirements: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    review_result: dict[str, Any],
    metrics: dict[str, Any],
    run_dir: str | Path,
    hardened_dir: str | Path,
    set_name: str | None = None,
) -> dict[str, str]:
    run_dir = Path(run_dir)
    hardened_dir = Path(hardened_dir)
    set_name = set_name or hardened_dir.name
    paths: dict[str, str] = {}

    # Run artifacts
    _write_json(run_dir / "02_findings" / "findings.json", findings)
    _write_json(run_dir / "04_reviews" / "review.json", review_result)
    _write_json(run_dir / "05_verified" / "metrics.json", metrics)
    _write_json(run_dir / "05_verified" / "requirements_extended.json", requirements)
    _write_csv(run_dir / "05_verified" / "requirements_extended.csv", extended_rows(requirements), list(extended_rows(requirements)[0].keys()) if requirements else ["id"])
    _write_csv(run_dir / "07_test_design" / "test_design.csv", test_design_rows(requirements), list(test_design_rows(requirements)[0].keys()) if requirements else ["Test_ID"])
    _write_csv(run_dir / "06_trace" / "trace_matrix.csv", trace_rows(requirements), list(trace_rows(requirements)[0].keys()) if requirements else ["Req_ID"])

    # Hardened baseline (new folder; originals untouched)
    _write_json(hardened_dir / f"{set_name}_requirements_extended.json", requirements)
    _write_csv(hardened_dir / f"{set_name}_requirements_hardened.csv", compatibility_rows(requirements), [
        "Object Identifier", "Object Heading", "Object Text", "Object Level", "Allocated To",
        "ASIL", "Priority", "Status", "Type", "Parent_ID", "Notes",
    ])
    _write_csv(hardened_dir / f"{set_name}_requirements_extended.csv", extended_rows(requirements), list(extended_rows(requirements)[0].keys()) if requirements else ["id"])
    _write_csv(hardened_dir / "test_design.csv", test_design_rows(requirements), list(test_design_rows(requirements)[0].keys()) if requirements else ["Test_ID"])
    _write_csv(hardened_dir / "trace_matrix.csv", trace_rows(requirements), list(trace_rows(requirements)[0].keys()) if requirements else ["Req_ID"])

    paths["findings"] = str(run_dir / "02_findings" / "findings.json")
    paths["review"] = str(run_dir / "04_reviews" / "review.json")
    paths["metrics"] = str(run_dir / "05_verified" / "metrics.json")
    paths["extended_json"] = str(hardened_dir / f"{set_name}_requirements_extended.json")
    paths["hardened_csv"] = str(hardened_dir / f"{set_name}_requirements_hardened.csv")
    paths["extended_csv"] = str(hardened_dir / f"{set_name}_requirements_extended.csv")
    paths["test_design"] = str(hardened_dir / "test_design.csv")
    paths["trace"] = str(hardened_dir / "trace_matrix.csv")
    return paths
