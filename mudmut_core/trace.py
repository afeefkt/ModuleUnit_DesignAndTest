"""Requirement → design → test traceability.

Reuses the pure helpers in ``bridge/mud_to_tests.py`` and adds a per-TEST
mapping, where possible, from the requirement IDs attached to each skeleton
function to the ``Test_<function>.cpp`` that exercises it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Optional

from mudmut_core.env import REPO_ROOT

if str(REPO_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "bridge"))

from mud_to_tests import (  # noqa: E402
    extract_requirements,
    list_test_files,
    requirement_ids_in,
)

_FUNC_SIG = re.compile(r"\b(?:static\s+)?void\s+(\w+)\s*\(\s*void\s*\)")


def function_requirements(code: str) -> dict[str, list[str]]:
    """Map skeleton function name → requirement IDs referenced in its body.

    Handles the exporter's style where ``{`` sits on its own line below the
    function signature.
    """
    result: dict[str, list[str]] = {}
    current: Optional[str] = None
    depth = 0
    for line in code.splitlines():
        m = _FUNC_SIG.search(line)
        if m and depth == 0 and not current:
            current = m.group(1)
            result.setdefault(current, [])
        if current is None:
            continue
        for req in requirement_ids_in(line):
            if req not in result[current]:
                result[current].append(req)
        depth += line.count("{") - line.count("}")
        if depth <= 0 and line.strip() == "}":
            current = None
    return result


_TESTCASE_RE = re.compile(r"<testcase\b[^>]*\bfile=\"([^\"]+)\"[^>]*>(.*?)</testcase>", re.DOTALL)

# Trace statuses, strongest evidence first.
VERIFIED = "verified_by_test"        # its tests ran and all passed
FAILING = "failing_test"             # its tests ran and at least one failed
NOT_RUN = "test_not_run"             # a test file exists but produced no results
NOT_VERIFIED = "not_verified"        # no test exercises a function carrying the ID
STATUSES = (VERIFIED, FAILING, NOT_RUN, NOT_VERIFIED)


def _test_dir(output_directory: str) -> Optional[Path]:
    if not output_directory:
        return None
    out = Path(output_directory)
    if not out.is_dir():
        out = REPO_ROOT / "cpputest-rag" / "generated_tests" / out.name
    return out if out.is_dir() else None


def junit_by_file(test_dir: Optional[Path]) -> dict[str, dict[str, int]]:
    """Per test file: number of test cases run and how many failed/errored."""
    stats: dict[str, dict[str, int]] = {}
    xml = test_dir / "test-results.xml" if test_dir else None
    if not xml or not xml.is_file():
        return stats
    for fname, body in _TESTCASE_RE.findall(xml.read_text(encoding="utf-8", errors="ignore")):
        s = stats.setdefault(Path(fname).name, {"tests": 0, "failed": 0})
        s["tests"] += 1
        if "<failure" in body or "<error" in body:
            s["failed"] += 1
    return stats


def build_trace(module: str, code: str, generation: dict) -> dict[str, Any]:
    """Build the traceability record, adding per-TEST requirement mapping.

    A requirement counts as verified only when the test file of a function
    whose design carries its ID actually ran (JUnit) and every case passed.
    """
    requirements = extract_requirements(code)
    func_reqs = function_requirements(code)
    test_files = list_test_files(generation.get("output_directory", ""))
    results = junit_by_file(_test_dir(generation.get("output_directory", "")))

    trace: list[dict[str, Any]] = []
    for req in requirements:
        matching = [
            f"Test_{func}.cpp"
            for func, reqs in func_reqs.items()
            if req in reqs and f"Test_{func}.cpp" in test_files
        ]
        ran = [results[f] for f in matching if results.get(f, {}).get("tests")]
        if not matching:
            status = NOT_VERIFIED
        elif not ran:
            status = NOT_RUN
        elif any(r["failed"] for r in ran):
            status = FAILING
        else:
            status = VERIFIED
        trace.append({"requirement": req, "verified_by": matching, "status": status})

    return {
        "module": module,
        "source_requirements": requirements,
        "design_artifact": f"{module}.c (MUD Activity/Code-Flow skeleton)",
        "generated_tests": {
            "output_directory": generation.get("output_directory", ""),
            "test_files": test_files,
            "functions_analyzed": generation.get("functions_analyzed"),
            "tests_generated": generation.get("tests_generated"),
            "failed_functions": generation.get("failed_functions") or [],
            "results_by_file": results,
        },
        "trace": trace,
        "summary": {
            "requirements": len(requirements),
            **{s: sum(1 for t in trace if t["status"] == s) for s in STATUSES},
        },
    }
