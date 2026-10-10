"""Regression tests for the code-review fixes (event loop, codegen, trace)."""

from __future__ import annotations

import asyncio

from mudmut_core import aio, compilable, env
from mudmut_core.trace import build_trace, extract_requirements


def test_run_sync_reuses_one_loop_across_calls():
    # A client created on the first call must still work on later calls — the
    # orchestrator's cached httpx client depends on this.
    async def current_loop():
        return asyncio.get_running_loop()

    first = aio.run_sync(current_loop())
    second = aio.run_sync(current_loop())
    assert first is second
    assert not first.is_closed()


def test_run_sync_returns_value_and_raises():
    async def ok():
        return 42

    async def boom():
        raise ValueError("x")

    assert aio.run_sync(ok()) == 42
    try:
        aio.run_sync(boom())
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("exception not propagated")


def _test_generator():
    env.ensure_environment()
    from app.services import test_generator
    return test_generator


def test_uniquify_does_not_rename_function_calls():
    tg = _test_generator()
    code = (
        "TEST_GROUP(RE_EstimateSOC) {};\n"
        "TEST(RE_EstimateSOC, runs) { RE_EstimateSOC(); CHECK(true); }\n"
        "IGNORE_TEST(RE_EstimateSOC, later) { RE_EstimateSOC(); }\n"
    )
    out = tg._uniquify_test_group(code, "RE_EstimateSOC")
    assert "TEST_GROUP(RE_EstimateSOC_Group)" in out
    assert "TEST(RE_EstimateSOC_Group, runs)" in out
    assert "IGNORE_TEST(RE_EstimateSOC_Group, later)" in out
    # the call to the function under test is untouched
    assert out.count("RE_EstimateSOC();") == 2


def test_uniquify_handles_every_group():
    tg = _test_generator()
    code = "TEST_GROUP(A) {};\nTEST(A, x) {}\nTEST_GROUP(B) {};\nTEST(B, y) {}\n"
    out = tg._uniquify_test_group(code, "f")
    assert "TEST_GROUP(f_Group)" in out and "TEST(f_Group, x)" in out
    assert "TEST_GROUP(f_Group2)" in out and "TEST(f_Group2, y)" in out


def test_generated_makefile_and_runner_have_lf_endings(tmp_path):
    tg = _test_generator()
    tg.create_makefile(tmp_path)
    tg.create_main_runner(tmp_path)
    assert b"\r" not in (tmp_path / "Makefile").read_bytes()
    assert b"\r" not in (tmp_path / "AllTests.cpp").read_bytes()
    assert b"CPPUTEST_HOME ?= /usr\n" in (tmp_path / "Makefile").read_bytes()


def test_trace_keeps_full_requirement_ids_and_ignores_noise():
    code = (
        "/* Requirements: REQ-BMS-001, REQ-BMS-002 */\n"
        '#include "Rte_Type.h"  /* encoding UTF-8, ISO-26262 */\n'
        "void RE_A(void)\n{\n    /* [REQ-BMS-001] */\n    l_u8X = 1;\n}\n"
    )
    assert extract_requirements(code) == ["REQ-BMS-001", "REQ-BMS-002"]


def _junit(*cases):
    body = "".join(
        f'<testcase classname="c" name="n{i}" file="{f}" line="1">'
        + ("<failure message='x'/>" if failed else "")
        + "</testcase>\n"
        for i, (f, failed) in enumerate(cases)
    )
    return f'<?xml version="1.0"?><testsuites><testsuite>{body}</testsuite></testsuites>'


def test_trace_statuses_follow_real_test_results(tmp_path):
    out_dir = tmp_path / "tests_x"
    out_dir.mkdir()
    for f in ("Test_RE_A.cpp", "Test_RE_B.cpp", "Test_RE_C.cpp"):
        (out_dir / f).write_text("// t", encoding="utf-8")
    (out_dir / "test-results.xml").write_text(
        _junit(("Test_RE_A.cpp", False), ("Test_RE_A.cpp", False), ("Test_RE_B.cpp", True)),
        encoding="utf-8",
    )
    code = (
        "/* Requirements: REQ-1, REQ-2, REQ-3, REQ-4 */\n"
        "void RE_A(void)\n{\n    /* [REQ-1] */\n    l_u8X = 1;\n}\n"
        "void RE_B(void)\n{\n    /* [REQ-2] */\n    l_u8X = 2;\n}\n"
        "void RE_C(void)\n{\n    /* [REQ-3] */\n    l_u8X = 3;\n}\n"
    )
    record = build_trace("SWC_X", code, {"output_directory": str(out_dir)})
    status = {t["requirement"]: t["status"] for t in record["trace"]}
    assert status == {
        "REQ-1": "verified_by_test",   # ran, all passed
        "REQ-2": "failing_test",       # ran, a case failed
        "REQ-3": "test_not_run",       # test file exists, no results
        "REQ-4": "not_verified",       # no function carries it
    }
    assert record["summary"]["verified_by_test"] == 1
    assert record["summary"]["not_verified"] == 1


def test_implicit_declaration_pattern_accepts_curly_and_ascii_quotes():
    for msg in (
        "x.c:3:5: error: implicit declaration of function ‘EKF_Predict’",
        "x.c:3:5: error: implicit declaration of function 'EKF_Predict'",
    ):
        assert compilable._IMPLICIT_DECL_RE.findall(msg) == ["EKF_Predict"]
