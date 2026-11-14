# AEB requirements — polished L2-oriented draft

> Status: **review draft**. Human approval required. Not certified.
> Source: `inputs/requirements/aeb/aeb_requirements.csv` (unchanged).
> Requirements: **120** (80 retained/derived + 40 atomic split parts).

## How to read this document

Each requirement is atomic where possible. 37 compound requirements were split into 40 atomic parts; the original ID keeps part 1 and parts 2+ use `REQ-AEB-1001..REQ-AEB-1040`. Acceptance criteria are drafts derived from the source text. Open issues are decisions for the human reviewer, not hidden assumptions.

## Summary by allocation

| Allocation | Requirements |
|---|---|
| SWC_AEB_BrakeActuator | 10 |
| SWC_AEB_Controller | 19 |
| SWC_AEB_HMI | 6 |
| SWC_AEB_RiskAssessor | 14 |
| SWC_AEB_SafetyMonitor | 27 |
| SWC_AEB_SensorFusion | 18 |
| SWC_AEB_VehicleState | 7 |
| System | 19 |

## SWC_AEB_BrakeActuator

### REQ-AEB-401 — Actuator Cycle

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** SWC_AEB_BrakeActuator shall execute RE_CommandBrake cyclically every 5 ms to convert the deceleration demand into a brake pressure command and apply it via the brake booster.

**Rationale:** Derived from REQ-AEB-001. Source notes: 5 ms actuation cycle; req_type=TIMING. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 5 ms trigger occurs.
- **Then:** SWC_AEB_BrakeActuator shall execute RE_CommandBrake cyclically every 5 ms to convert the deceleration demand into a brake pressure command and apply it via the brake booster. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator · test=TD-REQ-AEB-401

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-402 — Pressure Mapping

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_CommandBrake shall convert the deceleration demand to a target brake pressure using P_target = decel_demand * K_veh_mass / K_brake_gain, where K_veh_mass is the calibrated vehicle mass (kg) and K_brake_gain is the calibrated deceleration-per-bar gain (m/s2 per bar).

**Rationale:** Derived from REQ-AEB-001. Source notes: Decel-to-pressure map; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Pressure Mapping' occurs.
- **Then:** RE_CommandBrake shall convert the deceleration demand to a target brake pressure using P_target = decel_demand * K_veh_mass / K_brake_gain, where K_veh_mass is the calibrated vehicle mass (kg) and K_brake_gain is the calibrated deceleration-per-bar gain (m/s2 per bar).
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator · test=TD-REQ-AEB-402

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Confirm K_veh_mass and K_brake_gain ranges and validity conditions with the brake actuator owner.

---

### REQ-AEB-403 — Pressure Ramp

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_CommandBrake shall ramp the commanded brake pressure toward P_target at a maximum rate of 200 bar/s on application and 300 bar/s on release to avoid pressure spikes.

**Rationale:** Derived from REQ-AEB-001. Source notes: Apply 200 bar/s, release 300 bar/s; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Pressure Ramp' occurs.
- **Then:** RE_CommandBrake shall ramp the commanded brake pressure toward P_target at a maximum rate of 200 bar/s on application and 300 bar/s on release to avoid pressure spikes.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `200 bar` → 199.99, 200.0, 200.01
- `300 bar` → 299.99, 300.0, 300.01

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator · test=TD-REQ-AEB-403

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-404 — Brake Feedback Check

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_CommandBrake shall read back the achieved brake pressure via RP_BrakePressureFeedback and compare it to the commanded value.

**Rationale:** 15 bar / 50 ms feedback deviation is a calibration/diagnostic default; confirm with the brake actuator and safety monitor owners.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Brake Feedback Check' occurs.
- **Then:** RE_CommandBrake shall read back the achieved brake pressure via RP_BrakePressureFeedback and compare it to the commanded value.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator · test=TD-REQ-AEB-404

**Split into:** REQ-AEB-1024

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1024; the original ID retains part 1.

---

### REQ-AEB-405 — Pressure Output

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_BrakeActuator shall publish PP_BrakePressure (SR IF_SR_Pressure) every 5 ms containing the commanded brake pressure (bar, resolution 0.1) and a status flag indicating actuation health.

**Rationale:** Derived from REQ-AEB-001. Source notes: Pressure command output; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_BrakeActuator component is running and the referenced producer/consumer ports are connected.
- **When:** Pressure Output is exercised at its defined update rate.
- **Then:** SWC_AEB_BrakeActuator shall publish PP_BrakePressure (SR IF_SR_Pressure) every 5 ms containing the commanded brake pressure (bar, resolution 0.1) and a status flag indicating actuation health. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_BrakeActuator · test=TD-REQ-AEB-405

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-406 — Safe Default Output

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** On initialization and whenever no braking demand is active, RE_CommandBrake shall command 0 bar (no braking) and set the actuation status to IDLE.

**Rationale:** Derived from REQ-AEB-001. Source notes: Safe default 0 bar; req_type=SAFETY. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Safe Default Output' occurs.
- **Then:** On initialization and whenever no braking demand is active, RE_CommandBrake shall command 0 bar (no braking) and set the actuation status to IDLE.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0 bar` → -0.01, 0.0, 0.01

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator · test=TD-REQ-AEB-406

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-407 — Actuator Saturation

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_CommandBrake shall clamp the commanded brake pressure to the range [0, P_MAX], where P_MAX = 250 bar.

**Rationale:** Derived from REQ-AEB-001. Source notes: Clamp [0, 250] bar, deadband 1 bar; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Actuator Saturation' occurs.
- **Then:** RE_CommandBrake shall clamp the commanded brake pressure to the range [0, P_MAX], where P_MAX = 250 bar.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `250 bar` → 249.99, 250.0, 250.01

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator · test=TD-REQ-AEB-407

**Split into:** REQ-AEB-1025

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1025; the original ID retains part 1.

---

### REQ-AEB-408 — Brake Actuator Calibration

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_BrakeActuator shall expose K_veh_mass, K_brake_gain, ramp rates (200 bar/s apply, 300 bar/s release), deviation threshold 15 bar, and P_MAX 250 bar as calibration parameters stored in ROM.

**Rationale:** Derived from REQ-AEB-001. Source notes: Actuator calibration table; req_type=CONSTRAINT. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** SWC_AEB_BrakeActuator shall expose K_veh_mass, K_brake_gain, ramp rates (200 bar/s apply, 300 bar/s release), deviation threshold 15 bar, and P_MAX 250 bar as calibration parameters stored in ROM. The constraint is satisfied with no exceptions.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `200 bar` → 199.99, 200.0, 200.01
- `300 bar` → 299.99, 300.0, 300.01
- `15 bar` → 14.99, 15.0, 15.01
- `250 bar` → 249.99, 250.0, 250.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_BrakeActuator · test=TD-REQ-AEB-408

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1024 — Brake Feedback Check — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A deviation exceeding 15 bar for more than 50 ms shall be reported to SWC_AEB_SafetyMonitor as a brake actuation fault.

**Rationale:** 15 bar / 50 ms feedback deviation is a calibration/diagnostic default; confirm with the brake actuator and safety monitor owners. Split from REQ-AEB-404.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Brake Feedback Check — Part 2' occurs and persists for the specified debounce.
- **Then:** A deviation exceeding 15 bar for more than 50 ms shall be reported to SWC_AEB_SafetyMonitor as a brake actuation fault. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `15 bar` → 14.99, 15.0, 15.01
- `50 ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator · test=TD-REQ-AEB-1024

**Split from:** `REQ-AEB-404`

**Open issues:** Split from REQ-AEB-404; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-1025 — Actuator Saturation — Part 2

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Commands below 1 bar shall be treated as 0 bar to avoid residual pressure.

**Rationale:** Derived from REQ-AEB-001. Source notes: Clamp [0, 250] bar, deadband 1 bar; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-407.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Actuator Saturation — Part 2' occurs.
- **Then:** Commands below 1 bar shall be treated as 0 bar to avoid residual pressure.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1 bar` → 0.99, 1.0, 1.01
- `0 bar` → -0.01, 0.0, 0.01

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator · test=TD-REQ-AEB-1025

**Split from:** `REQ-AEB-407`

**Open issues:** Split from REQ-AEB-407; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## SWC_AEB_Controller

### REQ-AEB-301 — Controller Cycle

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** SWC_AEB_Controller shall execute RE_ArbitrateBrakeDemand cyclically every 10 ms to convert the risk assessment into a deceleration demand and a braking mode.

**Rationale:** Derived from REQ-AEB-001. Source notes: 10 ms arbitration cycle; req_type=TIMING. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 10 ms trigger occurs.
- **Then:** SWC_AEB_Controller shall execute RE_ArbitrateBrakeDemand cyclically every 10 ms to convert the risk assessment into a deceleration demand and a braking mode. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-301

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-302 — Brake Demand Arbitration

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ArbitrateBrakeDemand shall select the highest braking level among the driver demand, the AEB risk level, and any fail-safe request.

**Rationale:** Derived from REQ-AEB-001. Source notes: Max-select arbitration; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Brake Demand Arbitration' occurs.
- **Then:** RE_ArbitrateBrakeDemand shall select the highest braking level among the driver demand, the AEB risk level, and any fail-safe request.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-302

**Split into:** REQ-AEB-1019

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1019; the original ID retains part 1.

---

### REQ-AEB-303 — Deceleration Demand Map

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ArbitrateBrakeDemand shall map the risk level to a deceleration demand: NONE to 0.0 m/s2, WARNING to 0.0 m/s2 (warning only), PARTIAL to 4.0 m/s2, and FULL to 9.0 m/s2.

**Rationale:** Interim pilot decision: retain 9.0 m/s2 as the FULL performance target; ABS arbitration may reduce it. The UNECE R152 minimum is 5.0 m/s2. Homologation/vehicle-dynamics confirmation remains open.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Deceleration Demand Map' occurs.
- **Then:** RE_ArbitrateBrakeDemand shall map the risk level to a deceleration demand: NONE to 0.0 m/s2, WARNING to 0.0 m/s2 (warning only), PARTIAL to 4.0 m/s2, and FULL to 9.0 m/s2.
- **Tolerance:** ±0.01 m/s2 at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0.0 m/s2` → -0.01, 0.0, 0.01
- `0.0 m/s2` → -0.01, 0.0, 0.01
- `4.0 m/s2` → 3.99, 4.0, 4.01
- `9.0 m/s2` → 8.99, 9.0, 9.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-303

**Split into:** REQ-AEB-1020

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FULL demand 9.0 m/s2 exceeds the UNECE R152 minimum 5.0 m/s2. Rationale: performance target; confirm calibration and homologation intent.; Interim decision recorded: keep 9.0 m/s2 as the FULL performance target; ABS may reduce it; confirm homologation/vehicle dynamics.; Split into REQ-AEB-1020; the original ID retains part 1.

---

### REQ-AEB-304 — Deceleration Rate Limiter

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ArbitrateBrakeDemand shall limit the rate of change of the commanded deceleration to 15 m/s3 using a first-order rate limiter to avoid wheel lock and occupant discomfort.

**Rationale:** 15 m/s3 deceleration rate limit is a calibration default to avoid wheel lock and occupant discomfort; confirm with vehicle dynamics.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Deceleration Rate Limiter' occurs.
- **Then:** RE_ArbitrateBrakeDemand shall limit the rate of change of the commanded deceleration to 15 m/s3 using a first-order rate limiter to avoid wheel lock and occupant discomfort.
- **Tolerance:** ±0.01 m/s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `15 m/s` → 14.99, 15.0, 15.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-304

**Split into:** REQ-AEB-1021

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1021; the original ID retains part 1.

---

### REQ-AEB-305 — Driver Override Detection

**Type:** safety · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ArbitrateBrakeDemand shall cancel the AEB braking demand when the driver brake pressure exceeds the AEB-equivalent brake pressure by 10 bar.

**Rationale:** Driver override thresholds (10 bar, 80 percent) are calibration defaults; confirm with the brake system and HMI owners.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Driver Override Detection' occurs.
- **Then:** RE_ArbitrateBrakeDemand shall cancel the AEB braking demand when the driver brake pressure exceeds the AEB-equivalent brake pressure by 10 bar.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 bar` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-305

**Split into:** REQ-AEB-1022, REQ-AEB-1023

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1022, REQ-AEB-1023; the original ID retains part 1.

---

### REQ-AEB-306 — Brake Pre-Fill

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ArbitrateBrakeDemand shall issue a brake pre-fill command (pre-tension pads, target 5 bar) when the risk level is WARNING, so the service brake is prepared before full braking onset.

**Rationale:** Derived from REQ-AEB-001. Source notes: Pre-fill target 5 bar; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Brake Pre-Fill' occurs.
- **Then:** RE_ArbitrateBrakeDemand shall issue a brake pre-fill command (pre-tension pads, target 5 bar) when the risk level is WARNING, so the service brake is prepared before full braking onset.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 bar` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-306

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-307 — Brake Demand Output

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_Controller shall publish PP_BrakeDemand (SR IF_SR_BrakeDemand) every 10 ms containing deceleration demand in m/s2 (resolution 0.01), brake mode enum {NONE, PREFILL, PARTIAL, FULL, FAILSAFE}, and a demand counter for E2E.

**Rationale:** Derived from REQ-AEB-001. Source notes: Brake demand output + E2E counter; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_Controller component is running and the referenced producer/consumer ports are connected.
- **When:** Brake Demand Output is exercised at its defined update rate.
- **Then:** SWC_AEB_Controller shall publish PP_BrakeDemand (SR IF_SR_BrakeDemand) every 10 ms containing deceleration demand in m/s2 (resolution 0.01), brake mode enum {NONE, PREFILL, PARTIAL, FULL, FAILSAFE}, and a demand counter for E2E. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_Controller · test=TD-REQ-AEB-307

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-308 — Fail-Safe Demand

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When SWC_AEB_SafetyMonitor reports a plausibility fault, RE_ArbitrateBrakeDemand shall enter FAILSAFE mode and command a controlled braking demand of 6.0 m/s2 at vehicle speeds of 10 km/h or above, or 0.0 m/s2 below 10 km/h while FCW remains active.

**Rationale:** Interim pilot decision: above 10 km/h use controlled failsafe braking of 6.0 m/s2; below 10 km/h command 0.0 m/s2 and keep FCW active. The source did not define the low-speed case.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Fail-Safe Demand' occurs and persists for the specified debounce.
- **Then:** When SWC_AEB_SafetyMonitor reports a plausibility fault, RE_ArbitrateBrakeDemand shall enter FAILSAFE mode and command a controlled braking demand of 6.0 m/s2 at vehicle speeds of 10 km/h or above, or 0.0 m/s2 below 10 km/h while FCW remains active. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 m/s2 at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `6.0 m/s2` → 5.99, 6.0, 6.01
- `10 km/h` → 9.99, 10.0, 10.01
- `0.0 m/s2` → -0.01, 0.0, 0.01
- `10 km/h` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-308

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Behaviour below 10 km/h is undefined in the source. Proposed: command 0 m/s2 and keep FCW active; confirm with the safety/feature owner.; Interim decision recorded for the pilot; confirm the low-speed failsafe behaviour with the safety manager.

---

### REQ-AEB-309 — Brake Demand Counter

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ArbitrateBrakeDemand shall increment a 16-bit demand counter on every published PP_BrakeDemand, rolling over from 0xFFFF to 0x0000 for use by the E2E protect routine.

**Rationale:** The demand counter is part of the E2E protection of PP_BrakeDemand; rollover behaviour must be deterministic.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Brake Demand Counter' occurs.
- **Then:** RE_ArbitrateBrakeDemand shall increment a 16-bit demand counter on every published PP_BrakeDemand, rolling over from 0xFFFF to 0x0000 for use by the E2E protect routine.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-309

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-310 — Ego Path Filter

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ArbitrateBrakeDemand shall ignore a risk assessment whose critical object is outside the ego path (lateral offset magnitude above 1.5 m) when vehicle speed is above 40 km/h, to reduce false braking on curves.

**Rationale:** Interim pilot decision: promote to 'must' because unintended braking is a safety-relevant hazard. Final priority awaits HARA/FSR confirmation.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Ego Path Filter' occurs.
- **Then:** RE_ArbitrateBrakeDemand shall ignore a risk assessment whose critical object is outside the ego path (lateral offset magnitude above 1.5 m) when vehicle speed is above 40 km/h, to reduce false braking on curves.
- **Tolerance:** ±0.01 m at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1.5 m` → 1.49, 1.5, 1.51
- `40 km/h` → 39.99, 40.0, 40.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-310

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Source priority is 'should' for a false-braking mitigation. Confirm whether it is safety-relevant and whether it must be 'must'.; Interim decision recorded: promote to 'must' for the pilot; confirm with the safety analysis.

---

### REQ-AEB-311 — ABS Arbitration

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** RE_ArbitrateBrakeDemand shall accept RP_ABSStatus (boolean) from the brake system and reduce the deceleration demand to the ABS-allowed maximum when ABS reports active wheel slip, preventing conflict between AEB and ABS.

**Rationale:** Derived from REQ-AEB-001. Source notes: AEB/ABS coordination; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_Controller component is running and the referenced producer/consumer ports are connected.
- **When:** ABS Arbitration is exercised at its defined update rate.
- **Then:** RE_ArbitrateBrakeDemand shall accept RP_ABSStatus (boolean) from the brake system and reduce the deceleration demand to the ABS-allowed maximum when ABS reports active wheel slip, preventing conflict between AEB and ABS. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-311

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-312 — Controller Calibration

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_Controller shall expose the TTC-to-demand thresholds, deceleration rate limit 15 m/s3, override thresholds (10 bar, 80 percent), and pre-fill target 5 bar as calibration parameters stored in ROM.

**Rationale:** Derived from REQ-AEB-001. Source notes: Controller calibration table; req_type=CONSTRAINT. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** SWC_AEB_Controller shall expose the TTC-to-demand thresholds, deceleration rate limit 15 m/s3, override thresholds (10 bar, 80 percent), and pre-fill target 5 bar as calibration parameters stored in ROM. The constraint is satisfied with no exceptions.
- **Tolerance:** ±0.01 m/s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `15 m/s` → 14.99, 15.0, 15.01
- `10 bar` → 9.99, 10.0, 10.01
- `5 bar` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_Controller · test=TD-REQ-AEB-312

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-805 — ABS Interaction Limit

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When ABS reports active wheel slip, the AEB deceleration demand shall not exceed the ABS-allowed maximum.

**Rationale:** The source requires ABS arbitration but not the conflict-free limit or the verification condition.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'ABS Interaction Limit' occurs and persists for the specified debounce.
- **Then:** When ABS reports active wheel slip, the AEB deceleration demand shall not exceed the ABS-allowed maximum. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-805

**Split into:** REQ-AEB-1034

**Open issues:** The ABS-allowed maximum is supplied by the brake system; confirm its range, update rate and failure behaviour.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Split into REQ-AEB-1034; the original ID retains part 1.

---

### REQ-AEB-1019 — Brake Demand Arbitration — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** AEB shall win over driver braking during active emergency braking unless the driver override condition holds.

**Rationale:** Derived from REQ-AEB-001. Source notes: Max-select arbitration; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-302.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Brake Demand Arbitration — Part 2' occurs.
- **Then:** AEB shall win over driver braking during active emergency braking unless the driver override condition holds.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-1019

**Split from:** `REQ-AEB-302`

**Open issues:** Split from REQ-AEB-302; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1020 — Deceleration Demand Map — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The FULL deceleration demand shall satisfy the UNECE R152 minimum of 5.0 m/s2.

**Rationale:** Interim pilot decision: retain 9.0 m/s2 as the FULL performance target; ABS arbitration may reduce it. The UNECE R152 minimum is 5.0 m/s2. Homologation/vehicle-dynamics confirmation remains open. Split from REQ-AEB-303.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Deceleration Demand Map — Part 2' occurs.
- **Then:** The FULL deceleration demand shall satisfy the UNECE R152 minimum of 5.0 m/s2.
- **Tolerance:** ±0.01 m at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `152 m` → 151.99, 152.0, 152.01
- `5.0 m/s2` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-1020

**Split from:** `REQ-AEB-303`

**Open issues:** Split from REQ-AEB-303; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1021 — Deceleration Rate Limiter — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The rate-limiter state shall be preserved between cycles.

**Rationale:** 15 m/s3 deceleration rate limit is a calibration default to avoid wheel lock and occupant discomfort; confirm with vehicle dynamics. Split from REQ-AEB-304.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Deceleration Rate Limiter — Part 2' occurs.
- **Then:** The rate-limiter state shall be preserved between cycles.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-1021

**Split from:** `REQ-AEB-304`

**Open issues:** Split from REQ-AEB-304; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1022 — Driver Override Detection — Part 2

**Type:** safety · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ArbitrateBrakeDemand shall cancel the AEB braking demand when the accelerator pedal is pressed beyond 80 percent of full travel.

**Rationale:** Driver override thresholds (10 bar, 80 percent) are calibration defaults; confirm with the brake system and HMI owners. Split from REQ-AEB-305.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Driver Override Detection — Part 2' occurs.
- **Then:** RE_ArbitrateBrakeDemand shall cancel the AEB braking demand when the accelerator pedal is pressed beyond 80 percent of full travel.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-1022

**Split from:** `REQ-AEB-305`

**Open issues:** Split from REQ-AEB-305; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1023 — Driver Override Detection — Part 3

**Type:** safety · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The driver override shall clear the AEB demand within one 10 ms cycle.

**Rationale:** Driver override thresholds (10 bar, 80 percent) are calibration defaults; confirm with the brake system and HMI owners. Split from REQ-AEB-305.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Driver Override Detection — Part 3' occurs.
- **Then:** The driver override shall clear the AEB demand within one 10 ms cycle.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-1023

**Split from:** `REQ-AEB-305`

**Open issues:** Split from REQ-AEB-305; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1034 — ABS Interaction Limit — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The AEB feature shall not command a deceleration that conflicts with the ABS request.

**Rationale:** The source requires ABS arbitration but not the conflict-free limit or the verification condition. Split from REQ-AEB-805.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'ABS Interaction Limit — Part 2' occurs.
- **Then:** The AEB feature shall not command a deceleration that conflicts with the ABS request.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, SWC_AEB_Controller · test=TD-REQ-AEB-1034

**Split from:** `REQ-AEB-805`

**Open issues:** Split from REQ-AEB-805; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## SWC_AEB_HMI

### REQ-AEB-701 — Warning Output

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_HMI shall drive the forward collision warning to the instrument cluster via PP_HMIWarning (SR IF_SR_HMI) containing the warning level enum {NONE, VISUAL, VISUAL_ACOUSTIC, VISUAL_HAPTIC}.

**Rationale:** Derived from REQ-AEB-001. Source notes: HMI warning output; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_HMI component is running and the referenced producer/consumer ports are connected.
- **When:** Warning Output is exercised at its defined update rate.
- **Then:** SWC_AEB_HMI shall drive the forward collision warning to the instrument cluster via PP_HMIWarning (SR IF_SR_HMI) containing the warning level enum {NONE, VISUAL, VISUAL_ACOUSTIC, VISUAL_HAPTIC}. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_HMI · test=TD-REQ-AEB-701

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-702 — Multi-Modal Warning

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_UpdateWarning shall activate at least two warning modalities (visual plus acoustic, or visual plus haptic) whenever the FCW warning request is active, satisfying the UNECE R152 collision warning requirement.

**Rationale:** Derived from REQ-AEB-001. Source notes: R152 multi-modal warning; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Multi-Modal Warning' occurs.
- **Then:** RE_UpdateWarning shall activate at least two warning modalities (visual plus acoustic, or visual plus haptic) whenever the FCW warning request is active, satisfying the UNECE R152 collision warning requirement.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_UpdateWarning, SWC_AEB_HMI · test=TD-REQ-AEB-702

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-703 — Warning Update

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_UpdateWarning shall update the cluster warning state on a DataReceivedEvent of PP_RiskAssessment.

**Rationale:** Derived from REQ-AEB-001. Source notes: 500 ms clear; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Warning Update' occurs.
- **Then:** RE_UpdateWarning shall update the cluster warning state on a DataReceivedEvent of PP_RiskAssessment.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_UpdateWarning, SWC_AEB_HMI · test=TD-REQ-AEB-703

**Split into:** REQ-AEB-1031

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1031; the original ID retains part 1.

---

### REQ-AEB-704 — AEB Status to Cluster

**Type:** interface · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_HMI shall relay the AEB availability and fault status to the cluster for the tell-tale lamp, updated every 100 ms, using PP_AEBStatus.

**Rationale:** Derived from REQ-AEB-001. Source notes: Tell-tale lamp feed; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_HMI component is running and the referenced producer/consumer ports are connected.
- **When:** AEB Status to Cluster is exercised at its defined update rate.
- **Then:** SWC_AEB_HMI shall relay the AEB availability and fault status to the cluster for the tell-tale lamp, updated every 100 ms, using PP_AEBStatus. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100 ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_HMI · test=TD-REQ-AEB-704

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-806 — HMI Warning Priority and Clearing

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the FCW warning request is active, the AEB feature shall activate at least two warning modalities, clear the warning within 500 ms after the risk level returns to NONE, and ensure a higher-priority warning is not masked by a lower-priority one.

**Rationale:** Combines the warning-modality, clearing and priority expectations into one verifiable HMI requirement.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'HMI Warning Priority and Clearing' occurs.
- **Then:** When the FCW warning request is active, the AEB feature shall activate at least two warning modalities, clear the warning within 500 ms after the risk level returns to NONE, and ensure a higher-priority warning is not masked by a lower-priority one.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `500 ms` → 499.99, 500.0, 500.01

**Trace:** parent=REQ-AEB-001 · design=RE_UpdateWarning, SWC_AEB_HMI · test=TD-REQ-AEB-806

**Open issues:** Confirm the warning priority table and whether a haptic modality is available on all variants.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1031 — Warning Update — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_UpdateWarning shall clear the warning within 500 ms of the risk level returning to NONE.

**Rationale:** Derived from REQ-AEB-001. Source notes: 500 ms clear; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-703.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Warning Update — Part 2' occurs.
- **Then:** RE_UpdateWarning shall clear the warning within 500 ms of the risk level returning to NONE.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `500 ms` → 499.99, 500.0, 500.01

**Trace:** parent=REQ-AEB-001 · design=RE_UpdateWarning, SWC_AEB_HMI · test=TD-REQ-AEB-1031

**Split from:** `REQ-AEB-703`

**Open issues:** Split from REQ-AEB-703; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## SWC_AEB_RiskAssessor

### REQ-AEB-201 — Risk Runnable Cycle

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** SWC_AEB_RiskAssessor shall execute RE_AssessCollisionRisk cyclically every 20 ms to compute Time-To-Collision (TTC) and collision probability for the most critical fused object in the ego lane.

**Rationale:** Derived from REQ-AEB-001. Source notes: 20 ms risk cycle; req_type=TIMING. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 20 ms trigger occurs.
- **Then:** SWC_AEB_RiskAssessor shall execute RE_AssessCollisionRisk cyclically every 20 ms to compute Time-To-Collision (TTC) and collision probability for the most critical fused object in the ego lane. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `20 ms` → 19.99, 20.0, 20.01

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-201

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-202 — TTC Computation

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_AssessCollisionRisk shall compute TTC = distance / relative_speed for each fused object with positive relative speed (approaching), where distance is longitudinal range in meters and relative_speed is in m/s.

**Rationale:** TTC = distance / relative speed is the standard definition for an approaching object. TTC_MAX must be a calibrated value; the source does not state it.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'TTC Computation' occurs.
- **Then:** RE_AssessCollisionRisk shall compute TTC = distance / relative_speed for each fused object with positive relative speed (approaching), where distance is longitudinal range in meters and relative_speed is in m/s.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-202

**Split into:** REQ-AEB-1014

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1014; the original ID retains part 1.

---

### REQ-AEB-203 — Critical Object Selection

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_AssessCollisionRisk shall select the critical object as the fused object with the smallest valid TTC whose lateral offset places it within the ego path, using a path half-width of 1.0 m plus the object half-width.

**Rationale:** Ego-path half-width 1.0 m is a calibration default; confirm with the vehicle geometry and path-estimation design.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Critical Object Selection' occurs.
- **Then:** RE_AssessCollisionRisk shall select the critical object as the fused object with the smallest valid TTC whose lateral offset places it within the ego path, using a path half-width of 1.0 m plus the object half-width.
- **Tolerance:** ±0.01 m at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1.0 m` → 0.99, 1.0, 1.01

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-203

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-204 — FCW Warning Threshold

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_AssessCollisionRisk shall raise the FCW warning request when the critical object TTC falls to 2.6 s or below.

**Rationale:** FCW at TTC 2.6 s with release at 2.9 s is an engineering calibration default consistent with published AEB practice; R152 is performance-based and does not mandate these values.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'FCW Warning Threshold' occurs.
- **Then:** RE_AssessCollisionRisk shall raise the FCW warning request when the critical object TTC falls to 2.6 s or below.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `2.6 s` → 2.59, 2.6, 2.61

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-204

**Split into:** REQ-AEB-1015

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1015; the original ID retains part 1.

---

### REQ-AEB-205 — Partial Braking Threshold

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_AssessCollisionRisk shall request partial braking (40 percent) when the critical object TTC falls to 1.6 s or below.

**Rationale:** Partial braking at TTC 1.6 s is an engineering calibration default; the 40 percent level is a design choice, not an R152 normative value.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Partial Braking Threshold' occurs.
- **Then:** RE_AssessCollisionRisk shall request partial braking (40 percent) when the critical object TTC falls to 1.6 s or below.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1.6 s` → 1.59, 1.6, 1.61

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-205

**Split into:** REQ-AEB-1016

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1016; the original ID retains part 1.

---

### REQ-AEB-206 — Full Braking Threshold

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_AssessCollisionRisk shall request full braking (100 percent) when the critical object TTC falls to 0.6 s or below.

**Rationale:** Full braking at TTC 0.6 s is an engineering calibration default; confirm with the vehicle dynamics and homologation plan.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Full Braking Threshold' occurs.
- **Then:** RE_AssessCollisionRisk shall request full braking (100 percent) when the critical object TTC falls to 0.6 s or below.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0.6 s` → 0.59, 0.6, 0.61

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-206

**Split into:** REQ-AEB-1017

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1017; the original ID retains part 1.

---

### REQ-AEB-207 — Collision Probability

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_AssessCollisionRisk shall compute collision probability as a continuous value in [0,1] from the critical TTC using a piecewise-linear map: 0.0 at TTC >= 3.0 s, 0.5 at TTC = 1.6 s, and 1.0 at TTC <= 0.6 s, clipped to [0,1].

**Rationale:** Derived from REQ-AEB-001. Source notes: Piecewise-linear probability; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Collision Probability' occurs.
- **Then:** RE_AssessCollisionRisk shall compute collision probability as a continuous value in [0,1] from the critical TTC using a piecewise-linear map: 0.0 at TTC >= 3.0 s, 0.5 at TTC = 1.6 s, and 1.0 at TTC <= 0.6 s, clipped to [0,1].
- **Tolerance:** ±0.01 a at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0.0 a` → -0.01, 0.0, 0.01
- `3.0 s` → 2.99, 3.0, 3.01
- `0.5 a` → 0.49, 0.5, 0.51
- `1.6 s` → 1.59, 1.6, 1.61
- `1.0 a` → 0.99, 1.0, 1.01
- `0.6 s` → 0.59, 0.6, 0.61

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-207

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Confirm the probability map points (0.0 at 3.0 s, 0.5 at 1.6 s, 1.0 at 0.6 s) with the risk-assessment owner.

---

### REQ-AEB-208 — Risk Output

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_RiskAssessor shall publish PP_RiskAssessment (SR IF_SR_Risk) every 20 ms containing critical_TTC (0.01 s resolution), collision_probability (0.001 resolution), risk_level enum {NONE, WARNING, PARTIAL, FULL}, and critical_object_id.

**Rationale:** Derived from REQ-AEB-001. Source notes: Risk assessment output; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_RiskAssessor component is running and the referenced producer/consumer ports are connected.
- **When:** Risk Output is exercised at its defined update rate.
- **Then:** SWC_AEB_RiskAssessor shall publish PP_RiskAssessment (SR IF_SR_Risk) every 20 ms containing critical_TTC (0.01 s resolution), collision_probability (0.001 resolution), risk_level enum {NONE, WARNING, PARTIAL, FULL}, and critical_object_id. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `20 ms` → 19.99, 20.0, 20.01
- `0.01 s` → 0.0, 0.01, 0.02

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_RiskAssessor · test=TD-REQ-AEB-208

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-209 — FCW Only Condition

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_AssessCollisionRisk shall suppress the braking escalation (partial or full) while vehicle speed is below 10 km/h.

**Rationale:** Interim pilot decision: braking escalation is suppressed below 10 km/h, but pedestrian FCW remains active below 10 km/h. Confirm the warning/braking split and hysteresis.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'FCW Only Condition' occurs.
- **Then:** RE_AssessCollisionRisk shall suppress the braking escalation (partial or full) while vehicle speed is below 10 km/h.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 km/h` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-209

**Split into:** REQ-AEB-1018

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Conflict with REQ-AEB-002: automatic braking is deactivated below 10 km/h but pedestrian FCW remains active. Confirm the exception and the warning/braking split.; Interim decision recorded for the pilot; confirm the pedestrian FCW/braking split and hysteresis with the feature owner.; Split into REQ-AEB-1018; the original ID retains part 1.

---

### REQ-AEB-1014 — TTC Computation — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Objects with relative_speed <= 0 shall be assigned TTC = TTC_MAX (no collision).

**Rationale:** TTC = distance / relative speed is the standard definition for an approaching object. TTC_MAX must be a calibrated value; the source does not state it. Split from REQ-AEB-202.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'TTC Computation — Part 2' occurs.
- **Then:** Objects with relative_speed <= 0 shall be assigned TTC = TTC_MAX (no collision).
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0 s` → -0.01, 0.0, 0.01

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-1014

**Split from:** `REQ-AEB-202`

**Open issues:** Split from REQ-AEB-202; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1015 — FCW Warning Threshold — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The FCW warning request shall be latched until TTC rises above 2.9 s (hysteresis) to prevent warning flicker.

**Rationale:** FCW at TTC 2.6 s with release at 2.9 s is an engineering calibration default consistent with published AEB practice; R152 is performance-based and does not mandate these values. Split from REQ-AEB-204.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'FCW Warning Threshold — Part 2' occurs.
- **Then:** The FCW warning request shall be latched until TTC rises above 2.9 s (hysteresis) to prevent warning flicker.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `2.9 s` → 2.89, 2.9, 2.91

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-1015

**Split from:** `REQ-AEB-204`

**Open issues:** Split from REQ-AEB-204; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1016 — Partial Braking Threshold — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The partial braking request shall remain until TTC rises above 1.8 s.

**Rationale:** Partial braking at TTC 1.6 s is an engineering calibration default; the 40 percent level is a design choice, not an R152 normative value. Split from REQ-AEB-205.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Partial Braking Threshold — Part 2' occurs.
- **Then:** The partial braking request shall remain until TTC rises above 1.8 s.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1.8 s` → 1.79, 1.8, 1.81

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-1016

**Split from:** `REQ-AEB-205`

**Open issues:** Split from REQ-AEB-205; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1017 — Full Braking Threshold — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The full braking request shall remain until the collision is resolved or the driver overrides.

**Rationale:** Full braking at TTC 0.6 s is an engineering calibration default; confirm with the vehicle dynamics and homologation plan. Split from REQ-AEB-206.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Full Braking Threshold — Part 2' occurs.
- **Then:** The full braking request shall remain until the collision is resolved or the driver overrides.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-1017

**Split from:** `REQ-AEB-206`

**Open issues:** Split from REQ-AEB-206; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1018 — FCW Only Condition — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_AssessCollisionRisk shall continue issuing the FCW warning when a pedestrian-class object is detected crossing ahead, even below 10 km/h.

**Rationale:** Interim pilot decision: braking escalation is suppressed below 10 km/h, but pedestrian FCW remains active below 10 km/h. Confirm the warning/braking split and hysteresis. Split from REQ-AEB-209.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'FCW Only Condition — Part 2' occurs.
- **Then:** RE_AssessCollisionRisk shall continue issuing the FCW warning when a pedestrian-class object is detected crossing ahead, even below 10 km/h.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 km/h` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_AssessCollisionRisk, SWC_AEB_RiskAssessor · test=TD-REQ-AEB-1018

**Split from:** `REQ-AEB-209`

**Open issues:** Split from REQ-AEB-209; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## SWC_AEB_SafetyMonitor

### REQ-AEB-501 — Monitor Cycle

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** SWC_AEB_SafetyMonitor shall execute RE_MonitorSafety cyclically every 5 ms to perform plausibility checks, E2E verification, watchdog triggering, and degraded-mode management.

**Rationale:** Derived from REQ-AEB-001. Source notes: 5 ms monitor cycle; req_type=TIMING. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 5 ms trigger occurs.
- **Then:** SWC_AEB_SafetyMonitor shall execute RE_MonitorSafety cyclically every 5 ms to perform plausibility checks, E2E verification, watchdog triggering, and degraded-mode management. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-501

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-502 — Sensor Plausibility

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall compare the fused critical object's longitudinal distance and relative speed against the raw radar measurement every 5 ms.

**Rationale:** 1.0 m / 3.0 m/s / 3-cycle plausibility thresholds are diagnostic calibration defaults; confirm with the sensor-fusion and safety monitor owners.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Sensor Plausibility' occurs.
- **Then:** RE_MonitorSafety shall compare the fused critical object's longitudinal distance and relative speed against the raw radar measurement every 5 ms.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-502

**Split into:** REQ-AEB-1026

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1026; the original ID retains part 1.

---

### REQ-AEB-503 — E2E Verification

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall verify the E2E Profile 2 protection on all safety-relevant input signals (RP_RadarObjects, RP_CameraObjects, RP_VehicleSpeed, RP_YawRate).

**Rationale:** E2E Profile 2 and 2 consecutive failures are derived from the AUTOSAR E2E design; confirm the failure count with the safety monitor owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'E2E Verification' occurs.
- **Then:** RE_MonitorSafety shall verify the E2E Profile 2 protection on all safety-relevant input signals (RP_RadarObjects, RP_CameraObjects, RP_VehicleSpeed, RP_YawRate).
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-503

**Split into:** REQ-AEB-1027

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1027; the original ID retains part 1.

---

### REQ-AEB-504 — Watchdog Trigger

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall trigger the hardware watchdog via Rte_Call every 5 ms.

**Rationale:** Derived from REQ-AEB-001. Source notes: HW watchdog 5 ms; req_type=SAFETY; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Trigger' occurs and persists for the specified debounce.
- **Then:** RE_MonitorSafety shall trigger the hardware watchdog via Rte_Call every 5 ms. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-504

**Split into:** REQ-AEB-1028

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Split into REQ-AEB-1028; the original ID retains part 1.

---

### REQ-AEB-505 — Degraded Mode

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall transition the AEB feature to DEGRADED mode (braking limited to 4.0 m/s2, warning disabled) when a single sensor source fails, and to FAILSAFE mode (controlled braking 6.0 m/s2) when both sources fail or an actuation fault is present.

**Rationale:** Degraded 4.0 m/s2 and failsafe 6.0 m/s2 are design choices; the source does not derive them from R152. Confirm with the safety analysis.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Degraded Mode' occurs and persists for the specified debounce.
- **Then:** RE_MonitorSafety shall transition the AEB feature to DEGRADED mode (braking limited to 4.0 m/s2, warning disabled) when a single sensor source fails, and to FAILSAFE mode (controlled braking 6.0 m/s2) when both sources fail or an actuation fault is present. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 m/s2 at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `4.0 m/s2` → 3.99, 4.0, 4.01
- `6.0 m/s2` → 5.99, 6.0, 6.01

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-505

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-506 — Fault Reporting

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall report every detected fault to DEM via Dem_ReportErrorStatus and store the fault snapshot (fault code, TTC, vehicle speed, timestamp) in NVM via NvM_WriteBlock(NvM_AEB_FaultLog).

**Rationale:** Derived from REQ-AEB-001. Source notes: DEM + NvM fault log; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Fault Reporting' occurs.
- **Then:** RE_MonitorSafety shall report every detected fault to DEM via Dem_ReportErrorStatus and store the fault snapshot (fault code, TTC, vehicle speed, timestamp) in NVM via NvM_WriteBlock(NvM_AEB_FaultLog).
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-506

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-507 — Monitoring Status Output

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_SafetyMonitor shall publish PP_SafetyStatus (SR IF_SR_Safety) every 5 ms containing the AEB mode enum, an active fault bitmask, and E2E verification status per source.

**Rationale:** Derived from REQ-AEB-001. Source notes: Safety status output; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_SafetyMonitor component is running and the referenced producer/consumer ports are connected.
- **When:** Monitoring Status Output is exercised at its defined update rate.
- **Then:** SWC_AEB_SafetyMonitor shall publish PP_SafetyStatus (SR IF_SR_Safety) every 5 ms containing the AEB mode enum, an active fault bitmask, and E2E verification status per source. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-507

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-508 — Startup Self-Test

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall perform RAM checksum and ROM CRC-32 self-tests at startup.

**Rationale:** Derived from REQ-AEB-001. Source notes: RAM/ROM self-test; req_type=SAFETY; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Startup Self-Test' occurs.
- **Then:** RE_MonitorSafety shall perform RAM checksum and ROM CRC-32 self-tests at startup.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `-32 s` → -32.01, -32.0, -31.99

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-508

**Split into:** REQ-AEB-1029

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1029; the original ID retains part 1.

---

### REQ-AEB-509 — Monitor Calibration

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_SafetyMonitor shall expose plausibility thresholds (1.0 m, 3.0 m/s, 3 cycles), E2E failure count 2, and the degrade and derate levels as calibration parameters stored in ROM.

**Rationale:** Derived from REQ-AEB-001. Source notes: Monitor calibration table; req_type=CONSTRAINT. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** SWC_AEB_SafetyMonitor shall expose plausibility thresholds (1.0 m, 3.0 m/s, 3 cycles), E2E failure count 2, and the degrade and derate levels as calibration parameters stored in ROM. The constraint is satisfied with no exceptions.
- **Tolerance:** ±0.01 m at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1.0 m` → 0.99, 1.0, 1.01
- `3.0 m/s` → 2.99, 3.0, 3.01
- `3 cycles` → 2.99, 3.0, 3.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-509

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-801 — Sensor Source Loss Safe State

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When one sensor source (radar or camera) is unavailable, the AEB feature shall continue with the remaining source in single-source degraded mode, raise a sensor-source fault within 100 ms, and transition to FAILSAFE mode as specified in REQ-AEB-505 when both sources are unavailable.

**Rationale:** The source set defines single-source fusion and a degraded mode but does not state the system-level safe state and timing for complete sensor loss.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Sensor Source Loss Safe State' occurs and persists for the specified debounce.
- **Then:** When one sensor source (radar or camera) is unavailable, the AEB feature shall continue with the remaining source in single-source degraded mode, raise a sensor-source fault within 100 ms, and transition to FAILSAFE mode as specified in REQ-AEB-505 when both sources are unavailable. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100 ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-801

**Open issues:** The 100 ms fault-reaction value is derived from the per-source timeout in REQ-AEB-108; confirm with the safety analysis.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-802 — Degraded and Failsafe Recovery

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The AEB feature shall transition from DEGRADED or FAILSAFE mode back to STANDBY only after the triggering fault is no longer present and the recovery criteria in the safety analysis are satisfied.

**Rationale:** The source defines entry into DEGRADED/FAILSAFE but not the recovery condition or its observability.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Degraded and Failsafe Recovery' occurs and persists for the specified debounce.
- **Then:** The AEB feature shall transition from DEGRADED or FAILSAFE mode back to STANDBY only after the triggering fault is no longer present and the recovery criteria in the safety analysis are satisfied. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-802

**Split into:** REQ-AEB-1032

**Open issues:** Recovery criteria are not defined in the source; they must come from the safety analysis and FTTI. This requirement is a placeholder for that decision.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Split into REQ-AEB-1032; the original ID retains part 1.

---

### REQ-AEB-803 — E2E Fault Reaction

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** On an E2E Profile 2 counter mismatch or CRC failure on a safety-relevant input, the AEB feature shall raise the corresponding fault after two consecutive failures, enter DEGRADED mode within 10 ms of the second failure, and report and persist the fault to DEM and NVM.

**Rationale:** The source defines E2E detection but not the reaction time, degraded-mode entry or persistence.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'E2E Fault Reaction' occurs and persists for the specified debounce.
- **Then:** On an E2E Profile 2 counter mismatch or CRC failure on a safety-relevant input, the AEB feature shall raise the corresponding fault after two consecutive failures, enter DEGRADED mode within 10 ms of the second failure, and report and persist the fault to DEM and NVM. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-803

**Open issues:** The 10 ms reaction time is proposed from the 5 ms monitor cycle plus one confirmation cycle; confirm with the safety analysis.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-804 — Brake Feedback Fault Handling

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the commanded brake pressure deviates from the feedback pressure by more than 15 bar for more than 50 ms, the AEB feature shall report a brake actuation fault to SWC_AEB_SafetyMonitor.

**Rationale:** The source defines detection and reporting but not the resulting system reaction.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Brake Feedback Fault Handling' occurs and persists for the specified debounce.
- **Then:** When the commanded brake pressure deviates from the feedback pressure by more than 15 bar for more than 50 ms, the AEB feature shall report a brake actuation fault to SWC_AEB_SafetyMonitor. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 bar at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `15 bar` → 14.99, 15.0, 15.01
- `50 ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-804

**Split into:** REQ-AEB-1033

**Open issues:** Confirm whether FAILSAFE is the correct reaction for a brake feedback fault or whether a controlled stop is required.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Split into REQ-AEB-1033; the original ID retains part 1.

---

### REQ-AEB-807 — Startup and Shutdown Safe State

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** On ECU startup, the AEB feature shall initialize all outputs to the safe state (no braking demand, no warning) and remain in STANDBY until RAM/ROM self-tests and signal validation pass.

**Rationale:** The source covers startup self-tests and safe default output, but not an explicit shutdown-to-safe-state requirement.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Startup and Shutdown Safe State' occurs.
- **Then:** On ECU startup, the AEB feature shall initialize all outputs to the safe state (no braking demand, no warning) and remain in STANDBY until RAM/ROM self-tests and signal validation pass.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_BrakeActuator, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-807

**Split into:** REQ-AEB-1035

**Open issues:** Confirm the shutdown timing budget and whether a controlled stop is required before power-down.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1035; the original ID retains part 1.

---

### REQ-AEB-808 — Fault Healing and Persistence

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A healable AEB fault shall be cleared only after the DEM healing criterion is satisfied with no recurrence of the triggering condition.

**Rationale:** The source requires fault reporting and NVM storage but not healing or persistence of healing events.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Fault Healing and Persistence' occurs and persists for the specified debounce.
- **Then:** A healable AEB fault shall be cleared only after the DEM healing criterion is satisfied with no recurrence of the triggering condition. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-808

**Split into:** REQ-AEB-1036

**Open issues:** The DEM healing criterion is configuration-dependent; confirm the configured values and the list of non-healable faults.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Split into REQ-AEB-1036; the original ID retains part 1.

---

### REQ-AEB-809 — Calibration Verification

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** At startup and after a calibration update, the AEB feature shall verify that every safety-relevant calibration parameter is within its declared minimum/maximum range and that its default/current value is consistent with the vehicle variant.

**Rationale:** The source exposes calibration parameters but does not require their verification or the reaction to an invalid value.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Calibration Verification' occurs.
- **Then:** At startup and after a calibration update, the AEB feature shall verify that every safety-relevant calibration parameter is within its declared minimum/maximum range and that its default/current value is consistent with the vehicle variant.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-809

**Split into:** REQ-AEB-1037

**Open issues:** The safety-relevant calibration list and the variant matrix must be confirmed.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1037; the original ID retains part 1.

---

### REQ-AEB-813 — Fault Injection and Observability

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The AEB feature shall expose test hooks to inject sensor loss, E2E failure, brake-feedback deviation, ABS-active and plausibility faults.

**Rationale:** Verification of the safety mechanisms requires controllability and observability; the source defines status outputs but not injection hooks.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The AEB feature shall expose test hooks to inject sensor loss, E2E failure, brake-feedback deviation, ABS-active and plausibility faults. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-813

**Split into:** REQ-AEB-1040

**Open issues:** Test hooks must not weaken production safety/security; confirm the production-disable mechanism.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1040; the original ID retains part 1.

---

### REQ-AEB-1026 — Sensor Plausibility — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A deviation above 1.0 m or 3.0 m/s for more than 3 consecutive cycles shall raise a sensor plausibility fault.

**Rationale:** 1.0 m / 3.0 m/s / 3-cycle plausibility thresholds are diagnostic calibration defaults; confirm with the sensor-fusion and safety monitor owners. Split from REQ-AEB-502.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Sensor Plausibility — Part 2' occurs and persists for the specified debounce.
- **Then:** A deviation above 1.0 m or 3.0 m/s for more than 3 consecutive cycles shall raise a sensor plausibility fault. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 m at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1.0 m` → 0.99, 1.0, 1.01
- `3.0 m/s` → 2.99, 3.0, 3.01

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1026

**Split from:** `REQ-AEB-502`

**Open issues:** Split from REQ-AEB-502; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-1027 — E2E Verification — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A counter mismatch or CRC failure shall trigger the corresponding fault after 2 consecutive failures.

**Rationale:** E2E Profile 2 and 2 consecutive failures are derived from the AUTOSAR E2E design; confirm the failure count with the safety monitor owner. Split from REQ-AEB-503.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'E2E Verification — Part 2' occurs and persists for the specified debounce.
- **Then:** A counter mismatch or CRC failure shall trigger the corresponding fault after 2 consecutive failures. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1027

**Split from:** `REQ-AEB-503`

**Open issues:** Split from REQ-AEB-503; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-1028 — Watchdog Trigger — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A missed watchdog trigger shall cause the ASIL-D hardware watchdog to reset the ECU.

**Rationale:** Derived from REQ-AEB-001. Source notes: HW watchdog 5 ms; req_type=SAFETY; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-504.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Trigger — Part 2' occurs and persists for the specified debounce.
- **Then:** A missed watchdog trigger shall cause the ASIL-D hardware watchdog to reset the ECU. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1028

**Split from:** `REQ-AEB-504`

**Open issues:** Split from REQ-AEB-504; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-1029 — Startup Self-Test — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A RAM/ROM self-test failure shall set the AEB feature to FAULT mode and inhibit automatic braking until ECU service.

**Rationale:** Derived from REQ-AEB-001. Source notes: RAM/ROM self-test; req_type=SAFETY; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-508.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Startup Self-Test — Part 2' occurs and persists for the specified debounce.
- **Then:** A RAM/ROM self-test failure shall set the AEB feature to FAULT mode and inhibit automatic braking until ECU service. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1029

**Split from:** `REQ-AEB-508`

**Open issues:** Split from REQ-AEB-508; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-1032 — Degraded and Failsafe Recovery — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The DEGRADED/FAILSAFE transition and the recovery criteria shall be observable in PP_SafetyStatus.

**Rationale:** The source defines entry into DEGRADED/FAILSAFE but not the recovery condition or its observability. Split from REQ-AEB-802.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Degraded and Failsafe Recovery — Part 2' occurs.
- **Then:** The DEGRADED/FAILSAFE transition and the recovery criteria shall be observable in PP_SafetyStatus.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1032

**Split from:** `REQ-AEB-802`

**Open issues:** Split from REQ-AEB-802; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1033 — Brake Feedback Fault Handling — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** On a brake actuation fault, the AEB feature shall enter FAILSAFE mode unless the safety analysis defines a different reaction.

**Rationale:** The source defines detection and reporting but not the resulting system reaction. Split from REQ-AEB-804.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Brake Feedback Fault Handling — Part 2' occurs and persists for the specified debounce.
- **Then:** On a brake actuation fault, the AEB feature shall enter FAILSAFE mode unless the safety analysis defines a different reaction. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_CommandBrake, SWC_AEB_BrakeActuator, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1033

**Split from:** `REQ-AEB-804`

**Open issues:** Split from REQ-AEB-804; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-1035 — Startup and Shutdown Safe State — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** On shutdown, the AEB feature shall command zero braking demand and clear active warnings before the ECU powers down.

**Rationale:** The source covers startup self-tests and safe default output, but not an explicit shutdown-to-safe-state requirement. Split from REQ-AEB-807.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Startup and Shutdown Safe State — Part 2' occurs.
- **Then:** On shutdown, the AEB feature shall command zero braking demand and clear active warnings before the ECU powers down.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_BrakeActuator, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1035

**Split from:** `REQ-AEB-807`

**Open issues:** Split from REQ-AEB-807; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1036 — Fault Healing and Persistence — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Fault snapshots and healing events shall be persisted in NvM_AEB_FaultLog across power cycles.

**Rationale:** The source requires fault reporting and NVM storage but not healing or persistence of healing events. Split from REQ-AEB-808.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Fault Healing and Persistence — Part 2' occurs and persists for the specified debounce.
- **Then:** Fault snapshots and healing events shall be persisted in NvM_AEB_FaultLog across power cycles. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_MonitorSafety, SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1036

**Split from:** `REQ-AEB-808`

**Open issues:** Split from REQ-AEB-808; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-1037 — Calibration Verification — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A calibration verification failure shall set a calibration fault and inhibit automatic braking until corrected.

**Rationale:** The source exposes calibration parameters but does not require their verification or the reaction to an invalid value. Split from REQ-AEB-809.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Calibration Verification — Part 2' occurs and persists for the specified debounce.
- **Then:** A calibration verification failure shall set a calibration fault and inhibit automatic braking until corrected. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1037

**Split from:** `REQ-AEB-809`

**Open issues:** Split from REQ-AEB-809; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-AEB-1040 — Fault Injection and Observability — Part 2

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The AEB feature shall publish the resulting mode, fault bitmask and E2E status in PP_SafetyStatus for verification.

**Rationale:** Verification of the safety mechanisms requires controllability and observability; the source defines status outputs but not injection hooks. Split from REQ-AEB-813.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The AEB feature shall publish the resulting mode, fault bitmask and E2E status in PP_SafetyStatus for verification. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SafetyMonitor · test=TD-REQ-AEB-1040

**Split from:** `REQ-AEB-813`

**Open issues:** Split from REQ-AEB-813; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## SWC_AEB_SensorFusion

### REQ-AEB-101 — Fusion Runnable Cycle

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** SWC_AEB_SensorFusion shall execute RE_FuseObjects cyclically every 10 ms to time-align and fuse the radar object list and the camera object list into a single fused object list.

**Rationale:** Derived from REQ-AEB-001. Source notes: 10 ms fusion cycle; req_type=TIMING. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 10 ms trigger occurs.
- **Then:** SWC_AEB_SensorFusion shall execute RE_FuseObjects cyclically every 10 ms to time-align and fuse the radar object list and the camera object list into a single fused object list. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-101

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-102 — Fusion Inputs

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_SensorFusion shall read RP_RadarObjects (SR IF_SR_ObjectList, up to 64 objects) via its required port.

**Rationale:** Derived from REQ-AEB-001. Source notes: Radar + camera object lists; req_type=INTERFACE; split into 3 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_SensorFusion component is running and the referenced producer/consumer ports are connected.
- **When:** Fusion Inputs is exercised at its defined update rate.
- **Then:** SWC_AEB_SensorFusion shall read RP_RadarObjects (SR IF_SR_ObjectList, up to 64 objects) via its required port. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 objects at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `64 objects` → 63.99, 64.0, 64.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SensorFusion · test=TD-REQ-AEB-102

**Split into:** REQ-AEB-1006, REQ-AEB-1007

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.; Split into REQ-AEB-1006, REQ-AEB-1007; the original ID retains part 1.

---

### REQ-AEB-103 — Fused Object Output

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_SensorFusion shall publish the fused object list via PP_FusedObjects (SR IF_SR_ObjectList, up to 128 objects) every 10 ms.

**Rationale:** Derived from REQ-AEB-001. Source notes: Fused object list output; req_type=INTERFACE; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_SensorFusion component is running and the referenced producer/consumer ports are connected.
- **When:** Fused Object Output is exercised at its defined update rate.
- **Then:** SWC_AEB_SensorFusion shall publish the fused object list via PP_FusedObjects (SR IF_SR_ObjectList, up to 128 objects) every 10 ms. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 objects at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `128 objects` → 127.99, 128.0, 128.01
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SensorFusion · test=TD-REQ-AEB-103

**Split into:** REQ-AEB-1008

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.; Split into REQ-AEB-1008; the original ID retains part 1.

---

### REQ-AEB-104 — Time Alignment

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_FuseObjects shall time-align radar and camera objects to the current cycle using each sensor's last valid measurement timestamp and the object relative speed.

**Rationale:** 200 ms staleness drop is a calibration default from the fusion design; the value is not normative in UNECE R152.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Time Alignment' occurs.
- **Then:** RE_FuseObjects shall time-align radar and camera objects to the current cycle using each sensor's last valid measurement timestamp and the object relative speed.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-104

**Split into:** REQ-AEB-1009

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1009; the original ID retains part 1.

---

### REQ-AEB-105 — Object Association

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_TrackAssociate shall associate a radar object and a camera object to the same fused track when their longitudinal distance and lateral offset each agree within 0.5 m AND their relative speed agrees within 2.0 m/s. Exactly one radar object may associate to one camera object.

**Rationale:** Association gates 0.5 m and 2.0 m/s are calibration defaults from the fusion design; confirm with the sensor-fusion owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Object Association' occurs.
- **Then:** RE_TrackAssociate shall associate a radar object and a camera object to the same fused track when their longitudinal distance and lateral offset each agree within 0.5 m AND their relative speed agrees within 2.0 m/s. Exactly one radar object may associate to one camera object.
- **Tolerance:** ±0.01 m at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0.5 m` → 0.49, 0.5, 0.51
- `2.0 m/s` → 1.99, 2.0, 2.01

**Trace:** parent=REQ-AEB-001 · design=RE_TrackAssociate, SWC_AEB_SensorFusion · test=TD-REQ-AEB-105

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-106 — Sensor Blindness Handling

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When one sensor source (radar or camera) is unavailable, RE_FuseObjects shall continue using the remaining sensor, set the source mask accordingly, and mark the fused confidence reduced.

**Rationale:** Derived from REQ-AEB-001. Source notes: Single-source degraded fusion; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Sensor Blindness Handling' occurs.
- **Then:** When one sensor source (radar or camera) is unavailable, RE_FuseObjects shall continue using the remaining sensor, set the source mask accordingly, and mark the fused confidence reduced.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-106

**Split into:** REQ-AEB-1010

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1010; the original ID retains part 1.

---

### REQ-AEB-107 — Object Plausibility

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_FuseObjects shall reject fused objects whose longitudinal distance is negative (behind ego), whose relative speed magnitude exceeds 80 m/s, or whose existence probability is below 0.4.

**Rationale:** Plausibility gating protects the risk assessor from physically impossible objects; thresholds are calibration defaults.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Object Plausibility' occurs.
- **Then:** RE_FuseObjects shall reject fused objects whose longitudinal distance is negative (behind ego), whose relative speed magnitude exceeds 80 m/s, or whose existence probability is below 0.4.
- **Tolerance:** ±0.01 m/s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `80 m/s` → 79.99, 80.0, 80.01

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-107

**Split into:** REQ-AEB-1011

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1011; the original ID retains part 1.

---

### REQ-AEB-108 — Sensor Timeout Flag

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_FuseObjects shall set a per-source timeout flag when a sensor provides no valid objects for more than 100 ms.

**Rationale:** Derived from REQ-AEB-001. Source notes: 100 ms per-source timeout; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Sensor Timeout Flag' occurs.
- **Then:** RE_FuseObjects shall set a per-source timeout flag when a sensor provides no valid objects for more than 100 ms.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100 ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-108

**Split into:** REQ-AEB-1012

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1012; the original ID retains part 1.

---

### REQ-AEB-109 — Fusion Calibration Parameters

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_SensorFusion shall expose the fusion thresholds (association distance 0.5 m, association speed 2.0 m/s, drop age 200 ms, minimum probability 0.4) as calibration parameters stored in ROM.

**Rationale:** Derived from REQ-AEB-001. Source notes: Calibration table; req_type=CONSTRAINT. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** SWC_AEB_SensorFusion shall expose the fusion thresholds (association distance 0.5 m, association speed 2.0 m/s, drop age 200 ms, minimum probability 0.4) as calibration parameters stored in ROM. The constraint is satisfied with no exceptions.
- **Tolerance:** ±0.01 m at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0.5 m` → 0.49, 0.5, 0.51
- `2.0 m/s` → 1.99, 2.0, 2.01
- `200 ms` → 199.99, 200.0, 200.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SensorFusion · test=TD-REQ-AEB-109

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-110 — Fusion Determinism

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** RE_FuseObjects shall not allocate dynamic memory.

**Rationale:** Derived from REQ-AEB-001. Source notes: No dynamic memory; 2.0 ms WCET; req_type=CONSTRAINT; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** RE_FuseObjects shall not allocate dynamic memory. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-110

**Split into:** REQ-AEB-1013

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1013; the original ID retains part 1.

---

### REQ-AEB-1006 — Fusion Inputs — Part 2

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_SensorFusion shall read RP_CameraObjects (SR IF_SR_ObjectList, up to 32 objects) via its required port.

**Rationale:** Derived from REQ-AEB-001. Source notes: Radar + camera object lists; req_type=INTERFACE; split into 3 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-102.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_SensorFusion component is running and the referenced producer/consumer ports are connected.
- **When:** Fusion Inputs — Part 2 is exercised at its defined update rate.
- **Then:** SWC_AEB_SensorFusion shall read RP_CameraObjects (SR IF_SR_ObjectList, up to 32 objects) via its required port. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 objects at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `32 objects` → 31.99, 32.0, 32.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SensorFusion · test=TD-REQ-AEB-1006

**Split from:** `REQ-AEB-102`

**Open issues:** Split from REQ-AEB-102; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-1007 — Fusion Inputs — Part 3

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** Each radar and camera object shall carry object ID, longitudinal distance, lateral offset, relative speed, object class, and existence probability.

**Rationale:** Derived from REQ-AEB-001. Source notes: Radar + camera object lists; req_type=INTERFACE; split into 3 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-102.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_SensorFusion component is running and the referenced producer/consumer ports are connected.
- **When:** Fusion Inputs — Part 3 is exercised at its defined update rate.
- **Then:** Each radar and camera object shall carry object ID, longitudinal distance, lateral offset, relative speed, object class, and existence probability. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SensorFusion · test=TD-REQ-AEB-1007

**Split from:** `REQ-AEB-102`

**Open issues:** Split from REQ-AEB-102; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-1008 — Fused Object Output — Part 2

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** Each fused object shall carry a confidence score in [0.0, 1.0] and a source mask indicating radar, camera, or both.

**Rationale:** Derived from REQ-AEB-001. Source notes: Fused object list output; req_type=INTERFACE; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-103.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_SensorFusion component is running and the referenced producer/consumer ports are connected.
- **When:** Fused Object Output — Part 2 is exercised at its defined update rate.
- **Then:** Each fused object shall carry a confidence score in [0.0, 1.0] and a source mask indicating radar, camera, or both. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_SensorFusion · test=TD-REQ-AEB-1008

**Split from:** `REQ-AEB-103`

**Open issues:** Split from REQ-AEB-103; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-1009 — Time Alignment — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_FuseObjects shall drop objects older than 200 ms.

**Rationale:** 200 ms staleness drop is a calibration default from the fusion design; the value is not normative in UNECE R152. Split from REQ-AEB-104.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Time Alignment — Part 2' occurs.
- **Then:** RE_FuseObjects shall drop objects older than 200 ms.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `200 ms` → 199.99, 200.0, 200.01

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-1009

**Split from:** `REQ-AEB-104`

**Open issues:** Split from REQ-AEB-104; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1010 — Sensor Blindness Handling — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When running single-source, RE_FuseObjects shall set bit[1] of the PP_FusedObjects status.

**Rationale:** Derived from REQ-AEB-001. Source notes: Single-source degraded fusion; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-106.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Sensor Blindness Handling — Part 2' occurs.
- **Then:** When running single-source, RE_FuseObjects shall set bit[1] of the PP_FusedObjects status.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-1010

**Split from:** `REQ-AEB-106`

**Open issues:** Split from REQ-AEB-106; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1011 — Object Plausibility — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Rejected objects shall not appear in PP_FusedObjects.

**Rationale:** Plausibility gating protects the risk assessor from physically impossible objects; thresholds are calibration defaults. Split from REQ-AEB-107.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Object Plausibility — Part 2' occurs.
- **Then:** Rejected objects shall not appear in PP_FusedObjects.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-1011

**Split from:** `REQ-AEB-107`

**Open issues:** Split from REQ-AEB-107; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1012 — Sensor Timeout Flag — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The per-source timeout flags shall be exposed on the PP_FusedObjects status for consumption by SWC_AEB_SafetyMonitor.

**Rationale:** Derived from REQ-AEB-001. Source notes: 100 ms per-source timeout; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-108.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Sensor Timeout Flag — Part 2' occurs.
- **Then:** The per-source timeout flags shall be exposed on the PP_FusedObjects status for consumption by SWC_AEB_SafetyMonitor.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-1012

**Split from:** `REQ-AEB-108`

**Open issues:** Split from REQ-AEB-108; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1013 — Fusion Determinism — Part 2

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** RE_FuseObjects shall complete within 2.0 ms worst case on its 10 ms cycle with a fixed computation path.

**Rationale:** Derived from REQ-AEB-001. Source notes: No dynamic memory; 2.0 ms WCET; req_type=CONSTRAINT; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-110.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** RE_FuseObjects shall complete within 2.0 ms worst case on its 10 ms cycle with a fixed computation path. The constraint is satisfied with no exceptions.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `2.0 ms` → 1.99, 2.0, 2.01
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_FuseObjects, SWC_AEB_SensorFusion · test=TD-REQ-AEB-1013

**Split from:** `REQ-AEB-110`

**Open issues:** Split from REQ-AEB-110; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## SWC_AEB_VehicleState

### REQ-AEB-601 — Ego Motion Cycle

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** SWC_AEB_VehicleState shall execute RE_UpdateEgoMotion cyclically every 10 ms to update ego vehicle speed, longitudinal acceleration, yaw rate, and steering angle from vehicle sensors.

**Rationale:** Derived from REQ-AEB-001. Source notes: 10 ms ego-motion cycle; req_type=TIMING. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 10 ms trigger occurs.
- **Then:** SWC_AEB_VehicleState shall execute RE_UpdateEgoMotion cyclically every 10 ms to update ego vehicle speed, longitudinal acceleration, yaw rate, and steering angle from vehicle sensors. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=RE_UpdateEgoMotion, SWC_AEB_VehicleState · test=TD-REQ-AEB-601

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-602 — Vehicle Speed Input

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_VehicleState shall read RP_VehicleSpeed (SR IF_SR_Speed, range 0-350 km/h, resolution 0.01 km/h, 10 ms cycle) and RP_WheelSpeedFL, RP_WheelSpeedFR, RP_WheelSpeedRL, RP_WheelSpeedRR (four wheel speeds) via required ports.

**Rationale:** Derived from REQ-AEB-001. Source notes: Speed + 4 wheel speeds; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_VehicleState component is running and the referenced producer/consumer ports are connected.
- **When:** Vehicle Speed Input is exercised at its defined update rate.
- **Then:** SWC_AEB_VehicleState shall read RP_VehicleSpeed (SR IF_SR_Speed, range 0-350 km/h, resolution 0.01 km/h, 10 ms cycle) and RP_WheelSpeedFL, RP_WheelSpeedFR, RP_WheelSpeedRL, RP_WheelSpeedRR (four wheel speeds) via required ports. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 km/h (one resolution step)

**Boundary values:**

- `350 km/h` → 349.99, 350.0, 350.01
- `0.01 km/h` → 0.0, 0.01, 0.02
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_VehicleState · test=TD-REQ-AEB-602

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-603 — Speed Signal Validation

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_UpdateEgoMotion shall validate RP_VehicleSpeed against the four wheel speeds.

**Rationale:** Derived from REQ-AEB-001. Source notes: 3 km/h / 100 ms validation; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Speed Signal Validation' occurs.
- **Then:** RE_UpdateEgoMotion shall validate RP_VehicleSpeed against the four wheel speeds.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_UpdateEgoMotion, SWC_AEB_VehicleState · test=TD-REQ-AEB-603

**Split into:** REQ-AEB-1030

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1030; the original ID retains part 1.

---

### REQ-AEB-604 — Yaw Rate and Steering Input

**Type:** interface · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_VehicleState shall read RP_YawRate (range -100 to +100 deg/s, resolution 0.01 deg/s) and RP_SteeringAngle (range -720 to +720 deg, resolution 0.1 deg) for ego-path estimation.

**Rationale:** Derived from REQ-AEB-001. Source notes: Yaw + steering for path; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_VehicleState component is running and the referenced producer/consumer ports are connected.
- **When:** Yaw Rate and Steering Input is exercised at its defined update rate.
- **Then:** SWC_AEB_VehicleState shall read RP_YawRate (range -100 to +100 deg/s, resolution 0.01 deg/s) and RP_SteeringAngle (range -720 to +720 deg, resolution 0.1 deg) for ego-path estimation. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 deg/s (one resolution step)

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_VehicleState · test=TD-REQ-AEB-604

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-605 — Ego State Output

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_AEB_VehicleState shall publish PP_VehicleState (SR IF_SR_EgoState) every 10 ms containing vehicle speed, longitudinal acceleration, yaw rate, steering angle, and a signal-validity bitmask.

**Rationale:** Derived from REQ-AEB-001. Source notes: Ego state output; req_type=INTERFACE. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_AEB_VehicleState component is running and the referenced producer/consumer ports are connected.
- **When:** Ego State Output is exercised at its defined update rate.
- **Then:** SWC_AEB_VehicleState shall publish PP_VehicleState (SR IF_SR_EgoState) every 10 ms containing vehicle speed, longitudinal acceleration, yaw rate, steering angle, and a signal-validity bitmask. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-AEB-001 · design=SWC_AEB_VehicleState · test=TD-REQ-AEB-605

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-AEB-606 — Standstill Detection

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_UpdateEgoMotion shall set the standstill flag when vehicle speed is below 0.5 km/h for more than 200 ms, and clear it when speed exceeds 1.0 km/h (hysteresis).

**Rationale:** Derived from REQ-AEB-001. Source notes: Standstill hysteresis; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Standstill Detection' occurs.
- **Then:** RE_UpdateEgoMotion shall set the standstill flag when vehicle speed is below 0.5 km/h for more than 200 ms, and clear it when speed exceeds 1.0 km/h (hysteresis).
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0.5 km/h` → 0.49, 0.5, 0.51
- `200 ms` → 199.99, 200.0, 200.01
- `1.0 km/h` → 0.99, 1.0, 1.01

**Trace:** parent=REQ-AEB-001 · design=RE_UpdateEgoMotion, SWC_AEB_VehicleState · test=TD-REQ-AEB-606

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1030 — Speed Signal Validation — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If the difference exceeds 3 km/h for more than 100 ms, the vehicle speed signal shall be flagged invalid and the last valid value held.

**Rationale:** Derived from REQ-AEB-001. Source notes: 3 km/h / 100 ms validation; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-603.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Speed Signal Validation — Part 2' occurs.
- **Then:** If the difference exceeds 3 km/h for more than 100 ms, the vehicle speed signal shall be flagged invalid and the last valid value held.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `3 km/h` → 2.99, 3.0, 3.01
- `100 ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-AEB-001 · design=RE_UpdateEgoMotion, SWC_AEB_VehicleState · test=TD-REQ-AEB-1030

**Split from:** `REQ-AEB-603`

**Open issues:** Split from REQ-AEB-603; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## System

### REQ-AEB-001 — AEB System Architecture

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The AEB feature shall be implemented as a distributed AUTOSAR application composed of seven application SWCs allocated to the AEB partition on ECU_AEB_Main: SWC_AEB_SensorFusion, SWC_AEB_RiskAssessor, SWC_AEB_Controller, SWC_AEB_BrakeActuator, SWC_AEB_SafetyMonitor, SWC_AEB_VehicleState, and SWC_AEB_HMI. The feature-level behaviour of detecting an imminent forward collision, warning the driver and requesting service braking is specified in REQ-AEB-009.

**Rationale:** Architecture allocation requirement derived from the AEB feature decomposition. The feature behaviour is separated into REQ-AEB-009 so that architecture and behaviour can be verified independently.

**Acceptance criteria (draft):**

- **Given:** The AEB software architecture is under review and the ECU_AEB_Main partition is defined.
- **When:** The architecture work product is inspected.
- **Then:** Exactly the seven listed application SWCs are allocated to the AEB partition, and no additional AEB application SWC is allocated outside the partition.
- **Tolerance:** Exact match on SWC names and allocation.

**Trace:** parent=— · design=System · test=TD-REQ-AEB-001

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Feature-level behaviour was split into REQ-AEB-009; confirm the split with the architecture owner.

---

### REQ-AEB-002 — AEBS Operating Speed Range

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The AEB function shall be active over the vehicle speed range 10 km/h to 60 km/h inclusive for car-to-car scenarios, per UNECE R152.

**Rationale:** Interim pilot decision: automatic braking is active 10-60 km/h for car-to-car; pedestrian FCW remains active below 10 km/h per REQ-AEB-209. Hysteresis is a calibration item, not a new normative value.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'AEBS Operating Speed Range' occurs.
- **Then:** The AEB function shall be active over the vehicle speed range 10 km/h to 60 km/h inclusive for car-to-car scenarios, per UNECE R152.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 km/h` → 9.99, 10.0, 10.01
- `60 km/h` → 59.99, 60.0, 60.01

**Trace:** parent=— · design=System · test=TD-REQ-AEB-002

**Split into:** REQ-AEB-1001, REQ-AEB-1002

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Conflict with REQ-AEB-209: pedestrian FCW remains active below 10 km/h. The automatic braking exception is clarified in the statement; confirm with the feature owner.; Interim decision recorded: automatic braking is deactivated outside 10-60 km/h and pedestrian FCW remains active below 10 km/h; confirm transition/hysteresis with the feature owner.; Split into REQ-AEB-1001, REQ-AEB-1002; the original ID retains part 1.

---

### REQ-AEB-003 — Emergency Braking Demand Level

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When a collision is deemed imminent, the AEB Controller shall request a braking demand of at least 5.0 m/s2 to the service braking system, per UNECE R152 emergency braking requirement.

**Rationale:** UNECE R152 requires an emergency braking demand of at least 5.0 m/s2. The sample uses the normative minimum as the acceptance threshold.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Emergency Braking Demand Level' occurs.
- **Then:** When a collision is deemed imminent, the AEB Controller shall request a braking demand of at least 5.0 m/s2 to the service braking system, per UNECE R152 emergency braking requirement.
- **Tolerance:** ±0.01 m/s2 at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5.0 m/s2` → 4.99, 5.0, 5.01

**Trace:** parent=— · design=System · test=TD-REQ-AEB-003

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-004 — Collision Warning Requirement

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The AEB feature shall provide a forward collision warning using at least two of the acoustic, haptic, and optical modalities.

**Rationale:** Derived from the AEB system context. Source notes: R152 collision warning (>=2 modalities); req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Collision Warning Requirement' occurs.
- **Then:** The AEB feature shall provide a forward collision warning using at least two of the acoustic, haptic, and optical modalities.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-AEB-004

**Split into:** REQ-AEB-1003

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1003; the original ID retains part 1.

---

### REQ-AEB-005 — Driver Override

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A driver-initiated brake or accelerator action that exceeds the AEB braking demand shall override and cancel the AEB braking request.

**Rationale:** Derived from the AEB system context. Source notes: Driver intent has priority; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Driver Override' occurs.
- **Then:** A driver-initiated brake or accelerator action that exceeds the AEB braking demand shall override and cancel the AEB braking request.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-AEB-005

**Split into:** REQ-AEB-1004

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; The source says 'one control cycle'; the controller cycle is 10 ms (REQ-AEB-301). Confirmed in the statement, but confirm for every mode.; Interim decision recorded: use the 10 ms arbitration cycle; confirm that no faster override path is required in every mode.; Split into REQ-AEB-1004; the original ID retains part 1.

---

### REQ-AEB-006 — AEB Availability Status

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The AEB feature shall publish its availability and state (OFF, STANDBY, ACTIVE, WARNING, BRAKING, FAULT) to the gateway via provided port PP_AEBStatus with Sender-Receiver interface IF_SR_AEBStatus, updated every 10 ms.

**Rationale:** Gateway tell-tale feed requirement. The 10 ms update is the availability/status refresh; the state transition itself may occur on an event.

**Acceptance criteria (draft):**

- **Given:** The System component is running and the referenced producer/consumer ports are connected.
- **When:** AEB Availability Status is exercised at its defined update rate.
- **Then:** The AEB feature shall publish its availability and state (OFF, STANDBY, ACTIVE, WARNING, BRAKING, FAULT) to the gateway via provided port PP_AEBStatus with Sender-Receiver interface IF_SR_AEBStatus, updated every 10 ms. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=— · design=System · test=TD-REQ-AEB-006

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.; Confirm whether PP_AEBStatus is cyclic (10 ms) only or also event-driven on state change.

---

### REQ-AEB-007 — System Initialization

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** On ECU startup, the AEB SWCs shall complete RAM and ROM self-tests, initialize all internal states to safe defaults (no braking demand, no warning), and remain in STANDBY until vehicle state and sensor signals are validated.

**Rationale:** Derived from the AEB system context. Source notes: Safe-state init before any runnable runs; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'System Initialization' occurs.
- **Then:** On ECU startup, the AEB SWCs shall complete RAM and ROM self-tests, initialize all internal states to safe defaults (no braking demand, no warning), and remain in STANDBY until vehicle state and sensor signals are validated.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-AEB-007

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-008 — Traceability and E2E Baseline

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** Every AEB requirement shall be traceable to one software runnable, one MUD flowchart step, and one or more unit test cases.

**Rationale:** Derived from the AEB system context. Source notes: Traceability + E2E Profile 2; req_type=CONSTRAINT; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** Every AEB requirement shall be traceable to one software runnable, one MUD flowchart step, and one or more unit test cases. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-AEB-008

**Split into:** REQ-AEB-1005

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1005; the original ID retains part 1.

---

### REQ-AEB-009 — AEB Feature Behaviour

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The AEB feature shall detect an imminent forward collision, warn the driver using at least two warning modalities, and request service braking of at least 5.0 m/s2 to avoid or mitigate the collision, in accordance with UNECE R152.

**Rationale:** Separates the feature-level behaviour from the architecture allocation so each can be verified independently.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'AEB Feature Behaviour' occurs.
- **Then:** The AEB feature shall detect an imminent forward collision, warn the driver using at least two warning modalities, and request service braking of at least 5.0 m/s2 to avoid or mitigate the collision, in accordance with UNECE R152.
- **Tolerance:** ±0.01 m/s2 at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5.0 m/s2` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-AEB-001 · design=System · test=TD-REQ-AEB-009

**Open issues:** Split from REQ-AEB-001; confirm with the feature owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-810 — Software and Calibration Update Integrity

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The AEB feature shall only accept authenticated and integrity-protected software and calibration updates, prevent activation on a failed authenticity or integrity check, and record a fault.

**Rationale:** A safety-critical braking function needs update integrity; the source set does not address cybersecurity.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The AEB feature shall only accept authenticated and integrity-protected software and calibration updates, prevent activation on a failed authenticity or integrity check, and record a fault. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=System · test=TD-REQ-AEB-810

**Open issues:** Cybersecurity requirements must be developed with the ISO 21434 process; this is a placeholder, not a complete cybersecurity specification.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-811 — Vehicle Variant Configuration

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The AEB feature shall select its speed range, vehicle mass, brake gain and warning modalities from a validated vehicle-variant configuration.

**Rationale:** The source uses vehicle-dependent calibration values but does not define variant selection or mismatch handling.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The AEB feature shall select its speed range, vehicle mass, brake gain and warning modalities from a validated vehicle-variant configuration. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=System · test=TD-REQ-AEB-811

**Split into:** REQ-AEB-1038

**Open issues:** The variant matrix and the configuration source (coding plug, dataset, end-of-line) must be confirmed.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1038; the original ID retains part 1.

---

### REQ-AEB-812 — Runtime Resource Budget

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** Each AEB runnable shall complete within its allocated WCET budget on ECU_AEB_Main: RE_CommandBrake and RE_MonitorSafety within 5 ms, RE_FuseObjects and RE_ArbitrateBrakeDemand and RE_UpdateEgoMotion within 10 ms, RE_AssessCollisionRisk within 20 ms.

**Rationale:** The source defines cycles but does not state a system-level WCET/resource budget or a no-dynamic-memory rule for every runnable.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The defined trigger occurs.
- **Then:** Each AEB runnable shall complete within its allocated WCET budget on ECU_AEB_Main: RE_CommandBrake and RE_MonitorSafety within 5 ms, RE_FuseObjects and RE_ArbitrateBrakeDemand and RE_UpdateEgoMotion within 10 ms, RE_AssessCollisionRisk within 20 ms. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01
- `10 ms` → 9.99, 10.0, 10.01
- `20 ms` → 19.99, 20.0, 20.01

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, RE_AssessCollisionRisk, RE_CommandBrake, RE_FuseObjects, RE_MonitorSafety, RE_UpdateEgoMotion, System · test=TD-REQ-AEB-812

**Split into:** REQ-AEB-1039

**Open issues:** The WCET numbers reuse the runnable periods as a conservative budget; actual WCET must be measured on the target.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-AEB-1039; the original ID retains part 1.

---

### REQ-AEB-1001 — AEBS Operating Speed Range — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Below 10 km/h and above 60 km/h, the AEB function shall deactivate the automatic braking demand while AEB monitoring and availability reporting continue.

**Rationale:** Interim pilot decision: automatic braking is active 10-60 km/h for car-to-car; pedestrian FCW remains active below 10 km/h per REQ-AEB-209. Hysteresis is a calibration item, not a new normative value. Split from REQ-AEB-002.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'AEBS Operating Speed Range — Part 2' occurs.
- **Then:** Below 10 km/h and above 60 km/h, the AEB function shall deactivate the automatic braking demand while AEB monitoring and availability reporting continue.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 km/h` → 9.99, 10.0, 10.01
- `60 km/h` → 59.99, 60.0, 60.01

**Trace:** parent=— · design=System · test=TD-REQ-AEB-1001

**Split from:** `REQ-AEB-002`

**Open issues:** Split from REQ-AEB-002; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1002 — AEBS Operating Speed Range — Part 3

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Pedestrian forward-collision warning below 10 km/h shall follow REQ-AEB-209.

**Rationale:** Interim pilot decision: automatic braking is active 10-60 km/h for car-to-car; pedestrian FCW remains active below 10 km/h per REQ-AEB-209. Hysteresis is a calibration item, not a new normative value. Split from REQ-AEB-002.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'AEBS Operating Speed Range — Part 3' occurs.
- **Then:** Pedestrian forward-collision warning below 10 km/h shall follow REQ-AEB-209.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 km/h` → 9.99, 10.0, 10.01

**Trace:** parent=— · design=System · test=TD-REQ-AEB-1002

**Split from:** `REQ-AEB-002`

**Open issues:** Split from REQ-AEB-002; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1003 — Collision Warning Requirement — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The forward collision warning shall be issued no later than the start of the emergency braking intervention.

**Rationale:** Derived from the AEB system context. Source notes: R152 collision warning (>=2 modalities); req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-004.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Collision Warning Requirement — Part 2' occurs.
- **Then:** The forward collision warning shall be issued no later than the start of the emergency braking intervention.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-AEB-1003

**Split from:** `REQ-AEB-004`

**Open issues:** Split from REQ-AEB-004; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1004 — Driver Override — Part 2

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The driver override shall be detected within one 10 ms arbitration cycle (REQ-AEB-301).

**Rationale:** Derived from the AEB system context. Source notes: Driver intent has priority; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-005.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Driver Override — Part 2' occurs.
- **Then:** The driver override shall be detected within one 10 ms arbitration cycle (REQ-AEB-301).
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=— · design=System · test=TD-REQ-AEB-1004

**Split from:** `REQ-AEB-005`

**Open issues:** Split from REQ-AEB-005; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1005 — Traceability and E2E Baseline — Part 2

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** All safety-relevant AEB signals shall be protected with AUTOSAR E2E Profile 2.

**Rationale:** Derived from the AEB system context. Source notes: Traceability + E2E Profile 2; req_type=CONSTRAINT; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-AEB-008.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** All safety-relevant AEB signals shall be protected with AUTOSAR E2E Profile 2. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-AEB-1005

**Split from:** `REQ-AEB-008`

**Open issues:** Split from REQ-AEB-008; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1038 — Vehicle Variant Configuration — Part 2

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** An unknown or inconsistent variant shall set a configuration fault and inhibit automatic braking.

**Rationale:** The source uses vehicle-dependent calibration values but does not define variant selection or mismatch handling. Split from REQ-AEB-811.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** An unknown or inconsistent variant shall set a configuration fault and inhibit automatic braking. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=System · test=TD-REQ-AEB-1038

**Split from:** `REQ-AEB-811`

**Open issues:** Split from REQ-AEB-811; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-AEB-1039 — Runtime Resource Budget — Part 2

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** No cyclic AEB runnable shall perform dynamic memory allocation or unbounded blocking calls.

**Rationale:** The source defines cycles but does not state a system-level WCET/resource budget or a no-dynamic-memory rule for every runnable. Split from REQ-AEB-812.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The defined trigger occurs.
- **Then:** No cyclic AEB runnable shall perform dynamic memory allocation or unbounded blocking calls. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-AEB-001 · design=RE_ArbitrateBrakeDemand, RE_AssessCollisionRisk, RE_CommandBrake, RE_FuseObjects, RE_MonitorSafety, RE_UpdateEgoMotion, System · test=TD-REQ-AEB-1039

**Split from:** `REQ-AEB-812`

**Open issues:** Split from REQ-AEB-812; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Cycle period is not specified; confirm the scheduling contract.

---
