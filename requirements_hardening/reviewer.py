"""Independent Reviewer agent.

The Reviewer is deliberately separate from the Author. It never edits the
requirement; it returns a decision and comments. For this MVP the review is
deterministic and stricter than the audit: every blocking field must exist, and
unresolved values must be recorded as open issues.
"""

from __future__ import annotations

from typing import Any

from .schema import VERIFICATION_METHODS


def _comment(rule_id: str, severity: str, message: str, suggested_fix: str) -> dict[str, str]:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "comment": message,
        "suggested_fix": suggested_fix,
    }


def review_requirement(req: dict[str, Any]) -> dict[str, Any]:
    comments: list[dict[str, str]] = []
    rid = req.get("id", "")

    if not rid:
        comments.append(_comment("RV-01", "critical", "Missing requirement ID.", "Assign a unique ID."))
    if not req.get("title"):
        comments.append(_comment("RV-02", "major", "Missing title.", "Add a short, unique title."))
    if not req.get("statement"):
        comments.append(_comment("RV-03", "critical", "Missing statement.", "Add a normative statement."))
    if not req.get("rationale"):
        comments.append(_comment("RV-04", "major", "Missing rationale.", "Explain why the requirement exists."))
    if not req.get("source") and not req.get("provenance", {}).get("source_file"):
        comments.append(_comment("RV-05", "major", "Missing source/provenance.", "Record the source or mark as an assumption."))

    ac = req.get("acceptance_criteria") or {}
    if not (ac.get("given") and ac.get("when") and ac.get("then")):
        comments.append(_comment("RV-06", "critical", "Acceptance criteria incomplete.", "Add Given/When/Then."))
    if not ac.get("expected_outputs"):
        comments.append(_comment("RV-07", "major", "No expected outputs in acceptance criteria.", "State the observable expected result."))
    if not ac.get("tolerance"):
        comments.append(_comment("RV-08", "minor", "No tolerance stated.", "State the measurement tolerance."))

    if req.get("verification_method") not in VERIFICATION_METHODS:
        comments.append(_comment("RV-09", "critical", "Invalid/missing verification method.", "Use test/analysis/review/inspection."))

    if req.get("level") in {"software", "unit"} and not req.get("parent_ids"):
        comments.append(_comment("RV-10", "major", "No parent requirement.", "Link to a system/stakeholder requirement."))

    if not (req.get("links") or {}).get("test"):
        comments.append(_comment("RV-11", "major", "No test-design link.", "Add at least one TD-* link."))

    if req.get("asil", "QM") != "QM":
        if not req.get("safety_goal_id") and not req.get("open_issues"):
            comments.append(_comment("RV-12", "major", "ASIL without safety goal/open issue.", "Add a safety goal/FSR reference or an open issue."))
        if not req.get("safe_state") and not req.get("fault_reaction") and req.get("type") == "safety":
            comments.append(_comment("RV-13", "major", "No safe state/fault reaction.", "Define the safe state or fault reaction."))

    if req.get("type") == "interface" and not req.get("interfaces"):
        comments.append(_comment("RV-14", "major", "Interface data missing.", "Add port/type/unit/range/resolution/rate."))
    if req.get("type") == "timing" and not req.get("timing"):
        comments.append(_comment("RV-15", "major", "Timing data missing.", "Add trigger/period/deadline/WCET."))
    if req.get("type") == "constraint" and not req.get("constraint_rationale"):
        comments.append(_comment("RV-16", "minor", "Constraint rationale missing.", "Explain why it is a constraint and how it is verified."))

    if req.get("implementation_constraint") is True and not req.get("constraint_rationale"):
        comments.append(_comment("RV-17", "major", "Implementation constraint without rationale.", "Add a constraint rationale."))

    if req.get("provenance", {}).get("source_file") == "gap_analysis" and not req.get("open_issues"):
        comments.append(_comment("RV-18", "major", "New requirement without an approval note.", "Add an open issue marking it as proposed."))

    # Decision
    critical = [c for c in comments if c["severity"] == "critical"]
    major = [c for c in comments if c["severity"] == "major"]
    if critical:
        decision = "reject"
        score = 40
    elif major:
        decision = "revise"
        score = 65
    elif req.get("open_issues"):
        decision = "accept_with_open_issues"
        score = 85
    else:
        decision = "accept"
        score = 100

    return {
        "requirement_id": rid,
        "decision": decision,
        "score": score,
        "blocking": bool(critical or major),
        "comments": comments,
        "open_issues": req.get("open_issues", []),
    }


def review(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    reviews = [review_requirement(req) for req in requirements]
    counts: dict[str, int] = {}
    for item in reviews:
        counts[item["decision"]] = counts.get(item["decision"], 0) + 1
    return {
        "reviewer": "independent-reviewer-v0.1",
        "requirements": len(reviews),
        "decisions": counts,
        "accept": counts.get("accept", 0) + counts.get("accept_with_open_issues", 0),
        "blocking": sum(1 for r in reviews if r["blocking"]),
        "reviews": reviews,
    }
