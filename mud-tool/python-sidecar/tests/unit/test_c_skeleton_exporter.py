"""CSkeletonExporter: control-flow structure of the emitted C code."""

from __future__ import annotations

from mudtool.generator.c_skeleton_exporter import CSkeletonExporter
from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityEdge,
    ActivityNode,
    ActivityNodeType,
)


def _node(nid: str, name: str, kind: ActivityNodeType, **kw) -> ActivityNode:
    return ActivityNode(id=nid, name=name, node_type=kind, **kw)


def _diamond(guard_first: str = "no", guard_second: str = "yes") -> ActivityDiagram:
    """Start → Read → [Volt > Max?] → (yes: Fault | no: Normal) → Merge → Write → End"""
    return ActivityDiagram(
        name="RE_Check Code Flow",
        owner_swc="SWC_Test",
        owner_runnable="RE_Check",
        source_requirements=["REQ-T-001"],
        nodes=[
            _node("S", "Start", ActivityNodeType.INITIAL),
            _node("R", "Rte_Read_Volt(&l_u16Volt)", ActivityNodeType.CALL, trace_reqs=["REQ-T-001"]),
            _node("D", "l_u16Volt > MAX_VOLT?", ActivityNodeType.DECISION),
            _node("F", "Dem_SetEventStatus(DEM_OVERVOLT, FAILED)", ActivityNodeType.EXCEPTION),
            _node("N", "l_u16Out = l_u16Volt", ActivityNodeType.ACTION),
            _node("M", "merge", ActivityNodeType.MERGE),
            _node("W", "Rte_Write_Out(l_u16Out)", ActivityNodeType.CALL, trace_reqs=["REQ-T-002"]),
            _node("E", "End", ActivityNodeType.FINAL),
        ],
        edges=[
            ActivityEdge(source="S", target="R"),
            ActivityEdge(source="R", target="D"),
            # "no" edge listed first on purpose — exporter must still put "yes" in the if
            ActivityEdge(source="D", target="N", guard=guard_first),
            ActivityEdge(source="D", target="F", guard=guard_second),
            ActivityEdge(source="F", target="M"),
            ActivityEdge(source="N", target="M"),
            ActivityEdge(source="M", target="W"),
            ActivityEdge(source="W", target="E"),
        ],
    )


def _body_lines(code: str) -> list[str]:
    return [ln.strip() for ln in code.splitlines() if ln.strip()]


def test_code_after_merge_is_emitted_once_after_if_else():
    code = CSkeletonExporter().export_diagram(_diamond())
    lines = _body_lines(code)

    write_idx = lines.index("Rte_Write_Out(l_u16Out);")
    else_idx = lines.index("else")
    # the closing brace of the else block comes right before the post-merge code
    assert write_idx > else_idx
    assert code.count("Rte_Write_Out(l_u16Out);") == 1
    # post-merge code sits at function-body indentation, not inside a branch
    assert "    Rte_Write_Out(l_u16Out);" in code.splitlines()
    assert "        Rte_Write_Out(l_u16Out);" not in code.splitlines()
    # both branches are populated
    assert lines[lines.index("if (l_u16Volt > MAX_VOLT)") + 2].startswith("Dem_SetEventStatus")
    assert lines[else_idx + 2] == "l_u16Out = l_u16Volt;"


def test_yes_no_guards_become_condition_from_decision_name():
    code = CSkeletonExporter().export_diagram(_diamond())
    assert "if (l_u16Volt > MAX_VOLT)" in code
    assert "if (yes)" not in code and "if (no)" not in code


def test_expression_guard_used_verbatim():
    code = CSkeletonExporter().export_diagram(
        _diamond(guard_first="l_u16Volt <= MAX_VOLT", guard_second="else")
    )
    assert "if (l_u16Volt <= MAX_VOLT)" in code


def test_trace_comments_and_header_requirements_present():
    code = CSkeletonExporter().export_diagram(_diamond())
    assert "/* Requirements: REQ-T-001 */" in code
    assert "/* [REQ-T-002] */" in code


def test_sub_diagram_is_static_helper_without_repeated_includes():
    parent = _diamond()
    sub = ActivityDiagram(
        name="ClampOut Code Flow",
        function_name="ClampOut",
        owner_swc="SWC_Test",
        owner_runnable="RE_Check",
        nodes=[
            _node("s", "Start", ActivityNodeType.INITIAL),
            _node("a", "l_u16Out = MIN(l_u16Out, MAX_OUT)", ActivityNodeType.ACTION),
            _node("e", "End", ActivityNodeType.FINAL),
        ],
        edges=[ActivityEdge(source="s", target="a"), ActivityEdge(source="a", target="e")],
    )
    parent.sub_diagrams = [sub]
    code = CSkeletonExporter().export_diagram(parent)

    assert code.count('#include "Rte_Type.h"') == 1
    assert "static void ClampOut(void);" in code
    assert "static void ClampOut(void)\n{" in code
    # parent function is not redefined by the sub-diagram's owner_runnable
    assert code.count("void RE_Check(void)") == 1
    # variables are declared once at file scope
    assert code.count("static uint16 l_u16Out;") == 1
