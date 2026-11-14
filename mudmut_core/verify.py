"""MUT (unit-test half): analyze → generate tests → build/run → fix loop.

Runs the cpputest-rag library in-process (no FastAPI, no Docker).
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Optional

from mudmut_core import env, settings, toolchain

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
async def generate_tests(project_dir: Path | str, function_name: Optional[str] = None, output_dir: Optional[Path] = None,
                         progress=None) -> dict:
    env.ensure_environment()
    from app.services.test_generator import generate_tests_for_project

    await ensure_rag_index()
    result = await generate_tests_for_project(Path(project_dir), function_name=function_name,
                                              output_dir=output_dir, progress=progress)

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


def write_makefile(test_dir: Path | str) -> toolchain.CppUTestInfo:
    """(Re)write ``<test_dir>/Makefile`` against the configured / detected CppUTest.

    Called before every build, so changing the CppUTest folder in Settings takes
    effect without regenerating the tests.
    """
    env.ensure_environment()
    from app.services.test_generator import create_makefile
    cfg = settings.get_settings()
    info = toolchain.find_cpputest(cfg["cpputest_home"])
    cpputest = {
        "home": info.home, "include_dir": info.include_dir,
        "lib_dir": info.lib_dir, "has_ext": info.has_ext,
    } if info.found else None
    create_makefile(Path(test_dir), cpputest=cpputest, extra_cflags=cfg["extra_cflags"])
    return info


# Typographic characters a model writes into code ("l_x \u2014 1", \u201cquotes\u201d) are not valid C++ outside a
# comment or string: g++ "extended character is not valid in an identifier" failed a whole coverage round.
_ASCII_MAP = {"\u2014": "-", "\u2013": "-", "\u2212": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"',
              "\u201d": '"', "\u00a0": " ", "\u2026": "...", "\u00d7": "*", "\u2264": "<=", "\u2265": ">=",
              "\u2260": "!=", "\u2192": "->"}


def ascii_test_sources(test_dir: Path | str) -> list[str]:
    """Replace typographic characters in the AI-written ``Test_*.cpp`` files with ASCII; returns the files changed."""
    changed = []
    for f in sorted(Path(test_dir).glob("Test_*.cpp")):
        text = f.read_text(encoding="utf-8", errors="replace")
        fixed = "".join(_ASCII_MAP.get(ch, ch) for ch in text)
        if fixed != text:
            f.write_text(fixed, encoding="utf-8")
            changed.append(f.name)
    return changed


def build_and_run(test_dir: Path | str) -> dict[str, Any]:
    """Build (``make clean all``) then run with coverage (``make coverage``)."""
    test_dir = Path(test_dir)
    ascii_test_sources(test_dir)

    cpputest = write_makefile(test_dir)
    cpputest_info = {
        "found": cpputest.found, "home": cpputest.home,
        "include_dir": cpputest.include_dir, "lib_dir": cpputest.lib_dir,
    }
    if not cpputest.found:
        return {
            "status": "build_failed",
            "cpputest_missing": True,
            "cpputest": cpputest_info,
            "build_output": "",
            "build_error": (
                f"{cpputest.detail}. Set the CppUTest folder on the Settings page "
                f"(or MUDMUT_CPPUTEST_HOME), or install it: {toolchain.APT_INSTALL_CPPUTEST_LCOV}"
            ),
            "test_output": None,
            "test_error": None,
        }

    build = toolchain.run_make(test_dir, targets=("clean", "all"))
    if not build.ok:
        return {
            "status": "build_failed",
            "cpputest": cpputest_info,
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
        "cpputest": cpputest_info,
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
def _fixer_generate(prompt: str, *, timeout: int = 300, max_tokens: int = 8000) -> str:
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
    try:
        return chat_blocking(
            provider, model, [{"role": "user", "content": prompt}],
            max_tokens=max_tokens, temperature=0.2, timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - a failed fix attempt is non-fatal
        print(f"[mudmut_core] test fixer generation failed: {exc}")
        return ""


def _failed_test_files(stderr: str, test_dir: Path) -> list[Path]:
    """Find ``Test_*.cpp`` files referenced by compiler errors."""
    files: list[Path] = []
    for m in re.finditer(r"(Test_\w+\.cpp):\d+", stderr):
        p = test_dir / m.group(1)
        if p.is_file() and p not in files:
            files.append(p)
    return files


_GROUP_RE = re.compile(r"\bTEST_GROUP\s*\(\s*(\w+)\s*\)")

_TEST_API_HINT = (
    "\nTEST INTERFACE of the code under test (from Rte_<SWC>.h): RTE signals are plain variables. "
    "Set Rte_Read_<port>, Rte_IRead_<port> and Rte_Prm_<port> before calling a runnable, check Rte_Write_<port> / Rte_IWrite_<port> after, "
    "and call Rte_Stubs_Reset() in setup(). Rte_Prm(<port>) is assignable too. Accessors with an element "
    "name (Rte_Read_<port>_<elem>, Rte_IRead_<port>_<elem>, Rte_Write_<port>_<elem>) are variables in the "
    "same way: assign or compare them, never call them from a test. IRVs (Rte_IrvRead/Rte_IrvWrite(IRV_X, ..)) are "
    "the variables IRV_X. Calls to other functions (Dem_*, WdgM_*, Rte_Call_* ...) are recorded: check "
    "<function>_callCount and <function>_arg0, <function>_arg1 ...; never define your own mock of them. "
    "Rte_IsUpdated(port) returns Rte_IsUpdated_return (default 1 = updated; set it to 0 for the not-updated path). "
    "A status-returning read - Rte_IrvRead(IRV_X, &x), Rte_Read(RP_X, &x), Rte_Read_<port>_<elem>(&x) - returns the "
    "variable IRV_X_status / Rte_Read_RP_X_status / Rte_Read_<port>_<elem>_status (0 = RTE_E_OK by default, reset by "
    "Rte_Stubs_Reset()); set it to RTE_E_NO_DATA (or any non-zero value) to make that read fail. Only those "
    "*_status variables exist for reads - never invent RTE_E_NOT_OK or *_return variables for them. Use only constants that exist in the headers; for \"a value different from X\" write (X + 1).\n"
)


def same_test_groups(original: str, fixed: str) -> bool:
    """A fix must keep the file's TEST_GROUP names (it may not turn into another file's tests)."""
    before = set(_GROUP_RE.findall(original))
    return not before or set(_GROUP_RE.findall(fixed)) == before


def errors_for_file(stderr: str, filename: str, limit: int = 3000) -> str:
    """Only the compiler/linker lines about ``filename`` (plus the lines that follow each one)."""
    lines = (stderr or "").splitlines()
    keep: list[str] = []
    for i, line in enumerate(lines):
        if filename in line:
            keep.extend(lines[i:i + 3])
    text = "\n".join(dict.fromkeys(keep)) or (stderr or "")[-limit:]
    return text[:limit]


MAX_FIX_ATTEMPTS = 8      # rebuild-and-ask rounds (each round asks for every file that still fails)
COVERAGE_ROUNDS = 3       # coverage-gap rounds after the suite is green (0 = off)
MAX_FIX_STALLS = 2        # a file whose compiler error did not change this many answers in a row is given up


def available_stub_symbols(test_dir: Path | str, limit: int = 120) -> str:
    """Names of the extern variables / functions the Rte header gives a test (so a fixer stops inventing others)."""
    names: list[str] = []
    for h in sorted(Path(test_dir).glob("Rte_*.h")):
        text = h.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"^[ \t]*extern[ \t]+[\w \t\*]+?(\w+)[ \t]*(?:\[[^\]]*\])?[ \t]*[;(]", text, re.M):
            names.append(m.group(1))
    return ", ".join(dict.fromkeys(names))[:limit * 40]


def _undeclared_hint(errors: str, test_dir: Path) -> str:
    missing = list(dict.fromkeys(re.findall(r"['‘]([A-Za-z_]\w*)['’] was not declared", errors)))
    if not missing:
        return ""
    return (
        "\nThese names do not exist: " + ", ".join(missing) + ". Do NOT invent them. The variables a test can use are: "
        + available_stub_symbols(test_dir) + ". To make a read fail set its *_status variable (e.g. IRV_X_status = "
        "RTE_E_NO_DATA;). If a scenario cannot be expressed with these variables, DELETE that TEST instead of "
        "inventing symbols.\n"
    )



def fix_loop(test_dir: Path | str, max_attempts: int = MAX_FIX_ATTEMPTS, *, coverage_rounds: int = COVERAGE_ROUNDS) -> dict[str, Any]:
    """Rebuild; when a ``Test_*.cpp`` fails to compile, send the compiler errors to the model for a
    corrected file — again and again until every file compiles.

    Each round asks for every file that still fails. A file is given up (and later quarantined,
    reported) only after ``max_attempts`` rounds or when its compiler error stayed the same for
    more than ``MAX_FIX_STALLS`` answers in a row, so the loop cannot run forever.
    """
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

    last_errors: dict[str, str] = {}
    stalls: dict[str, int] = {}
    while result.get("status") == "build_failed" and attempts < max_attempts:
        stderr = (result.get("build_error") or "") + (result.get("build_output") or "")
        files = _failed_test_files(stderr, test_dir)
        if not files:
            break
        asked = 0
        for f in files:
            errors = errors_for_file(stderr, f.name)
            stalls[f.name] = stalls.get(f.name, -1) + 1 if last_errors.get(f.name) == errors else 0
            last_errors[f.name] = errors
            if stalls[f.name] > MAX_FIX_STALLS:
                continue                      # the model cannot fix this one: it gets quarantined below
            asked += 1
            code = f.read_text(encoding="utf-8", errors="ignore")
            again = (f"\nYour previous fix still shows the same error — change the code the error points at.\n"
                     if stalls[f.name] else "")
            prompt = (
                "The following CppUTest file fails to compile. Fix the compile errors "
                "and return ONLY the corrected, complete file (no markdown fences, no explanation). "
                f"Keep its TEST_GROUP and TEST names; do not write tests for other functions.\n\n"
                f"COMPILER ERRORS (for {f.name} only):\n{errors}\n{again}{_undeclared_hint(errors, test_dir)}\n"
                f"FILE ({f.name}):\n```cpp\n{code}\n```\n"
                f"{_TEST_API_HINT}"
            )
            fixed = _fixer_generate(prompt)
            if not fixed:
                continue
            fixed = fixed.strip()
            fixed = re.sub(r"^```(?:cpp|c\+\+)?\s*", "", fixed)
            fixed = re.sub(r"\s*```$", "", fixed)
            if fixed and fixed != code:
                if not same_test_groups(code, fixed):
                    # The model answered with another file's tests (seen: Test_RE_CommandBrake.cpp
                    # replaced by RE_Init tests → duplicate symbols at link time). Keep the original.
                    print(f"[mudmut_core] test fixer reply for {f.name} changed its TEST_GROUPs — rejected")
                    continue
                f.write_text(fixed, encoding="utf-8")
        if not asked:
            break                             # every failing file is given up
        attempts += 1
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

    dem_corrected: list[str] = []
    if result.get("status") == "test_failed" and not smoke:
        result, dem_corrected = fix_dem_expectations(test_dir, result)

    expectations_repaired: list[str] = []
    if coverage_rounds and result.get("status") == "test_failed" and not smoke:
        result, expectations_repaired = fix_failing_expectations(test_dir, result)

    coverage_extended: list[str] = []
    if coverage_rounds and result.get("status") in ("passed", "test_failed") and not smoke:
        result, coverage_extended = improve_coverage(test_dir, result, rounds=coverage_rounds)

    link_errors = list(dict.fromkeys(
        re.findall(r"undefined reference to [`']([^`']+)['`]",
                   (result.get("build_error") or "") + (result.get("build_output") or ""))
    ))
    result["link_errors"] = link_errors
    result["fix_attempts"] = attempts
    result["quarantined_tests"] = quarantined
    result["smoke_fallback"] = smoke
    result["dem_expectations_corrected"] = dem_corrected
    result["coverage_extended"] = coverage_extended
    result["expectations_repaired"] = expectations_repaired
    return result


# ── tests that misjudge the Dem reports of the code ──────────────────────────────────────────────────────
# A monitor reports FAILED on the bad path and PASSED on the healthy one, so "Dem_ReportErrorStatus_callCount
# is 0 for valid input" is a wrong expectation, not a code defect (it made 5-26 tests per run fail). The
# failing tests are sent back once with the function's own Dem reports; the answer is kept only when it
# lowers the number of failures.
_DEM_FAILURE_RE = re.compile(r"Dem_ReportErrorStatus_(?:callCount|arg\d|hist_arg\d)")
_DEM_CALL_RE = re.compile(r"\bDem_ReportErrorStatus\s*\(\s*([^,()]+?)\s*,\s*([^()]+?)\s*\)")


def failing_dem_tests(test_dir: Path | str) -> dict[str, list[tuple[str, str]]]:
    """``{Test_X.cpp: [(test name, failure message), ...]}`` for failures about Dem_ReportErrorStatus."""
    import xml.etree.ElementTree as ET
    test_dir = Path(test_dir)
    out: dict[str, list[tuple[str, str]]] = {}
    xml = test_dir / "test-results.xml"
    if not xml.is_file():
        return out
    try:
        root = ET.parse(xml).getroot()
    except ET.ParseError:
        return out
    for tc in root.iter("testcase"):
        failure = tc.find("failure")
        if failure is None:
            continue
        message = (failure.get("message") or failure.text or "")
        if not _DEM_FAILURE_RE.search(message):
            continue
        group = (tc.get("classname") or "").split(".")[-1]
        fname = "Test_" + re.sub(r"_Group$", "", group) + ".cpp"
        if (test_dir / fname).is_file():
            out.setdefault(fname, []).append((tc.get("name") or "?", message.strip().replace("\n", " | ")[:300]))
    return out


def function_source(test_dir: Path | str, name: str) -> str:
    """The C source of function ``name`` from the code under test in ``test_dir`` ('' when not found)."""
    for c_file in sorted(Path(test_dir).glob("*.c")):
        if c_file.name == "Rte_Stubs.c":
            continue
        text = c_file.read_text(encoding="utf-8", errors="ignore")
        m = re.search(rf"^[A-Za-z_][\w \t\*]*\b{re.escape(name)}\s*\([^)]*\)\s*\n?\s*\{{", text, re.MULTILINE)
        if not m:
            continue
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += (text[i] == "{") - (text[i] == "}")
            i += 1
        return text[m.start():i]
    return ""


def fix_dem_expectations(test_dir: Path | str, result: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """One correction round for tests whose Dem expectations contradict the code's own reports.

    Returns ``(result, corrected file names)``. A file is replaced only when the rebuilt suite has fewer
    failing tests; otherwise the original file is restored.
    """
    test_dir = Path(test_dir)
    if result.get("status") != "test_failed":
        return result, []
    wrong = failing_dem_tests(test_dir)
    if not wrong:
        return result, []
    before = _failure_count(test_dir)
    originals: dict[str, str] = {}
    for fname, failures in wrong.items():
        path = test_dir / fname
        code = path.read_text(encoding="utf-8", errors="ignore")
        group = re.sub(r"^Test_|\.cpp$", "", fname)
        src = function_source(test_dir, group)
        reports = list(dict.fromkeys(f"{ev}, {st}" for ev, st in _DEM_CALL_RE.findall(src)))
        listing = "\n".join(f"- {n}: {m}" for n, m in failures[:12])
        prompt = (
            "These CppUTest tests fail because their expectations about Dem_ReportErrorStatus do not match what "
            "the code under test really reports. The code is the reference for WHAT it reports: read its source, "
            "work out for each failing test which reports its path makes (a healthy path usually still reports "
            "DEM_EVENT_STATUS_PASSED), and correct only those expectations — keep every test, its inputs and its "
            "other assertions, and do not delete or loosen checks. Use <function>_callCount for the count and "
            "Dem_ReportErrorStatus_hist_arg0[k] / _hist_arg1[k] for the k-th report (k = 0 first). Return ONLY the "
            "complete corrected file (no markdown fences, no explanation).\n\n"
            f"FAILING TESTS ({fname}):\n{listing}\n\n"
            f"DEM REPORTS IN THE CODE (event, status): {'; '.join(reports) or 'none found'}\n\n"
            f"FUNCTION UNDER TEST:\n```c\n{src[:6000]}\n```\n\n"
            f"FILE ({fname}):\n```cpp\n{code}\n```\n"
            f"{_TEST_API_HINT}"
        )
        fixed = _fixer_generate(prompt)
        if not fixed:
            continue
        fixed = re.sub(r"\s*```$", "", re.sub(r"^```(?:cpp|c\+\+)?\s*", "", fixed.strip()))
        if fixed and fixed != code and same_test_groups(code, fixed):
            originals[fname] = code
            path.write_text(fixed, encoding="utf-8")
    if not originals:
        return result, []
    rebuilt = build_and_run(test_dir)
    after = _failure_count(test_dir) if rebuilt.get("status") in ("test_failed", "passed") else None
    if after is None or after >= before:
        for fname, code in originals.items():       # no improvement: put the original tests back
            (test_dir / fname).write_text(code, encoding="utf-8")
        return build_and_run(test_dir), []
    return rebuilt, sorted(originals)


def fix_failing_expectations(test_dir: Path | str, result: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """One correction round for tests that still fail: the model re-derives each expectation from the C source.

    Nothing is deleted or loosened. A file is replaced only when the rebuilt suite has fewer failing tests;
    otherwise the original file is restored. Remaining failures stay visible (they may be real code defects).
    """
    test_dir = Path(test_dir)
    if result.get("status") != "test_failed":
        return result, []
    failing = failing_tests(test_dir)
    if not failing:
        return result, []
    before = _failure_count(test_dir)
    originals: dict[str, str] = {}
    for fname, items in failing.items():
        path = test_dir / fname
        code = path.read_text(encoding="utf-8", errors="ignore")
        group = re.sub(r"^Test_|\.cpp$", "", fname)
        listing = "\n".join(f"- {n}: {m}" for n, m in items[:12])
        prompt = (
            "These CppUTest tests fail. The C code under test is the reference for WHAT it computes: read its source, "
            "work out by hand what it returns / writes / reports for each failing test's inputs, and correct the "
            "expectation, or the inputs that do not reach the intended path. Keep every test and its name; do not "
            "delete tests, do not weaken checks to constants, do not change tests that pass. Return ONLY the complete "
            "corrected file (no markdown fences, no explanation).\n\n"
            f"FAILING TESTS ({fname}):\n{listing}\n\n"
            f"FUNCTION UNDER TEST:\n```c\n{function_source(test_dir, group)[:6000]}\n```\n\n"
            f"FILE ({fname}):\n```cpp\n{code}\n```\n{_TEST_API_HINT}"
        )
        fixed = re.sub(r"\s*```$", "", re.sub(r"^```(?:cpp|c\+\+)?\s*", "", (_fixer_generate(prompt) or "").strip()))
        if fixed and fixed != code and same_test_groups(code, fixed):
            originals[fname] = code
            path.write_text(fixed, encoding="utf-8")
    if not originals:
        return result, []
    rebuilt = build_and_run(test_dir)
    after = _failure_count(test_dir) if rebuilt.get("status") in ("test_failed", "passed") else None
    print(f"[mudmut_core] expectation repair: failing {before} -> {after}")
    if after is None or after >= before:
        for fname, code in originals.items():
            (test_dir / fname).write_text(code, encoding="utf-8")
        return build_and_run(test_dir), []
    return rebuilt, sorted(originals)


def _failure_count(test_dir: Path | str) -> int:
    import xml.etree.ElementTree as ET
    xml = Path(test_dir) / "test-results.xml"
    try:
        return sum(1 for tc in ET.parse(xml).getroot().iter("testcase") if tc.find("failure") is not None)
    except (ET.ParseError, OSError):
        return 10 ** 6



# ── coverage gaps: ask for tests that reach the lines / branches no test reaches ─────────────────────────
COVERAGE_TARGET = 85.0          # per-function line+branch percentage below which a function gets one more round


def coverage_gaps(test_dir: Path | str) -> dict[str, dict[str, Any]]:
    """``{function: {pct, lines (uncovered line numbers), branch_lines, start, end, file}}`` from coverage.info."""
    test_dir = Path(test_dir)
    info = test_dir / "coverage.info"
    if not info.is_file():
        return {}
    gaps: dict[str, dict[str, Any]] = {}
    for rec in info.read_text(encoding="utf-8", errors="replace").split("end_of_record"):
        sf = re.search(r"^SF:(.+)$", rec, re.M)
        if not sf or Path(sf.group(1).strip()).name == "Rte_Stubs.c":
            continue
        fname = Path(sf.group(1).strip()).name
        ranges = {int(m.group(1)): (int(m.group(2)), int(m.group(3)))
                  for m in re.finditer(r"^FNL:(\d+),(\d+),(\d+)\s*$", rec, re.M)}
        names = {int(m.group(1)): m.group(3) for m in re.finditer(r"^FNA:(\d+),(\d+),(.+)$", rec, re.M)}
        lines = {int(m.group(1)): int(m.group(2)) for m in re.finditer(r"^DA:(\d+),(\d+)", rec, re.M)}
        branches = [(int(m.group(1)), m.group(2)) for m in re.finditer(r"^BRDA:(\d+),\d+,\d+,(\S+)$", rec, re.M)]
        for idx, (start, end) in ranges.items():
            name = names.get(idx)
            if not name:
                continue
            in_fn = {ln: c for ln, c in lines.items() if start <= ln <= end}
            br = [(ln, c) for ln, c in branches if start <= ln <= end]
            total = len(in_fn) + len(br)
            if not total:
                continue
            hit = sum(1 for c in in_fn.values() if c > 0) + sum(1 for _l, c in br if c not in ("-", "0"))
            gaps[name] = {
                "pct": 100.0 * hit / total, "file": fname, "start": start, "end": end,
                "lines": sorted(ln for ln, c in in_fn.items() if c == 0),
                "branch_lines": sorted({ln for ln, c in br if c in ("-", "0")}),
            }
    return gaps


def _coverage_pct(test_dir: Path | str) -> float:
    gaps = coverage_gaps(test_dir)
    return sum(g["pct"] for g in gaps.values()) / len(gaps) if gaps else 0.0


def _numbered_source(test_dir: Path, gap: dict[str, Any]) -> str:
    src = (test_dir / gap["file"]).read_text(encoding="utf-8", errors="ignore").splitlines()
    unreached = set(gap["lines"]) | set(gap["branch_lines"])
    out = []
    for n in range(gap["start"], min(gap["end"], len(src)) + 1):
        out.append(f"{'>>' if n in unreached else '  '} {n:4d}| {src[n - 1]}")
    return "\n".join(out)


def failing_tests(test_dir: Path | str) -> dict[str, list[tuple[str, str]]]:
    """``{Test_X.cpp: [(test name, failure message), ...]}`` for every failing test in test-results.xml."""
    import xml.etree.ElementTree as ET
    test_dir = Path(test_dir)
    out: dict[str, list[tuple[str, str]]] = {}
    try:
        root = ET.parse(test_dir / "test-results.xml").getroot()
    except (ET.ParseError, OSError):
        return out
    for tc in root.iter("testcase"):
        failure = tc.find("failure")
        if failure is None:
            continue
        group = (tc.get("classname") or "").split(".")[-1]
        fname = "Test_" + re.sub(r"_Group$", "", group) + ".cpp"
        if (test_dir / fname).is_file():
            msg = (failure.get("message") or failure.text or "").strip().replace("\n", " | ")[:300]
            out.setdefault(fname, []).append((tc.get("name") or "?", msg))
    return out


def remove_tests(code: str, names: set[str]) -> str:
    """``code`` without the ``TEST(group, name) { ... }`` blocks whose name is in ``names``."""
    out, pos = [], 0
    for m in re.finditer(r"^[ \t]*TEST\s*\(\s*\w+\s*,\s*(\w+)\s*\)\s*\{", code, re.M):
        if m.start() < pos or m.group(1) not in names:
            continue
        depth, i = 1, m.end()
        while i < len(code) and depth:
            depth += (code[i] == "{") - (code[i] == "}")
            i += 1
        out.append(code[pos:m.start()])
        pos = i
    out.append(code[pos:])
    return "".join(out)


def _repair_new_failures(test_dir: Path, before: dict[str, set[str]]) -> None:
    """Tests that fail now but did not before: one correction round with their failure messages and the
    function source, then the ones that still fail are removed (a failing generated test is not trusted)."""
    for attempt in ("repair", "drop"):
        now = failing_tests(test_dir)
        new = {f: [(n, m) for n, m in items if n not in before.get(f, set())] for f, items in now.items()}
        new = {f: items for f, items in new.items() if items}
        if not new:
            return
        for fname, items in new.items():
            path = test_dir / fname
            code = path.read_text(encoding="utf-8", errors="ignore")
            if attempt == "repair":
                group = re.sub(r"^Test_|\.cpp$", "", fname)
                listing = "\n".join(f"- {n}: {m}" for n, m in items[:12])
                prompt = (
                    "These newly added CppUTest tests fail. The C code is the reference: read its source, work out by "
                    "hand what it returns / writes / reports for each failing test's inputs, and correct the "
                    "expectation (or the inputs that do not reach the intended path). Keep every other test unchanged; "
                    "do not weaken checks to constants. Return ONLY the complete corrected file "
                    "(no markdown fences, no explanation).\n\n"
                    f"FAILING TESTS ({fname}):\n{listing}\n\n"
                    f"FUNCTION UNDER TEST:\n```c\n{function_source(test_dir, group)[:6000]}\n```\n\n"
                    f"FILE ({fname}):\n```cpp\n{code}\n```\n{_TEST_API_HINT}"
                )
                fixed = re.sub(r"\s*```$", "", re.sub(r"^```(?:cpp|c\+\+)?\s*", "", (_fixer_generate(prompt) or "").strip()))
                if fixed and fixed != code and same_test_groups(code, fixed):
                    path.write_text(fixed, encoding="utf-8")
            else:
                path.write_text(remove_tests(code, {n for n, _m in items}), encoding="utf-8")
        build_and_run(test_dir)


def improve_coverage(test_dir: Path | str, result: dict[str, Any], rounds: int = 2) -> tuple[dict[str, Any], list[str]]:
    """Up to ``COVERAGE_ROUNDS`` rounds: functions below ``COVERAGE_TARGET`` get extra tests for their unreached
    lines / branches. A round is kept only when overall coverage rises and the failing-test count does not grow.
    Returns ``(result, files extended)``."""
    test_dir = Path(test_dir)
    extended: list[str] = []
    for _round in range(rounds):
        if result.get("status") not in ("passed", "test_failed"):
            break
        weak = {n: g for n, g in coverage_gaps(test_dir).items()
                if g["pct"] < COVERAGE_TARGET and (test_dir / f"Test_{n}.cpp").is_file()}
        if not weak:
            break
        before_cov, before_fail = _coverage_pct(test_dir), _failure_count(test_dir)
        originals: dict[str, str] = {}
        for name, gap in weak.items():
            path = test_dir / f"Test_{name}.cpp"
            code = path.read_text(encoding="utf-8", errors="ignore")
            gm = re.search(r"TEST_GROUP\s*\(\s*(\w+)\s*\)", code)
            if not gm:
                continue
            prompt = (
                f"The CppUTest file below tests {name} (TEST_GROUP {gm.group(1)}). Its tests leave part of the function "
                f"unreached (line+branch coverage {gap['pct']:.0f}%). Lines marked '>>' in the source are not executed, "
                "or have a branch no test takes. Write NEW test cases that drive those lines/branches: choose inputs, "
                "stubbed return values and IRV/parameter values from the source so each condition is really taken, "
                "and assert the result the source computes (work it out from the code - do not guess). Use only "
                "helpers and stub variables already used in the file. Return ONLY the new "
                f"TEST({gm.group(1)}, <UniqueName>) {{ ... }} blocks - no includes, no TEST_GROUP, not the existing "
                "tests, no markdown fences, no explanation. Use names that do not exist yet. To reach a read-failure "
                "branch set the read's status variable before the call (IRV_X_status = RTE_E_NO_DATA; or "
                "Rte_Read_RP_X_status = RTE_E_NO_DATA;) - only these *_status variables exist; RTE_E_NOT_OK and "
                "*_return variables do not.\n\n"
                f"SOURCE OF {name} ('>>' = not reached):\n```c\n{_numbered_source(test_dir, gap)}\n```\n\n"
                f"EXISTING FILE (Test_{name}.cpp):\n```cpp\n{code}\n```\n"
                f"{_TEST_API_HINT}"
            )
            added = re.sub(r"\s*```$", "", re.sub(r"^```(?:cpp|c\+\+)?\s*", "", (_fixer_generate(prompt) or "").strip()))
            existing = set(re.findall(r"^\s*TEST\s*\(\s*\w+\s*,\s*(\w+)\s*\)", code, re.M))
            blocks = [b for b in re.split(r"(?m)^(?=\s*TEST\s*\()", added) if re.match(r"\s*TEST\s*\(", b)]
            blocks = [b for b in blocks if re.match(r"\s*TEST\s*\(\s*\w+\s*,\s*(\w+)", b).group(1) not in existing]
            if blocks and added.count("{") == added.count("}"):
                originals[path.name] = code
                path.write_text(code.rstrip() + "\n\n" + "\n".join(b.strip() + "\n" for b in blocks), encoding="utf-8")
        if not originals:
            print(f"[mudmut_core] coverage round {_round + 1}: no usable reply for {sorted(weak)}")
            break
        before_names = {f: {n for n, _m in items} for f, items in failing_tests(test_dir).items()}
        rebuilt = build_and_run(test_dir)
        if rebuilt.get("status") == "build_failed":      # new tests that do not compile
            errs = [l for l in ((rebuilt.get("build_error") or "") + (rebuilt.get("build_output") or "")).splitlines() if " error" in l]
            print("[mudmut_core] coverage round first build errors:", " | ".join(errs[:5])[:900])
            rebuilt = fix_loop(test_dir, max_attempts=3, coverage_rounds=0)
            if rebuilt.get("status") == "build_failed":
                errs = [l for l in ((rebuilt.get("build_error") or "") + (rebuilt.get("build_output") or "")).splitlines() if "error" in l]
                print("[mudmut_core] coverage round build errors:", " | ".join(errs[:4])[:600])
            if set(rebuilt.get("quarantined_tests", [])) & set(originals):
                rebuilt = {"status": "build_failed"}      # a file we extended was given up: revert below
        if rebuilt.get("status") == "test_failed" and _failure_count(test_dir) > before_fail:
            _repair_new_failures(test_dir, before_names)
            rebuilt = build_and_run(test_dir)
        ok = rebuilt.get("status") in ("passed", "test_failed")
        after_cov = _coverage_pct(test_dir) if ok else -1.0
        after_fail = _failure_count(test_dir) if ok else -1
        print(f"[mudmut_core] coverage round {_round + 1}: {before_cov:.1f}% -> {after_cov:.1f}%, "
              f"failing {before_fail} -> {after_fail}, status={rebuilt.get('status')}")
        if ok and after_cov > before_cov and after_fail <= before_fail:
            result = rebuilt
            extended.extend(f for f in originals if f not in extended)
            continue
        for fname, code in originals.items():       # no gain: put the original tests back
            (test_dir / fname).unlink(missing_ok=True)
            (test_dir / "quarantined" / fname).unlink(missing_ok=True)
            (test_dir / fname).write_text(code, encoding="utf-8")
        result = build_and_run(test_dir)
        break
    return result, extended


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
