"""Sub-SWC consolidation must not merge an explicit multi-SWC architecture."""

from mudtool.ai.module_planner import ModuleInfo, _consolidate_sub_swcs


def _m(name, reqs=()):
    return ModuleInfo(swc_name=name, short_name=name, description="", req_ids=list(reqs))


def test_underscore_feature_swcs_are_kept_apart():
    names = ["SWC_AEB_SensorFusion", "SWC_AEB_RiskAssessor", "SWC_AEB_Controller", "SWC_AEB_BrakeActuator",
             "SWC_AEB_SafetyMonitor", "SWC_AEB_HMI", "SWC_AEB_EgoMotion"]
    out = _consolidate_sub_swcs([_m(n, [f"REQ-AEB-{i}"]) for i, n in enumerate(names, 1)])
    assert sorted(m.swc_name for m in out) == sorted(names)
    assert "SWC_AE" not in {m.swc_name for m in out}


def test_pascal_case_over_split_still_merges():
    names = ["SWC_MtrMonOvercurrent", "SWC_MtrMonOvervoltage", "SWC_MtrMonUndervoltage", "SWC_Battery", "SWC_Fan"]
    out = {m.swc_name for m in _consolidate_sub_swcs([_m(n) for n in names])}
    assert "SWC_MtrMon" in out and "SWC_Battery" in out and "SWC_Fan" in out
    assert not any(n.startswith("SWC_MtrMonO") for n in out)
