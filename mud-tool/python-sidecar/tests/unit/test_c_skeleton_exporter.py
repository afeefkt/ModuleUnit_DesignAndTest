"""Unit tests for the C-skeleton exporter (join-node walk + guards + helpers)."""

from __future__ import annotations

from mudtool.generator.c_skeleton_exporter import CSkeletonExporter
from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityEdge,
    ActivityNode,
    ActivityNodeType,
    GenerationResult,
)


def _node(id_: str, name: str, ntype: ActivityNodeType, *, trace=None) -> ActivityNode:
    return ActivityNode(id=id_, name=name, node_type=ntype, trace_reqs=trace or [])


def _edge(src: str, dst: str, guard: str | None = None) -> ActivityEdge:
    return ActivityEdge(source=src, target=dst, guard=guard)


def _decision_if_else_diagram() -> ActivityDiagram:
    """initial → A → decision →[yes] X / [no] Y → merge → Z → final."""
    nodes = [
        _node("n0", "Start", ActivityNodeType.INITIAL),
        _node("n1", "l_u8X = 1", ActivityNodeType.ACTION, trace=["REQ_1"]),
        _node("n2", "l_u8X > 5", ActivityNodeType.DECISION),
        _node("n3", "l_u8X = 2", ActivityNodeType.ACTION),
        _node("n4", "l_u8X = 3", ActivityNodeType.ACTION),
        _node("n5", "merge", ActivityNodeType.MERGE),
        _node("n6", "l_u8Y = l_u8X", ActivityNodeType.ACTION, trace=["REQ_2"]),
        _node("n7", "End", ActivityNodeType.FINAL),
    ]
    edges = [
        _edge("n0", "n1"),
        _edge("n1", "n2"),
        _edge("n2", "n3", "yes"),
        _edge("n2", "n4", "no"),
        _edge("n3", "n5"),
        _edge("n4", "n5"),
        _edge("n5", "n6"),
        _edge("n6", "n7"),
    ]
    return ActivityDiagram(
        name="RE_Foo Code Flow", owner_swc="SWC_Bms", owner_runnable="RE_Foo",
        nodes=nodes, edges=edges,
    )


def test_code_after_if_else_is_emitted_once_outside_branches():
    code = CSkeletonExporter().export_diagram(_decision_if_else_diagram())

    # Both branch statements must appear, and the statement after the merge
    # (REQ_2) must come AFTER the closing of the else block.
    assert "l_u8X = 2;" in code
    assert "l_u8X = 3;" in code
    assert "l_u8Y = l_u8X;" in code

    if_idx = code.index("if (")
    else_idx = code.index("else")
    post_merge_idx = code.index("/* [REQ_2] */")

    # The reconverged code must appear after the else, not inside the if.
    assert post_merge_idx > else_idx
    # And it is emitted exactly once.
    assert code.count("l_u8Y = l_u8X;") == 1
    assert code.count("/* [REQ_2] */") == 1


def test_yes_no_guards_map_to_real_condition():
    code = CSkeletonExporter().export_diagram(_decision_if_else_diagram())
    # The decision's own label is the C condition, not the literal "yes".
    assert "if (l_u8X > 5)" in code
    assert "if (yes)" not in code


def test_real_guard_is_preserved():
    nodes = [
        _node("n0", "Start", ActivityNodeType.INITIAL),
        _node("n1", "IsActive", ActivityNodeType.DECISION),
        _node("n2", "l_u8A = 1", ActivityNodeType.ACTION),
        _node("n3", "l_u8A = 0", ActivityNodeType.ACTION),
        _node("n4", "m", ActivityNodeType.MERGE),
        _node("n5", "End", ActivityNodeType.FINAL),
    ]
    edges = [
        _edge("n0", "n1"),
        _edge("n1", "n2", "l_u8Mode == 1"),
        _edge("n1", "n3", "else"),
        _edge("n2", "n4"),
        _edge("n3", "n4"),
        _edge("n4", "n5"),
    ]
    d = ActivityDiagram(name="RE_Bar Code Flow", owner_runnable="RE_Bar", nodes=nodes, edges=edges)
    code = CSkeletonExporter().export_diagram(d)
    assert "if (l_u8Mode == 1)" in code


def test_sub_diagram_emitted_as_static_helper_without_repeated_includes():
    sub = ActivityDiagram(
        name="Helper Code Flow", function_name="Helper",
        nodes=[
            _node("s0", "Start", ActivityNodeType.INITIAL),
            _node("s1", "l_u8Z = 9", ActivityNodeType.ACTION),
            _node("s2", "End", ActivityNodeType.FINAL),
        ],
        edges=[_edge("s0", "s1"), _edge("s1", "s2")],
    )
    parent = ActivityDiagram(
        name="RE_Foo Code Flow", owner_swc="SWC_Bms", owner_runnable="RE_Foo",
        nodes=[
            _node("n0", "Start", ActivityNodeType.INITIAL),
            _node("n1", "Helper", ActivityNodeType.FUNCTION_CALL, trace=["REQ_9"]),
            _node("n2", "End", ActivityNodeType.FINAL),
        ],
        edges=[_edge("n0", "n1"), _edge("n1", "n2")],
        sub_diagrams=[sub],
    )
    code = CSkeletonExporter().export_diagram(parent)

    assert "static void Helper(void);" in code   # forward declaration
    assert "static void Helper(void)" in code    # helper definition
    assert "Helper();" in code                   # actual call
    # Includes appear only once (in the top-level block), not in the helper.
    assert code.count('#include "Rte_Type.h"') == 1


def test_export_result_only_top_level_diagrams():
    top = _decision_if_else_diagram()
    result = GenerationResult(diagrams=[top])
    out = CSkeletonExporter().export_result(result)
    assert "RE_Foo_Code_Flow" in out
    assert "if (l_u8X > 5)" in out["RE_Foo_Code_Flow"]
