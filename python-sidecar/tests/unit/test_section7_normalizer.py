from mudtool.ai.mud_activity_context import build_mud_activity_context, synthesize_activity_diagrams_from_context
from mudtool.ai.section7_normalizer import normalize_section7_markdown
from mudtool.models.json_uml import ActivityNodeType


def test_normalize_section7_rewrites_inline_control_flow_and_calls():
    markdown = """
# MUD Spec: SWC_Stream

## 1. Overview
Keep this section untouched.

## 7. Functional Description
### RE_Stream
// Reads: RP_IgnitionStatus
1. Guard: mode check: if (RteIRead(RP_IgnitionStatus) == false) { RteIWrite(PP_EPSStatus, 0); return; }
2. Continue: DemReportErrorStatus(SWC_DEM_E_WARN, DEM_EVENT_STATUS_PASSED); RteWrite(PP_AssistLevel, assistLevel)
"""

    result = normalize_section7_markdown(markdown)

    assert result.succeeded is True
    assert result.changed is True
    assert "## 1. Overview\nKeep this section untouched." in result.normalized_markdown
    assert "1. Guard: mode check:" in result.normalized_markdown
    assert "if (Rte_IRead(RP_IgnitionStatus) == false) {" in result.normalized_markdown
    assert "Rte_IWrite(PP_EPSStatus, 0);" in result.normalized_markdown
    assert "Dem_ReportErrorStatus(SWC_DEM_E_WARN, DEM_EVENT_STATUS_PASSED);" in result.normalized_markdown
    assert "Rte_Write(PP_AssistLevel, assistLevel)" in result.normalized_markdown
    assert result.changed_runnable_count == 1
    assert result.runnable_reports[0].mixed_rewrites >= 1


def test_normalize_section7_preserves_ambiguous_prose_with_warning():
    markdown = """
# MUD Spec: SWC_Ambiguous

## 7. Functional Description
### RE_Ambiguous
1. Validation otherwise set fault: check the input and maybe Rte_Write(PP_Status, 0)
"""

    result = normalize_section7_markdown(markdown)

    assert result.succeeded is True
    assert "Validation otherwise set fault" in result.normalized_markdown
    assert result.runnable_reports[0].ambiguous_lines >= 1
    assert result.runnable_reports[0].warnings


def test_normalized_section7_improves_activity_context_branching():
    raw_markdown = """
# MUD Spec: SWC_ElectricPowerSteering

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_ControlTorque | Cyclic | 5 ms | ASIL-D | Main EPS control loop |

## 7. Functional Description
### RE_ControlTorque
1. Guard: mode check: if (RteIRead(RP_IgnitionStatus) == false) { RteIWrite(PP_MotorCurrentDemand, 0); return; }
2. Write output: if (motorTemperature > 120) { RteIWrite(PP_EPSStatus, 3); } else if (assistDemand > 50) { RteIWrite(PP_EPSStatus, 2); } else { RteIWrite(PP_EPSStatus, 1); }
"""

    normalized = normalize_section7_markdown(raw_markdown).normalized_markdown
    context = build_mud_activity_context(normalized, module_context="SWC_ElectricPowerSteering")
    diagram = synthesize_activity_diagrams_from_context(context, ["REQ-501"])[0]

    assert context.has_structured_flow_source is True
    assert sum(1 for node in diagram.nodes if node.node_type == ActivityNodeType.DECISION) >= 2
    assert sum(1 for node in diagram.nodes if node.node_type == ActivityNodeType.MERGE) >= 2
    assert any((node.rte_call or "") == "Rte_IWrite" for node in diagram.nodes)
