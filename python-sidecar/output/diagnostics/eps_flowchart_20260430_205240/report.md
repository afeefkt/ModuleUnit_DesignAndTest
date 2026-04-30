# EPS Flowchart Diagnostic Report

- Timestamp: `2026-04-30T21:00:53`
- Input CSV: `D:\AI_Learnigns\moduleunitdesign\data\sample\eps_requirements.csv`
- Output directory: `D:\AI_Learnigns\moduleunitdesign\python-sidecar\output\diagnostics\eps_flowchart_20260430_205240`
- Imported requirements: `55`
- Selected SWC: `SWC_ElectricPowerSteering`
- Selected ASIL: `ASIL-D`
- Runnable count: `5`
- Linked req count: `55`

## Stage Summary

| Stage | OK | Status | Duration ms | Detail |
|---|---|---:|---:|---|
| health | yes | 200 | 100 | ok |
| import_requirements | yes | 200 | 14 | requirements=55 |
| plan_modules | yes | 200 | 42238 | modules=1 |
| generate_mud_spec | yes | 200 | 138731 | events=13 chars=9254 normalized=5 |
| review_mud_spec | yes | 200 | 73264 | approved=False issues=0 suggestions=2 |
| generate_activity | yes | 200 | 238646 | activity_diagrams=5 placeholder_like=False |
| export_mermaid_inline | yes | 200 | 4 | diagrams=5 |
| validate_generated_activity | yes | 200 | 5 | passed=False issues=8 |

## Section 7 Normalization

- Succeeded: `True`
- Runnable blocks: `5`
- Adjusted blocks: `5`
- Warning count: `12`

- `RE_ControlTorque`: changed=True, controls=if,return, mixed_rewrites=0, ambiguous_lines=4, warnings=2
- `RE_MonitorSafety`: changed=True, controls=if,return, mixed_rewrites=0, ambiguous_lines=3, warnings=1
- `RE_Initialize`: changed=True, controls=none, mixed_rewrites=0, ambiguous_lines=1, warnings=1
- `RE_HandleModeChange`: changed=True, controls=if,return, mixed_rewrites=0, ambiguous_lines=2, warnings=1
- `RE_DiagnosticUpdate`: changed=True, controls=if,return, mixed_rewrites=0, ambiguous_lines=1, warnings=1

## Activity Diagram Summary

- `RE_ControlTorque Code Flow`: nodes=17, edges=20, decision=True, merge=False (0), function_call=True, guarded_edges=6, early_returns=0, unreachable=0
- `RE_MonitorSafety Code Flow`: nodes=18, edges=21, decision=True, merge=False (0), function_call=True, guarded_edges=8, early_returns=0, unreachable=4
- `RE_Initialize Code Flow`: nodes=4, edges=3, decision=False, merge=False (0), function_call=True, guarded_edges=0, early_returns=0, unreachable=0
- `RE_HandleModeChange Code Flow`: nodes=6, edges=6, decision=True, merge=False (0), function_call=True, guarded_edges=2, early_returns=0, unreachable=0
- `RE_DiagnosticUpdate Code Flow`: nodes=6, edges=6, decision=True, merge=False (0), function_call=False, guarded_edges=2, early_returns=0, unreachable=0

## Canonical CFG Summary

No canonical deterministic activity diagrams were reconstructed.

## Mermaid Preview Keys

- `activity_RE_ControlTorque Code Flow` -> `flowchart TD`
- `activity_RE_MonitorSafety Code Flow` -> `flowchart TD`
- `activity_RE_Initialize Code Flow` -> `flowchart TD`
- `activity_RE_HandleModeChange Code Flow` -> `flowchart TD`
- `activity_RE_DiagnosticUpdate Code Flow` -> `flowchart TD`

## Artifacts

- `health`: `health.json`
- `import_requirements`: `import_response.json`
- `plan_modules`: `module_plan.json`
- `generate_mud_spec`: `section7_normalization.json`
- `review_mud_spec`: `mud_spec_review.json`
- `generate_activity`: `generate_activity_response.json`
- `export_mermaid_inline`: `mermaid_inline.json`
- `validate_generated_activity`: `validation_report.json`
