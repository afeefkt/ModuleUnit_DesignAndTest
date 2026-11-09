"""Section 7 parsing fixes found on a real DeepSeek AEB run: multi-line statements, nested parens
in conditions, and requirement links through design symbols when steps name no IDs."""

from mudtool.ai.mud_activity_context import (
    _balanced_condition,
    _join_continuations,
    _parse_numbered_step_entries,
    build_mud_activity_context,
    ids_for_symbols,
    symbol_requirement_map,
    synthesize_activity_diagrams_from_context,
)
from mudtool.generator.c_skeleton_exporter import CSkeletonExporter

SPEC = """# MUD Spec: SWC_Brake

## 6. Error Handling & Safety
- `SWC_DEM_E_ABS_CONFLICT` — ABS active while braking (REQ-AEB-805, REQ-AEB-1034).
- Watchdog: `WdgM_UpdateAliveCounter(WDG_Brake)` every 5 ms (REQ-AEB-1028).

## 7. Functional Description

### RE_Command
1. Read inputs
```c
Rte_Read(RP_Demand, &l_f32Demand);
Rte_Read(RP_Abs, &l_boolAbs);
```

2. Ramp
```c
l_f32Ramped = RampPressure(irvRamped, l_f32Demand,
                           Rte_Prm(RP_CalPrm_RampApply),
                           Rte_Prm(RP_CalPrm_RampRelease));
```

3. Arbitrate
```c
if (l_f32Demand > Rte_Prm(RP_CalPrm_Max)) {
   l_f32Demand = Rte_Prm(RP_CalPrm_Max);
}
if (l_boolAbs == TRUE) {
   Dem_ReportErrorStatus(SWC_DEM_E_ABS_CONFLICT, DEM_EVENT_STATUS_PREPASSED);
}
WdgM_UpdateAliveCounter(WDG_Brake);
```
"""


def test_multi_line_call_is_joined():
    joined = _join_continuations([
        "l_x = F(a,",
        "        Rte_Prm(P1),",
        "        Rte_Prm(P2));",
        "l_y = 1;",
    ])
    assert joined[0].replace("  ", " ").startswith("l_x = F(a, Rte_Prm(P1), Rte_Prm(P2));")
    assert joined[1] == "l_y = 1;"


def test_condition_keeps_inner_closing_paren():
    assert _balanced_condition("l_f > Rte_Prm(X))") == "l_f > Rte_Prm(X)"
    assert _balanced_condition("(a & B) != 0U)") == "(a & B) != 0U"
    assert _balanced_condition("a > b") == "a > b"


def test_no_fragment_steps_from_a_multi_line_call():
    ctx = build_mud_activity_context(SPEC, "SWC_Brake")
    steps = [s.text for s in _parse_numbered_step_entries(ctx.runnables[0].functional_description)]
    assert not any(t.strip().startswith("Rte_Prm(RP_CalPrm_Ramp") for t in steps)
    assert any("RampPressure(irvRamped" in t and "RP_CalPrm_RampRelease" in t for t in steps)


def test_symbol_map_links_dem_event_and_watchdog():
    m = symbol_requirement_map(SPEC)
    assert m["SWC_DEM_E_ABS_CONFLICT"] == ["REQ-AEB-805", "REQ-AEB-1034"]
    assert "REQ-AEB-1028" in m["WdgM_UpdateAliveCounter"]
    assert ids_for_symbols(m, "Dem_ReportErrorStatus(SWC_DEM_E_ABS_CONFLICT, X)") == ["REQ-AEB-805", "REQ-AEB-1034"]
    # Section 7 itself is not a source of links
    assert "l_f32Demand" not in m


def test_flow_from_spec_traces_and_compiles_conditions():
    ctx = build_mud_activity_context(SPEC, "SWC_Brake")
    ids = ["REQ-AEB-805", "REQ-AEB-1034", "REQ-AEB-1028", "REQ-AEB-001", "REQ-AEB-002", "REQ-AEB-003"]
    diagrams = synthesize_activity_diagrams_from_context(ctx, ids)
    code = "\n".join(CSkeletonExporter().export_diagram(d) for d in diagrams)
    assert "if (l_f32Demand > Rte_Prm(RP_CalPrm_Max))" in code
    assert "RampPressure(irvRamped, l_f32Demand, Rte_Prm(RP_CalPrm_RampApply), Rte_Prm(RP_CalPrm_RampRelease));" in code
    assert "REQ-AEB-805" in code and "REQ-AEB-1028" in code
    assert "Arbitrate;" not in code and "/* Arbitrate */" in code
