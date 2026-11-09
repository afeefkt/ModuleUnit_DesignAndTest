"""Deterministic requirement audit rules and scoring."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .parser import extract_numbers, extract_period_ms

VAGUE_TERMS = [
    "appropriate", "sufficient", "sufficiently", "fast", "quick", "robust", "minimize",
    "minimise", "maximize", "maximise", "as needed", "if necessary", "etc.", "and/or",
    "user-friendly", "efficient", "adequate", "reasonable", "normal", "proper", "smooth",
]
AMBIGUOUS_PHRASES = [
    "one control cycle", "full charge cycle", "as soon as possible", "real time", "near real time",
    "high speed", "low speed", "full rated", "within a reasonable time", "when required",
]
DESIGN_KEYWORDS = [
    "algorithm", "formula", "equation", "pi control", "butterworth", "piecewise",
    "lookup table", "kalman", "ekf", "smt solver", "helper function", "calls ",
    "pointer", "malloc",
]

KNOWN_CONFLICTS = [
    {
        "ids": ["REQ-AEB-002", "REQ-AEB-209"],
        "message": "Original conflict: automatic braking is deactivated outside 10-60 km/h while pedestrian FCW remains active below 10 km/h. Interim decision: keep the split; confirm transition/hysteresis.",
    },
    {
        "ids": ["REQ-AEB-308"],
        "message": "Original gap: failsafe behaviour below 10 km/h was unspecified. Interim decision: 0 m/s2 + FCW; confirm with the safety manager.",
    },
    {
        "ids": ["REQ-AEB-005"],
        "message": "Original ambiguity: 'one control cycle' spans 5/10/20 ms runnables. Interim decision: use the 10 ms arbitration cycle; confirm in every mode.",
    },
    {
        "ids": ["REQ-AEB-303"],
        "message": "Original tension: FULL 9.0 m/s2 vs the UNECE R152 5.0 m/s2 minimum. Interim decision: keep 9.0 as the performance target; ABS may reduce it; confirm homologation.",
    },
    {
        "ids": ["REQ-AEB-310"],
        "message": "Original priority was 'should' for a false-braking mitigation. Interim decision: promote to 'must'; confirm with the safety analysis.",
    },
]

SEVERITY_WEIGHT = {"critical": 25, "major": 10, "minor": 3, "info": 1}


def load_rulebook(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path or Path(__file__).parent / "rules" / "rulebook.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _finding(
    req: dict[str, Any],
    rule_id: str,
    severity: str,
    message: str,
    evidence: str,
    suggested_fix: str,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "finding_id": f"F-{req.get('id', 'UNKNOWN')}-{rule_id}",
        "requirement_id": req.get("id", ""),
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "evidence": evidence[:500],
        "suggested_fix": suggested_fix,
        "confidence": confidence,
        "source": "deterministic",
    }


def _has_open_issue(req: dict[str, Any], *keywords: str) -> bool:
    blob = " ".join(str(x) for x in req.get("open_issues", [])) + " " + str(req.get("rationale", ""))
    keywords = tuple(keywords) + ("decision", "confirm", "promoted")
    return any(k.lower() in blob.lower() for k in keywords)


def audit(requirements: list[dict[str, Any]], stage: str = "baseline") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    ids = [r.get("id", "") for r in requirements]
    duplicates = {rid for rid in ids if ids.count(rid) > 1}

    for req in requirements:
        rid = req.get("id", "")
        statement = req.get("statement", "")
        text = statement.lower()

        # RQ-01 atomicity
        shall_count = len(re.findall(r"\bshall\b", statement, flags=re.IGNORECASE))
        if shall_count > 1:
            severity = "major" if shall_count >= 3 else "minor"
            findings.append(_finding(
                req, "RQ-01", severity,
                f"Compound requirement: {shall_count} 'shall' clauses (split candidate).",
                f"{shall_count} 'shall' clauses in: {statement[:220]}",
                "Split into one atomic requirement per independent obligation; keep a parent for the group.",
            ))

        # RQ-02 vague language
        hits = [term for term in VAGUE_TERMS if re.search(rf"\b{re.escape(term)}\b", text)]
        if hits:
            findings.append(_finding(
                req, "RQ-02", "minor", f"Vague term(s): {', '.join(hits)}.",
                statement[:240], "Replace with a measurable condition, range or tolerance.",
            ))

        # RQ-03 acceptance criteria
        ac = req.get("acceptance_criteria") or {}
        if not (ac.get("given") and ac.get("when") and ac.get("then")):
            findings.append(_finding(
                req, "RQ-03", "critical", "Missing Given/When/Then acceptance criteria.",
                str(ac)[:240], "Add testable preconditions, stimulus, expected outputs and tolerance.",
            ))

        # RQ-04 verification method
        if not req.get("verification_method"):
            findings.append(_finding(
                req, "RQ-04", "critical", "Missing verification method.",
                "", "Assign test/analysis/review/inspection per requirement.",
            ))

        # RQ-05 parent trace
        if req.get("level") in {"software", "unit"} and not req.get("parent_ids"):
            findings.append(_finding(
                req, "RQ-05", "major", "Missing parent requirement link.",
                "", "Link to the allocated system/stakeholder requirement.",
            ))

        # RQ-06 ASIL rationale
        if req.get("asil", "QM") != "QM":
            if not req.get("safety_goal_id") and not _has_open_issue(req, "safety goal", "hara", "fsr", "tsr"):
                findings.append(_finding(
                    req, "RQ-06", "major", "ASIL is asserted without a safety goal/FSR reference.",
                    f"ASIL={req.get('asil')}", "Add safety goal/FSR/TSR reference or an explicit open issue for HARA confirmation.",
                ))

        # RQ-07 design leakage
        if req.get("type") != "constraint" and not req.get("implementation_constraint"):
            design_hits = [k for k in DESIGN_KEYWORDS if k in text]
            if design_hits:
                findings.append(_finding(
                    req, "RQ-07", "major", f"Possible design leakage: {', '.join(design_hits[:4])}.",
                    statement[:240], "Move 'how' details to the design artifact, or mark as a constraint with rationale.",
                ))

        # RQ-08 interface completeness
        if req.get("type") == "interface" and not req.get("interfaces"):
            findings.append(_finding(
                req, "RQ-08", "major", "Interface requirement has no structured interface data.",
                statement[:240], "Add port, direction, data type, unit, range, resolution and update rate.",
            ))

        # RQ-09 timing completeness
        if req.get("type") == "timing" and not req.get("timing"):
            findings.append(_finding(
                req, "RQ-09", "major", "Timing requirement has no structured timing data.",
                statement[:240], "Add trigger, period, deadline/WCET and jitter.",
            ))

        # RQ-10 safety completeness
        if req.get("type") == "safety" and not req.get("safe_state") and not req.get("fault_reaction") and req.get("ftti_ms") is None:
            findings.append(_finding(
                req, "RQ-10", "major", "Safety requirement has no safe state, fault reaction or FTTI.",
                statement[:240], "Add fault condition, safe state/reaction, debounce and FTTI.",
            ))

        # RQ-11 safety priority
        if req.get("type") == "safety" and str(req.get("priority", "")).lower() != "must":
            findings.append(_finding(
                req, "RQ-11", "major", "Safety requirement is not marked 'must'.",
                f"priority={req.get('priority')}", "Set priority to 'must' or justify why the requirement is not safety-critical.",
            ))

        # RQ-12 duplicate ID
        if rid in duplicates:
            findings.append(_finding(
                req, "RQ-12", "critical", "Duplicate requirement ID.",
                rid, "Make IDs unique; preserve the original in provenance.",
            ))

        # RQ-13 test link
        if not (req.get("links") or {}).get("test"):
            findings.append(_finding(
                req, "RQ-13", "major", "Missing test-design link.",
                "", "Assign at least one test-design ID and add it to links.test.",
            ))

        # RQ-14 unsupported numeric threshold
        numbers = extract_numbers(statement)
        if numbers and not req.get("rationale") and not _has_open_issue(req, "rationale", "source", "calibration", "threshold"):
            findings.append(_finding(
                req, "RQ-14", "info", "Numeric threshold has no stated rationale/source.",
                ", ".join(n["raw"] for n in numbers[:6]),
                "Add rationale/source or record an open issue for calibration/standard confirmation.",
            ))

        # RQ-15 ambiguous phrase
        ambiguous = [p for p in AMBIGUOUS_PHRASES if p in text]
        if ambiguous:
            findings.append(_finding(
                req, "RQ-15", "minor", f"Ambiguous phrase(s): {', '.join(ambiguous)}.",
                statement[:240], "Replace with a measurable condition (e.g. explicit cycle time).",
            ))

        # RQ-17 constraint rationale
        if req.get("type") == "constraint" and not req.get("constraint_rationale"):
            findings.append(_finding(
                req, "RQ-17", "minor", "Constraint has no rationale/verification note.",
                statement[:240], "State why it is a constraint and how compliance is verified.",
            ))

        # RQ-18 normative statement
        if not re.search(r"\bshall(?:\s+not)?\b", statement, flags=re.IGNORECASE):
            findings.append(_finding(
                req, "RQ-18", "major", "Statement is not normative (no 'shall').",
                statement[:240], "Rewrite as a normative 'shall' statement.",
            ))

        # RQ-19 HARA assumption
        if req.get("asil", "QM") != "QM" and stage == "baseline":
            findings.append(_finding(
                req, "RQ-19", "info", "ASIL value is a sample assumption; HARA/FSR confirmation required.",
                f"ASIL={req.get('asil')}", "Record as an assumption; confirm with the safety manager.",
            ))

    # RQ-16 known conflicts
    for conflict in KNOWN_CONFLICTS:
        for rid in conflict["ids"]:
            req = next((r for r in requirements if r.get("id") == rid), None)
            if not req:
                continue
            if _has_open_issue(req, "conflict", "reconcil", "clarif", "ambiguous", "undefined", "rationale"):
                severity = "info"
            else:
                severity = "major"
            findings.append(_finding(
                req, "RQ-16", severity, conflict["message"],
                "Cross-requirement consistency check", "Reconcile the requirements or record a decision/open issue.",
                confidence=0.95,
            ))

    return findings


def score(requirements: list[dict[str, Any]], findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute requirement-level and set-level metrics."""
    by_req: dict[str, list[dict[str, Any]]] = {}
    for f in findings:
        by_req.setdefault(f["requirement_id"], []).append(f)

    per_req: list[dict[str, Any]] = []
    for req in requirements:
        req_findings = by_req.get(req.get("id", ""), [])
        penalty = sum(SEVERITY_WEIGHT.get(f["severity"], 1) for f in req_findings)
        per_req.append({
            "id": req.get("id"),
            "score": max(0, 100 - penalty),
            "critical": sum(1 for f in req_findings if f["severity"] == "critical"),
            "major": sum(1 for f in req_findings if f["severity"] == "major"),
            "minor": sum(1 for f in req_findings if f["severity"] == "minor"),
            "info": sum(1 for f in req_findings if f["severity"] == "info"),
        })

    total = len(requirements) or 1
    average = round(sum(r["score"] for r in per_req) / total, 1)

    interface_reqs = [r for r in requirements if r.get("type") == "interface"]
    timing_reqs = [r for r in requirements if r.get("type") == "timing"]
    safety_reqs = [r for r in requirements if r.get("type") == "safety"]
    traceable_reqs = [r for r in requirements if r.get("level") in {"software", "unit"}]

    return {
        "requirements": len(requirements),
        "findings": len(findings),
        "critical": sum(1 for f in findings if f["severity"] == "critical"),
        "major": sum(1 for f in findings if f["severity"] == "major"),
        "minor": sum(1 for f in findings if f["severity"] == "minor"),
        "info": sum(1 for f in findings if f["severity"] == "info"),
        "average_score": average,
        "with_acceptance_criteria": sum(1 for r in requirements if (r.get("acceptance_criteria") or {}).get("then")),
        "with_verification_method": sum(1 for r in requirements if r.get("verification_method")),
        "with_parent": sum(1 for r in traceable_reqs if r.get("parent_ids")),
        "traceable_total": len(traceable_reqs),
        "with_test_link": sum(1 for r in requirements if (r.get("links") or {}).get("test")),
        "with_safety_goal": sum(1 for r in requirements if r.get("safety_goal_id")),
        "with_interface_data": sum(1 for r in interface_reqs if r.get("interfaces")),
        "interface_total": len(interface_reqs),
        "with_timing_data": sum(1 for r in timing_reqs if r.get("timing")),
        "timing_total": len(timing_reqs),
        "with_safe_state": sum(1 for r in safety_reqs if r.get("safe_state") or r.get("fault_reaction")),
        "safety_total": len(safety_reqs),
        "atomic": sum(1 for r in requirements if len(re.findall(r"\bshall\b", r.get("statement", ""), flags=re.IGNORECASE)) <= 1),
        "compound_candidates": sum(1 for r in requirements if len(re.findall(r"\bshall\b", r.get("statement", ""), flags=re.IGNORECASE)) == 2),
        "per_requirement": per_req,
    }
