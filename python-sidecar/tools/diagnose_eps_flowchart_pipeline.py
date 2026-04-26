from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from mudtool.main import create_app


@dataclass
class StageResult:
    name: str
    ok: bool
    duration_ms: int
    status_code: int | None = None
    detail: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifact: str | None = None


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sidecar_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_csv() -> Path:
    return _repo_root() / "data" / "sample" / "eps_requirements.csv"


def _default_output_dir() -> Path:
    return _sidecar_root() / "output" / "diagnostics" / f"eps_flowchart_{_now_stamp()}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parse_sse_bytes(raw: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event_name = "message"
    data_lines: list[str] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            if data_lines:
                data_text = "\n".join(data_lines)
                try:
                    payload = json.loads(data_text)
                except json.JSONDecodeError:
                    payload = {"raw": data_text}
                events.append({"event": event_name, "data": payload})
                data_lines = []
                event_name = "message"
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
    if data_lines:
        data_text = "\n".join(data_lines)
        try:
            payload = json.loads(data_text)
        except json.JSONDecodeError:
            payload = {"raw": data_text}
        events.append({"event": event_name, "data": payload})
    return events


def _select_module(modules: list[dict[str, Any]], requested_swc: str | None) -> dict[str, Any]:
    if not modules:
        raise RuntimeError("Module planner returned no modules.")
    if requested_swc:
        for module in modules:
            if module.get("swc_name") == requested_swc:
                return module
        raise RuntimeError(f"Requested SWC '{requested_swc}' not found in planned modules.")

    eps_like = [m for m in modules if "eps" in (m.get("swc_name", "") + m.get("description", "")).lower()]
    if eps_like:
        return max(eps_like, key=lambda m: (len(m.get("req_ids", [])), len(m.get("runnables", []))))
    return max(modules, key=lambda m: (len(m.get("req_ids", [])), len(m.get("runnables", []))))


def _activity_diagram_summary(result_json: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for diagram in result_json.get("result", {}).get("diagrams", []):
        if diagram.get("diagram_type") != "activity":
            continue
        nodes = diagram.get("nodes", [])
        edges = diagram.get("edges", [])
        node_types = [node.get("node_type") for node in nodes]
        summaries.append(
            {
                "name": diagram.get("name"),
                "owner_swc": diagram.get("owner_swc"),
                "owner_runnable": diagram.get("owner_runnable"),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "node_types": node_types,
                "has_decision": "decision" in node_types,
                "has_merge": "merge" in node_types,
                "merge_count": sum(1 for node_type in node_types if node_type == "merge"),
                "has_function_call": "function_call" in node_types,
                "guarded_edges": sum(1 for edge in edges if edge.get("guard")),
                "early_return_count": sum(
                    1
                    for node in nodes
                    if (node.get("name") or "").strip().lower() == "return"
                ),
            }
        )
    return summaries


def _canonical_activity_summary(mud_spec_markdown: str, swc_name: str, req_ids: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from mudtool.ai.mud_activity_context import build_mud_activity_context, synthesize_activity_diagrams_from_context

    context = build_mud_activity_context(mud_spec_markdown, module_context=swc_name)
    diagrams = synthesize_activity_diagrams_from_context(context, req_ids)
    payload = {
        "result": {
            "diagrams": [diagram.model_dump(mode="json") for diagram in diagrams],
        }
    }
    return _activity_diagram_summary(payload), payload


def _unreachable_count_by_diagram(validation_report: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in validation_report.get("issues", []):
        if issue.get("rule_id") != "STR-023":
            continue
        diagram_name = issue.get("diagram_name") or ""
        counts[diagram_name] = counts.get(diagram_name, 0) + 1
    return counts


def _looks_like_placeholder_summary(activity_summaries: list[dict[str, Any]]) -> bool:
    if not activity_summaries:
        return True
    for summary in activity_summaries:
        non_terminal = [t for t in summary["node_types"] if t not in ("initial", "final")]
        if len(non_terminal) > 1:
            return False
        if summary["has_decision"] or summary["has_merge"] or summary["guarded_edges"] > 0:
            return False
    return True


def _make_markdown_report(
    *,
    csv_path: Path,
    output_dir: Path,
    selected_module: dict[str, Any] | None,
    imported_count: int,
    activity_summaries: list[dict[str, Any]],
    canonical_activity_summaries: list[dict[str, Any]],
    section7_normalization: dict[str, Any] | None,
    mermaid_preview: dict[str, str],
    stages: list[StageResult],
    unreachable_counts: dict[str, int],
) -> str:
    lines: list[str] = []
    lines.append("# EPS Flowchart Diagnostic Report")
    lines.append("")
    lines.append(f"- Timestamp: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- Input CSV: `{csv_path}`")
    lines.append(f"- Output directory: `{output_dir}`")
    lines.append(f"- Imported requirements: `{imported_count}`")
    if selected_module:
        lines.append(f"- Selected SWC: `{selected_module.get('swc_name', 'unknown')}`")
        lines.append(f"- Selected ASIL: `{selected_module.get('asil', 'QM')}`")
        lines.append(f"- Runnable count: `{len(selected_module.get('runnables', []))}`")
        lines.append(f"- Linked req count: `{len(selected_module.get('req_ids', []))}`")
    lines.append("")
    lines.append("## Stage Summary")
    lines.append("")
    lines.append("| Stage | OK | Status | Duration ms | Detail |")
    lines.append("|---|---|---:|---:|---|")
    for stage in stages:
        status = "" if stage.status_code is None else str(stage.status_code)
        ok_text = "yes" if stage.ok else "no"
        lines.append(f"| {stage.name} | {ok_text} | {status} | {stage.duration_ms} | {stage.detail or '-'} |")
    lines.append("")
    lines.append("## Section 7 Normalization")
    lines.append("")
    if not section7_normalization:
        lines.append("No Section 7 normalization metadata was captured.")
    else:
        lines.append(
            f"- Succeeded: `{section7_normalization.get('succeeded')}`"
        )
        lines.append(
            f"- Runnable blocks: `{section7_normalization.get('normalized_runnable_count', 0)}`"
        )
        lines.append(
            f"- Adjusted blocks: `{section7_normalization.get('changed_runnable_count', 0)}`"
        )
        lines.append(
            f"- Warning count: `{section7_normalization.get('warning_count', 0)}`"
        )
        runnable_reports = section7_normalization.get("runnable_reports", [])
        if runnable_reports:
            lines.append("")
            for report in runnable_reports:
                lines.append(
                    f"- `{report.get('runnable_name', 'unknown')}`: "
                    f"changed={report.get('changed')}, "
                    f"controls={','.join(report.get('control_structures', [])) or 'none'}, "
                    f"mixed_rewrites={report.get('mixed_rewrites', 0)}, "
                    f"ambiguous_lines={report.get('ambiguous_lines', 0)}, "
                    f"warnings={len(report.get('warnings', []))}"
                )
    lines.append("")
    lines.append("## Activity Diagram Summary")
    lines.append("")
    if not activity_summaries:
        lines.append("No activity diagrams were produced.")
    else:
        for summary in activity_summaries:
            lines.append(
                f"- `{summary['name']}`: nodes={summary['node_count']}, edges={summary['edge_count']}, "
                f"decision={summary['has_decision']}, merge={summary['has_merge']} ({summary['merge_count']}), "
                f"function_call={summary['has_function_call']}, guarded_edges={summary['guarded_edges']}, "
                f"early_returns={summary['early_return_count']}, unreachable={unreachable_counts.get(summary['name'], 0)}"
            )
    lines.append("")
    lines.append("## Canonical CFG Summary")
    lines.append("")
    if not canonical_activity_summaries:
        lines.append("No canonical deterministic activity diagrams were reconstructed.")
    else:
        for summary in canonical_activity_summaries:
            lines.append(
                f"- `{summary['name']}`: nodes={summary['node_count']}, edges={summary['edge_count']}, "
                f"decision={summary['has_decision']}, merge={summary['has_merge']} ({summary['merge_count']}), "
                f"guarded_edges={summary['guarded_edges']}, early_returns={summary['early_return_count']}"
            )
    lines.append("")
    lines.append("## Mermaid Preview Keys")
    lines.append("")
    if mermaid_preview:
        for key, value in mermaid_preview.items():
            first_line = value.splitlines()[0] if value else ""
            lines.append(f"- `{key}` -> `{first_line}`")
    else:
        lines.append("No Mermaid preview generated.")
    lines.append("")
    if _looks_like_placeholder_summary(activity_summaries):
        lines.append("## Diagnostic Flag")
        lines.append("")
        lines.append("The generated activity result still looks placeholder-like.")
        lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    for stage in stages:
        if stage.artifact:
            lines.append(f"- `{stage.name}`: `{stage.artifact}`")
    return "\n".join(lines) + "\n"


def _run_stage(name: str, fn):
    start = time.perf_counter()
    try:
        value = fn()
        duration_ms = int((time.perf_counter() - start) * 1000)
        return value, duration_ms, None
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return None, duration_ms, exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run full EPS flowchart diagnostics from CSV import to Mermaid activity output."
    )
    parser.add_argument("--csv", type=Path, default=_default_csv(), help="Input EPS requirements CSV.")
    parser.add_argument("--swc", type=str, default=None, help="Exact SWC name to use after module planning.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
        help="Directory for diagnostic artifacts.",
    )
    parser.add_argument(
        "--spec-pipeline",
        choices=["single_pass", "two_stage"],
        default="two_stage",
        help="MUD spec generation pipeline mode.",
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Skip the /modules/review stage.",
    )
    args = parser.parse_args()

    csv_path = args.csv.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stages: list[StageResult] = []
    selected_module: dict[str, Any] | None = None
    imported_count = 0
    activity_summaries: list[dict[str, Any]] = []
    canonical_activity_summaries: list[dict[str, Any]] = []
    section7_normalization: dict[str, Any] | None = None
    mermaid_preview: dict[str, str] = {}
    unreachable_counts: dict[str, int] = {}

    if not csv_path.exists():
        print(f"[FAIL] CSV not found: {csv_path}")
        return 2

    app = create_app()

    try:
        with TestClient(app) as client:
            health_resp, duration_ms, exc = _run_stage("health", lambda: client.get("/api/v1/health"))
            if exc:
                tb = traceback.format_exc()
                _write_text(output_dir / "health_error.txt", tb)
                stages.append(StageResult("health", False, duration_ms, detail=str(exc), errors=[tb], artifact="health_error.txt"))
                raise exc
            _write_json(output_dir / "health.json", health_resp.json())
            stages.append(
                StageResult(
                    "health",
                    health_resp.status_code == 200,
                    duration_ms,
                    status_code=health_resp.status_code,
                    detail=health_resp.json().get("status", ""),
                    artifact="health.json",
                )
            )

            raw_text = csv_path.read_text(encoding="utf-8", errors="replace")
            files = {"file": (csv_path.name, csv_path.read_bytes(), "text/csv")}
            import_resp, duration_ms, exc = _run_stage(
                "import_requirements",
                lambda: client.post("/api/v1/requirements/import", files=files),
            )
            if exc:
                raise exc
            import_json = import_resp.json()
            _write_json(output_dir / "import_response.json", import_json)
            imported_count = len(import_json.get("requirement_set", {}).get("requirements", []))
            stages.append(
                StageResult(
                    "import_requirements",
                    import_resp.status_code == 200 and imported_count > 0 and not import_json.get("errors"),
                    duration_ms,
                    status_code=import_resp.status_code,
                    detail=f"requirements={imported_count}",
                    warnings=import_json.get("warnings", []),
                    errors=import_json.get("errors", []),
                    artifact="import_response.json",
                )
            )
            if import_resp.status_code != 200 or imported_count == 0:
                raise RuntimeError("Requirement import failed or returned no requirements.")

            plan_payload = {"requirements_text": raw_text, "temperature": 0.1}
            plan_resp, duration_ms, exc = _run_stage(
                "plan_modules",
                lambda: client.post("/api/v1/modules/plan", json=plan_payload),
            )
            if exc:
                raise exc
            plan_json = plan_resp.json()
            _write_json(output_dir / "module_plan.json", plan_json)
            modules = plan_json.get("modules", [])
            stages.append(
                StageResult(
                    "plan_modules",
                    plan_resp.status_code == 200 and bool(modules),
                    duration_ms,
                    status_code=plan_resp.status_code,
                    detail=f"modules={len(modules)}",
                    artifact="module_plan.json",
                )
            )
            if plan_resp.status_code != 200 or not modules:
                raise RuntimeError("Module planning failed or returned no modules.")

            selected_module = _select_module(modules, args.swc)
            _write_json(output_dir / "selected_module.json", selected_module)

            mud_spec_payload = {
                "swc_name": selected_module.get("swc_name", ""),
                "description": selected_module.get("description", ""),
                "asil": selected_module.get("asil", "QM"),
                "runnables": selected_module.get("runnables", []),
                "req_ids": selected_module.get("req_ids", []),
                "requirements_text": raw_text,
                "temperature": 0.15,
                "spec_pipeline": args.spec_pipeline,
            }
            mud_resp, duration_ms, exc = _run_stage(
                "generate_mud_spec",
                lambda: client.post("/api/v1/modules/mud-spec", json=mud_spec_payload),
            )
            if exc:
                raise exc
            mud_events = _parse_sse_bytes(mud_resp.content)
            _write_json(output_dir / "mud_spec_events.json", mud_events)
            final_spec_event = next((e for e in reversed(mud_events) if e.get("event") == "complete"), None)
            mud_spec = ""
            if final_spec_event:
                mud_spec = final_spec_event.get("data", {}).get("mud_spec_markdown", "")
                section7_normalization = final_spec_event.get("data", {}).get("section7_normalization")
            if mud_spec:
                _write_text(output_dir / "mud_spec.md", mud_spec)
            if section7_normalization:
                _write_json(output_dir / "section7_normalization.json", section7_normalization)
            stages.append(
                StageResult(
                    "generate_mud_spec",
                    mud_resp.status_code == 200 and bool(mud_spec),
                    duration_ms,
                    status_code=mud_resp.status_code,
                    detail=(
                        f"events={len(mud_events)} chars={len(mud_spec)} "
                        f"normalized={section7_normalization.get('changed_runnable_count', 0) if section7_normalization else 0}"
                    ),
                    errors=[str(e.get('data')) for e in mud_events if e.get("event") == "error"],
                    artifact="section7_normalization.json" if section7_normalization else ("mud_spec.md" if mud_spec else "mud_spec_events.json"),
                )
            )
            if mud_resp.status_code != 200 or not mud_spec:
                raise RuntimeError("MUD spec generation failed or returned empty markdown.")

            if not args.skip_review:
                review_payload = {
                    "swc_name": selected_module.get("swc_name", ""),
                    "asil": selected_module.get("asil", "QM"),
                    "req_ids": selected_module.get("req_ids", []),
                    "requirements_text": raw_text,
                    "mud_spec_markdown": mud_spec,
                    "temperature": 0.1,
                    "iteration": 1,
                }
                review_resp, duration_ms, exc = _run_stage(
                    "review_mud_spec",
                    lambda: client.post("/api/v1/modules/review", json=review_payload),
                )
                if exc:
                    raise exc
                review_json = review_resp.json()
                _write_json(output_dir / "mud_spec_review.json", review_json)
                review_issues = review_json.get("issues", [])
                suggestion_issues = review_json.get("suggestions", [])
                stages.append(
                    StageResult(
                        "review_mud_spec",
                        review_resp.status_code == 200,
                        duration_ms,
                        status_code=review_resp.status_code,
                        detail=(
                            f"approved={review_json.get('approved')} "
                            f"issues={len(review_issues)} suggestions={len(suggestion_issues)}"
                        ),
                        artifact="mud_spec_review.json",
                    )
                )

            generate_payload = {
                "requirements": import_json["requirement_set"],
                "diagram_types": ["activity"],
                "module_context": selected_module.get("swc_name", ""),
                "temperature": 0.15,
                "apply_autosar_mapping": True,
                "autosar_compliant": True,
                "activity_label_style": "pseudocode",
                "mud_spec_markdown": mud_spec,
                "activity_source": "mud_spec",
            }
            generate_resp, duration_ms, exc = _run_stage(
                "generate_activity",
                lambda: client.post("/api/v1/generate", json=generate_payload),
            )
            if exc:
                raise exc
            generate_json = generate_resp.json()
            _write_json(output_dir / "generate_activity_response.json", generate_json)
            activity_summaries = _activity_diagram_summary(generate_json)
            _write_json(output_dir / "activity_diagram_summary.json", activity_summaries)
            canonical_activity_summaries, canonical_payload = _canonical_activity_summary(
                mud_spec,
                selected_module.get("swc_name", ""),
                selected_module.get("req_ids", []),
            )
            _write_json(output_dir / "canonical_activity_from_mud.json", canonical_payload)
            _write_json(output_dir / "canonical_activity_summary.json", canonical_activity_summaries)
            result_warnings = generate_json.get("result", {}).get("warnings", [])
            result_errors = generate_json.get("result", {}).get("errors", [])
            stages.append(
                StageResult(
                    "generate_activity",
                    generate_resp.status_code == 200 and bool(activity_summaries) and not result_errors,
                    duration_ms,
                    status_code=generate_resp.status_code,
                    detail=f"activity_diagrams={len(activity_summaries)} placeholder_like={_looks_like_placeholder_summary(activity_summaries)}",
                    warnings=result_warnings,
                    errors=result_errors,
                    artifact="generate_activity_response.json",
                )
            )
            if generate_resp.status_code != 200 or not activity_summaries:
                raise RuntimeError("Activity generation failed or returned no activity diagrams.")

            inline_payload = {"result": generate_json["result"]}
            mermaid_resp, duration_ms, exc = _run_stage(
                "export_mermaid_inline",
                lambda: client.post("/api/v1/export/mermaid/inline", json=inline_payload),
            )
            if exc:
                raise exc
            mermaid_json = mermaid_resp.json()
            _write_json(output_dir / "mermaid_inline.json", mermaid_json)
            mermaid_preview = mermaid_json.get("diagrams", {})
            for key, diagram_text in mermaid_preview.items():
                safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in key).strip("_") or "diagram"
                _write_text(output_dir / f"{safe_name}.mmd", diagram_text)
            stages.append(
                StageResult(
                    "export_mermaid_inline",
                    mermaid_resp.status_code == 200 and bool(mermaid_preview),
                    duration_ms,
                    status_code=mermaid_resp.status_code,
                    detail=f"diagrams={len(mermaid_preview)}",
                    artifact="mermaid_inline.json",
                )
            )
            if mermaid_resp.status_code != 200 or not mermaid_preview:
                raise RuntimeError("Mermaid inline export failed or returned no diagrams.")

            validate_payload = {"result": generate_json["result"]}
            validate_resp, duration_ms, exc = _run_stage(
                "validate_generated_activity",
                lambda: client.post("/api/v1/validate", json=validate_payload),
            )
            if exc:
                raise exc
            validate_json = validate_resp.json()
            _write_json(output_dir / "validation_report.json", validate_json)
            unreachable_counts = _unreachable_count_by_diagram(validate_json)
            stages.append(
                StageResult(
                    "validate_generated_activity",
                    validate_resp.status_code == 200,
                    duration_ms,
                    status_code=validate_resp.status_code,
                    detail=(
                        f"passed={validate_json.get('passed')} "
                        f"issues={len(validate_json.get('issues', []))}"
                    ),
                    artifact="validation_report.json",
                )
            )

    except Exception as exc:
        tb = traceback.format_exc()
        _write_text(output_dir / "fatal_error.txt", tb)
        stages.append(
            StageResult(
                "fatal_error",
                False,
                0,
                detail=str(exc),
                errors=[tb],
                artifact="fatal_error.txt",
            )
        )

    report = _make_markdown_report(
        csv_path=csv_path,
        output_dir=output_dir,
        selected_module=selected_module,
        imported_count=imported_count,
        activity_summaries=activity_summaries,
        canonical_activity_summaries=canonical_activity_summaries,
        section7_normalization=section7_normalization,
        mermaid_preview=mermaid_preview,
        stages=stages,
        unreachable_counts=unreachable_counts,
    )
    _write_text(output_dir / "report.md", report)
    _write_json(output_dir / "stage_results.json", [asdict(stage) for stage in stages])

    print("=" * 72)
    print("EPS FLOWCHART DIAGNOSTIC")
    print("=" * 72)
    print(f"Artifacts: {output_dir}")
    for stage in stages:
        status = "PASS" if stage.ok else "FAIL"
        code = "" if stage.status_code is None else f" status={stage.status_code}"
        print(f"[{status}] {stage.name} ({stage.duration_ms} ms){code} {stage.detail}")
        for warning in stage.warnings[:3]:
            print(f"  warning: {warning}")
        for error in stage.errors[:3]:
            print(f"  error: {error}")
    print("=" * 72)

    failed = any(not stage.ok for stage in stages if stage.name != "review_mud_spec")
    if _looks_like_placeholder_summary(activity_summaries):
        print("Diagnostic flag: activity output still looks placeholder-like.")
        failed = True
    print(f"Report: {output_dir / 'report.md'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
