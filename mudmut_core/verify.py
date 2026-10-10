"""MUT (unit-test half): analyze → generate tests → build/run → fix loop.

Runs the cpputest-rag library in-process (no FastAPI, no Docker).
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Optional

from mudmut_core import env, toolchain

_index_built = False


# ── analysis ─────────────────────────────────────────────────────────────────
def analyze(project_dir: Path | str):
    env.ensure_environment()
    from app.services.c_parser import analyze_c_project
    return analyze_c_project(Path(project_dir))


# ── RAG index ────────────────────────────────────────────────────────────────
async def ensure_rag_index() -> bool:
    """Build the FAISS example index once per process. Returns True on success.

    Async so it can be awaited inside an already-running loop (the chain runs the
    whole pipeline on the shared loop from ``mudmut_core.aio``).
    """
    global _index_built
    if _index_built:
        return True
    env.ensure_environment()
    from app.config import config
    from app.services.rag_engine import build_examples_index

    # rag_engine writes its index files relative to the working directory;
    # keep them in cpputest-rag/data/ instead of wherever the app was started.
    data_dir = env.REPO_ROOT / "cpputest-rag" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config.INDEX_FILE = str(data_dir / "test_examples.index")
    config.META_FILE = str(data_dir / "test_examples_meta.pkl")
    try:
        await build_examples_index()
    except Exception as exc:  # noqa: BLE001 - non-fatal; generation works without RAG
        print(f"[mudmut_core] RAG index build skipped ({exc})")
    _index_built = True
    return _index_built


# ── generation ───────────────────────────────────────────────────────────────
async def generate_tests(project_dir: Path | str, function_name: Optional[str] = None, output_dir: Optional[Path] = None) -> dict:
    env.ensure_environment()
    from app.services.test_generator import generate_tests_for_project

    await ensure_rag_index()
    result = await generate_tests_for_project(Path(project_dir), function_name=function_name, output_dir=output_dir)

    # Copy the generated stub headers + Rte_Stubs.c into the test dir so the
    # generated Makefile (which compiles every *.c) can link them.
    out_dir = Path(result.get("output_directory", ""))
    if out_dir and out_dir.is_dir():
        src = Path(project_dir)
        for name in ("Rte_Type.h", "Rte_Stubs.c"):
            if (src / name).is_file():
                _copy2(src / name, out_dir / name)
        for header in src.glob("Rte_*.h"):
            _copy2(header, out_dir / header.name)
    return result


def _copy2(src: Path, dst: Path) -> None:
    from shutil import copy2
    copy2(src, dst)


# ── build & run ──────────────────────────────────────────────────────────────
def parse_junit(xml_path: Path) -> dict[str, int]:
    """Parse a CppUTest JUnit XML into pass/fail/error counts."""
    if not xml_path.is_file():
        return {"tests": 0, "failures": 0, "errors": 0, "passed": 0}
    text = xml_path.read_text(encoding="utf-8", errors="ignore")
    tests = len(re.findall(r"<testcase\b", text))
    failures = len(re.findall(r"<failure\b", text))
    errors = len(re.findall(r"<error\b", text))
    return {"tests": tests, "failures": failures, "errors": errors, "passed": tests - failures - errors}


def build_and_run(test_dir: Path | str) -> dict[str, Any]:
    """Build (``make clean all``) then run with coverage (``make coverage``)."""
    test_dir = Path(test_dir)

    build = toolchain.run_make(test_dir, targets=("clean", "all"))
    if not build.ok:
        return {
            "status": "build_failed",
            "build_output": build.stdout,
            "build_error": build.stderr,
            "test_output": None,
            "test_error": None,
        }

    run = toolchain.run_make(test_dir, targets=("coverage",))
    test_status = "passed" if run.ok else "test_failed"

    junit = parse_junit(test_dir / "test-results.xml")
    coverage_info = test_dir / "coverage.info"
    coverage_html = test_dir / "coverage_html"
    junit_xml = test_dir / "test-results.xml"

    result = {
        "status": test_status,
        "build_output": build.stdout,
        "build_error": build.stderr,
        "test_output": run.stdout,
        "test_error": run.stderr,
        "exit_code": run.returncode,
        "coverage_available": coverage_info.exists(),
        "html_coverage_available": (coverage_html / "index.html").exists(),
        "junit_xml_available": junit_xml.exists(),
        "coverage_info_path": str(coverage_info) if coverage_info.exists() else None,
        "coverage_html_path": str(coverage_html / "index.html") if (coverage_html / "index.html").exists() else None,
        "junit_xml_path": str(junit_xml) if junit_xml.exists() else None,
        "junit": junit,
    }

    try:
        env.ensure_environment()
        from app.services.report_generator import generate_html_report
        html = generate_html_report(test_result=result, test_directory=test_dir.name, project_path=None)
        (test_dir / "test-report.html").write_text(html, encoding="utf-8")
        result["report_path"] = str(test_dir / "test-report.html")
        result["report_available"] = True
    except Exception as exc:  # noqa: BLE001
        result["report_available"] = False
        result["report_error"] = str(exc)

    return result


# ── fix loop ─────────────────────────────────────────────────────────────────
def _fixer_generate(prompt: str, *, timeout: int = 300) -> str:
    """Generate a corrected test file via the ``test_fixer`` stage (provider+model).

    Synchronous (``chat_blocking``) so it can run inside the chain's running loop.
    """
    import os
    env.ensure_environment()
    from mudmut_core.llm import chat_blocking, get_providers
    provider_id, model = "ollama", os.environ.get("GEN_MODEL", "qwen2.5:7b")
    try:
        from mudmut_core import agents
        st = agents.get_stages().get("test_fixer", {})
        provider_id = st.get("provider", "ollama")
        model = st.get("model") or model
    except Exception:
        pass
    provider = get_providers().get(provider_id) or get_providers().get("ollama")
    return chat_blocking(
        provider, model, [{"role": "user", "content": prompt}],
        max_tokens=4000, temperature=0.2, timeout=timeout,
    )


def _failed_test_files(stderr: str, test_dir: Path) -> list[Path]:
    """Find ``Test_*.cpp`` files referenced by compiler errors."""
    files: list[Path] = []
    for m in re.finditer(r"(Test_\w+\.cpp):\d+", stderr):
        p = test_dir / m.group(1)
        if p.is_file() and p not in files:
            files.append(p)
    return files


def fix_loop(test_dir: Path | str, max_attempts: int = 2) -> dict[str, Any]:
    """Rebuild; when a ``Test_*.cpp`` fails to compile, ask the model to fix it."""
    env.ensure_environment()
    from app.config import config

    test_dir = Path(test_dir)
    result = build_and_run(test_dir)
    attempts = 0

    # Deterministic first: models often invent the "opposite" constant
    # (MODULE_NOT_READY next to MODULE_READY). Define those placeholders in the
    # test file itself (marked TODO(test)) instead of spending a model call.
    for _ in range(3):
        if result.get("status") != "build_failed":
            break
        stderr = (result.get("build_error") or "") + (result.get("build_output") or "")
        if not define_invented_constants(stderr, test_dir):
            break
        result = build_and_run(test_dir)

    while result.get("status") == "build_failed" and attempts < max_attempts:
        attempts += 1
        stderr = (result.get("build_error") or "") + (result.get("build_output") or "")
        files = _failed_test_files(stderr, test_dir)
        if not files:
            break
        for f in files:
            code = f.read_text(encoding="utf-8", errors="ignore")
            prompt = (
                "The following CppUTest file fails to compile. Fix the compile errors "
                "and return ONLY the corrected, complete file (no markdown fences, no explanation).\n\n"
                f"COMPILER ERRORS:\n{stderr[-3000:]}\n\n"
                f"FILE ({f.name}):\n```cpp\n{code}\n```\n"
            )
            fixed = _fixer_generate(prompt)
            if not fixed:
                continue
            fixed = fixed.strip()
            fixed = re.sub(r"^```(?:cpp|c\+\+)?\s*", "", fixed)
            fixed = re.sub(r"\s*```$", "", fixed)
            if fixed and fixed != code:
                f.write_text(fixed, encoding="utf-8")
        result = build_and_run(test_dir)

    # Still red: set aside the test files that keep failing to compile so the
    # rest of the suite can build, run and produce real results. They stay on
    # disk (quarantined/) and are reported — never silently dropped.
    quarantined: list[str] = []
    while result.get("status") == "build_failed":
        stderr = (result.get("build_error") or "") + (result.get("build_output") or "")
        files = _failed_test_files(stderr, test_dir)
        if not files:
            break
        qdir = test_dir / "quarantined"
        qdir.mkdir(exist_ok=True)
        for f in files:
            f.replace(qdir / f.name)
            quarantined.append(f.name)
        if not list(test_dir.glob("Test_*.cpp")):
            break
        result = build_and_run(test_dir)

    # Nothing AI-written survived: fall back to a deterministic smoke test so
    # the design is still built, executed and measured (coverage). It is
    # labelled as such in the results — not presented as model output.
    smoke = False
    if not list(test_dir.glob("Test_*.cpp")):
        if write_smoke_test(test_dir):
            smoke = True
            result = build_and_run(test_dir)

    result["fix_attempts"] = attempts
    result["quarantined_tests"] = quarantined
    result["smoke_fallback"] = smoke
    return result


_PROTOTYPE_RE = re.compile(r"^\s*void\s+(\w+)\s*\(\s*void\s*\)\s*;", re.MULTILINE)
# g++: 'X' was not declared in this scope  (‘X’ in UTF-8 locales)
_NOT_DECLARED_RE = re.compile(
    "(Test_\\w+\\.cpp):\\d+:\\d+: error: ['‘]([A-Z][A-Z0-9_]*)['’] was not declared in this scope"
)


def define_invented_constants(build_log: str, test_dir: Path) -> bool:
    """Add ``#define`` placeholders for UPPER_CASE constants a test file uses but
    nothing defines. Returns True if any file was changed."""
    per_file: dict[str, set[str]] = {}
    for fname, name in _NOT_DECLARED_RE.findall(build_log):
        per_file.setdefault(fname, set()).add(name)
    changed = False
    for fname, names in per_file.items():
        path = Path(test_dir) / fname
        if not path.is_file():
            continue
        code = path.read_text(encoding="utf-8", errors="ignore")
        block = "".join(
            f"#ifndef {n}\n#define {n} ({9000 + i})  /* TODO(test): constant invented by the model */\n#endif\n"
            for i, n in enumerate(sorted(names))
            if f"#define {n} " not in code
        )
        if block:
            path.write_text(block + code, encoding="utf-8", newline="\n")
            changed = True
    return changed


def write_smoke_test(test_dir: Path) -> bool:
    """Write ``Test_Smoke.cpp`` calling every runnable declared in the module
    header (``<SWC>.h`` from ``compilable``). Returns False if none found."""
    test_dir = Path(test_dir)
    for header in sorted(test_dir.glob("*.h")):
        if header.name.startswith("Rte_"):
            continue
        runnables = list(dict.fromkeys(_PROTOTYPE_RE.findall(header.read_text(encoding="utf-8"))))
        if not runnables:
            continue
        tests = "\n".join(
            f"TEST(Smoke, {name}_runs)\n{{\n    {name}();\n    CHECK(true);\n}}\n"
            for name in runnables
        )
        (test_dir / "Test_Smoke.cpp").write_text(
            "// Deterministic smoke test (fallback): every AI-generated test file failed\n"
            "// to compile and was quarantined. Each runnable is executed once.\n"
            '#include "CppUTest/TestHarness.h"\n'
            f'#include "{header.name}"\n\n'
            "TEST_GROUP(Smoke) {};\n\n" + tests,
            encoding="utf-8", newline="\n",
        )
        return True
    return False
