"""Flow-chart quality score: structure, requirement coverage, fidelity to Section 7, an AI judge, pass at 80."""

from __future__ import annotations

from mudtool.models.json_uml import ActivityDiagram, ActivityEdge, ActivityNode, ActivityNodeType, GenerationResult

from mudmut_core import flow_quality

T = ActivityNodeType

SPEC = """# MUD Spec: SWC_T
## 7. Functional Description
### RE_Cmd
// Reads: RP_In
1. Read
```c
Rte_Read(RP_In, &l_in);
l_out = l_in * 2.0F;
```
2. Guard
```c
if (l_out > 10.0F) {
    l_out = 10.0F;
}
Rte_Write(PP_Out, l_out);
```
"""


SPEC_CITED = SPEC + "\nTraceability: REQ-1, REQ-2, REQ-3, REQ-4\n"


def node(id_, name, ntype, *, code=None, trace=None, callee=None):
    return ActivityNode(id=id_, name=name, node_type=ntype, code=code, trace_reqs=trace or [], callee=callee)


def edge(a, b, guard=None):
    return ActivityEdge(source=a, target=b, guard=guard)


def good_diagram(name="RE_Cmd", reqs=("REQ-1", "REQ-2")):
    return ActivityDiagram(
        name=f"{name} Code Flow", owner_runnable=name, source_requirements=list(reqs),
        nodes=[node("n0", "Start", T.INITIAL),
               node("n1", "Rte_Read(RP_In, &l_in)", T.CALL, code="Rte_Read(RP_In, &l_in)", trace=["REQ-1"]),
               node("n2", "l_out = l_in * 2.0F", T.ACTION, code="l_out = l_in * 2.0F", trace=["REQ-1"]),
               node("n3", "l_out > 10.0F", T.DECISION),
               node("n4", "l_out = 10.0F", T.ACTION, code="l_out = 10.0F", trace=["REQ-2"]),
               node("n5", "merge", T.MERGE),
               node("n6", "Rte_Write(PP_Out, l_out)", T.CALL, code="Rte_Write(PP_Out, l_out)", trace=["REQ-2"]),
               node("n7", "End", T.FINAL)],
        edges=[edge("n0", "n1"), edge("n1", "n2"), edge("n2", "n3"), edge("n3", "n4", "yes"),
               edge("n3", "n5", "no"), edge("n4", "n5"), edge("n5", "n6"), edge("n6", "n7")],
    )


def result_of(*diagrams):
    return GenerationResult(diagrams=list(diagrams))


def test_a_complete_flow_scores_full_marks_without_a_judge():
    q = flow_quality.evaluate(result_of(good_diagram()), SPEC_CITED, ["REQ-1", "REQ-2"], render=None, judge=None)
    assert q["parts"]["structure"] == 100 and q["parts"]["requirements"] == 100 and q["parts"]["fidelity"] == 100
    assert q["score"] == 100 and q["passed"] is True
    assert q["judge"] is None and "no AI judge" in " ".join(q["notes"])


def test_structure_problems_lower_the_score_and_are_listed():
    d = good_diagram()
    d.edges = [e for e in d.edges if not (e.source == "n3" and e.target == "n5")]     # decision with one branch
    d.nodes.append(node("n9", "orphan = 1", T.ACTION, code="orphan = 1"))              # unreachable node
    d.nodes = [n for n in d.nodes if n.node_type != T.FINAL]                           # no final node
    d.edges = [e for e in d.edges if e.target != "n7"]
    q = flow_quality.evaluate(result_of(d), SPEC, ["REQ-1", "REQ-2"], render=None, judge=None)
    text = " ".join(q["problems"])
    assert "no final node" in text and "unreachable" in text and "decision" in text
    assert q["parts"]["structure"] < 60


def test_requirement_ids_the_flow_never_mentions_are_reported():
    d = good_diagram(reqs=("REQ-1",))
    for n in d.nodes:
        n.trace_reqs = [r for r in n.trace_reqs if r == "REQ-1"]
    q = flow_quality.evaluate(result_of(d), SPEC_CITED, ["REQ-1", "REQ-2", "REQ-3", "REQ-4"], render=None, judge=None)
    assert q["parts"]["requirements"] == 25 and q["missing_requirements"] == ["REQ-2", "REQ-3", "REQ-4"]
    assert q["passed"] is False                      # coverage 25 % pulls the score under 80


def test_spec_statements_missing_from_the_flow_lower_fidelity():
    d = good_diagram()
    d.nodes = [n for n in d.nodes if n.id != "n6"]                      # the Rte_Write step is gone
    d.edges = [e for e in d.edges if "n6" not in (e.source, e.target)] + [edge("n5", "n7")]
    q = flow_quality.evaluate(result_of(d), SPEC, ["REQ-1", "REQ-2"], render=None, judge=None)
    assert q["parts"]["fidelity"] < 100 and "Rte_Write(PP_Out, l_out)" in " ".join(q["missing_steps"])


def test_the_judge_is_combined_with_the_checks_and_its_findings_are_kept():
    judged = {"score": 40, "missing": ["REQ-2 clamp"], "wrong": [], "suggestions": ["show the clamp branch"]}
    q = flow_quality.evaluate(result_of(good_diagram()), SPEC, ["REQ-1", "REQ-2"], render=None,
                              judge=lambda *a, **k: judged)
    assert q["parts"]["judge"] == 40 and q["score"] == 70 and q["passed"] is False     # (100 + 40) / 2
    assert q["judge"]["missing"] == ["REQ-2 clamp"] and q["threshold"] == 80


def test_a_failing_judge_call_is_not_a_zero():
    def broken(*a, **k):
        raise RuntimeError("provider down")
    q = flow_quality.evaluate(result_of(good_diagram()), SPEC, ["REQ-1", "REQ-2"], render=None, judge=broken)
    assert q["judge"] is None and q["score"] == 100 and "judge failed" in " ".join(q["notes"])


def test_a_diagram_that_does_not_render_loses_points():
    q = flow_quality.evaluate(result_of(good_diagram()), SPEC_CITED, ["REQ-1", "REQ-2"],
                              render=lambda mmd, path: (False, "Parse error on line 3"), judge=None)
    assert q["render"]["ok"] is False and q["score"] == 75 and q["passed"] is False
    assert "Parse error" in " ".join(q["problems"])


def test_render_result_is_recorded_when_it_works(tmp_path):
    q = flow_quality.evaluate(result_of(good_diagram()), SPEC, ["REQ-1"], render=lambda mmd, path: (True, ""),
                              judge=None, png_path=tmp_path / "flow.png")
    assert q["render"] == {"ok": True, "error": "", "png": str(tmp_path / "flow.png")} and q["score"] == 100


def test_parse_judge_reads_json_inside_prose_and_clamps_the_score():
    text = 'Here is my verdict:\n```json\n{"score": 135, "missing": ["a"], "wrong": "b", "suggestions": []}\n```'
    j = flow_quality.parse_judge(text)
    assert j == {"score": 100, "missing": ["a"], "wrong": ["b"], "suggestions": []}
    assert flow_quality.parse_judge("no json here") is None
    assert flow_quality.parse_judge('{"score": "high"}') is None


def test_verdict_bands():
    assert [flow_quality.verdict(s) for s in (100, 80, 79, 60, 59, 0)] == ["✅", "✅", "⚠️", "⚠️", "❌", "❌"]


def test_feedback_for_a_retry_names_what_is_missing():
    q = {"missing_requirements": ["REQ-3"], "missing_steps": ["Rte_Write(PP_Out, l_out)"], "problems": ["RE_Cmd: no final node"],
         "judge": {"missing": ["clamp branch"], "wrong": ["inverted guard"], "suggestions": []}}
    text = flow_quality.feedback_text(q)
    for needle in ("REQ-3", "Rte_Write(PP_Out, l_out)", "no final node", "clamp branch", "inverted guard"):
        assert needle in text


def test_prefer_alternative_takes_the_flow_that_keeps_section7_steps():
    ai = {"passed": True, "score": 90, "missing_steps": ["a = Rte_Prm(X)"]}
    det = {"passed": True, "score": 85, "missing_steps": []}
    assert flow_quality.prefer_alternative(ai, det) is True
    assert flow_quality.prefer_alternative(det, ai) is False


def test_prefer_alternative_never_swaps_a_pass_for_a_fail():
    ai = {"passed": True, "score": 90, "missing_steps": ["x"]}
    det = {"passed": False, "score": 67, "missing_steps": []}
    assert flow_quality.prefer_alternative(ai, det) is False


def test_a_spec_that_cites_no_requirement_ids_skips_requirement_coverage():
    q = flow_quality.evaluate(result_of(good_diagram()), SPEC, ["REQ-7", "REQ-8"], render=None, judge=None)
    assert "requirements" not in q["parts"] and q["missing_requirements"] == []
    assert any("not measured" in n for n in q["notes"])
    assert q["score"] == 100
