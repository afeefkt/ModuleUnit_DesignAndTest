from mudmut_core import toolchain


def test_wsl_path_converts_drive_letter():
    assert toolchain.wsl_path("D:\\foo\\bar") == "/mnt/d/foo/bar"
    assert toolchain.wsl_path("C:\\x") == "/mnt/c/x"


def test_wsl_path_preserves_unix_path():
    assert toolchain.wsl_path("/mnt/d/foo") == "/mnt/d/foo"


def test_check_toolchain_returns_known_tools():
    report = toolchain.check_toolchain()
    names = {t.name for t in report.tools}
    assert {"gcc", "g++", "make", "gcov", "CppUTest", "lcov"} <= names


def test_make_result_ok():
    assert toolchain.MakeResult([], 0, "", "", []).ok is True
    assert toolchain.MakeResult([], 1, "", "", []).ok is False


def test_run_make_missing_target_reports_failure(tmp_path):
    result = toolchain.run_make(tmp_path, targets=("nonexistent-target",), timeout=60)
    assert result.returncode != 0
