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


def test_stray_comment_fragments_are_a_spec_gap():
    from mudmut_core import spec_check, design
    assert spec_check.stray_comments("x = 1; /* ok */\nprose fragment */ if (a) {") == ["prose fragment */ if (a) {"]
    check = {"stray_comments": {"RE_Init": ["/* open"]}}
    assert spec_check.gap_count(check) == 1 and "RE_Init" in design.spec_check_issues(check)[0][1]


def test_rte_is_updated_stub_is_a_controllable_boolean():
    from mudmut_core import compilable
    stubs = compilable.generate_rte_stubs("SWC_X", {"Rte_IsUpdated"}, calls={"Rte_IsUpdated": 1})
    assert "uint32 Rte_IsUpdated_return = 1;" in stubs
    assert "return (Std_ReturnType)Rte_IsUpdated_return;" in stubs
    assert "Rte_IsUpdated_return = 1;" in stubs.split("Rte_Stubs_Reset(void)")[1]


def test_review_loop_never_reviews_an_empty_regeneration(monkeypatch):
    """r34: a regeneration came back empty, was reviewed as 'specification body is empty' and became the verdict."""
    import asyncio
    from types import SimpleNamespace
    from mudmut_core import design
    import mudtool.ai.mud_spec_generator as gen_mod

    spec = "# SWC_X\n\n## 7. Functional Description\n\n### RE_Init\n```c\nl_a = 1;\n```\n" + "x" * 400
    reviewed: list[str] = []

    async def fake_review(module, text, md, *, iteration=1):
        reviewed.append(md)
        return SimpleNamespace(approved=False, error_count=1, warning_count=0, issues=[])

    class FakeGen:
        def __init__(self, *_a, **_k):
            pass

        async def regenerate_spec(self, **_k):
            return ""

    monkeypatch.setattr(design, "review_spec", fake_review)
    monkeypatch.setattr(design, "_orchestrator", lambda: None)
    monkeypatch.setattr(gen_mod, "MudSpecGenerator", FakeGen)
    module = SimpleNamespace(swc_name="SWC_X", asil="QM", req_ids=[])
    md, review = asyncio.run(design.review_and_improve(module, "", spec, max_rounds=2))
    assert md == spec and reviewed == [spec] and review.error_count == 1


def test_wdgm_runnable_argument_becomes_entity_constant():
    from mudmut_core import compilable as c
    out = c._WDGM_RUNNABLE_ARG_RE.sub(lambda m: f"{m.group(1)}WDGM_SE_{m.group(2).upper()}{m.group(3)}",
                                      "WdgM_UpdateAliveCounter(RE_Init);")
    assert out == "WdgM_UpdateAliveCounter(WDGM_SE_RE_INIT);"


def test_multiline_comments_are_dropped_from_section7_steps():
    from mudtool.ai.mud_activity_context import build_mud_activity_context
    md = ("# SWC_X\n\n## 7. Functional Description\n\n### RE_A\n```c\n/* note that\n uses > comparison. */\n"
          "if (l_t > 5u) { l_x = 1; } /* keep */\n```\n")
    body = build_mud_activity_context(md, "SWC_X").runnables[0].functional_description
    assert "*/ if" not in body and "comparison" not in body and "/* keep */" in body


def test_status_overwrite_and_output_read_are_spec_gaps():
    from mudmut_core import spec_check, design
    assert spec_check.status_overwrites("l_x = Rte_IrvRead(IRV_A, &l_x);\nl_st = Rte_IrvRead(IRV_B, &l_y);") == ["l_x"]
    assert spec_check.output_reads("if (Rte_IRead(PP_S) == 3) {}\nl_a = Rte_IRead(RP_In);") == ["PP_S"]
    check = {"status_overwrites": {"RE_A": ["l_x"]}, "output_reads": {"RE_Init": ["PP_S"]}}
    assert spec_check.gap_count(check) == 2 and len(design.spec_check_issues(check)) == 2


def test_generation_failed_stub_is_an_empty_runnable():
    from mudmut_core import spec_check
    md = ("# SWC_X\n\n## 7. Functional Description\n\n### RE_A\n**1. Guard**\n```c\nl_a = 1;\n```\n\n"
          "### RE_B\n// Reads:  none\n1. // TODO: Section 7 generation failed for RE_B\n")
    sc = spec_check.check_spec(md, "SWC_X")
    assert "RE_B" in sc["empty"] and "RE_B" not in sc["usable"]


_SPEC2 = ("# SWC_X\n\n## 4. IRVs\n| IRV_A | x |\n\n## 7. Functional Description\n\n"
          "### RE_A\n// Reads:  none\n**1. Compute**\n```c\nl_a = 1;\nRte_IrvWrite(IRV_A, l_a);\n```\n\n"
          "### RE_B\n// Reads:  none\n**1. Compute**\n```c\nl_b = 2;\n```\n\n## 8. Notes\nend\n")


def test_runnable_subsection_and_issue_grouping():
    from types import SimpleNamespace
    from mudmut_core import design
    s, e = design.runnable_subsection(_SPEC2, "RE_A")
    assert _SPEC2[s:e].startswith("### RE_A") and "RE_B" not in _SPEC2[s:e]
    s, e = design.runnable_subsection(_SPEC2, "RE_B")
    assert _SPEC2[s:e].startswith("### RE_B") and "## 8" not in _SPEC2[s:e]
    review = SimpleNamespace(issues=[SimpleNamespace(severity="error", section="7 RE_B step 1", message="bad"),
                                     SimpleNamespace(severity="info", section="7 RE_A", message="style")])
    assert design.review_issues_by_runnable(review, ["RE_A", "RE_B"]) == {"RE_B": ["[error] bad"]}


def test_repair_runnables_replaces_only_the_named_subsection(monkeypatch):
    from types import SimpleNamespace
    from mudmut_core import design
    new_b = "### RE_B\n// Reads:  none\n**1. Compute**\n```c\nl_b = 3;\n```"
    monkeypatch.setattr(design, "_spec_model_chat", lambda prompt, **_k: new_b)
    review = SimpleNamespace(issues=[SimpleNamespace(severity="error", section="7 RE_B", message="l_b must be 3")])
    module = SimpleNamespace(swc_name="SWC_X", runnables=["RE_A", "RE_B"])
    out, fixed = design.repair_runnables_from_review(module, "", _SPEC2, review)
    assert fixed == ["RE_B"] and "l_b = 3;" in out and "l_a = 1;" in out and "## 8. Notes" in out
    monkeypatch.setattr(design, "_spec_model_chat", lambda prompt, **_k: "sorry, cannot")
    out, fixed = design.repair_runnables_from_review(module, "", _SPEC2, review)
    assert fixed == [] and out == _SPEC2


def test_undeclared_irv_is_a_spec_gap():
    from mudmut_core import spec_check
    spec = "## 4. IRVs\n| IRV_A | x |\n\n## 7. Functional Description\n"
    assert spec_check.undeclared_irvs(spec, "Rte_IrvWrite(IRV_A, 1);\nl_s = Rte_IrvRead(IRV_B, &l_b);") == ["IRV_B"]
    assert spec_check.undeclared_irvs("## 7. x\n", "Rte_IrvWrite(IRV_B, 1);") == []


def test_lost_state_local_and_multi_writer_are_spec_gaps():
    from types import SimpleNamespace
    from mudmut_core import spec_check
    assert spec_check.lost_state_locals("l_deb = 0;\nl_deb = l_deb + 5;\n") == ["l_deb"]
    assert spec_check.lost_state_locals("l_s = Rte_IrvRead(IRV_T, &l_t);\nl_t += 5;\nRte_IrvWrite(IRV_T, l_t);") == []
    assert spec_check.lost_state_locals("for (l_i = 0; l_i < 3; l_i++) {}") == []
    rs = [SimpleNamespace(name="RE_Init", functional_description="Rte_IrvWrite(IRV_A, 0);"),
          SimpleNamespace(name="RE_X", functional_description="Rte_IrvWrite(IRV_A, 1);"),
          SimpleNamespace(name="RE_Y", functional_description="Rte_IWrite(PP_O, 1);\nRte_IrvWrite(IRV_A, 2);")]
    assert spec_check.multi_writers(rs) == {"IRV_A": ["RE_X", "RE_Y"]}


def test_coverage_gap_naming_a_runnable_goes_to_its_repair():
    from types import SimpleNamespace
    from mudmut_core import design
    review = SimpleNamespace(issues=[], coverage_gaps=["REQ-1 (zeroing): RE_B lacks the 1 bar zeroing step"])
    assert design.review_issues_by_runnable(review, ["RE_A", "RE_B"]) == {
        "RE_B": ["[uncovered requirement] REQ-1 (zeroing): RE_B lacks the 1 bar zeroing step"]}
