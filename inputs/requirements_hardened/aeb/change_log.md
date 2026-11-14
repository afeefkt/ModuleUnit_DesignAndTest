# AEB change log

- Original requirements: 66
- Hardened requirements: 120
- Atomic split parts: 40 (IDs REQ-AEB-1001..REQ-AEB-1040)
- Gap requirements: 14
- Existing requirements changed: 66

## Atomic split parts

| ID | Split from | Title | Type | ASIL |
|---|---|---|---|---|
| REQ-AEB-1001 | REQ-AEB-002 | AEBS Operating Speed Range — Part 2 | functional | ASIL-D |
| REQ-AEB-1002 | REQ-AEB-002 | AEBS Operating Speed Range — Part 3 | functional | ASIL-D |
| REQ-AEB-1003 | REQ-AEB-004 | Collision Warning Requirement — Part 2 | functional | ASIL-D |
| REQ-AEB-1004 | REQ-AEB-005 | Driver Override — Part 2 | functional | ASIL-C |
| REQ-AEB-1005 | REQ-AEB-008 | Traceability and E2E Baseline — Part 2 | constraint | ASIL-B |
| REQ-AEB-1006 | REQ-AEB-102 | Fusion Inputs — Part 2 | interface | ASIL-D |
| REQ-AEB-1007 | REQ-AEB-102 | Fusion Inputs — Part 3 | interface | ASIL-D |
| REQ-AEB-1008 | REQ-AEB-103 | Fused Object Output — Part 2 | interface | ASIL-D |
| REQ-AEB-1009 | REQ-AEB-104 | Time Alignment — Part 2 | functional | ASIL-D |
| REQ-AEB-1010 | REQ-AEB-106 | Sensor Blindness Handling — Part 2 | functional | ASIL-B |
| REQ-AEB-1011 | REQ-AEB-107 | Object Plausibility — Part 2 | safety | ASIL-D |
| REQ-AEB-1012 | REQ-AEB-108 | Sensor Timeout Flag — Part 2 | functional | ASIL-D |
| REQ-AEB-1013 | REQ-AEB-110 | Fusion Determinism — Part 2 | constraint | ASIL-B |
| REQ-AEB-1014 | REQ-AEB-202 | TTC Computation — Part 2 | functional | ASIL-D |
| REQ-AEB-1015 | REQ-AEB-204 | FCW Warning Threshold — Part 2 | safety | ASIL-D |
| REQ-AEB-1016 | REQ-AEB-205 | Partial Braking Threshold — Part 2 | safety | ASIL-D |
| REQ-AEB-1017 | REQ-AEB-206 | Full Braking Threshold — Part 2 | safety | ASIL-D |
| REQ-AEB-1018 | REQ-AEB-209 | FCW Only Condition — Part 2 | functional | ASIL-B |
| REQ-AEB-1019 | REQ-AEB-302 | Brake Demand Arbitration — Part 2 | functional | ASIL-D |
| REQ-AEB-1020 | REQ-AEB-303 | Deceleration Demand Map — Part 2 | functional | ASIL-D |
| REQ-AEB-1021 | REQ-AEB-304 | Deceleration Rate Limiter — Part 2 | safety | ASIL-D |
| REQ-AEB-1022 | REQ-AEB-305 | Driver Override Detection — Part 2 | safety | ASIL-C |
| REQ-AEB-1023 | REQ-AEB-305 | Driver Override Detection — Part 3 | safety | ASIL-C |
| REQ-AEB-1024 | REQ-AEB-404 | Brake Feedback Check — Part 2 | safety | ASIL-D |
| REQ-AEB-1025 | REQ-AEB-407 | Actuator Saturation — Part 2 | functional | ASIL-C |
| REQ-AEB-1026 | REQ-AEB-502 | Sensor Plausibility — Part 2 | safety | ASIL-D |
| REQ-AEB-1027 | REQ-AEB-503 | E2E Verification — Part 2 | safety | ASIL-D |
| REQ-AEB-1028 | REQ-AEB-504 | Watchdog Trigger — Part 2 | safety | ASIL-D |
| REQ-AEB-1029 | REQ-AEB-508 | Startup Self-Test — Part 2 | safety | ASIL-D |
| REQ-AEB-1030 | REQ-AEB-603 | Speed Signal Validation — Part 2 | functional | ASIL-D |
| REQ-AEB-1031 | REQ-AEB-703 | Warning Update — Part 2 | functional | ASIL-B |
| REQ-AEB-1032 | REQ-AEB-802 | Degraded and Failsafe Recovery — Part 2 | safety | ASIL-D |
| REQ-AEB-1033 | REQ-AEB-804 | Brake Feedback Fault Handling — Part 2 | safety | ASIL-D |
| REQ-AEB-1034 | REQ-AEB-805 | ABS Interaction Limit — Part 2 | safety | ASIL-D |
| REQ-AEB-1035 | REQ-AEB-807 | Startup and Shutdown Safe State — Part 2 | safety | ASIL-D |
| REQ-AEB-1036 | REQ-AEB-808 | Fault Healing and Persistence — Part 2 | safety | ASIL-D |
| REQ-AEB-1037 | REQ-AEB-809 | Calibration Verification — Part 2 | safety | ASIL-D |
| REQ-AEB-1038 | REQ-AEB-811 | Vehicle Variant Configuration — Part 2 | constraint | ASIL-D |
| REQ-AEB-1039 | REQ-AEB-812 | Runtime Resource Budget — Part 2 | timing | ASIL-D |
| REQ-AEB-1040 | REQ-AEB-813 | Fault Injection and Observability — Part 2 | constraint | ASIL-D |

## Gap requirements

| ID | Title | Type | ASIL | Status |
|---|---|---|---|---|
| REQ-AEB-009 | AEB Feature Behaviour | functional | ASIL-D | review |
| REQ-AEB-801 | Sensor Source Loss Safe State | safety | ASIL-D | review |
| REQ-AEB-802 | Degraded and Failsafe Recovery | safety | ASIL-D | review |
| REQ-AEB-803 | E2E Fault Reaction | safety | ASIL-D | review |
| REQ-AEB-804 | Brake Feedback Fault Handling | safety | ASIL-D | review |
| REQ-AEB-805 | ABS Interaction Limit | safety | ASIL-D | review |
| REQ-AEB-806 | HMI Warning Priority and Clearing | functional | ASIL-D | review |
| REQ-AEB-807 | Startup and Shutdown Safe State | safety | ASIL-D | review |
| REQ-AEB-808 | Fault Healing and Persistence | safety | ASIL-D | review |
| REQ-AEB-809 | Calibration Verification | safety | ASIL-D | review |
| REQ-AEB-810 | Software and Calibration Update Integrity | constraint | ASIL-D | review |
| REQ-AEB-811 | Vehicle Variant Configuration | constraint | ASIL-D | review |
| REQ-AEB-812 | Runtime Resource Budget | timing | ASIL-D | review |
| REQ-AEB-813 | Fault Injection and Observability | constraint | ASIL-D | review |

## Existing requirements changed

| ID | Changed fields |
|---|---|
| REQ-AEB-001 | statement, rationale, acceptance_criteria, open_issues |
| REQ-AEB-002 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-003 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-004 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-005 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-006 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-007 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-008 | statement, rationale, acceptance_criteria, open_issues |
| REQ-AEB-101 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-102 | statement, rationale, acceptance_criteria, open_issues |
| REQ-AEB-103 | statement, rationale, acceptance_criteria, open_issues |
| REQ-AEB-104 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-105 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-106 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-107 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-108 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-109 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-110 | statement, rationale, acceptance_criteria, open_issues |
| REQ-AEB-201 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-202 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-203 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-204 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-205 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-206 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-207 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-208 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-209 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-301 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-302 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-303 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-304 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-305 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-306 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-307 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-308 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-309 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-310 | rationale, verification_method, acceptance_criteria, open_issues, priority |
| REQ-AEB-311 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-312 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-401 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-402 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-403 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-404 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-405 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-406 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-407 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-408 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-501 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-502 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-503 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-504 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-505 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-506 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-507 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-508 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-509 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-601 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-602 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-603 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-604 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-605 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-606 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-701 | rationale, acceptance_criteria, open_issues |
| REQ-AEB-702 | rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-703 | statement, rationale, verification_method, acceptance_criteria, open_issues |
| REQ-AEB-704 | rationale, acceptance_criteria, open_issues |
