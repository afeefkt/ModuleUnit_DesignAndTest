#!/usr/bin/env python3
"""MUD_MUT bridge: MUD flow chart  ->  C skeleton  ->  CppUTest unit tests.

This is the glue that turns the two halves of the monorepo into one ASPICE
pipeline and — crucially — emits the requirement -> design -> test traceability
record that ASPICE expects and that neither tool produces on its own.

Pipeline
--------
    (mud-tool)                          (this script)              (cpputest-rag)
    Activity/Code-Flow diagram  --->  C skeleton (.c)  --->  analyze + generate tests
                                             |                          |
                                             +------ traceability ------+

Two input modes
---------------
  1. --skeleton path/to/module.c
        Use a C skeleton you already exported from the mud-tool UI/API.
        Works with zero changes and no running mud-tool server.

  2. --result path/to/generation_result.json
        A GenerationResult JSON (what mud-tool's /generate returns). The bridge
        calls mud-tool's  POST /api/v1/export  with format=c_skeleton to produce
        the .c automatically, then continues.

Then it drops the skeleton into  cpputest-rag/c_projects/<module>/ , calls
cpputest-rag's  /analyze-project  and  /generate-tests , optionally  /run-tests ,
and writes a traceability JSON mapping requirement IDs to generated test files.

No third-party dependencies — standard library only:
    python bridge/mud_to_tests.py --skeleton out/MyModule.c --module SWC_MyModule --run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
CPPUTEST_PROJECTS = REPO_ROOT / "cpputest-rag" / "c_projects"

DEFAULT_MUD_URL = "http://localhost:8042/api/v1"
DEFAULT_CPPUTEST_URL = "http://localhost:8000"

# Requirement-ID patterns used both in the MUD "Requirements:" header comment
# and in per-node trace comments emitted by CSkeletonExporter.
_REQ_HEADER_RE = re.compile(r"Requirements?:\s*([^\*/\n]+)", re.IGNORECASE)
_REQ_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*[-_]?\d+\b")


# ─────────────────────────── HTTP helpers (stdlib) ──────────────────────────
def _post_json(url: str, payload: dict, timeout: int = 900) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, timeout: int = 120) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fail(msg: str) -> "None":
    print(f"\n[bridge] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


# ─────────────────────────── Stage 1: obtain the C skeleton ─────────────────
def skeleton_from_file(path: Path) -> str:
    if not path.is_file():
        _fail(f"skeleton file not found: {path}")
    return path.read_text(encoding="utf-8")


def skeleton_from_result(result_json: Path, mud_url: str, out_dir: Path) -> Path:
    """Call mud-tool /export (format=c_skeleton) and return the first .c produced."""
    if not result_json.is_file():
        _fail(f"result JSON not found: {result_json}")
    result = json.loads(result_json.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[bridge] Requesting C skeleton from mud-tool at {mud_url}/export ...")
    try:
        resp = _post_json(
            f"{mud_url}/export",
            {"format": "c_skeleton", "result": result, "output_path": str(out_dir)},
        )
    except urllib.error.URLError as exc:  # pragma: no cover - network dependent
        _fail(f"could not reach mud-tool ({mud_url}). Is `mudtool-server` running? {exc}")
    paths = resp.get("paths") or []
    if not paths:
        _fail("mud-tool returned no C-skeleton files (no ActivityDiagram in result?)")
    print(f"[bridge] mud-tool wrote {len(paths)} skeleton file(s): {paths}")
    return Path(paths[0])


# ─────────────────────────── Stage 2: place into cpputest-rag ───────────────
def place_skeleton(module: str, code: str) -> Path:
    project_dir = CPPUTEST_PROJECTS / module
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir / f"{module}.c"
    target.write_text(code, encoding="utf-8")
    print(f"[bridge] Placed skeleton at {target}")
    return project_dir


# ─────────────────────────── Stage 3: generate tests ───────────────────────
def analyze_and_generate(module: str, cpputest_url: str, run: bool) -> dict:
    # The cpputest-rag API resolves a bare project name against its C_PROJECT_DIR,
    # so we send the module name (works whether the backend runs on host or in Docker).
    print(f"[bridge] Analyzing project '{module}' via {cpputest_url}/analyze-project ...")
    try:
        analysis = _get_json(
            f"{cpputest_url}/analyze-project?project_path={urllib.request.quote(module)}"
        )
    except urllib.error.URLError as exc:  # pragma: no cover - network dependent
        _fail(f"could not reach cpputest-rag ({cpputest_url}). Is it running? {exc}")
    print(f"[bridge]   found {analysis.get('total_functions', '?')} function(s)")

    print(f"[bridge] Generating CppUTest tests via {cpputest_url}/generate-tests ...")
    generation = _post_json(f"{cpputest_url}/generate-tests", {"project_path": module})
    out_dir = generation.get("output_directory", "")
    print(
        f"[bridge]   generated {generation.get('tests_generated', '?')} test file(s) "
        f"in {out_dir}"
    )
    failed = generation.get("failed_functions") or []
    if failed:
        print(f"[bridge]   WARNING: {len(failed)} function(s) failed: {failed}")

    if run and out_dir:
        test_dir_name = Path(out_dir).name
        print(f"[bridge] Building + running tests ({test_dir_name}) ...")
        try:
            run_res = _post_json(
                f"{cpputest_url}/run-tests?test_directory="
                f"{urllib.request.quote(test_dir_name)}",
                {},
            )
            print(f"[bridge]   build/run: {run_res.get('status', run_res)}")
            generation["run_result"] = run_res
        except urllib.error.URLError as exc:
            print(f"[bridge]   WARNING: run-tests failed ({exc}); skipping.")
    return generation


# ─────────────────────────── Stage 4: traceability record ──────────────────
def extract_requirements(code: str) -> list[str]:
    reqs: set[str] = set()
    for header in _REQ_HEADER_RE.findall(code):
        for tok in re.split(r"[,\s]+", header.strip()):
            tok = tok.strip()
            if tok and _REQ_TOKEN_RE.fullmatch(tok):
                reqs.add(tok)
    # Also catch inline trace comments like  /* trace: REQ_012 */
    for tok in _REQ_TOKEN_RE.findall(code):
        if any(c.isdigit() for c in tok) and not tok.isdigit():
            reqs.add(tok)
    return sorted(reqs)


def list_test_files(output_directory: str) -> list[str]:
    if not output_directory:
        return []
    out = Path(output_directory)
    if not out.is_absolute():
        out = CPPUTEST_PROJECTS.parent / "generated_tests" / out.name
    if not out.is_dir():
        return []
    return sorted(p.name for p in out.glob("Test_*.cpp"))


def write_traceability(
    module: str, code: str, generation: dict, out_path: Path
) -> None:
    requirements = extract_requirements(code)
    test_files = list_test_files(generation.get("output_directory", ""))
    record = {
        "module": module,
        "source_requirements": requirements,
        "design_artifact": f"{module}.c (MUD Activity/Code-Flow skeleton)",
        "generated_tests": {
            "output_directory": generation.get("output_directory", ""),
            "test_files": test_files,
            "functions_analyzed": generation.get("functions_analyzed"),
            "tests_generated": generation.get("tests_generated"),
            "failed_functions": generation.get("failed_functions") or [],
        },
        "trace": [
            {"requirement": req, "verified_by": test_files} for req in requirements
        ]
        or [{"requirement": "(none parsed from skeleton)", "verified_by": test_files}],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"\n[bridge] Traceability record written to {out_path}")
    print(
        f"[bridge]   {len(requirements)} requirement(s) <- {len(test_files)} test file(s)"
    )


# ─────────────────────────────────── CLI ───────────────────────────────────
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bridge MUD flow charts to CppUTest unit tests with traceability."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--skeleton", type=Path, help="Existing C skeleton (.c) file")
    src.add_argument(
        "--result", type=Path, help="GenerationResult JSON (calls mud-tool /export)"
    )
    parser.add_argument(
        "--module",
        required=True,
        help="Module / SWC name — used as the cpputest-rag project folder name",
    )
    parser.add_argument("--run", action="store_true", help="Also build + run the tests")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Traceability JSON output path (default: bridge/out/<module>_trace.json)",
    )
    parser.add_argument("--mud-url", default=DEFAULT_MUD_URL)
    parser.add_argument("--cpputest-url", default=DEFAULT_CPPUTEST_URL)
    args = parser.parse_args(argv)

    # Stage 1 — get the skeleton
    if args.skeleton:
        code = skeleton_from_file(args.skeleton)
    else:
        export_dir = REPO_ROOT / "bridge" / "out" / "skeletons"
        c_file = skeleton_from_result(args.result, args.mud_url, export_dir)
        code = c_file.read_text(encoding="utf-8")

    # Stage 2 — place into cpputest-rag
    place_skeleton(args.module, code)

    # Stage 3 — analyze + generate (+ optional run)
    generation = analyze_and_generate(args.module, args.cpputest_url, args.run)

    # Stage 4 — traceability
    out_path = args.out or (REPO_ROOT / "bridge" / "out" / f"{args.module}_trace.json")
    write_traceability(args.module, code, generation, out_path)

    print("\n[bridge] Done. requirements -> MUD flow chart -> unit tests linked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
