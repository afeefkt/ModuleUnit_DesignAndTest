# BMS change log

- Original requirements: 30
- Hardened requirements: 62
- Atomic split parts: 20 (IDs REQ-BMS-1001..REQ-BMS-1020)
- Gap requirements: 12
- Existing requirements changed: 30

## Atomic split parts

| ID | Split from | Title | Type | ASIL |
|---|---|---|---|---|
| REQ-BMS-1001 | REQ-BMS-022 | SOC Clamping — Part 2 | safety | ASIL-D |
| REQ-BMS-1002 | REQ-BMS-023 | Current Integration Backup — Part 2 | functional | ASIL-B |
| REQ-BMS-1003 | REQ-BMS-031 | Balancing Cell Selection Limit — Part 2 | functional | ASIL-B |
| REQ-BMS-1004 | REQ-BMS-032 | Balance Relay Control — Part 2 | functional | ASIL-B |
| REQ-BMS-1005 | REQ-BMS-040 | Temperature Gradient Calculation — Part 2 | functional | ASIL-C |
| REQ-BMS-1006 | REQ-BMS-041 | Cooling PWM Control — Part 2 | functional | ASIL-C |
| REQ-BMS-1007 | REQ-BMS-050 | Overcurrent Detection — Part 2 | safety | ASIL-D |
| REQ-BMS-1008 | REQ-BMS-051 | Overvoltage / Undervoltage Detection — Part 2 | safety | ASIL-D |
| REQ-BMS-1009 | REQ-BMS-052 | Overtemperature Detection — Part 2 | safety | ASIL-D |
| REQ-BMS-1010 | REQ-BMS-052 | Overtemperature Detection — Part 3 | safety | ASIL-D |
| REQ-BMS-1011 | REQ-BMS-061 | Contactor State Verification — Part 2 | safety | ASIL-D |
| REQ-BMS-1012 | REQ-BMS-061 | Contactor State Verification — Part 3 | safety | ASIL-D |
| REQ-BMS-1013 | REQ-BMS-081 | DTC Healing — Part 2 | functional | ASIL-B |
| REQ-BMS-1014 | REQ-BMS-090 | E2E Protection — Part 2 | safety | ASIL-D |
| REQ-BMS-1015 | REQ-BMS-091 | Watchdog Supervision — Part 2 | safety | ASIL-D |
| REQ-BMS-1016 | REQ-BMS-091 | Watchdog Supervision — Part 3 | safety | ASIL-D |
| REQ-BMS-1017 | REQ-BMS-000 | BMS System Requirements Baseline — Part 2 | functional | ASIL-D |
| REQ-BMS-1018 | REQ-BMS-805 | SOC and SOH Plausibility — Part 2 | safety | ASIL-D |
| REQ-BMS-1019 | REQ-BMS-809 | Software and Calibration Update Integrity — Part 2 | constraint | ASIL-D |
| REQ-BMS-1020 | REQ-BMS-811 | Fault Injection and Observability — Part 2 | constraint | ASIL-D |

## Gap requirements

| ID | Title | Type | ASIL | Status |
|---|---|---|---|---|
| REQ-BMS-000 | BMS System Requirements Baseline | functional | ASIL-D | review |
| REQ-BMS-801 | Cell Voltage Sensor Loss Safe State | safety | ASIL-D | review |
| REQ-BMS-802 | Contactor Weld Detection | safety | ASIL-D | review |
| REQ-BMS-803 | Insulation Fault Reaction | safety | ASIL-D | review |
| REQ-BMS-804 | Thermal Propagation Warning | safety | ASIL-D | review |
| REQ-BMS-805 | SOC and SOH Plausibility | safety | ASIL-D | review |
| REQ-BMS-806 | Cell Balancing Fault Handling | safety | ASIL-B | review |
| REQ-BMS-807 | Diagnostic Freeze Frame and Persistence | functional | ASIL-D | review |
| REQ-BMS-808 | Calibration Verification | safety | ASIL-D | review |
| REQ-BMS-809 | Software and Calibration Update Integrity | constraint | ASIL-D | review |
| REQ-BMS-810 | Battery Variant Configuration | constraint | ASIL-D | review |
| REQ-BMS-811 | Fault Injection and Observability | constraint | ASIL-D | review |

## Existing requirements changed

| ID | Changed fields |
|---|---|
| REQ-BMS-001 | rationale, acceptance_criteria, open_issues |
| REQ-BMS-002 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-003 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-004 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-005 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-006 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-007 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-010 | rationale, acceptance_criteria, open_issues |
| REQ-BMS-011 | rationale, acceptance_criteria, open_issues |
| REQ-BMS-020 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-021 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-022 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-023 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-030 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-031 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-032 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-040 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-041 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-042 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-050 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-051 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-052 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-053 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-060 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-061 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-070 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-080 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-081 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-090 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-BMS-091 | statement, rationale, verification_method, acceptance_criteria, open_issues |
