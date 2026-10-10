#!/usr/bin/env python3
"""mudmut_cli — deterministic tools for the MUD_MUT agentic spike.

Small-model friendly: every subcommand prints COMPACT JSON to stdout and exits
non-zero on hard failure. All artifacts land under ``agentic/runs/<run_id>/``.

This CLI wraps the existing ``mudtool`` library IN-PROCESS (no Docker, no
FastAPI). It deliberately makes NO LLM calls — the agent (OpenCode) is the
generator; this CLI only imports, validates and exports deterministically.

Subcommands:
    import-reqs  <file>            --run <id>   → requirements.json + compact summary
    show-req     <req_id>          --run <id>   → one requirement's full text
    validate-activity <activity.json> --run <id> → top-5 issues as {code, element, message, fix_hint}
    export-c     <activity.json>   --run <id>   → C skeleton .c files
    render-mermaid <activity.json> --run <id>   → .mmd files for the UI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Bootstrap: make the mudtool + cpputest-rag libraries importable in-process ─
# Reuse mudmut_core's environment bootstrap (adds both halves to sys.path and
# sets absolute paths) — no duplicate path juggling here.
_REPO_ROOT = Path(__file__).resolve().parents[2]          # agentic/tools → repo root
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mudmut_core import env as _env                                   # noqa: E402
_env.ensure_environment()

from pydantic import ValidationError                                  # noqa: E402

from mudtool.config.settings import Settings                      # noqa: E402
from mudtool.generator.c_skeleton_exporter import CSkeletonExporter  # noqa: E402
from mudtool.generator.mermaid_exporter import MermaidExporter     # noqa: E402
from mudtool.importers.factory import ImporterFactory              # noqa: E402
from mudtool.models.json_uml import (                              # noqa: E402
    ActivityDiagram,
    DiagramType,
    GenerationResult,
)
from mudtool.validation.engine import ValidationEngine             # noqa: E402
from mudtool.validation.mermaid_linter import MermaidLinter        # noqa: E402

RUNS_DIR = _REPO_ROOT / "outputs"

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emit(obj: dict) -> None:
    """Print compact JSON to stdout (small-model friendly, human readable)."""
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def make_run_dir(run_id: str) -> Path:
    """Create (if needed) and return the run's artifact directory."""
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse_generation_result(obj: object) -> GenerationResult:
    """Parse an agent-written activity JSON into a GenerationResult.

    Accepts, leniently (small local models vary their envelope):
      * a bare ActivityDiagram object      → wrapped
      * {"diagrams": [ ... ]} GenerationResult wrapper
      * a list of diagram objects
    Forces ``diagram_type="activity"`` so pydantic's union discriminates
    correctly (the exporter + validators only understand activity diagrams here).
    """
    if isinstance(obj, dict) and "diagrams" in obj:
        wrapper = dict(obj)
        diagrams = wrapper.get("diagrams")
    elif isinstance(obj, dict):
        wrapper = {}
        diagrams = [obj]
    elif isinstance(obj, list):
        wrapper = {}
        diagrams = obj
    else:
        raise ValueError("activity JSON must be an object or array")

    if isinstance(diagrams, dict):
        diagrams = [diagrams]
    if not isinstance(diagrams, list):
        raise ValueError("'diagrams' must be a list of diagram objects")

    # Parse each diagram EXPLICITLY as an ActivityDiagram. Using the
    # GenerationResult union here would misclassify activity dicts as
    # SequenceDiagram (its diagram_type field is not frozen), silently dropping
    # nodes/edges as "extra". Explicit parsing makes malformed JSON fail loudly.
    parsed: list[ActivityDiagram] = []
    for d in diagrams:
        if not isinstance(d, dict):
            raise ValueError("each diagram must be a JSON object")
        try:
            parsed.append(ActivityDiagram.model_validate(d))
        except ValidationError as exc:
            msgs = []
            for err in exc.errors()[:8]:
                loc = ".".join(str(x) for x in err.get("loc", [])) or "diagram"
                msgs.append(f"{loc}: {err.get('msg')}")
            raise ValueError(
                "activity JSON does not match the schema — " + "; ".join(msgs)
            ) from exc

    return GenerationResult(
        diagrams=parsed,
        analyzed_requirements=list(wrapper.get("analyzed_requirements") or []),
    )


def load_generation_result(path: Path) -> GenerationResult:
    """Read a JSON file and parse it as a GenerationResult."""
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"activity JSON is not valid JSON: {exc}") from exc
    return parse_generation_result(obj)


def _load_req_ids(run_dir: Path) -> list[str] | None:
    """Return requirement IDs from the run's requirements.json, or None."""
    req_file = run_dir / "requirements.json"
    if not req_file.exists():
        return None
    data = json.loads(req_file.read_text(encoding="utf-8"))
    reqs = data.get("requirements", [])
    return [r["req_id"] for r in reqs if isinstance(r, dict) and r.get("req_id")]


def _issue_to_dict(issue) -> dict:
    return {
        "code": issue.rule_id,
        "severity": issue.severity.value,
        "element": issue.element_id or issue.element_name or issue.diagram_name or "",
        "message": issue.message,
        "fix_hint": issue.suggestion or "",
    }


def _top_issues(report, limit: int = 5) -> list[dict]:
    ordered = sorted(
        report.issues,
        key=lambda i: _SEVERITY_ORDER.get(i.severity.value, 3),
    )
    return [_issue_to_dict(i) for i in ordered[:limit]]


# ── Subcommand handlers ───────────────────────────────────────────────────────

def handle_import(args) -> dict:
    run_dir = make_run_dir(args.run)
    result = ImporterFactory.import_file(args.file)

    req_set = result.requirement_set
    # Persist the full requirement set for later stages (show-req / validation).
    (run_dir / "requirements.json").write_text(
        json.dumps(req_set.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = {
        "ok": result.success,
        "count": req_set.count,
        "ids": [r.req_id for r in req_set.requirements],
        "swc_hints": sorted({r.module_hint for r in req_set.requirements if r.module_hint}),
        "source_format": req_set.source_format,
        "warnings": result.warnings,
        "errors": result.errors,
        "run_dir": str(run_dir),
    }
    return summary


def handle_show(args) -> dict:
    run_dir = make_run_dir(args.run)
    req_file = run_dir / "requirements.json"
    if not req_file.exists():
        return {"ok": False, "error": f"no requirements.json in {run_dir}; run import-reqs first"}
    data = json.loads(req_file.read_text(encoding="utf-8"))
    for r in data.get("requirements", []):
        if r.get("req_id") == args.req_id:
            return {"ok": True, "requirement": r}
    return {"ok": False, "error": f"requirement '{args.req_id}' not found"}


def handle_validate(args) -> dict:
    run_dir = make_run_dir(args.run)
    result = load_generation_result(Path(args.activity_json))

    req_ids = _load_req_ids(run_dir)
    settings = Settings()
    engine = ValidationEngine(settings)
    report = engine.validate(result, requirement_ids=req_ids, autosar_compliant=True)

    # Lint the rendered Mermaid for syntax issues (needs text, so render first).
    inline = MermaidExporter().export_result_inline(result)
    linter = MermaidLinter()
    mermaid_summary: dict[str, dict] = {}
    for key, text in inline.items():
        lr = linter.lint(text, DiagramType.ACTIVITY, diagram_key=key)
        mermaid_summary[key] = {
            "valid": lr.valid,
            "error_count": len(lr.errors),
            "errors": lr.errors[:3],
        }

    out = {
        "ok": True,
        "valid": report.passed,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "diagrams": len(result.diagrams),
        "issues": _top_issues(report),
        "mermaid": mermaid_summary,
    }
    (run_dir / "validation_report.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return out


def handle_export_c(args) -> dict:
    run_dir = make_run_dir(args.run)
    result = load_generation_result(Path(args.activity_json))

    files = CSkeletonExporter().export_result(result)
    if not files:
        raise ValueError("no top-level activity diagrams found to export as C")

    written: dict[str, str] = {}
    for name, code in files.items():
        path = run_dir / f"{name}.c"
        path.write_text(code, encoding="utf-8")
        written[name] = str(path)
    return {"ok": True, "files": written}


def handle_render(args) -> dict:
    run_dir = make_run_dir(args.run)
    result = load_generation_result(Path(args.activity_json))

    inline = MermaidExporter().export_result_inline(result)
    if not inline:
        raise ValueError("no activity diagrams found to render as Mermaid")

    written: dict[str, str] = {}
    for key, text in inline.items():
        safe = key.replace(" ", "_").replace("/", "_")
        path = run_dir / f"{safe}.mmd"
        path.write_text(text, encoding="utf-8")
        written[key] = str(path)
    return {"ok": True, "files": written}


# ── MUT-stage subcommands (delegate to mudmut_core) ───────────────────────────

def _find_c(run_dir: Path, swc: str) -> Path:
    """Locate the C skeleton for ``swc`` (written by export-c)."""
    p = run_dir / f"{swc}.c"
    if p.is_file():
        return p
    for c in sorted(run_dir.glob("*.c")):
        return c
    raise ValueError(f"no C skeleton for '{swc}' in {run_dir}; run export-c first")


def handle_make_compilable(args) -> dict:
    from mudmut_core import compilable
    run_dir = make_run_dir(args.run)
    code = _find_c(run_dir, args.swc).read_text(encoding="utf-8")
    project_dir = run_dir / "code"
    rep = compilable.make_compilable(code, args.swc, project_dir)
    return {
        "ok": True, "summary": rep.summary(), "compile_ok": rep.compile_ok,
        "kept": rep.kept_statements, "stubbed": rep.stubbed_statements,
        "run_dir": str(run_dir),
    }


def handle_gen_tests(args) -> dict:
    from mudmut_core import aio, verify
    run_dir = make_run_dir(args.run)
    project_dir = run_dir / "code"
    if not project_dir.is_dir():
        raise ValueError(f"no code/ dir in {run_dir}; run make-compilable first")
    out_dir = run_dir / "tests"
    generation = aio.run_sync(verify.generate_tests(project_dir, output_dir=out_dir))
    return {
        "ok": True,
        "tests_generated": generation.get("tests_generated"),
        "failed_functions": generation.get("failed_functions") or [],
        "output_directory": generation.get("output_directory", ""),
        "run_dir": str(run_dir),
    }


def handle_build_run(args) -> dict:
    from mudmut_core import verify
    run_dir = make_run_dir(args.run)
    out_dir = run_dir / "tests"
    if not out_dir.is_dir():
        raise ValueError(f"no tests/ dir in {run_dir}; run gen-tests first")
    result = verify.fix_loop(out_dir, max_attempts=2)
    (run_dir / "run_result.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    return {"ok": True, "status": result.get("status"), "junit": result.get("junit"), "run_dir": str(run_dir)}


def handle_trace(args) -> dict:
    from mudmut_core import trace as trace_mod
    run_dir = make_run_dir(args.run)
    code = _find_c(run_dir, args.swc).read_text(encoding="utf-8")
    generation = {"output_directory": str(run_dir / "tests")}
    record = trace_mod.build_trace(args.swc, code, generation)
    (run_dir / "trace.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "requirements": len(record.get("source_requirements", [])),
        "summary": record.get("summary"),
        "run_dir": str(run_dir),
    }


def handle_report(args) -> dict:
    from mudmut_core import report as report_mod
    from mudmut_core.workspace import Run
    run_dir = make_run_dir(args.run)
    run = Run.load(run_dir)

    def _load(name: str, default=None):
        p = run_dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default

    summary = {
        "swc": args.swc or run.swc or args.run,
        "preset": getattr(run, "preset", "agentic"),
        "quick": True,
        "compilability": _load("code/compilability.json", {}),
        "tests": _load("run_result.json", {}),
        "trace": _load("trace.json", {}),
    }
    p = report_mod.write_run_report(run, summary)
    return {"ok": True, "report": str(p), "run_dir": str(run_dir)}


# ── CLI entry point ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mudmut_cli",
        description="Deterministic MUD_MUT tools (import / validate / export) for the agentic spike.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("import-reqs", help="Import a requirements file (CSV/XLSX/MD/TXT).")
    sp.add_argument("file")
    sp.add_argument("--run", required=True, help="run id; artifacts land under agentic/runs/<id>/")
    sp.set_defaults(func=handle_import)

    sp = sub.add_parser("show-req", help="Show one requirement's full text.")
    sp.add_argument("req_id")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_show)

    sp = sub.add_parser("validate-activity", help="Validate an activity JSON (top-5 issues).")
    sp.add_argument("activity_json")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_validate)

    sp = sub.add_parser("export-c", help="Export activity JSON to C skeleton .c files.")
    sp.add_argument("activity_json")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_export_c)

    sp = sub.add_parser("render-mermaid", help="Render activity JSON to Mermaid .mmd files.")
    sp.add_argument("activity_json")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_render)

    sp = sub.add_parser("make-compilable", help="Make an exported C skeleton compile (Rte stubs + gcc loop).")
    sp.add_argument("swc", help="SWC name (matches the .c file from export-c)")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_make_compilable)

    sp = sub.add_parser("gen-tests", help="Generate CppUTest tests into <run>/tests/.")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_gen_tests)

    sp = sub.add_parser("build-run", help="Build + run the tests in <run>/tests/ (with fix loop).")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_build_run)

    sp = sub.add_parser("trace", help="Write requirement -> test traceability to <run>/trace.json.")
    sp.add_argument("swc")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_trace)

    sp = sub.add_parser("report", help="Write RUN_REPORT.md + run.json for the run.")
    sp.add_argument("--swc", default="")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=handle_report)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.func(args)
    except Exception as exc:  # hard failure → exit 2, always JSON
        _emit({"ok": False, "error": str(exc)})
        return 2
    _emit(result)
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
