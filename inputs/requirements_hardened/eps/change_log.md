# EPS change log

- Original requirements: 55
- Hardened requirements: 98
- Atomic split parts: 32 (IDs REQ-EPS-1001..REQ-EPS-1032)
- Gap requirements: 11
- Existing requirements changed: 55

## Atomic split parts

| ID | Split from | Title | Type | ASIL |
|---|---|---|---|---|
| REQ-EPS-1001 | REQ-EPS-001 | EPS SWC Architecture — Part 2 | functional | ASIL-D |
| REQ-EPS-1002 | REQ-EPS-001 | EPS SWC Architecture — Part 3 | functional | ASIL-D |
| REQ-EPS-1003 | REQ-EPS-001 | EPS SWC Architecture — Part 4 | functional | ASIL-D |
| REQ-EPS-1004 | REQ-EPS-001 | EPS SWC Architecture — Part 5 | functional | ASIL-D |
| REQ-EPS-1005 | REQ-EPS-001 | EPS SWC Architecture — Part 6 | functional | ASIL-D |
| REQ-EPS-1006 | REQ-EPS-032 | Transition to STANDBY — Part 2 | functional | ASIL-B |
| REQ-EPS-1007 | REQ-EPS-034 | Transition to SHUTDOWN — Part 2 | functional | ASIL-D |
| REQ-EPS-1008 | REQ-EPS-035 | STANDBY Mode Behavior — Part 2 | functional | ASIL-B |
| REQ-EPS-1009 | REQ-EPS-035 | STANDBY Mode Behavior — Part 3 | functional | ASIL-B |
| REQ-EPS-1010 | REQ-EPS-036 | FAIL_SAFE Limp Home Mode — Part 2 | safety | ASIL-D |
| REQ-EPS-1011 | REQ-EPS-041 | Redundant Sensor Plausibility Check — Part 2 | safety | ASIL-D |
| REQ-EPS-1012 | REQ-EPS-042 | Motor Current Hard Limit — Part 2 | safety | ASIL-D |
| REQ-EPS-1013 | REQ-EPS-043 | Thermal Protection — Part 2 | safety | ASIL-B |
| REQ-EPS-1014 | REQ-EPS-043 | Thermal Protection — Part 3 | safety | ASIL-B |
| REQ-EPS-1015 | REQ-EPS-044 | Supply Voltage Monitoring — Part 2 | safety | ASIL-D |
| REQ-EPS-1016 | REQ-EPS-044 | Supply Voltage Monitoring — Part 3 | safety | ASIL-D |
| REQ-EPS-1017 | REQ-EPS-045 | Watchdog Supervision — Part 2 | safety | ASIL-D |
| REQ-EPS-1018 | REQ-EPS-045 | Watchdog Supervision — Part 3 | safety | ASIL-D |
| REQ-EPS-1019 | REQ-EPS-046 | CAN Signal End-to-End Protection — Part 2 | safety | ASIL-D |
| REQ-EPS-1020 | REQ-EPS-047 | Startup Self-Test — Part 2 | safety | ASIL-D |
| REQ-EPS-1021 | REQ-EPS-048 | Stack Overflow Detection — Part 2 | safety | ASIL-D |
| REQ-EPS-1022 | REQ-EPS-049 | CPU Load Monitoring — Part 2 | constraint | QM |
| REQ-EPS-1023 | REQ-EPS-051 | DTC Overcurrent — Part 2 | functional | ASIL-B |
| REQ-EPS-1024 | REQ-EPS-052 | DTC Overheat — Part 2 | functional | ASIL-B |
| REQ-EPS-1025 | REQ-EPS-053 | DTC Undervoltage — Part 2 | functional | ASIL-D |
| REQ-EPS-1026 | REQ-EPS-060 | Vehicle Speed CAN Input — Part 2 | interface | ASIL-D |
| REQ-EPS-1027 | REQ-EPS-063 | Primary Torque Sensor Interface — Part 2 | interface | ASIL-D |
| REQ-EPS-1028 | REQ-EPS-000 | EPS System Requirements Baseline — Part 2 | functional | ASIL-D |
| REQ-EPS-1029 | REQ-EPS-805 | Safe State per Fault Class — Part 2 | safety | ASIL-D |
| REQ-EPS-1030 | REQ-EPS-806 | Thermal Derating to Disable Transition — Part 2 | safety | ASIL-D |
| REQ-EPS-1031 | REQ-EPS-809 | Software and Calibration Update Integrity — Part 2 | constraint | ASIL-D |
| REQ-EPS-1032 | REQ-EPS-810 | Fault Injection and Observability — Part 2 | constraint | ASIL-D |

## Gap requirements

| ID | Title | Type | ASIL | Status |
|---|---|---|---|---|
| REQ-EPS-000 | EPS System Requirements Baseline | functional | ASIL-D | review |
| REQ-EPS-801 | Torque Sensor Loss Safe State | safety | ASIL-D | review |
| REQ-EPS-802 | Motor Position Sensor Loss | safety | ASIL-D | review |
| REQ-EPS-803 | Vehicle Speed Signal Loss | safety | ASIL-D | review |
| REQ-EPS-804 | Watchdog Reset Recovery | safety | ASIL-D | review |
| REQ-EPS-805 | Safe State per Fault Class | safety | ASIL-D | review |
| REQ-EPS-806 | Thermal Derating to Disable Transition | safety | ASIL-D | review |
| REQ-EPS-807 | Calibration Verification | safety | ASIL-D | review |
| REQ-EPS-808 | Steering Variant Configuration | constraint | ASIL-D | review |
| REQ-EPS-809 | Software and Calibration Update Integrity | constraint | ASIL-D | review |
| REQ-EPS-810 | Fault Injection and Observability | constraint | ASIL-D | review |

## Existing requirements changed

| ID | Changed fields |
|---|---|
| REQ-EPS-001 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-002 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-003 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-004 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-005 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-006 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-007 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-008 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-010 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-011 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-012 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-013 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-014 | statement, rationale, verification_method, acceptance_criteria |
| REQ-EPS-015 | statement, rationale, verification_method, acceptance_criteria |
| REQ-EPS-016 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-017 | statement, rationale, verification_method, acceptance_criteria |
| REQ-EPS-018 | statement, rationale, verification_method, acceptance_criteria |
| REQ-EPS-019 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-020 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-021 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-022 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-023 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-024 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-030 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-031 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-032 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-033 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-034 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-035 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-036 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-037 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-040 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-041 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-042 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-043 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-044 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-045 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-046 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-047 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-048 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-049 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-050 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-051 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-052 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-053 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-054 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-055 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-056 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-EPS-060 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-061 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-062 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-063 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-064 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-065 | statement, rationale, acceptance_criteria, open_issues |
| REQ-EPS-066 | statement, rationale, acceptance_criteria, open_issues |
