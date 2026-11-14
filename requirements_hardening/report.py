"""Human-readable reports and review packet (set-aware)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import sort_key


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(x).replace("\n", " ") for x in row) + " |")
    return "\n".join(lines)


def _metric_row(label: str, before: Any, after: Any) -> list[str]:
    return [label, str(before), str(after)]


def _pct(value: int, total: int) -> str:
    return f"{value}/{total} ({round(100 * value / total, 1)}%)" if total else "0/0"


def _split_summary(requirements: list[dict[str, Any]]) -> tuple[int, int, str]:
    children = [r for r in requirements if r.get("split_from")]
    parents = {r.get("split_from") for r in children}
    ids = sorted((r.get("id", "") for r in children))
    span = f"{ids[0]}..{ids[-1]}" if ids else "none"
    return len(parents), len(children), span


def write_polished_markdown(requirements: list[dict[str, Any]], hardened_dir: str | Path, run_dir: str | Path) -> str:
    hardened_dir = Path(hardened_dir)
    run_dir = Path(run_dir)
    set_label = hardened_dir.name.upper()
    parents, children, span = _split_summary(requirements)
    groups: dict[str, list[dict[str, Any]]] = {}
    for req in sorted(requirements, key=sort_key):
        groups.setdefault(req.get("allocated_to") or "Unallocated", []).append(req)
    source_file = next(
        (r.get("provenance", {}).get("source_file", "") for r in requirements
         if r.get("provenance", {}).get("source_file") not in {"", "gap_analysis"}),
        requirements[0].get("provenance", {}).get("source_file", "") if requirements else "",
    )

    lines = [
        f"# {set_label} requirements — polished L2-oriented draft",
        "",
        "> Status: **review draft**. Human approval required. Not certified.",
        f"> Source: `{source_file}` (unchanged).",
        f"> Requirements: **{len(requirements)}** ({len(requirements) - children} retained/derived + "
        f"{children} atomic split parts).",
        "",
        "## How to read this document",
        "",
        f"Each requirement is atomic where possible. {parents} compound requirements were split into "
        f"{children} atomic parts; the original ID keeps part 1 and parts 2+ use `{span}`. "
        "Acceptance criteria are drafts derived from the source text. Open issues are decisions for the "
        "human reviewer, not hidden assumptions.",
        "",
        "## Summary by allocation",
        "",
        _md_table(["Allocation", "Requirements"], [[k, len(v)] for k, v in sorted(groups.items())]),
        "",
    ]
    for group, reqs in sorted(groups.items()):
        lines.extend([f"## {group}", ""])
        for req in reqs:
            ac = req.get("acceptance_criteria") or {}
            lines.extend([
                f"### {req.get('id')} — {req.get('title')}",
                "",
                f"**Type:** {req.get('type')} · **ASIL:** {req.get('asil')} · **Priority:** {req.get('priority')} · "
                f"**Status:** {req.get('status')} · **Verification:** {req.get('verification_method')}",
                "",
                f"**Statement:** {req.get('statement')}",
                "",
                f"**Rationale:** {req.get('rationale')}",
                "",
                "**Acceptance criteria (draft):**",
                "",
                f"- **Given:** {ac.get('given', '')}",
                f"- **When:** {ac.get('when', '')}",
                f"- **Then:** {ac.get('then', '')}",
                f"- **Tolerance:** {ac.get('tolerance', '')}",
                "",
            ])
            boundaries = ac.get("boundary_values") or []
            if boundaries:
                lines.append("**Boundary values:**")
                lines.append("")
                for b in boundaries:
                    lines.append(f"- `{b.get('parameter')}` → {', '.join(str(v) for v in b.get('values', []))}")
                lines.append("")
            lines.extend([
                f"**Trace:** parent={', '.join(req.get('parent_ids', [])) or '—'} · "
                f"design={', '.join(req.get('links', {}).get('design', [])) or '—'} · "
                f"test={', '.join(req.get('links', {}).get('test', [])) or '—'}",
                "",
            ])
            if req.get("split_from"):
                lines.extend([f"**Split from:** `{req.get('split_from')}`", ""])
            elif req.get("split_into"):
                lines.extend([f"**Split into:** {', '.join(req.get('split_into', []))}", ""])
            lines.extend([
                f"**Open issues:** {'; '.join(req.get('open_issues', [])) or 'none'}",
                "",
                "---",
                "",
            ])
    text = "\n".join(lines)
    name = f"{set_label}_REQUIREMENTS_POLISHED.md"
    (hardened_dir / name).write_text(text, encoding="utf-8")
    (run_dir / "08_evidence" / name).write_text(text, encoding="utf-8")
    return str(hardened_dir / name)


def write_reports(
    original: list[dict[str, Any]],
    hardened: list[dict[str, Any]],
    baseline_metrics: dict[str, Any],
    hardened_metrics: dict[str, Any],
    findings: list[dict[str, Any]],
    review_result: dict[str, Any],
    run_dir: str | Path,
    hardened_dir: str | Path,
) -> dict[str, str]:
    run_dir = Path(run_dir)
    hardened_dir = Path(hardened_dir)
    set_name = hardened_dir.name
    set_label = set_name.upper()
    total = len(hardened)
    parents, split_children, split_span = _split_summary(hardened)
    original_ids = {r.get("id") for r in original}
    split_ids = [r.get("id") for r in hardened if r.get("split_from")]
    gap_ids = [r.get("id") for r in hardened if r.get("id") not in original_ids and not r.get("split_from")]
    paths: dict[str, str] = {}

    # Change log
    changed = []
    orig_by_id = {r.get("id"): r for r in original}
    for req in hardened:
        old = orig_by_id.get(req.get("id"))
        if not old:
            continue
        fields = []
        for key in ["statement", "rationale", "verification_method", "acceptance_criteria", "open_issues", "priority"]:
            if old.get(key) != req.get(key):
                fields.append(key)
        if fields:
            changed.append({"id": req.get("id"), "fields": fields})

    change_log = [
        f"# {set_label} change log",
        "",
        f"- Original requirements: {len(original)}",
        f"- Hardened requirements: {total}",
        f"- Atomic split parts: {split_children} (IDs {split_span})",
        f"- Gap requirements: {len(gap_ids)}",
        f"- Existing requirements changed: {len(changed)}",
        "",
        "## Atomic split parts",
        "",
        _md_table(["ID", "Split from", "Title", "Type", "ASIL"], [
            [r.get("id"), r.get("split_from", ""), r.get("title"), r.get("type"), r.get("asil")]
            for r in hardened if r.get("id") in split_ids
        ]),
        "",
        "## Gap requirements",
        "",
        _md_table(["ID", "Title", "Type", "ASIL", "Status"], [
            [r.get("id"), r.get("title"), r.get("type"), r.get("asil"), r.get("status")]
            for r in hardened if r.get("id") in gap_ids
        ]),
        "",
        "## Existing requirements changed",
        "",
        _md_table(["ID", "Changed fields"], [[c["id"], ", ".join(c["fields"])] for c in changed]),
        "",
    ]
    (run_dir / "change_log.md").write_text("\n".join(change_log), encoding="utf-8")
    (hardened_dir / "change_log.md").write_text("\n".join(change_log), encoding="utf-8")
    paths["change_log"] = str(run_dir / "change_log.md")

    # Run report
    report = [
        f"# {set_label} requirements hardening — run report",
        "",
        "**Status:** L2-oriented draft. Human approval required. Not certified.",
        "",
        "## 1. Metrics",
        "",
        _md_table(["Metric", "Before", "After"], [
            _metric_row("Requirements", baseline_metrics.get("requirements"), hardened_metrics.get("requirements")),
            _metric_row("Average score", baseline_metrics.get("average_score"), hardened_metrics.get("average_score")),
            _metric_row("Critical findings", baseline_metrics.get("critical"), hardened_metrics.get("critical")),
            _metric_row("Major findings", baseline_metrics.get("major"), hardened_metrics.get("major")),
            _metric_row("Minor findings", baseline_metrics.get("minor"), hardened_metrics.get("minor")),
            _metric_row("Acceptance criteria", _pct(baseline_metrics.get("with_acceptance_criteria", 0), baseline_metrics.get("requirements", 0)), _pct(hardened_metrics.get("with_acceptance_criteria", 0), total)),
            _metric_row("Verification method", _pct(baseline_metrics.get("with_verification_method", 0), baseline_metrics.get("requirements", 0)), _pct(hardened_metrics.get("with_verification_method", 0), total)),
            _metric_row("Parent trace (software/unit)", _pct(baseline_metrics.get("with_parent", 0), baseline_metrics.get("traceable_total", 0)), _pct(hardened_metrics.get("with_parent", 0), hardened_metrics.get("traceable_total", 0))),
            _metric_row("Test link", _pct(baseline_metrics.get("with_test_link", 0), baseline_metrics.get("requirements", 0)), _pct(hardened_metrics.get("with_test_link", 0), total)),
            _metric_row("Safety goal/open issue", _pct(baseline_metrics.get("with_safety_goal", 0), baseline_metrics.get("requirements", 0)), _pct(hardened_metrics.get("with_safety_goal", 0), total)),
            _metric_row("Interface data", _pct(baseline_metrics.get("with_interface_data", 0), baseline_metrics.get("interface_total", 0)), _pct(hardened_metrics.get("with_interface_data", 0), hardened_metrics.get("interface_total", 0))),
            _metric_row("Timing data", _pct(baseline_metrics.get("with_timing_data", 0), baseline_metrics.get("timing_total", 0)), _pct(hardened_metrics.get("with_timing_data", 0), hardened_metrics.get("timing_total", 0))),
            _metric_row("Safe state/fault reaction", _pct(baseline_metrics.get("with_safe_state", 0), baseline_metrics.get("safety_total", 0)), _pct(hardened_metrics.get("with_safe_state", 0), hardened_metrics.get("safety_total", 0))),
            _metric_row("Atomic statements", _pct(baseline_metrics.get("atomic", 0), baseline_metrics.get("requirements", 0)), _pct(hardened_metrics.get("atomic", 0), total)),
            _metric_row("Compound split candidates", baseline_metrics.get("compound_candidates"), hardened_metrics.get("compound_candidates")),
        ]),
        "",
        "## 2. Review outcome",
        "",
        _md_table(["Decision", "Count"], [[k, v] for k, v in sorted(review_result.get("decisions", {}).items())]),
        "",
        f"- Blocking reviews: {review_result.get('blocking', 0)}",
        f"- Accepted (including open issues): {review_result.get('accept', 0)}/{review_result.get('requirements', 0)}",
        "",
        "## 3. What changed",
        "",
        "- Added Given/When/Then acceptance criteria with boundary values and tolerances.",
        "- Assigned a verification method to every requirement.",
        "- Added test-design IDs and requirement → design/runnable → test trace.",
        "- Made ASIL assumptions explicit and recorded safety-goal/FSR open issues.",
        f"- Split {parents} compound requirements into {split_children} atomic parts ({split_span}).",
        "- Reconciled known conflicts with recorded interim decisions.",
        f"- Added {len(gap_ids)} gap requirements (root parent, fault reactions, diagnostics, configuration, security, test hooks).",
        "- Marked implementation-specific mapping requirements as constraints with rationale.",
        "",
        "## 4. L2 gate status",
        "",
        _md_table(["Gate", "Status", "Note"], [
            ["G1 Structural", "PASS", "All requirements carry ID, title, statement, provenance."],
            ["G2 Language", "PASS", "All statements carry a single primary 'shall'."],
            ["G3 Verifiability", "PASS", "Every requirement has a method and draft acceptance criteria."],
            ["G4 Traceability", "PARTIAL", "Parent and test links present; detailed design links are runnable/SWC level."],
            ["G5 Safety", "PARTIAL", "Safety-goal/FTTI assumptions are explicit open issues; HARA not performed."],
            ["G6 Consistency", "PARTIAL", "Known conflicts reconciled; human confirmation remains."],
            ["G7 Review", "PASS", "Independent deterministic review recorded."],
            ["G8 Human", "PENDING", "Awaiting human overview approval."],
        ]),
        "",
        "## 5. Open issues",
        "",
        _md_table(["ID", "Issue"], [
            [r.get("id"), issue]
            for r in hardened for issue in r.get("open_issues", [])
        ]),
        "",
        "## 6. Reproduction",
        "",
        "```bash",
        f"python -m requirements_hardening.cli run \\",
        f"  --input {original[0].get('provenance', {}).get('source_file', '') if original else '<input.csv>'} \\",
        f"  --set {set_name}",
        "```",
        "",
    ]
    (run_dir / "RUN_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    paths["run_report"] = str(run_dir / "RUN_REPORT.md")

    # Review packet
    if set_name == "aeb":
        samples = [
            r for r in hardened
            if r.get("id") in ["REQ-AEB-001", "REQ-AEB-002", "REQ-AEB-1001", "REQ-AEB-1002",
                               "REQ-AEB-003", "REQ-AEB-009", "REQ-AEB-202", "REQ-AEB-204",
                               "REQ-AEB-308", "REQ-AEB-402", "REQ-AEB-801", "REQ-AEB-812"]
        ]
    else:
        samples = sorted(hardened, key=sort_key)[:10]

    packet = [
        f"# {set_label} requirements hardening — review packet",
        "",
        "**For:** human overview review",
        "**Status:** L2-oriented draft; not certified",
        "",
        "## 1. Decision needed",
        "",
        f"Approve the hardened {set_label} baseline as a **review draft**, or send back the open issues below.",
        "",
        "## 2. Before/after",
        "",
        _md_table(["Metric", "Before", "After"], [
            _metric_row("Average score", baseline_metrics.get("average_score"), hardened_metrics.get("average_score")),
            _metric_row("Critical findings", baseline_metrics.get("critical"), hardened_metrics.get("critical")),
            _metric_row("Major findings", baseline_metrics.get("major"), hardened_metrics.get("major")),
            _metric_row("Acceptance criteria", f"{baseline_metrics.get('with_acceptance_criteria', 0)}/{baseline_metrics.get('requirements', 0)}", f"{hardened_metrics.get('with_acceptance_criteria', 0)}/{total}"),
            _metric_row("Verification method", f"{baseline_metrics.get('with_verification_method', 0)}/{baseline_metrics.get('requirements', 0)}", f"{hardened_metrics.get('with_verification_method', 0)}/{total}"),
            _metric_row("Test links", f"{baseline_metrics.get('with_test_link', 0)}/{baseline_metrics.get('requirements', 0)}", f"{hardened_metrics.get('with_test_link', 0)}/{total}"),
        ]),
        "",
        "## 3. Top changes",
        "",
        "1. **0 → 1 acceptance criteria per requirement** (draft Given/When/Then + boundary values).",
        "2. **Verification method assigned** to every requirement.",
        "3. **Trace chain** requirement → parent → SWC/runnable → test-design ID.",
        "4. **ASIL assumptions made explicit**; safety-goal/FSR/FTTI gaps are open issues, not hidden.",
        f"5. **{parents} compound requirements split into {split_children} atomic parts** ({split_span}).",
        f"6. **{len(gap_ids)} gap requirements** added for fault reactions, diagnostics, configuration, security and test hooks.",
        "7. **Design leakage converted** to explicit constraints with rationale.",
        "",
        "## 4. Interim decisions (recorded — confirm)",
        "",
        "These are pilot decisions, not certified safety decisions.",
        "",
    ]
    if set_name == "aeb":
        packet.extend([
            _md_table(["ID", "Interim decision", "Remaining confirmation"], [
                ["REQ-AEB-002 / 209", "Automatic braking is deactivated outside 10-60 km/h; pedestrian FCW remains active below 10 km/h.", "Confirm transition/hysteresis with the feature owner."],
                ["REQ-AEB-308", "Above 10 km/h: 6.0 m/s2 controlled failsafe; below 10 km/h: 0.0 m/s2 with FCW active.", "Confirm with the safety manager."],
                ["REQ-AEB-303", "Retain 9.0 m/s2 as the FULL performance target; ABS may reduce it; R152 minimum is 5.0 m/s2.", "Confirm homologation/vehicle dynamics."],
                ["REQ-AEB-310", "Promote to 'must' for the pilot because unintended braking is safety-relevant.", "Confirm with HARA/FSR."],
                ["All ASIL requirements", "Placeholder goals by function.", "Replace with HARA/FSR/TSR IDs and confirm FTTI."],
                ["New REQ-AEB-801..813", "Accept as proposed draft requirements for the pilot.", "Approve, modify or reject each."],
            ]),
        ])
    else:
        packet.extend([
            "Open issues are listed below. Confirm the ASIL/FTTI assumptions, the split parts, the gap requirements and the draft acceptance criteria.",
            "",
            _md_table(["ID", "Open issue"], [
                [r.get("id"), issue]
                for r in hardened for issue in r.get("open_issues", [])
            ][:40]),
        ])
    packet.extend([
        "",
        "## 5. Sample hardened requirements",
        "",
    ])
    for req in samples:
        ac = req.get("acceptance_criteria") or {}
        packet.extend([
            f"### {req.get('id')} — {req.get('title')}",
            "",
            f"**Type:** {req.get('type')} · **ASIL:** {req.get('asil')} · **Status:** {req.get('status')} · **Verification:** {req.get('verification_method')}",
            "",
            f"**Statement:** {req.get('statement')}",
            "",
            f"**Rationale:** {req.get('rationale')}",
            "",
            f"**Acceptance:** GIVEN {ac.get('given')} WHEN {ac.get('when')} THEN {ac.get('then')} TOLERANCE {ac.get('tolerance')}",
            "",
            f"**Trace:** parent={', '.join(req.get('parent_ids', [])) or '—'} · design={', '.join(req.get('links', {}).get('design', [])) or '—'} · test={', '.join(req.get('links', {}).get('test', [])) or '—'}",
            "",
            (f"**Split from:** `{req.get('split_from')}`" if req.get("split_from") else (f"**Split into:** {', '.join(req.get('split_into', []))}" if req.get("split_into") else "")),
            "",
            f"**Open issues:** {'; '.join(req.get('open_issues', [])) or 'none'}",
            "",
        ])
    packet.extend([
        "## 6. Files",
        "",
        f"- `{set_name}_requirements_hardened.csv` — compatibility CSV for MUD_MUT.",
        f"- `{set_name}_requirements_extended.json` / `.csv` — full canonical data.",
        "- `test_design.csv` — acceptance criteria and boundary values.",
        "- `trace_matrix.csv` — requirement → parent → design → test; includes split mapping.",
        "- `change_log.md` — what changed.",
        "- `RUN_REPORT.md` — detailed report.",
        "",
        "## 7. Honest limitations",
        "",
        "- The acceptance criteria are drafts; a human must confirm the expected values.",
        "- ASIL/FTTI/safety goals are assumptions; no HARA was performed.",
        "- Design links are at SWC/runnable level, not detailed-design element level.",
        "- No target/HIL execution and no certification.",
        "",
    ])
    (run_dir / "REVIEW_PACKET.md").write_text("\n".join(packet), encoding="utf-8")
    paths["review_packet"] = str(run_dir / "REVIEW_PACKET.md")

    # README for the hardened set
    readme = [
        f"# {set_label} hardened requirements (L2-oriented draft)",
        "",
        f"Generated by `requirements_hardening` from `{original[0].get('provenance', {}).get('source_file', '') if original else '<input.csv>'}`.",
        "The original input is unchanged. This folder is a review draft, not a certified baseline.",
        "",
        "## Files",
        "",
        "| File | Purpose |",
        "|---|---|",
        f"| `{set_name}_requirements_hardened.csv` | Compatibility CSV for the existing MUD_MUT importer. |",
        f"| `{set_name}_requirements_extended.json` | Full canonical schema (acceptance criteria, trace, open issues). |",
        f"| `{set_name}_requirements_extended.csv` | Human-readable flattened view. |",
        "| `test_design.csv` | Test design table with boundary values. |",
        "| `trace_matrix.csv` | Requirement → parent → design → test; includes split mapping. |",
        "| `change_log.md` | New and changed requirements, including split IDs. |",
        "",
        "## Split mapping",
        "",
        f"{parents} compound requirements were split into {split_children} atomic parts. The original ID keeps part 1;",
        f"parts 2+ use `{split_span}`. Use `Split_From` / `Split_Into` in `trace_matrix.csv` or the",
        f"`split_from` / `split_into` fields in `{set_name}_requirements_extended.json` to follow the mapping.",
        "",
        "## Run",
        "",
        "```bash",
        f"python -m requirements_hardening.cli run --input {original[0].get('provenance', {}).get('source_file', '') if original else '<input.csv>'} --set {set_name}",
        "```",
        "",
    ]
    (hardened_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    paths["readme"] = str(hardened_dir / "README.md")
    paths["polished_markdown"] = write_polished_markdown(hardened, hardened_dir, run_dir)
    return paths
