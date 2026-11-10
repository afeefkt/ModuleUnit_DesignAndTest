"""Benchmark tables: no-op test detection and the per-run numbers."""

from mudmut_core import benchmark, report
from mudmut_core.workspace import Run

NOOP = """
TEST_GROUP(G) {};
TEST(G, CallDoesNotCrash) { f(); CHECK_TRUE(true); }
TEST(G, Loop) { for (int i = 0; i < 3; ++i) { f(); } CHECK(1); }
"""
REAL = """
TEST_GROUP(G) {};
TEST(G, Smoke) { f(); CHECK_TRUE(true); }
TEST(G, Timer) { f(); LONGS_EQUAL(5U, timer); }
TEST(G, Flag) { f(); CHECK(fault == ACT_FAULT_DEVIATION); }
"""


def test_noop_and_real_test_cases():
    assert benchmark.test_case_kinds(NOOP) == {"CallDoesNotCrash": False, "Loop": False}
    assert benchmark.test_case_kinds(REAL) == {"Smoke": False, "Timer": True, "Flag": True}
    assert benchmark.test_case_kinds("TEST(G, A) { CHECK_FALSE(false); CHECK_TRUE(x > (y + 1)); }") == {"A": True}


def test_noop_files(tmp_path):
    (tmp_path / "Test_a.cpp").write_text(NOOP)
    (tmp_path / "Test_b.cpp").write_text(REAL)
    assert benchmark.noop_test_files(tmp_path, ["Test_a.cpp", "Test_b.cpp", "Test_missing.cpp"]) == ["Test_a.cpp"]


def test_verified_split_by_real_assertions(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "_ID_SETS", {})
    run = Run.create("SWC_X", root=tmp_path)
    run.save_state(quick=True)
    (run.dir("mut") / "Test_a.cpp").write_text(NOOP)
    (run.dir("mut") / "Test_b.cpp").write_text(REAL)
    run.save_json_in("code", "compilability.json", {"total_statements": 10, "kept_statements": 8,
                                                    "stubbed_statements": 2})
    run.save_json_in("mut", "results.json", {"generation": {"tests_generated": 2}})
    run.save_json_in("trace", "trace.json", {
        "generated_tests": {"test_files": ["Test_a.cpp", "Test_b.cpp"]},
        "trace": [{"requirement": "R-1", "status": "verified_by_test", "verified_by": ["Test_a.cpp"]},
                  {"requirement": "R-2", "status": "verified_by_test", "verified_by": ["Test_a.cpp", "Test_b.cpp"]},
                  {"requirement": "R-3", "status": "not_verified", "verified_by": []}],
        "summary": {"requirements": 3, "verified_by_test": 2, "failing_test": 0, "not_verified": 1}})
    report.write_run_report(run, {"swc": "SWC_X", "quick": True, "tests_generated": 2,
                                  "tests": {"status": "passed", "junit": {"passed": 4, "failures": 0}}})

    row = benchmark.run_row(Run.load(run.folder))

    assert row["verified"] == 2 and row["verified_real"] == 1
    assert row["noop_files"] == ["Test_a.cpp"]
    assert row["tests_compiled"] == 2 and row["stubbed_pct"] == 20 and row["mode"] == "quick"
    assert "| 2 | 1 |" in benchmark.markdown([row], [])


def test_folder_without_report_is_listed_as_not_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "_ID_SETS", {})
    Run.create("SWC_Empty", root=tmp_path)
    rows, skipped = benchmark.collect(tmp_path)
    assert rows == [] and "no run report" in skipped[0]
