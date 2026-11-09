"""Per-statement requirement links and C-export comment hygiene."""

from mudtool.ai.mud_activity_context import _ActivityGraphBuilder
from mudtool.generator.c_skeleton_exporter import (
    _call_args,
    _desc_comment,
    _drop_unreachable_returns,
    _safe_comment,
)


def _builder(own, all_ids):
    return _ActivityGraphBuilder(swc_name="SWC_X", runnable_name="RE_X", req_ids=own,
                                 helper_names=set(), helper_call_counts={}, all_ids=all_ids)


def test_step_gets_only_the_ids_it_names():
    module = [f"REQ-AEB-{i:03d}" for i in range(1, 121)] + ["REQ-AEB-402", "REQ-AEB-404", "REQ-AEB-1024"]
    b = _builder(["REQ-AEB-402"], module)
    # whole-ID match: REQ-AEB-102 must not match inside REQ-AEB-1024
    assert b.trace_for("Compute target pressure per REQ-AEB-404 and REQ-AEB-1024") == ["REQ-AEB-404", "REQ-AEB-1024"]
    assert b.trace_for("Write outputs") == ["REQ-AEB-402"]          # runnable's own, never all 120
    assert _builder([], module).trace_for("Write outputs") == []


def test_call_args_are_kept_from_the_design():
    assert _call_args("ApplyRamp(l_f32Target, l_f32Feedback, K_up, K_down)", "ApplyRamp") == \
        "l_f32Target, l_f32Feedback, K_up, K_down"
    assert _call_args("ApplyRamp()", "ApplyRamp") == ""
    assert _call_args("Call ApplyRamp(void)", "ApplyRamp") == ""


def test_comment_hygiene():
    assert "/*" not in _safe_comment("a /* b */ c")[1:]  # no comment opener inside
    assert _desc_comment("Guard", "Guard") == ""            # no echo of the statement
    assert _desc_comment("check limits", "Guard") == "  /* check limits */"


def test_duplicate_return_removed():
    body = ["    if (x)", "    {", "        return;  /* return */", "        return; /* [REQ-1] */", "    }", "    return;"]
    out = _drop_unreachable_returns(body)
    assert out.count("        return;  /* return */") == 1 and "        return; /* [REQ-1] */" not in out
    assert out[-1] == "    return;"


def test_call_args_with_nested_brackets_and_short_label():
    text = "ApplyRamp(...) l_f32Cmd = ApplyRamp(l_f32Target, Rte_Prm(RP_CalPrm_RampApply), K)"
    assert _call_args(text, "ApplyRamp") == "l_f32Target, Rte_Prm(RP_CalPrm_RampApply), K"


def test_long_statement_kept_in_full_for_c():
    from mudtool.ai.mud_activity_context import _code_statement
    stmt = "l_f32Target = irvBrakeDemand * Rte_Prm(RP_CalPrm_K_veh_mass) * Rte_Prm(RP_CalPrm_K_brake_gain);"
    assert _code_statement(stmt) == stmt.rstrip(";")
    assert _code_statement("Compute") is None and _code_statement("Write outputs") is None
    assert _desc_comment("l_f32Target = irvBrakeDemand * Rte_Prm(RP_CalPrm_K_ve...", stmt) == ""
