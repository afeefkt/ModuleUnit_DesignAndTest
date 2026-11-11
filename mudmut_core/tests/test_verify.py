from pathlib import Path

from mudmut_core import verify


def test_parse_junit_counts(tmp_path):
    xml = tmp_path / "test-results.xml"
    xml.write_text(
        '<?xml version="1.0"?><testsuites>'
        '<testsuite name="x" tests="4" failures="1" errors="0">'
        '<testcase name="a"/><testcase name="b"><failure/></testcase>'
        '<testcase name="c"/><testcase name="d"/>'
        "</testsuite></testsuites>"
    )
    counts = verify.parse_junit(xml)
    assert counts == {"tests": 4, "failures": 1, "errors": 0, "passed": 3}


def test_parse_junit_missing_file(tmp_path):
    counts = verify.parse_junit(tmp_path / "nope.xml")
    assert counts == {"tests": 0, "failures": 0, "errors": 0, "passed": 0}


def test_write_smoke_test_calls_every_runnable(tmp_path):
    (tmp_path / "Rte_SWC_X.h").write_text("void Rte_Ignored(void);\n", encoding="utf-8")
    (tmp_path / "SWC_X.h").write_text(
        "#ifndef SWC_X_H\nvoid RE_Init(void);\nvoid RE_Step(void);\nextern uint8 l_u8X;\n#endif\n",
        encoding="utf-8",
    )
    assert verify.write_smoke_test(tmp_path) is True
    smoke = (tmp_path / "Test_Smoke.cpp").read_text(encoding="utf-8")
    assert '#include "SWC_X.h"' in smoke
    assert "RE_Init();" in smoke and "RE_Step();" in smoke
    assert "Rte_Ignored" not in smoke


def test_write_smoke_test_without_header_returns_false(tmp_path):
    assert verify.write_smoke_test(tmp_path) is False


def _fake_build(test_dir_calls):
    """A build that fails while a test file still contains BAD, naming one error line per BAD."""
    def build(test_dir):
        test_dir_calls.append(1)
        errs = []
        for f in sorted(test_dir.glob("Test_*.cpp")):
            for i, line in enumerate(f.read_text().splitlines(), 1):
                if "BAD" in line:
                    errs.append(f"{f.name}:{i}:5: error: 'BAD' was not declared")
        if errs:
            return {"status": "build_failed", "build_error": "\n".join(errs), "build_output": ""}
        return {"status": "passed", "junit": {"tests": 1, "failures": 0}}
    return build


def test_fix_loop_keeps_asking_until_the_test_compiles(tmp_path, monkeypatch):
    """Compile errors go back to the model until the file compiles: three errors fixed one per answer
    needed three requests, and the old limit of two quarantined the file."""
    from mudmut_core import verify
    f = tmp_path / "Test_A.cpp"
    f.write_text("TEST_GROUP(A_Group) {};\nBAD one\nBAD two\nBAD three\n")
    builds, asked = [], []
    monkeypatch.setattr(verify, "build_and_run", _fake_build(builds))
    monkeypatch.setattr(verify, "define_invented_constants", lambda log, d: False)
    monkeypatch.setattr(verify, "write_smoke_test", lambda d: False)

    def fixer(prompt, **k):
        asked.append(prompt)
        text = f.read_text()
        return text.replace("BAD", "ok", 1)                     # one error fixed per answer

    monkeypatch.setattr(verify, "_fixer_generate", fixer)
    result = verify.fix_loop(tmp_path, max_attempts=verify.MAX_FIX_ATTEMPTS)
    assert result["status"] == "passed" and result["fix_attempts"] == 3 and len(asked) == 3
    assert result["quarantined_tests"] == [] and "BAD" not in f.read_text()


def test_fix_loop_stops_when_the_model_makes_no_progress(tmp_path, monkeypatch):
    f = tmp_path / "Test_A.cpp"
    f.write_text("TEST_GROUP(A_Group) {};\nBAD one\n")
    asked = []
    monkeypatch.setattr(verify, "build_and_run", _fake_build([]))
    monkeypatch.setattr(verify, "define_invented_constants", lambda log, d: False)
    monkeypatch.setattr(verify, "write_smoke_test", lambda d: False)
    monkeypatch.setattr(verify, "_fixer_generate", lambda prompt, **k: asked.append(prompt) or f.read_text())
    result = verify.fix_loop(tmp_path, max_attempts=verify.MAX_FIX_ATTEMPTS)
    assert len(asked) == 3          # the first answer, then two with the same error: not asked forever
    assert result["quarantined_tests"] == ["Test_A.cpp"]                  # the honest fallback, reported
    assert "still shows the same error" in asked[-1]                     # the later requests say what failed before


def test_fix_loop_records_link_errors(tmp_path, monkeypatch):
    f = tmp_path / "Test_A.cpp"
    f.write_text("TEST_GROUP(A_Group) {};\n")
    monkeypatch.setattr(verify, "build_and_run", lambda d: {
        "status": "build_failed",
        "build_error": "/usr/bin/ld: undefined reference to `AEB_ComputeTTC'",
        "build_output": ""})
    monkeypatch.setattr(verify, "define_invented_constants", lambda log, d: False)
    monkeypatch.setattr(verify, "write_smoke_test", lambda d: False)
    monkeypatch.setattr(verify, "_fixer_generate", lambda prompt, **k: "")
    result = verify.fix_loop(tmp_path, max_attempts=2)
    assert result["link_errors"] == ["AEB_ComputeTTC"]
    assert result["status"] == "build_failed"


def test_define_invented_constants_adds_placeholders(tmp_path):
    f = tmp_path / "Test_RE_A.cpp"
    f.write_text("TEST_GROUP(G){};\nTEST(G, t){ int x = MODULE_NOT_READY; }\n", encoding="utf-8")
    log = (
        "Test_RE_A.cpp:2:21: error: 'MODULE_NOT_READY' was not declared in this scope; "
        "did you mean 'MODULE_READY'?\n"
        "Test_RE_A.cpp:3:5: error: \u2018NVM_INVALID\u2019 was not declared in this scope\n"
        "Test_RE_A.cpp:4:5: error: 'lowercase_thing' was not declared in this scope\n"
    )
    assert verify.define_invented_constants(log, tmp_path) is True
    code = f.read_text(encoding="utf-8")
    assert "#define MODULE_NOT_READY (" in code and "#define NVM_INVALID (" in code
    assert "lowercase_thing" not in code.split("TEST_GROUP")[0]
    # idempotent
    assert verify.define_invented_constants(log, tmp_path) is False
