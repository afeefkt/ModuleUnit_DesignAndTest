"""One producer per IRV / provided port (RE_Init may initialise); a runnable must not write another's outputs."""
from mudtool.ai import mud_pipeline_stages as m


def test_skeleton_with_two_producers_is_a_problem():
    sk = {"runnables": [{"name": "RE_Init", "irvs_produced": ["IRV_A"]},
                        {"name": "RE_X", "irvs_produced": ["IRV_A"], "writes": ["PP_Out"]},
                        {"name": "RE_Y", "writes": ["PP_Out"]}]}
    problems = [p for p in m._skeleton_problems(sk, "QM") if "ONE producer" in p]
    assert problems and "PP_Out: RE_X, RE_Y" in problems[0] and "IRV_A" not in problems[0]


def test_foreign_writes_ignores_own_outputs_comments_and_re_init():
    s7 = {"steps": [{"code": "Rte_IrvWrite(IRV_B, 1);\nRte_IWrite(PP_Out, 0.0f); // Rte_IrvWrite(IRV_C, 1)\n"
                             "Rte_IrvWrite(IRV_A, 2);"}]}
    assert m._foreign_writes(s7, {"name": "RE_X", "irvs_produced": ["IRV_A"]}, {"PP_Out"}) == ["IRV_B", "PP_Out"]
    assert m._foreign_writes(s7, {"name": "RE_Init"}, {"PP_Out"}) == []


def test_skeleton_missing_planned_runnable_is_a_problem():
    sk = {"runnables": [{"name": "RE_Init"}, {"name": "RE_CommandBrake"}]}
    problems = [p for p in m._skeleton_problems(sk, "QM", ["RE_Init", "RE_CommandBrake", "RE_RampPressure"])
                if "planned runnable" in p]
    assert problems and "RE_RampPressure" in problems[0]
    assert not [p for p in m._skeleton_problems(sk, "QM", ["RE_Init"]) if "planned runnable" in p]


def test_runnable_below_module_asil_is_a_problem():
    sk = {"runnables": [{"name": "RE_Init", "asil": "ASIL-B"}, {"name": "RE_X", "asil": "ASIL-D"}],
          "dem_events": [{"event_id": "SWC_DEM_E_X"}]}
    problems = [p for p in m._skeleton_problems(sk, "ASIL-D") if "every runnable must carry" in p]
    assert problems and "RE_Init" in problems[0] and "RE_X" not in problems[0]
    assert not [p for p in m._skeleton_problems(sk, "QM") if "every runnable must carry" in p]
