"""CppUTest location setting, detection and the generated Makefile."""

import platform
from pathlib import Path

import pytest

from mudmut_core import settings, toolchain, verify

from mudmut_core.tests.test_review_fixes import _test_generator


def _fake_cpputest(root: Path, libdir: str, ext: bool = True) -> Path:
    (root / "include" / "CppUTest").mkdir(parents=True)
    (root / "include" / "CppUTest" / "TestHarness.h").write_text("")
    lib = root / libdir
    lib.mkdir(parents=True)
    (lib / "libCppUTest.a").write_text("")
    if ext:
        (lib / "libCppUTestExt.a").write_text("")
    return root


def test_settings_roundtrip_and_env_override(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.delenv("MUDMUT_CPPUTEST_HOME", raising=False)
    assert settings.get_settings()["cpputest_home"] == ""
    settings.save_settings(cpputest_home="/opt/x", extra_cflags="-DFOO")
    assert settings.get_settings()["cpputest_home"] == "/opt/x"
    monkeypatch.setenv("MUDMUT_CPPUTEST_HOME", "/env/x")
    assert settings.get_settings()["cpputest_home"] == "/env/x"
    # the env override is never written to the file
    settings.save_settings(extra_cflags="-DBAR")
    monkeypatch.delenv("MUDMUT_CPPUTEST_HOME")
    assert settings.get_settings()["cpputest_home"] == "/opt/x"


@pytest.mark.skipif(platform.system() == "Windows", reason="probe runs bash natively here; covered in WSL")
@pytest.mark.parametrize("libdir", ["lib", "lib64", "lib/x86_64-linux-gnu"])
def test_find_cpputest_lib_layouts(tmp_path, libdir):
    home = _fake_cpputest(tmp_path / "cpp", libdir)
    info = toolchain.find_cpputest(str(home))
    assert info.found and info.home == str(home)
    assert info.lib_dir == str(home / libdir) and info.has_ext


@pytest.mark.skipif(platform.system() == "Windows", reason="probe runs bash natively here; covered in WSL")
def test_find_cpputest_without_ext_and_missing(tmp_path):
    home = _fake_cpputest(tmp_path / "cpp", "lib", ext=False)
    assert toolchain.find_cpputest(str(home)).has_ext is False
    # a configured folder without CppUTest falls back to the usual places, never a crash
    info = toolchain.find_cpputest(str(tmp_path / "nothing"))
    assert info.found is False or info.home != str(tmp_path / "nothing")


def test_makefile_bakes_cpputest_paths(tmp_path):
    tg = _test_generator()
    tg.create_makefile(tmp_path, cpputest={
        "home": "/opt/cpp", "include_dir": "/opt/cpp/include",
        "lib_dir": "/opt/cpp/lib64", "has_ext": False,
    }, extra_cflags="-DUNIT_TEST")
    text = (tmp_path / "Makefile").read_text()
    assert "CPPUTEST_HOME ?= /opt/cpp\n" in text
    assert "CPPUTEST_LIB ?= /opt/cpp/lib64\n" in text
    assert "-lCppUTest --coverage" in text and "-lCppUTestExt" not in text
    assert "-MMD -MP" in text and "-include $(DEPS)" in text
    assert "CFLAGS += -DUNIT_TEST" in text
    assert "\r" not in text


def test_build_reports_missing_cpputest(tmp_path, monkeypatch):
    monkeypatch.setattr(toolchain, "find_cpputest", lambda home="": toolchain.CppUTestInfo(detail="CppUTest not found"))
    monkeypatch.setattr(verify, "write_makefile", lambda d: toolchain.CppUTestInfo(detail="CppUTest not found"))
    called = []
    monkeypatch.setattr(toolchain, "run_make", lambda *a, **k: called.append(1))
    result = verify.build_and_run(tmp_path)
    assert result["status"] == "build_failed" and result["cpputest_missing"] is True
    assert "Settings" in result["build_error"] and not called
