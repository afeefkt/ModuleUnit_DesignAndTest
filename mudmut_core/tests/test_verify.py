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
