from __future__ import annotations

from mudtool.ai.mud_spec_generator import (
    ReviewIssue,
    SpecReviewResult,
    build_fix_manifest,
    compare_review_results,
    review_issue_fingerprint,
    strip_fix_coverage_block,
)


def test_fix_manifest_treats_warnings_and_coverage_as_required_fixes():
    review = SpecReviewResult(
        approved=False,
        coverage_pct=70,
        issues=[
            ReviewIssue("error", "7", "Missing fail-safe write"),
            ReviewIssue("warning", "7", "Pseudo-code is too narrative"),
            ReviewIssue("info", "2", "Consider adding units"),
        ],
        suggestions=["Split long Section 7 validation step"],
        uncovered_req_ids=["REQ-42"],
        coverage_gaps=["REQ-42 not visible in runnable logic"],
    )

    manifest = build_fix_manifest(review)

    assert [item["kind"] for item in manifest] == [
        "issue",
        "issue",
        "issue",
        "suggestion",
        "coverage_gap",
    ]
    required = {item["message"]: item["required"] for item in manifest}
    assert required["Missing fail-safe write"] == "yes"
    assert required["Pseudo-code is too narrative"] == "yes"
    assert required["Consider adding units"] == "no"
    assert manifest[-1]["section"] == "7"
    assert manifest[-1]["required"] == "yes"


def test_issue_fingerprint_matches_whitespace_and_case_changes():
    first = ReviewIssue("warning", "Section 7", "  Missing   DEM call  ")
    second = ReviewIssue("WARNING", " section 7 ", "missing dem CALL")

    assert review_issue_fingerprint(first) == review_issue_fingerprint(second)


def test_compare_review_results_counts_resolved_and_repeated_issues():
    before = SpecReviewResult(
        approved=False,
        coverage_pct=60,
        issues=[
            ReviewIssue("error", "7", "Missing safe-state output"),
            ReviewIssue("warning", "7", "Missing DEM event"),
        ],
        uncovered_req_ids=["REQ-1"],
        coverage_gaps=["No Section 7 trace"],
    )
    after = SpecReviewResult(
        approved=False,
        coverage_pct=80,
        issues=[ReviewIssue("warning", "7", " missing dem event ")],
    )

    comparison = compare_review_results(before, after)

    assert comparison["initial_fix_count"] == 3
    assert comparison["resolved_issue_count"] == 2
    assert comparison["repeated_issue_count"] == 1
    assert comparison["quality_status"] == "needs_fix"


def test_strip_fix_coverage_block_removes_internal_notes():
    markdown = """# MUD Spec: SWC_Test

## 1. Overview
ok

## Fix Coverage
- ERROR-001 fixed

## 2. Ports
ok
"""

    cleaned = strip_fix_coverage_block(markdown)

    assert "Fix Coverage" not in cleaned
    assert "ERROR-001" not in cleaned
    assert "## 2. Ports" in cleaned
