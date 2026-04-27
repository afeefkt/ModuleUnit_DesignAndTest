from mudtool.generator.mermaid_exporter import MermaidExporter
from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityEdge,
    ActivityNode,
    ActivityNodeType,
    GenerationResult,
)


def test_export_result_inline_preview_simplifies_activity_and_filters_trivial_subdiagram():
    trivial_sub = ActivityDiagram(
        name="Helper Code Flow",
        function_name="Helper",
        nodes=[
            ActivityNode(id="N_00", name="Start", node_type=ActivityNodeType.INITIAL),
            ActivityNode(id="N_01", name="VeryLongHelperOperationNameWithManyArguments(alpha, beta, gamma)", node_type=ActivityNodeType.ACTION),
            ActivityNode(id="N_02", name="End", node_type=ActivityNodeType.FINAL),
        ],
        edges=[
            ActivityEdge(id="E_01", source="N_00", target="N_01"),
            ActivityEdge(id="E_02", source="N_01", target="N_02"),
        ],
    )
    activity = ActivityDiagram(
        name="RE_Control Code Flow",
        owner_swc="SWC_Test",
        owner_runnable="RE_Control",
        source_requirements=["REQ-1"],
        nodes=[
            ActivityNode(id="N_00", name="Start", node_type=ActivityNodeType.INITIAL),
            ActivityNode(id="N_01", name="torqueCommand = VeryLongComputationNameWithCalibration(speed, gain, friction, currentLimit)", node_type=ActivityNodeType.ACTION),
            ActivityNode(id="N_02", name="End", node_type=ActivityNodeType.FINAL),
        ],
        edges=[
            ActivityEdge(id="E_01", source="N_00", target="N_01"),
            ActivityEdge(id="E_02", source="N_01", target="N_02"),
        ],
        sub_diagrams=[trivial_sub],
    )
    result = GenerationResult(diagrams=[activity])

    full = MermaidExporter().export_result_inline(result)
    preview = MermaidExporter().export_result_inline(result, preview=True)

    assert any("__fn__Helper" in key for key in full)
    assert not any("__fn__Helper" in key for key in preview)

    main_key = next(iter(preview))
    preview_text = preview[main_key]
    assert "%% Requirements:" not in preview_text
    assert "VeryLongComputationNameWithCalibration" not in preview_text
