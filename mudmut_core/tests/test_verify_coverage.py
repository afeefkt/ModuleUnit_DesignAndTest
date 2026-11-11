"""Helpers of the coverage-gap round in verify.py (no LLM, no build)."""
from pathlib import Path

from mudmut_core import verify

_INFO = """TN:
SF:/x/SWC_A.c
FNL:0,10,20
FNA:0,1,RE_A
DA:11,1
DA:12,0
DA:13,3
BRDA:12,0,0,-
BRDA:12,0,1,2
end_of_record
SF:/x/Rte_Stubs.c
FNL:0,1,5
FNA:0,1,Rte_Stubs_Reset
DA:2,0
end_of_record
"""


def test_coverage_gaps_reads_uncovered_lines_and_skips_stubs(tmp_path: Path):
    (tmp_path / "coverage.info").write_text(_INFO)
    gaps = verify.coverage_gaps(tmp_path)
    assert list(gaps) == ["RE_A"]
    g = gaps["RE_A"]
    assert g["lines"] == [12] and g["branch_lines"] == [12]
    assert round(g["pct"]) == 60          # 2 of 3 lines + 1 of 2 branches = 3 of 5


def test_remove_tests_drops_only_named_blocks():
    code = "TEST(G, A)\n{\n  CHECK(1);\n}\nTEST(G, B)\n{\n  if (x) { y(); }\n}\nTEST(G, C)\n{\n}\n"
    out = verify.remove_tests(code, {"B"})
    assert "TEST(G, A)" in out and "TEST(G, C)" in out and "TEST(G, B)" not in out and "y();" not in out


def test_undeclared_hint_lists_real_stub_variables(tmp_path: Path):
    (tmp_path / "Rte_X.h").write_text("extern float32 IRV_Real;\nextern uint8 Rte_Prm_Real;\n")
    hint = verify._undeclared_hint("t.cpp:7:5: error: ‘Rte_Read_IRV_Real’ was not declared", tmp_path)
    assert "Rte_Read_IRV_Real" in hint and "IRV_Real" in hint and "DELETE" in hint
    assert verify._undeclared_hint("some other error", tmp_path) == ""


def test_spec_check_flags_planned_runnables_folded_away():
    from mudmut_core import spec_check, design
    check = {"missing_planned": ["RE_RampPressure"], "never_set": {}, "undescribed_helpers": {}}
    assert spec_check.gap_count(check) == 1
    issues = design.spec_check_issues(check)
    assert issues and "RE_RampPressure" in issues[0][1]


def test_struct_locals_detected_in_section7():
    from mudmut_core import spec_check
    bad = "DT_Cmd l_cmd = {0.0f, IDLE};\nl_cmd.pressure = 0.0f;\nif (l_a == 1) { }\n"
    assert spec_check.struct_locals(bad) == ["DT_Cmd l_cmd", "l_cmd.pressure ="]
    assert spec_check.struct_locals("l_p = Rte_IRead(x);\nl_s = l_p + 1; // l_c.d = 1\n") == []
    assert spec_check.gap_count({"struct_locals": {"RE_X": ["a", "b"]}}) == 2
