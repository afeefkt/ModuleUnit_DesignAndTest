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


def test_struct_typed_port_is_a_skeleton_problem():
    sk = {"runnables": [{"name": "RE_X", "writes": ["PP_Out"]}],
          "ports": [{"name": "PP_Out", "direction": "provided", "data_type": "T_Out"},
                    {"name": "RP_In", "direction": "required", "data_type": "DT_In"}],
          "data_types": [{"name": "T_Out", "base_type": "struct"}, {"name": "DT_In", "base_type": "float32"}]}
    problems = [p for p in m._skeleton_problems(sk, "QM") if "scalar data element" in p]
    assert problems and "PP_Out" in problems[0] and "RP_In" not in problems[0]
