# EPS requirements — polished L2-oriented draft

> Status: **review draft**. Human approval required. Not certified.
> Source: `inputs/requirements/samples/eps_requirements.csv` (unchanged).
> Requirements: **98** (66 retained/derived + 32 atomic split parts).

## How to read this document

Each requirement is atomic where possible. 24 compound requirements were split into 32 atomic parts; the original ID keeps part 1 and parts 2+ use `REQ-EPS-1001..REQ-EPS-1032`. Acceptance criteria are drafts derived from the source text. Open issues are decisions for the human reviewer, not hidden assumptions.

## Summary by allocation

| Allocation | Requirements |
|---|---|
| SWC_ElectricPowerSteering | 96 |
| System | 2 |

## SWC_ElectricPowerSteering

### REQ-EPS-001 — EPS SWC Architecture

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SWC_ElectricPowerSteering shall be implemented as an AUTOSAR ApplicationSwComponentType allocated to the EPS application partition on ECU_EPS_Main.

**Rationale:** EPS software architecture allocation. The source bundles architecture, runnables, ports, modes and a fail-safe reaction in one requirement; the hardening pass splits it into atomic parts.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EPS SWC Architecture' occurs.
- **Then:** SWC_ElectricPowerSteering shall be implemented as an AUTOSAR ApplicationSwComponentType allocated to the EPS application partition on ECU_EPS_Main.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, RE_DiagnosticUpdate, RE_HandleModeChange, RE_Initialize, RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-001

**Split into:** REQ-EPS-1001, REQ-EPS-1002, REQ-EPS-1003, REQ-EPS-1004, REQ-EPS-1005

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Placeholder system parent REQ-EPS-000; confirm the stakeholder/system requirement and ASIL allocation with the EPS owner.; Split into REQ-EPS-1001, REQ-EPS-1002, REQ-EPS-1003, REQ-EPS-1004, REQ-EPS-1005; the original ID retains part 1.

---

### REQ-EPS-002 — Control Torque Runnable

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** RE_ControlTorque shall execute cyclically every 5 ms to compute torque assist demand and write motor current output.

**Rationale:** Derived from REQ-EPS-000. Source notes: 5ms = 200 Hz control loop. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 5 ms trigger occurs.
- **Then:** RE_ControlTorque shall execute cyclically every 5 ms to compute torque assist demand and write motor current output. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, SWC_ElectricPowerSteering · test=TD-REQ-EPS-002

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-003 — Safety Monitor Runnable

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** RE_MonitorSafety shall execute cyclically every 10 ms to perform plausibility checks and update diagnostics.

**Rationale:** Derived from REQ-EPS-000. Source notes: 10ms safety monitor runs at half rate of control loop. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 10 ms trigger occurs.
- **Then:** RE_MonitorSafety shall execute cyclically every 10 ms to perform plausibility checks and update diagnostics. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-003

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-004 — Initialization Runnable

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_Initialize shall execute once on ECU startup to validate sensor signals set internal state to INIT and perform RAM and ROM self-test.

**Rationale:** Derived from REQ-EPS-000. Source notes: Called by OS on AUTOSAR startup hook. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Initialization Runnable' occurs.
- **Then:** RE_Initialize shall execute once on ECU startup to validate sensor signals set internal state to INIT and perform RAM and ROM self-test.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_Initialize, SWC_ElectricPowerSteering · test=TD-REQ-EPS-004

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-005 — Mode Change Runnable

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_HandleModeChange shall execute on DataReceivedEvent of IgnitionStatus_CAN to perform mode transitions between INIT ACTIVE STANDBY FAIL_SAFE and SHUTDOWN.

**Rationale:** Derived from REQ-EPS-000. Source notes: Event-triggered on CAN signal change. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Mode Change Runnable' occurs.
- **Then:** RE_HandleModeChange shall execute on DataReceivedEvent of IgnitionStatus_CAN to perform mode transitions between INIT ACTIVE STANDBY FAIL_SAFE and SHUTDOWN.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_HandleModeChange, SWC_ElectricPowerSteering · test=TD-REQ-EPS-005

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-006 — Diagnostic Update Runnable

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_DiagnosticUpdate shall execute on DataReceivedEvent of DEM notification to write active DTCs to NVM via NvM_WriteBlock.

**Rationale:** Derived from REQ-EPS-000. Source notes: Event-triggered by DEM callback. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Diagnostic Update Runnable' occurs.
- **Then:** RE_DiagnosticUpdate shall execute on DataReceivedEvent of DEM notification to write active DTCs to NVM via NvM_WriteBlock.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_DiagnosticUpdate, SWC_ElectricPowerSteering · test=TD-REQ-EPS-006

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-007 — Required Ports

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC shall declare: RP_VehicleSpeed (Sender-Receiver IF_SR_VehicleSpeed) RP_IgnitionStatus (SR IF_SR_IgnitionStatus) RP_YawRate (SR IF_SR_YawRate) RP_TorqueSensorPrimary (SR IF_SR_TorqueSensor) RP_TorqueSensorSecondary (SR IF_SR_TorqueSensor) RP_MotorTemperature (SR IF_SR_Temperature).

**Rationale:** Derived from REQ-EPS-000. Source notes: All required ports follow AUTOSAR R-Port naming RP_. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Required Ports is exercised at its defined update rate.
- **Then:** SWC shall declare: RP_VehicleSpeed (Sender-Receiver IF_SR_VehicleSpeed) RP_IgnitionStatus (SR IF_SR_IgnitionStatus) RP_YawRate (SR IF_SR_YawRate) RP_TorqueSensorPrimary (SR IF_SR_TorqueSensor) RP_TorqueSensorSecondary (SR IF_SR_TorqueSensor) RP_MotorTemperature (SR IF_SR_Temperature). The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-007

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-008 — Provided Ports

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC shall declare: PP_MotorCurrentDemand (Sender-Receiver IF_SR_MotorCurrent) PP_EPSStatus (SR IF_SR_EPSStatus) PP_AssistLevel (SR IF_SR_AssistLevel).

**Rationale:** Derived from REQ-EPS-000. Source notes: All provided ports follow AUTOSAR P-Port naming PP_. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Provided Ports is exercised at its defined update rate.
- **Then:** SWC shall declare: PP_MotorCurrentDemand (Sender-Receiver IF_SR_MotorCurrent) PP_EPSStatus (SR IF_SR_EPSStatus) PP_AssistLevel (SR IF_SR_AssistLevel). The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-008

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-010 — Basic Torque Assist

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The system shall compute a torque assist force proportional to the measured driver steering torque from TorqueSensorPrimary using the calibrated base gain.

**Rationale:** Derived from REQ-EPS-000. Source notes: Base gain is calibration parameter stored in ROM. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Basic Torque Assist' occurs.
- **Then:** The system shall compute a torque assist force proportional to the measured driver steering torque from TorqueSensorPrimary using the calibrated base gain.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-010

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-011 — Speed-Dependent Gain Reduction

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Torque assist gain shall decrease linearly from base_gain at 0 km/h to 30% of base_gain at 40 km/h and continue decreasing to 10% of base_gain at 120 km/h.

**Rationale:** Derived from REQ-EPS-000. Source notes: Prevents oversteer at highway speeds. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Speed-Dependent Gain Reduction' occurs.
- **Then:** Torque assist gain shall decrease linearly from base_gain at 0 km/h to 30% of base_gain at 40 km/h and continue decreasing to 10% of base_gain at 120 km/h.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0 km/h` → -0.01, 0.0, 0.01
- `30%` → 29.99, 30.0, 30.01
- `40 km/h` → 39.99, 40.0, 40.01
- `10%` → 9.99, 10.0, 10.01
- `120 km/h` → 119.99, 120.0, 120.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-011

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-012 — Minimum Assist at High Speed

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** At vehicle speeds >= 120 km/h torque assist shall not exceed 10% of rated maximum assist torque regardless of driver input.

**Rationale:** Derived from REQ-EPS-000. Source notes: Safety limit for high-speed stability. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Minimum Assist at High Speed' occurs.
- **Then:** At vehicle speeds >= 120 km/h torque assist shall not exceed 10% of rated maximum assist torque regardless of driver input.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `120 km/h` → 119.99, 120.0, 120.01
- `10%` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-012

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-013 — Maximum Assist at Low Speed

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The system shall provide the calibrated maximum assist torque at vehicle speeds of 5 km/h or below to support parking manoeuvres.

**Rationale:** Low-speed parking assist: provide the calibrated maximum assist capacity at <=5 km/h.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Maximum Assist at Low Speed' occurs.
- **Then:** The system shall provide the calibrated maximum assist torque at vehicle speeds of 5 km/h or below to support parking manoeuvres.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 km/h` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-013

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Confirm the calibrated maximum assist torque and the 5 km/h boundary with the steering-feel calibration.

---

### REQ-EPS-014 — Friction Compensation

**Type:** functional · **ASIL:** QM · **Priority:** should · **Status:** review · **Verification:** test

**Statement:** The system shall add a friction compensation offset to the assist torque based on the rate of change of steering angle using the calibrated friction gain.

**Rationale:** Derived from REQ-EPS-000. Source notes: Reduces steering effort during angle change phases. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Friction Compensation' occurs.
- **Then:** The system shall add a friction compensation offset to the assist torque based on the rate of change of steering angle using the calibrated friction gain.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-014

**Open issues:** none

---

### REQ-EPS-015 — Active Return to Center

**Type:** functional · **ASIL:** QM · **Priority:** should · **Status:** review · **Verification:** test

**Statement:** When the driver releases the steering wheel (driver torque < 0.5 Nm for > 200ms) the system shall apply a centering torque proportional to steering angle to return the wheel to center.

**Rationale:** Derived from REQ-EPS-000. Source notes: Improves straight-line driving comfort. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Active Return to Center' occurs.
- **Then:** When the driver releases the steering wheel (driver torque < 0.5 Nm for > 200ms) the system shall apply a centering torque proportional to steering angle to return the wheel to center.
- **Tolerance:** ±0.01 N at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0.5 N` → 0.49, 0.5, 0.51
- `200ms` → 199.99, 200.0, 200.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-015

**Open issues:** none

---

### REQ-EPS-016 — End-Stop Protection

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the steering angle exceeds 90% of the mechanical end-stop limit the system shall reduce assist torque linearly to zero at 100% end-stop limit to prevent mechanical damage.

**Rationale:** Derived from REQ-EPS-000. Source notes: Prevents damage to steering rack at mechanical limits. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'End-Stop Protection' occurs.
- **Then:** When the steering angle exceeds 90% of the mechanical end-stop limit the system shall reduce assist torque linearly to zero at 100% end-stop limit to prevent mechanical damage.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `90%` → 89.99, 90.0, 90.01
- `100%` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-016

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-017 — Active Damping

**Type:** functional · **ASIL:** QM · **Priority:** should · **Status:** review · **Verification:** test

**Statement:** The system shall apply an active damping torque opposing the rate of change of motor speed using the calibrated damping gain.

**Rationale:** Derived from REQ-EPS-000. Source notes: Prevents shimmy and oscillation on rough roads. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Active Damping' occurs.
- **Then:** The system shall apply an active damping torque opposing the rate of change of motor speed using the calibrated damping gain.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-017

**Open issues:** none

---

### REQ-EPS-018 — Road Camber Compensation

**Type:** functional · **ASIL:** QM · **Priority:** could · **Status:** review · **Verification:** test

**Statement:** The system shall detect and compensate for steady-state torque offset caused by road camber by applying a slow-adapting offset cancellation filter with time constant 5s.

**Rationale:** Derived from REQ-EPS-000. Source notes: Optional comfort feature to reduce driver fatigue. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Road Camber Compensation' occurs.
- **Then:** The system shall detect and compensate for steady-state torque offset caused by road camber by applying a slow-adapting offset cancellation filter with time constant 5s.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5s` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-018

**Open issues:** none

---

### REQ-EPS-019 — Motor Current Calculation

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The system shall convert the computed assist torque demand to a motor current setpoint using the calibrated motor torque constant.

**Rationale:** Derived from REQ-EPS-000. Source notes: Must account for motor efficiency curve at different speeds. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Motor Current Calculation' occurs.
- **Then:** The system shall convert the computed assist torque demand to a motor current setpoint using the calibrated motor torque constant.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-019

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-020 — Torque Demand Rate Limiter

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The rate of change of total torque assist demand shall be limited to 500 Nm/s using a first-order rate limiter to prevent abrupt steering responses.

**Rationale:** Torque-demand rate limit for smooth steering response. This is duplicated by REQ-EPS-040; keep one after review.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Torque Demand Rate Limiter' occurs.
- **Then:** The rate of change of total torque assist demand shall be limited to 500 Nm/s using a first-order rate limiter to prevent abrupt steering responses.
- **Tolerance:** ±0.01 N at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `500 N` → 499.99, 500.0, 500.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-020

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Duplicate 500 Nm/s limit with REQ-EPS-040; consolidate into one requirement and delete the duplicate.

---

### REQ-EPS-021 — Low Speed Maneuvering Boost

**Type:** functional · **ASIL:** QM · **Priority:** should · **Status:** review · **Verification:** test

**Statement:** At vehicle speeds below 10 km/h the system shall apply an additional gain factor of 1.5x to the computed assist torque to ease low-speed maneuvering and parking.

**Rationale:** Derived from REQ-EPS-000. Source notes: Parking boost improves user experience. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Low Speed Maneuvering Boost' occurs.
- **Then:** At vehicle speeds below 10 km/h the system shall apply an additional gain factor of 1.5x to the computed assist torque to ease low-speed maneuvering and parking.
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 km/h` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-021

**Open issues:** QM requirement adds 1.5x assist below 10 km/h; confirm the ASIL/QM classification because it changes steering torque.

---

### REQ-EPS-022 — High Speed Stability Assist

**Type:** functional · **ASIL:** QM · **Priority:** could · **Status:** review · **Verification:** test

**Statement:** At vehicle speeds above 100 km/h the system shall apply a lane-keeping assist correction torque based on yaw rate deviation from expected value. Correction = k_hs * (yaw_measured - yaw_expected).

**Rationale:** Derived from REQ-EPS-000. Source notes: Advanced feature requires yaw rate signal. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'High Speed Stability Assist' occurs.
- **Then:** At vehicle speeds above 100 km/h the system shall apply a lane-keeping assist correction torque based on yaw rate deviation from expected value. Correction = k_hs * (yaw_measured - yaw_expected).
- **Tolerance:** ±0.01 km/h at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100 km/h` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-022

**Open issues:** QM requirement adds a lane-keeping correction torque above 100 km/h; confirm the ASIL/QM classification and the yaw-rate reference.

---

### REQ-EPS-023 — Steering Angle Rate Limit

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The rate of change of the commanded steering angle shall not exceed 720 deg/s to prevent mechanical shock loads on the steering rack.

**Rationale:** Derived from REQ-EPS-000. Source notes: Protects steering rack from high-speed angle transients. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Steering Angle Rate Limit' occurs and persists for the specified debounce.
- **Then:** The rate of change of the commanded steering angle shall not exceed 720 deg/s to prevent mechanical shock loads on the steering rack. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-023

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; ASIL-B rate limit of 720 deg/s; confirm the mechanical limit and the ASIL allocation.

---

### REQ-EPS-024 — Torque Sensor Signal Processing

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The driver torque sensor signal from RP_TorqueSensorPrimary shall be low-pass filtered with the specified filter order and cutoff frequency before use in assist computation.

**Rationale:** Derived from REQ-EPS-000. Source notes: Noise rejection critical for stable control. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Torque Sensor Signal Processing' occurs.
- **Then:** The driver torque sensor signal from RP_TorqueSensorPrimary shall be low-pass filtered with the specified filter order and cutoff frequency before use in assist computation.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-024

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-030 — System Operating Modes

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SWC_ElectricPowerSteering shall implement the following operating modes managed by RE_HandleModeChange: INIT ACTIVE STANDBY FAIL_SAFE SHUTDOWN.

**Rationale:** Derived from REQ-EPS-000. Source notes: Mode is stored as internal state variable. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'System Operating Modes' occurs.
- **Then:** SWC_ElectricPowerSteering shall implement the following operating modes managed by RE_HandleModeChange: INIT ACTIVE STANDBY FAIL_SAFE SHUTDOWN.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_HandleModeChange, SWC_ElectricPowerSteering · test=TD-REQ-EPS-030

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-031 — Transition INIT to ACTIVE

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The system shall transition from INIT to ACTIVE mode when: (a) all sensor signals are valid (b) supply voltage >= 9V (c) motor temperature < 80 degrees Celsius and (d) RAM/ROM self-test passed.

**Rationale:** Derived from REQ-EPS-000. Source notes: All conditions must hold simultaneously for exactly one evaluation cycle. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Transition INIT to ACTIVE' occurs.
- **Then:** The system shall transition from INIT to ACTIVE mode when: (a) all sensor signals are valid (b) supply voltage >= 9V (c) motor temperature < 80 degrees Celsius and (d) RAM/ROM self-test passed.
- **Tolerance:** ±0.01 V at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `9V` → 8.99, 9.0, 9.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-031

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-032 — Transition to STANDBY

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The system shall transition to STANDBY mode when IgnitionStatus_CAN transitions from ON to OFF.

**Rationale:** Derived from REQ-EPS-000. Source notes: Graceful power-down prevents jerk on ignition off; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Transition to STANDBY' occurs.
- **Then:** The system shall transition to STANDBY mode when IgnitionStatus_CAN transitions from ON to OFF.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-032

**Split into:** REQ-EPS-1006

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1006; the original ID retains part 1.

---

### REQ-EPS-033 — Transition to FAIL_SAFE

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The system shall immediately transition to FAIL_SAFE mode when any of the following conditions are detected: sensor plausibility failure motor current > 70A motor temp > 80C supply voltage < 9V watchdog timeout or CAN timeout > 50ms.

**Rationale:** FAIL_SAFE triggers: sensor plausibility, overcurrent, overtemperature, undervoltage, watchdog timeout, CAN timeout. The source uses a single OR condition; it is retained as one reaction requirement.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Transition to FAIL_SAFE' occurs and persists for the specified debounce.
- **Then:** The system shall immediately transition to FAIL_SAFE mode when any of the following conditions are detected: sensor plausibility failure motor current > 70A motor temp > 80C supply voltage < 9V watchdog timeout or CAN timeout > 50ms. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 A at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `70A` → 69.99, 70.0, 70.01
- `9V` → 8.99, 9.0, 9.01
- `50ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-033

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Confirm each FAIL_SAFE trigger and its debounce/reaction time; the source groups six conditions without individual timing.

---

### REQ-EPS-034 — Transition to SHUTDOWN

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The system shall transition to SHUTDOWN from any mode when ECU power is removed or when explicit shutdown command received.

**Rationale:** Derived from REQ-EPS-000. Source notes: Power loss handled by hardware; SWC handles graceful shutdown signal; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Transition to SHUTDOWN' occurs.
- **Then:** The system shall transition to SHUTDOWN from any mode when ECU power is removed or when explicit shutdown command received.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-034

**Split into:** REQ-EPS-1007

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1007; the original ID retains part 1.

---

### REQ-EPS-035 — STANDBY Mode Behavior

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** In STANDBY mode the system shall hold motor current demand at zero.

**Rationale:** Derived from REQ-EPS-000. Source notes: Sensor monitoring in STANDBY detects re-activation conditions; split into 3 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'STANDBY Mode Behavior' occurs.
- **Then:** In STANDBY mode the system shall hold motor current demand at zero.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-035

**Split into:** REQ-EPS-1008, REQ-EPS-1009

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1008, REQ-EPS-1009; the original ID retains part 1.

---

### REQ-EPS-036 — FAIL_SAFE Limp Home Mode

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** In FAIL_SAFE mode the system shall provide reduced assist at maximum 20% of rated capacity to allow the driver to complete the journey.

**Rationale:** FAIL_SAFE limp-home: 20% of rated assist, 14 A current limit (20% of 70 A).

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'FAIL_SAFE Limp Home Mode' occurs.
- **Then:** In FAIL_SAFE mode the system shall provide reduced assist at maximum 20% of rated capacity to allow the driver to complete the journey.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `20%` → 19.99, 20.0, 20.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-036

**Split into:** REQ-EPS-1010

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1010; the original ID retains part 1.

---

### REQ-EPS-037 — Mode Transition Timing

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** All mode transitions shall complete (outputs stabilized at new mode setpoints) within 50 ms of the triggering condition being detected.

**Rationale:** Derived from REQ-EPS-000. Source notes: Worst-case includes 10 control cycles at 5ms each. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The defined trigger occurs.
- **Then:** All mode transitions shall complete (outputs stabilized at new mode setpoints) within 50 ms of the triggering condition being detected. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `50 ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-037

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Cycle period is not specified; confirm the scheduling contract.

---

### REQ-EPS-040 — Torque Gradient Safety Limit

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The rate of change of assist torque output shall never exceed 500 Nm/s. This limit is enforced in every execution of RE_ControlTorque independently of mode.

**Rationale:** Rate limit of 500 Nm/s enforced every RE_ControlTorque execution, independent of mode.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Torque Gradient Safety Limit' occurs and persists for the specified debounce.
- **Then:** The rate of change of assist torque output shall never exceed 500 Nm/s. This limit is enforced in every execution of RE_ControlTorque independently of mode. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 N at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `500 N` → 499.99, 500.0, 500.01

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, SWC_ElectricPowerSteering · test=TD-REQ-EPS-040

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Duplicate 500 Nm/s limit with REQ-EPS-020; consolidate into one requirement and delete the duplicate.

---

### REQ-EPS-041 — Redundant Sensor Plausibility Check

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall compare TorqueSensorPrimary and TorqueSensorSecondary values every 10ms.

**Rationale:** Derived from REQ-EPS-000. Source notes: 3-cycle debounce prevents false positives from transient noise; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Redundant Sensor Plausibility Check' occurs.
- **Then:** RE_MonitorSafety shall compare TorqueSensorPrimary and TorqueSensorSecondary values every 10ms.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-041

**Split into:** REQ-EPS-1011

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1011; the original ID retains part 1.

---

### REQ-EPS-042 — Motor Current Hard Limit

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Software shall limit motor current demand to <= 70A at all times. The hardware overcurrent protection triggers at 80A.

**Rationale:** Software current limit 70 A; hardware overcurrent protection at 80 A. The 10 A margin is the protection hierarchy.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Motor Current Hard Limit' occurs and persists for the specified debounce.
- **Then:** Software shall limit motor current demand to <= 70A at all times. The hardware overcurrent protection triggers at 80A. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 A at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `70A` → 69.99, 70.0, 70.01
- `80A` → 79.99, 80.0, 80.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-042

**Split into:** REQ-EPS-1012

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Confirm the 70 A software / 80 A hardware coordination and the >100 ms DTC debounce.; Split into REQ-EPS-1012; the original ID retains part 1.

---

### REQ-EPS-043 — Thermal Protection

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall monitor RP_MotorTemperature every 10ms.

**Rationale:** Thermal protection: linear derating above 80 C (5% per degree) and disable above 100 C. The source classifies this as ASIL-B while REQ-EPS-033 lists >80 C as a FAIL_SAFE trigger; reconcile.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Thermal Protection' occurs.
- **Then:** RE_MonitorSafety shall monitor RP_MotorTemperature every 10ms.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-043

**Split into:** REQ-EPS-1013, REQ-EPS-1014

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Reconcile the ASIL-B thermal requirement with the ASIL-D FAIL_SAFE trigger at >80 C; define the derating-to-disable transition.; Split into REQ-EPS-1013, REQ-EPS-1014; the original ID retains part 1.

---

### REQ-EPS-044 — Supply Voltage Monitoring

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall monitor ECU supply voltage every 10ms.

**Rationale:** Undervoltage protection below 9.0 V for 5 cycles; automatic recovery above 10.5 V.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Supply Voltage Monitoring' occurs.
- **Then:** RE_MonitorSafety shall monitor ECU supply voltage every 10ms.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-044

**Split into:** REQ-EPS-1015, REQ-EPS-1016

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1015, REQ-EPS-1016; the original ID retains part 1.

---

### REQ-EPS-045 — Watchdog Supervision

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The SWC shall trigger the hardware watchdog via Rte_Call every 5ms within RE_ControlTorque.

**Rationale:** Hardware watchdog trigger every 5 ms in RE_ControlTorque; reset cause is checked on startup.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Supervision' occurs and persists for the specified debounce.
- **Then:** The SWC shall trigger the hardware watchdog via Rte_Call every 5ms within RE_ControlTorque. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, SWC_ElectricPowerSteering · test=TD-REQ-EPS-045

**Split into:** REQ-EPS-1017, REQ-EPS-1018

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Split into REQ-EPS-1017, REQ-EPS-1018; the original ID retains part 1.

---

### REQ-EPS-046 — CAN Signal End-to-End Protection

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** All safety-relevant CAN input signals (VehicleSpeed IgnitionStatus TorqueSensors) shall be protected by E2E Profile 2 as per AUTOSAR E2E library.

**Rationale:** E2E Profile 2 protection on safety-relevant CAN inputs; counter mismatch triggers a CAN-timeout DTC after 2 consecutive failures.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'CAN Signal End-to-End Protection' occurs.
- **Then:** All safety-relevant CAN input signals (VehicleSpeed IgnitionStatus TorqueSensors) shall be protected by E2E Profile 2 as per AUTOSAR E2E library.
- **Tolerance:** ±0.01 a at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `2 a` → 1.99, 2.0, 2.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-046

**Split into:** REQ-EPS-1019

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Reconcile the 2-failure E2E reaction with REQ-EPS-054 (50 ms / 5 cycles) and define the debounce.; Split into REQ-EPS-1019; the original ID retains part 1.

---

### REQ-EPS-047 — Startup Self-Test

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_Initialize shall perform RAM checksum test and ROM CRC-32 verification on startup.

**Rationale:** Startup RAM/ROM self-test; a failure drives permanent FAIL_SAFE until service.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Startup Self-Test' occurs.
- **Then:** RE_Initialize shall perform RAM checksum test and ROM CRC-32 verification on startup.
- **Tolerance:** ±0.01 v at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `-32 v` → -32.01, -32.0, -31.99

**Trace:** parent=REQ-EPS-000 · design=RE_Initialize, SWC_ElectricPowerSteering · test=TD-REQ-EPS-047

**Split into:** REQ-EPS-1020

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1020; the original ID retains part 1.

---

### REQ-EPS-048 — Stack Overflow Detection

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The OS configuration shall assign stack guard regions to all EPS tasks.

**Rationale:** Derived from REQ-EPS-000. Source notes: AUTOSAR OS stack monitoring feature; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Stack Overflow Detection' occurs.
- **Then:** The OS configuration shall assign stack guard regions to all EPS tasks.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-048

**Split into:** REQ-EPS-1021

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1021; the original ID retains part 1.

---

### REQ-EPS-049 — CPU Load Monitoring

**Type:** constraint · **ASIL:** QM · **Priority:** should · **Status:** review · **Verification:** review

**Statement:** RE_MonitorSafety shall measure execution time of RE_ControlTorque each cycle.

**Rationale:** CPU-load monitoring; warning DTC at 80% average over 100 cycles and NVM profiling data.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** RE_MonitorSafety shall measure execution time of RE_ControlTorque each cycle. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-049

**Split into:** REQ-EPS-1022

**Open issues:** Split into REQ-EPS-1022; the original ID retains part 1.

---

### REQ-EPS-050 — DTC Sensor Failure

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC_EPS_SENSOR_FAIL (0x910001) shall be reported to DEM via Dem_ReportErrorStatus when TorqueSensorPrimary and TorqueSensorSecondary disagree by > 2.0 Nm for 3 consecutive 10ms cycles.

**Rationale:** Derived from REQ-EPS-000. Source notes: DTC is ASIL-D classified - requires confirmed failure before set. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Sensor Failure' occurs.
- **Then:** DTC_EPS_SENSOR_FAIL (0x910001) shall be reported to DEM via Dem_ReportErrorStatus when TorqueSensorPrimary and TorqueSensorSecondary disagree by > 2.0 Nm for 3 consecutive 10ms cycles.
- **Tolerance:** ±0.01 N at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `2.0 N` → 1.99, 2.0, 2.01
- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-050

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-051 — DTC Overcurrent

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC_EPS_OVERCURRENT (0x910002) shall be reported when motor current demand reaches the 70A software limit for more than 100ms.

**Rationale:** Derived from REQ-EPS-000. Source notes: Immediate NVM storage prevents data loss on power cycle; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Overcurrent' occurs.
- **Then:** DTC_EPS_OVERCURRENT (0x910002) shall be reported when motor current demand reaches the 70A software limit for more than 100ms.
- **Tolerance:** ±0.01 A at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `70A` → 69.99, 70.0, 70.01
- `100ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-051

**Split into:** REQ-EPS-1023

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1023; the original ID retains part 1.

---

### REQ-EPS-052 — DTC Overheat

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC_EPS_OVERHEAT (0x910003) shall be reported when motor temperature exceeds 80 degrees Celsius.

**Rationale:** Derived from REQ-EPS-000. Source notes: Snapshot data aids field diagnostics; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Overheat' occurs.
- **Then:** DTC_EPS_OVERHEAT (0x910003) shall be reported when motor temperature exceeds 80 degrees Celsius.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-052

**Split into:** REQ-EPS-1024

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1024; the original ID retains part 1.

---

### REQ-EPS-053 — DTC Undervoltage

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC_EPS_UNDERVOLTAGE (0x910004) shall be reported when supply voltage drops below 9.0V.

**Rationale:** Derived from REQ-EPS-000. Source notes: Undervoltage most common EPS field complaint - snapshot critical; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Undervoltage' occurs.
- **Then:** DTC_EPS_UNDERVOLTAGE (0x910004) shall be reported when supply voltage drops below 9.0V.
- **Tolerance:** ±0.01 V at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `9.0V` → 8.99, 9.0, 9.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-053

**Split into:** REQ-EPS-1025

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1025; the original ID retains part 1.

---

### REQ-EPS-054 — DTC CAN Timeout

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC_EPS_CAN_TIMEOUT (0x910005) shall be reported when any safety-relevant CAN signal is absent or fails E2E check for more than 50ms (5 cycles at 10ms CAN cycle).

**Rationale:** Derived from REQ-EPS-000. Source notes: CAN timeout must account for worst-case bus recovery time. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC CAN Timeout' occurs.
- **Then:** DTC_EPS_CAN_TIMEOUT (0x910005) shall be reported when any safety-relevant CAN signal is absent or fails E2E check for more than 50ms (5 cycles at 10ms CAN cycle).
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `50ms` → 49.99, 50.0, 50.01
- `5 cycles` → 4.99, 5.0, 5.01
- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-054

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-055 — DTC NVM Storage

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** All DTCs shall be stored in NVM via Dem_SetEventStatus followed by NvM_WriteBlock within the same RE_DiagnosticUpdate execution cycle to ensure fault persistence across power cycles.

**Rationale:** DTC persistence in the same RE_DiagnosticUpdate cycle; confirm whether NvM write can complete in the diagnostic event window.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC NVM Storage' occurs.
- **Then:** All DTCs shall be stored in NVM via Dem_SetEventStatus followed by NvM_WriteBlock within the same RE_DiagnosticUpdate execution cycle to ensure fault persistence across power cycles.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_DiagnosticUpdate, SWC_ElectricPowerSteering · test=TD-REQ-EPS-055

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-056 — DTC Healing Condition

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** All healable DTCs (0x910001 through 0x910005) shall be cleared automatically after 3 consecutive fault-free evaluation cycles with no recurrence of the triggering condition.

**Rationale:** Derived from REQ-EPS-000. Source notes: Healing counter reset on each fault detection. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Healing Condition' occurs.
- **Then:** All healable DTCs (0x910001 through 0x910005) shall be cleared automatically after 3 consecutive fault-free evaluation cycles with no recurrence of the triggering condition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-056

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-060 — Vehicle Speed CAN Input

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** VehicleSpeed signal shall be received on CAN via RP_VehicleSpeed with range 0-250 km/h resolution 0.01 km/h and a 10ms transmission cycle.

**Rationale:** Vehicle-speed CAN input, 0-250 km/h, 0.01 km/h, 10 ms; loss >50 ms triggers CAN timeout.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Vehicle Speed CAN Input is exercised at its defined update rate.
- **Then:** VehicleSpeed signal shall be received on CAN via RP_VehicleSpeed with range 0-250 km/h resolution 0.01 km/h and a 10ms transmission cycle. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 km/h (one resolution step)

**Boundary values:**

- `250 km/h` → 249.99, 250.0, 250.01
- `0.01 km/h` → 0.0, 0.01, 0.02
- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-060

**Split into:** REQ-EPS-1026

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.; Split into REQ-EPS-1026; the original ID retains part 1.

---

### REQ-EPS-061 — Ignition Status CAN Input

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** IgnitionStatus signal shall be received via RP_IgnitionStatus as a boolean (ON/OFF) with 20ms transmission cycle. Signal is E2E protected with Profile 2.

**Rationale:** Ignition-status CAN input, boolean, 20 ms, E2E Profile 2.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Ignition Status CAN Input is exercised at its defined update rate.
- **Then:** IgnitionStatus signal shall be received via RP_IgnitionStatus as a boolean (ON/OFF) with 20ms transmission cycle. Signal is E2E protected with Profile 2. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `20ms` → 19.99, 20.0, 20.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-061

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-062 — Yaw Rate CAN Input

**Type:** interface · **ASIL:** QM · **Priority:** should · **Status:** review · **Verification:** review

**Statement:** YawRate signal shall be received via RP_YawRate with range -100 to +100 deg/s resolution 0.01 deg/s and 10ms transmission cycle for high-speed stability function.

**Rationale:** Yaw-rate CAN input, -100 to +100 deg/s, 0.01 deg/s, 10 ms; supports the high-speed stability function.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Yaw Rate CAN Input is exercised at its defined update rate.
- **Then:** YawRate signal shall be received via RP_YawRate with range -100 to +100 deg/s resolution 0.01 deg/s and 10ms transmission cycle for high-speed stability function. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 deg/s (one resolution step)

**Boundary values:**

- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-062

**Open issues:** Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-063 — Primary Torque Sensor Interface

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** TorqueSensorPrimary signal shall be received via RP_TorqueSensorPrimary from a direct SPI interface with range -25 to +25 Nm resolution 0.01 Nm and 1ms acquisition cycle.

**Rationale:** Primary torque sensor: direct SPI, -25 to +25 Nm, 0.01 Nm, 1 ms; filtered before use.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Primary Torque Sensor Interface is exercised at its defined update rate.
- **Then:** TorqueSensorPrimary signal shall be received via RP_TorqueSensorPrimary from a direct SPI interface with range -25 to +25 Nm resolution 0.01 Nm and 1ms acquisition cycle. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 Nm (one resolution step)

**Boundary values:**

- `25 N` → 24.99, 25.0, 25.01
- `0.01 N` → 0.0, 0.01, 0.02
- `1ms` → 0.99, 1.0, 1.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-063

**Split into:** REQ-EPS-1027

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.; Split into REQ-EPS-1027; the original ID retains part 1.

---

### REQ-EPS-064 — Secondary Torque Sensor Interface

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** TorqueSensorSecondary shall provide a fully redundant torque measurement via RP_TorqueSensorSecondary with identical range and resolution to the primary sensor but using an independent SPI bus and different physical sensor element.

**Rationale:** Secondary torque sensor: redundant measurement, identical range/resolution, independent SPI bus and physical element.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Secondary Torque Sensor Interface is exercised at its defined update rate.
- **Then:** TorqueSensorSecondary shall provide a fully redundant torque measurement via RP_TorqueSensorSecondary with identical range and resolution to the primary sensor but using an independent SPI bus and different physical sensor element. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-064

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-065 — Motor Current Output

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** MotorCurrentDemand shall be written via PP_MotorCurrentDemand with range 0-70A resolution 0.1A and updated every 5ms in RE_ControlTorque. The motor controller ECU reads this signal via CAN to command the motor drive.

**Rationale:** Motor-current demand output, 0-70 A, 0.1 A, 5 ms.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Motor Current Output is exercised at its defined update rate.
- **Then:** MotorCurrentDemand shall be written via PP_MotorCurrentDemand with range 0-70A resolution 0.1A and updated every 5ms in RE_ControlTorque. The motor controller ECU reads this signal via CAN to command the motor drive. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.1 A (one resolution step)

**Boundary values:**

- `70A` → 69.99, 70.0, 70.01
- `0.1A` → 0.09, 0.1, 0.11
- `5ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, SWC_ElectricPowerSteering · test=TD-REQ-EPS-065

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-066 — EPS Status CAN Output

**Type:** interface · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** EPSStatus shall be written via PP_EPSStatus every 10ms containing: current_mode (4 bits) active_dtc_count (8 bits) assist_level_percent (8 bits) and system_health (4 bits). This data is used by the instrument cluster and gateway.

**Rationale:** EPS status output every 10 ms with mode, DTC count, assist level and health.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** EPS Status CAN Output is exercised at its defined update rate.
- **Then:** EPSStatus shall be written via PP_EPSStatus every 10ms containing: current_mode (4 bits) active_dtc_count (8 bits) assist_level_percent (8 bits) and system_health (4 bits). This data is used by the instrument cluster and gateway. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-066

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-801 — Torque Sensor Loss Safe State

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When both torque-sensor channels are invalid or disagree beyond the calibrated tolerance for more than 30 ms, the EPS shall enter FAIL_SAFE and limit motor current to the calibrated limp-home value.

**Rationale:** The source defines a plausibility check but not the both-channel-loss safe state and timing.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Torque Sensor Loss Safe State' occurs and persists for the specified debounce.
- **Then:** When both torque-sensor channels are invalid or disagree beyond the calibrated tolerance for more than 30 ms, the EPS shall enter FAIL_SAFE and limit motor current to the calibrated limp-home value. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `30 ms` → 29.99, 30.0, 30.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-801

**Open issues:** 30 ms reaction and limp-home current are proposed; confirm with the EPS safety analysis.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-802 — Motor Position Sensor Loss

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the motor position sensor is invalid for more than 20 ms, the EPS shall disable field-oriented control and enter FAIL_SAFE.

**Rationale:** The source set does not cover loss of motor position feedback, which is required for safe torque control.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Motor Position Sensor Loss' occurs and persists for the specified debounce.
- **Then:** When the motor position sensor is invalid for more than 20 ms, the EPS shall disable field-oriented control and enter FAIL_SAFE. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `20 ms` → 19.99, 20.0, 20.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-802

**Open issues:** Confirm the position-sensor interface, detection window and FAIL_SAFE reaction.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-803 — Vehicle Speed Signal Loss

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the vehicle-speed signal is invalid or lost for more than 50 ms, the EPS shall limit assist to the calibrated limp-home value and set a CAN-timeout DTC.

**Rationale:** The source defines CAN-timeout detection but not the assist limitation during loss of vehicle speed.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Vehicle Speed Signal Loss' occurs and persists for the specified debounce.
- **Then:** When the vehicle-speed signal is invalid or lost for more than 50 ms, the EPS shall limit assist to the calibrated limp-home value and set a CAN-timeout DTC. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `50 ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-803

**Open issues:** Confirm the limp-home assist value and recovery condition after speed returns.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-804 — Watchdog Reset Recovery

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** After an ECU reset caused by the hardware watchdog, the EPS shall remain in FAIL_SAFE until the startup self-test passes and the reset cause is recorded.

**Rationale:** The source detects watchdog expiry but does not define the post-reset safe-state and recovery condition.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Reset Recovery' occurs and persists for the specified debounce.
- **Then:** After an ECU reset caused by the hardware watchdog, the EPS shall remain in FAIL_SAFE until the startup self-test passes and the reset cause is recorded. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-804

**Open issues:** Confirm the reset-cause register mapping and the self-test pass criteria.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-805 — Safe State per Fault Class

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The EPS shall map each safety-relevant fault class to a defined safe state (assist disabled, limp-home, or controlled shutdown).

**Rationale:** The source uses FAIL_SAFE as a single state but does not define fault-class-specific safe states.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Safe State per Fault Class' occurs and persists for the specified debounce.
- **Then:** The EPS shall map each safety-relevant fault class to a defined safe state (assist disabled, limp-home, or controlled shutdown). The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-805

**Split into:** REQ-EPS-1029

**Open issues:** The fault-class-to-safe-state table must come from the safety analysis.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Split into REQ-EPS-1029; the original ID retains part 1.

---

### REQ-EPS-806 — Thermal Derating to Disable Transition

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The EPS shall transition from thermal derating to motor disable when motor temperature exceeds 100 C.

**Rationale:** The source defines 80 C derating and 100 C disable but not the recovery threshold or re-enable condition.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Thermal Derating to Disable Transition' occurs.
- **Then:** The EPS shall transition from thermal derating to motor disable when motor temperature exceeds 100 C.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-806

**Split into:** REQ-EPS-1030

**Open issues:** Confirm the recovery threshold and hysteresis with the thermal/steering-feel calibration.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1030; the original ID retains part 1.

---

### REQ-EPS-807 — Calibration Verification

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** At startup and after a calibration update, the EPS shall verify that every safety-relevant calibration parameter is within its declared range and consistent with the steering variant.

**Rationale:** The source exposes calibration parameters but does not require verification.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Calibration Verification' occurs.
- **Then:** At startup and after a calibration update, the EPS shall verify that every safety-relevant calibration parameter is within its declared range and consistent with the steering variant.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-807

**Open issues:** Define the safety-relevant calibration list and variant matrix.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-808 — Steering Variant Configuration

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The EPS shall select its assist map, torque constant, current limit and end-stop limits from a validated steering-variant configuration.

**Rationale:** The source uses vehicle-dependent parameters but does not define variant selection.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The EPS shall select its assist map, torque constant, current limit and end-stop limits from a validated steering-variant configuration. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-808

**Open issues:** Define the variant matrix and configuration source.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-809 — Software and Calibration Update Integrity

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The EPS shall only accept authenticated and integrity-protected software and calibration updates.

**Rationale:** A safety-critical steering function needs update integrity; the source set does not address cybersecurity.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The EPS shall only accept authenticated and integrity-protected software and calibration updates. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-809

**Split into:** REQ-EPS-1031

**Open issues:** Develop the full ISO 21434 cybersecurity requirements; this is a placeholder.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1031; the original ID retains part 1.

---

### REQ-EPS-810 — Fault Injection and Observability

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The EPS shall expose test hooks to inject torque-sensor loss, position-sensor loss, CAN timeout, undervoltage and overtemperature faults.

**Rationale:** Verification of the safety mechanisms needs controllability and observability.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The EPS shall expose test hooks to inject torque-sensor loss, position-sensor loss, CAN timeout, undervoltage and overtemperature faults. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-810

**Split into:** REQ-EPS-1032

**Open issues:** Confirm the production-disable mechanism for the test hooks.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1032; the original ID retains part 1.

---

### REQ-EPS-1001 — EPS SWC Architecture — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SWC_ElectricPowerSteering shall own the runnables RE_Initialize (startup event), RE_ControlTorque (5 ms timing event), RE_MonitorSafety (10 ms timing event), RE_HandleModeChange (DataReceivedEvent on RP_IgnitionStatus), and RE_DiagnosticUpdate (diagnostic event).

**Rationale:** EPS software architecture allocation. The source bundles architecture, runnables, ports, modes and a fail-safe reaction in one requirement; the hardening pass splits it into atomic parts. Split from REQ-EPS-001.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EPS SWC Architecture — Part 2' occurs.
- **Then:** SWC_ElectricPowerSteering shall own the runnables RE_Initialize (startup event), RE_ControlTorque (5 ms timing event), RE_MonitorSafety (10 ms timing event), RE_HandleModeChange (DataReceivedEvent on RP_IgnitionStatus), and RE_DiagnosticUpdate (diagnostic event).
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, RE_DiagnosticUpdate, RE_HandleModeChange, RE_Initialize, RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1001

**Split from:** `REQ-EPS-001`

**Open issues:** Split from REQ-EPS-001; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1002 — EPS SWC Architecture — Part 3

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SWC_ElectricPowerSteering shall read VehicleSpeed, IgnitionStatus, YawRate, TorqueSensorPrimary, TorqueSensorSecondary, and MotorTemperature through the required ports RP_VehicleSpeed, RP_IgnitionStatus, RP_YawRate, RP_TorqueSensorPrimary, RP_TorqueSensorSecondary, and RP_MotorTemperature.

**Rationale:** EPS software architecture allocation. The source bundles architecture, runnables, ports, modes and a fail-safe reaction in one requirement; the hardening pass splits it into atomic parts. Split from REQ-EPS-001.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EPS SWC Architecture — Part 3' occurs.
- **Then:** SWC_ElectricPowerSteering shall read VehicleSpeed, IgnitionStatus, YawRate, TorqueSensorPrimary, TorqueSensorSecondary, and MotorTemperature through the required ports RP_VehicleSpeed, RP_IgnitionStatus, RP_YawRate, RP_TorqueSensorPrimary, RP_TorqueSensorSecondary, and RP_MotorTemperature.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, RE_DiagnosticUpdate, RE_HandleModeChange, RE_Initialize, RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1002

**Split from:** `REQ-EPS-001`

**Open issues:** Split from REQ-EPS-001; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1003 — EPS SWC Architecture — Part 4

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SWC_ElectricPowerSteering shall publish MotorCurrentDemand, EPSStatus, and AssistLevel through the provided ports PP_MotorCurrentDemand, PP_EPSStatus, and PP_AssistLevel.

**Rationale:** EPS software architecture allocation. The source bundles architecture, runnables, ports, modes and a fail-safe reaction in one requirement; the hardening pass splits it into atomic parts. Split from REQ-EPS-001.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EPS SWC Architecture — Part 4' occurs.
- **Then:** SWC_ElectricPowerSteering shall publish MotorCurrentDemand, EPSStatus, and AssistLevel through the provided ports PP_MotorCurrentDemand, PP_EPSStatus, and PP_AssistLevel.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, RE_DiagnosticUpdate, RE_HandleModeChange, RE_Initialize, RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1003

**Split from:** `REQ-EPS-001`

**Open issues:** Split from REQ-EPS-001; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1004 — EPS SWC Architecture — Part 5

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** During ACTIVE mode the SWC shall execute torque calculation every 5 ms and safety supervision every 10 ms.

**Rationale:** EPS software architecture allocation. The source bundles architecture, runnables, ports, modes and a fail-safe reaction in one requirement; the hardening pass splits it into atomic parts. Split from REQ-EPS-001.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EPS SWC Architecture — Part 5' occurs.
- **Then:** During ACTIVE mode the SWC shall execute torque calculation every 5 ms and safety supervision every 10 ms.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, RE_DiagnosticUpdate, RE_HandleModeChange, RE_Initialize, RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1004

**Split from:** `REQ-EPS-001`

**Open issues:** Split from REQ-EPS-001; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1005 — EPS SWC Architecture — Part 6

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** During FAIL_SAFE mode the SWC shall clamp MotorCurrentDemand to 14 A maximum (20 percent of the 70 A rated current) and report the active DTC through DEM within one 10 ms monitoring cycle.

**Rationale:** EPS software architecture allocation. The source bundles architecture, runnables, ports, modes and a fail-safe reaction in one requirement; the hardening pass splits it into atomic parts. Split from REQ-EPS-001.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EPS SWC Architecture — Part 6' occurs.
- **Then:** During FAIL_SAFE mode the SWC shall clamp MotorCurrentDemand to 14 A maximum (20 percent of the 70 A rated current) and report the active DTC through DEM within one 10 ms monitoring cycle.
- **Tolerance:** ±0.01 A at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `14 A` → 13.99, 14.0, 14.01
- `70 A` → 69.99, 70.0, 70.01
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, RE_DiagnosticUpdate, RE_HandleModeChange, RE_Initialize, RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1005

**Split from:** `REQ-EPS-001`

**Open issues:** Split from REQ-EPS-001; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1006 — Transition to STANDBY — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Motor current output shall be ramped to zero over 500ms before entering STANDBY.

**Rationale:** Derived from REQ-EPS-000. Source notes: Graceful power-down prevents jerk on ignition off; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-032.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Transition to STANDBY — Part 2' occurs.
- **Then:** Motor current output shall be ramped to zero over 500ms before entering STANDBY.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `500ms` → 499.99, 500.0, 500.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1006

**Split from:** `REQ-EPS-032`

**Open issues:** Split from REQ-EPS-032; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1007 — Transition to SHUTDOWN — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** All outputs shall be set to zero before shutdown.

**Rationale:** Derived from REQ-EPS-000. Source notes: Power loss handled by hardware; SWC handles graceful shutdown signal; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-034.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Transition to SHUTDOWN — Part 2' occurs.
- **Then:** All outputs shall be set to zero before shutdown.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1007

**Split from:** `REQ-EPS-034`

**Open issues:** Split from REQ-EPS-034; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1008 — STANDBY Mode Behavior — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Sensor monitoring shall continue at reduced rate (10ms cycle).

**Rationale:** Derived from REQ-EPS-000. Source notes: Sensor monitoring in STANDBY detects re-activation conditions; split into 3 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-035.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'STANDBY Mode Behavior — Part 2' occurs.
- **Then:** Sensor monitoring shall continue at reduced rate (10ms cycle).
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1008

**Split from:** `REQ-EPS-035`

**Open issues:** Split from REQ-EPS-035; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1009 — STANDBY Mode Behavior — Part 3

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The SWC shall be ready to transition to ACTIVE within 100ms of ignition ON.

**Rationale:** Derived from REQ-EPS-000. Source notes: Sensor monitoring in STANDBY detects re-activation conditions; split into 3 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-035.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'STANDBY Mode Behavior — Part 3' occurs.
- **Then:** The SWC shall be ready to transition to ACTIVE within 100ms of ignition ON.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1009

**Split from:** `REQ-EPS-035`

**Open issues:** Split from REQ-EPS-035; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1010 — FAIL_SAFE Limp Home Mode — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Motor current limit shall be 14A (20% of 70A rated).

**Rationale:** FAIL_SAFE limp-home: 20% of rated assist, 14 A current limit (20% of 70 A). Split from REQ-EPS-036.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'FAIL_SAFE Limp Home Mode — Part 2' occurs.
- **Then:** Motor current limit shall be 14A (20% of 70A rated).
- **Tolerance:** ±0.01 A at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `14A` → 13.99, 14.0, 14.01
- `20%` → 19.99, 20.0, 20.01
- `70A` → 69.99, 70.0, 70.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1010

**Split from:** `REQ-EPS-036`

**Open issues:** Split from REQ-EPS-036; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1011 — Redundant Sensor Plausibility Check — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If the absolute deviation exceeds 2.0 Nm for more than 3 consecutive cycles the system shall set DTC_EPS_SENSOR_FAIL and transition to FAIL_SAFE.

**Rationale:** Derived from REQ-EPS-000. Source notes: 3-cycle debounce prevents false positives from transient noise; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-041.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Redundant Sensor Plausibility Check — Part 2' occurs and persists for the specified debounce.
- **Then:** If the absolute deviation exceeds 2.0 Nm for more than 3 consecutive cycles the system shall set DTC_EPS_SENSOR_FAIL and transition to FAIL_SAFE. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 N at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `2.0 N` → 1.99, 2.0, 2.01

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1011

**Split from:** `REQ-EPS-041`

**Open issues:** Split from REQ-EPS-041; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-1012 — Motor Current Hard Limit — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If software limit is reached for > 100ms DTC_EPS_OVERCURRENT shall be set.

**Rationale:** Software current limit 70 A; hardware overcurrent protection at 80 A. The 10 A margin is the protection hierarchy. Split from REQ-EPS-042.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Motor Current Hard Limit — Part 2' occurs.
- **Then:** If software limit is reached for > 100ms DTC_EPS_OVERCURRENT shall be set.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1012

**Split from:** `REQ-EPS-042`

**Open issues:** Split from REQ-EPS-042; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1013 — Thermal Protection — Part 2

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When temp > 80 degrees Celsius assist shall be linearly reduced by 5% per degree above 80C.

**Rationale:** Thermal protection: linear derating above 80 C (5% per degree) and disable above 100 C. The source classifies this as ASIL-B while REQ-EPS-033 lists >80 C as a FAIL_SAFE trigger; reconcile. Split from REQ-EPS-043.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Thermal Protection — Part 2' occurs.
- **Then:** When temp > 80 degrees Celsius assist shall be linearly reduced by 5% per degree above 80C.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5%` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1013

**Split from:** `REQ-EPS-043`

**Open issues:** Split from REQ-EPS-043; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1014 — Thermal Protection — Part 3

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When temp > 100C motor shall be disabled and DTC_EPS_OVERHEAT set.

**Rationale:** Thermal protection: linear derating above 80 C (5% per degree) and disable above 100 C. The source classifies this as ASIL-B while REQ-EPS-033 lists >80 C as a FAIL_SAFE trigger; reconcile. Split from REQ-EPS-043.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Thermal Protection — Part 3' occurs.
- **Then:** When temp > 100C motor shall be disabled and DTC_EPS_OVERHEAT set.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1014

**Split from:** `REQ-EPS-043`

**Open issues:** Split from REQ-EPS-043; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1015 — Supply Voltage Monitoring — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If voltage drops below 9.0V for more than 5 consecutive cycles assist shall be disabled and DTC_EPS_UNDERVOLTAGE set.

**Rationale:** Undervoltage protection below 9.0 V for 5 cycles; automatic recovery above 10.5 V. Split from REQ-EPS-044.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Supply Voltage Monitoring — Part 2' occurs.
- **Then:** If voltage drops below 9.0V for more than 5 consecutive cycles assist shall be disabled and DTC_EPS_UNDERVOLTAGE set.
- **Tolerance:** ±0.01 V at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `9.0V` → 8.99, 9.0, 9.01

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1015

**Split from:** `REQ-EPS-044`

**Open issues:** Split from REQ-EPS-044; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1016 — Supply Voltage Monitoring — Part 3

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** System shall recover automatically when voltage returns above 10.5V.

**Rationale:** Undervoltage protection below 9.0 V for 5 cycles; automatic recovery above 10.5 V. Split from REQ-EPS-044.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Supply Voltage Monitoring — Part 3' occurs.
- **Then:** System shall recover automatically when voltage returns above 10.5V.
- **Tolerance:** ±0.01 V at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10.5V` → 10.49, 10.5, 10.51

**Trace:** parent=REQ-EPS-000 · design=RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1016

**Split from:** `REQ-EPS-044`

**Open issues:** Split from REQ-EPS-044; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1017 — Watchdog Supervision — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A missed trigger shall cause the watchdog to reset the ECU.

**Rationale:** Hardware watchdog trigger every 5 ms in RE_ControlTorque; reset cause is checked on startup. Split from REQ-EPS-045.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Supervision — Part 2' occurs and persists for the specified debounce.
- **Then:** A missed trigger shall cause the watchdog to reset the ECU. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1017

**Split from:** `REQ-EPS-045`

**Open issues:** Split from REQ-EPS-045; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-1018 — Watchdog Supervision — Part 3

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Software shall detect watchdog expiry via reset cause register on next startup.

**Rationale:** Hardware watchdog trigger every 5 ms in RE_ControlTorque; reset cause is checked on startup. Split from REQ-EPS-045.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Supervision — Part 3' occurs and persists for the specified debounce.
- **Then:** Software shall detect watchdog expiry via reset cause register on next startup. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1018

**Split from:** `REQ-EPS-045`

**Open issues:** Split from REQ-EPS-045; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-1019 — CAN Signal End-to-End Protection — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** E2E counter mismatch shall trigger DTC_EPS_CAN_TIMEOUT after 2 consecutive failures.

**Rationale:** E2E Profile 2 protection on safety-relevant CAN inputs; counter mismatch triggers a CAN-timeout DTC after 2 consecutive failures. Split from REQ-EPS-046.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'CAN Signal End-to-End Protection — Part 2' occurs and persists for the specified debounce.
- **Then:** E2E counter mismatch shall trigger DTC_EPS_CAN_TIMEOUT after 2 consecutive failures. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1019

**Split from:** `REQ-EPS-046`

**Open issues:** Split from REQ-EPS-046; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-1020 — Startup Self-Test — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Any failure shall set the SWC to FAIL_SAFE mode permanently until ECU is serviced.

**Rationale:** Startup RAM/ROM self-test; a failure drives permanent FAIL_SAFE until service. Split from REQ-EPS-047.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Startup Self-Test — Part 2' occurs and persists for the specified debounce.
- **Then:** Any failure shall set the SWC to FAIL_SAFE mode permanently until ECU is serviced. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=RE_Initialize, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1020

**Split from:** `REQ-EPS-047`

**Open issues:** Split from REQ-EPS-047; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-EPS-1021 — Stack Overflow Detection — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Stack overflow shall trigger an immediate FAIL_SAFE transition and DEM error notification.

**Rationale:** Derived from REQ-EPS-000. Source notes: AUTOSAR OS stack monitoring feature; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-048.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Stack Overflow Detection — Part 2' occurs.
- **Then:** Stack overflow shall trigger an immediate FAIL_SAFE transition and DEM error notification.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1021

**Split from:** `REQ-EPS-048`

**Open issues:** Split from REQ-EPS-048; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1022 — CPU Load Monitoring — Part 2

**Type:** constraint · **ASIL:** QM · **Priority:** should · **Status:** review · **Verification:** review

**Statement:** If average CPU load exceeds 80% over 100 consecutive cycles a warning DTC shall be set and execution profiling data written to NVM.

**Rationale:** CPU-load monitoring; warning DTC at 80% average over 100 cycles and NVM profiling data. Split from REQ-EPS-049.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** If average CPU load exceeds 80% over 100 consecutive cycles a warning DTC shall be set and execution profiling data written to NVM. The constraint is satisfied with no exceptions.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `80%` → 79.99, 80.0, 80.01

**Trace:** parent=REQ-EPS-000 · design=RE_ControlTorque, RE_MonitorSafety, SWC_ElectricPowerSteering · test=TD-REQ-EPS-1022

**Split from:** `REQ-EPS-049`

**Open issues:** Split from REQ-EPS-049; confirm atomicity and completeness with the requirement owner.

---

### REQ-EPS-1023 — DTC Overcurrent — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC shall be stored immediately in NVM.

**Rationale:** Derived from REQ-EPS-000. Source notes: Immediate NVM storage prevents data loss on power cycle; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-051.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Overcurrent — Part 2' occurs.
- **Then:** DTC shall be stored immediately in NVM.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1023

**Split from:** `REQ-EPS-051`

**Open issues:** Split from REQ-EPS-051; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1024 — DTC Overheat — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC shall include snapshot data: temperature speed and assist level at time of fault.

**Rationale:** Derived from REQ-EPS-000. Source notes: Snapshot data aids field diagnostics; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-052.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Overheat — Part 2' occurs.
- **Then:** DTC shall include snapshot data: temperature speed and assist level at time of fault.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1024

**Split from:** `REQ-EPS-052`

**Open issues:** Split from REQ-EPS-052; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1025 — DTC Undervoltage — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC shall include voltage value snapshot.

**Rationale:** Derived from REQ-EPS-000. Source notes: Undervoltage most common EPS field complaint - snapshot critical; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-EPS-053.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Undervoltage — Part 2' occurs.
- **Then:** DTC shall include voltage value snapshot.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1025

**Split from:** `REQ-EPS-053`

**Open issues:** Split from REQ-EPS-053; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1026 — Vehicle Speed CAN Input — Part 2

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** Loss of signal > 50ms shall trigger DTC_EPS_CAN_TIMEOUT.

**Rationale:** Vehicle-speed CAN input, 0-250 km/h, 0.01 km/h, 10 ms; loss >50 ms triggers CAN timeout. Split from REQ-EPS-060.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Vehicle Speed CAN Input — Part 2 is exercised at its defined update rate.
- **Then:** Loss of signal > 50ms shall trigger DTC_EPS_CAN_TIMEOUT. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `50ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1026

**Split from:** `REQ-EPS-060`

**Open issues:** Split from REQ-EPS-060; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-1027 — Primary Torque Sensor Interface — Part 2

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** Signal shall be filtered before use.

**Rationale:** Primary torque sensor: direct SPI, -25 to +25 Nm, 0.01 Nm, 1 ms; filtered before use. Split from REQ-EPS-063.

**Acceptance criteria (draft):**

- **Given:** The SWC_ElectricPowerSteering component is running and the referenced producer/consumer ports are connected.
- **When:** Primary Torque Sensor Interface — Part 2 is exercised at its defined update rate.
- **Then:** Signal shall be filtered before use. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1027

**Split from:** `REQ-EPS-063`

**Open issues:** Split from REQ-EPS-063; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### REQ-EPS-1029 — Safe State per Fault Class — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The EPS shall record the active safe state in PP_EPSStatus.

**Rationale:** The source uses FAIL_SAFE as a single state but does not define fault-class-specific safe states. Split from REQ-EPS-805.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Safe State per Fault Class — Part 2' occurs.
- **Then:** The EPS shall record the active safe state in PP_EPSStatus.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1029

**Split from:** `REQ-EPS-805`

**Open issues:** Split from REQ-EPS-805; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1030 — Thermal Derating to Disable Transition — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The EPS shall not re-enable assist until the temperature falls below the calibrated recovery threshold.

**Rationale:** The source defines 80 C derating and 100 C disable but not the recovery threshold or re-enable condition. Split from REQ-EPS-806.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Thermal Derating to Disable Transition — Part 2' occurs.
- **Then:** The EPS shall not re-enable assist until the temperature falls below the calibrated recovery threshold.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1030

**Split from:** `REQ-EPS-806`

**Open issues:** Split from REQ-EPS-806; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1031 — Software and Calibration Update Integrity — Part 2

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The EPS shall record a fault when verification fails.

**Rationale:** A safety-critical steering function needs update integrity; the source set does not address cybersecurity. Split from REQ-EPS-809.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The EPS shall record a fault when verification fails. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1031

**Split from:** `REQ-EPS-809`

**Open issues:** Split from REQ-EPS-809; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-EPS-1032 — Fault Injection and Observability — Part 2

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The EPS shall publish the resulting mode and DTC bitmask.

**Rationale:** Verification of the safety mechanisms needs controllability and observability. Split from REQ-EPS-810.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The EPS shall publish the resulting mode and DTC bitmask. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-EPS-000 · design=SWC_ElectricPowerSteering · test=TD-REQ-EPS-1032

**Split from:** `REQ-EPS-810`

**Open issues:** Split from REQ-EPS-810; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## System

### REQ-EPS-000 — EPS System Requirements Baseline

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The EPS software requirements baseline shall be allocated to SWC_ElectricPowerSteering on ECU_EPS_Main.

**Rationale:** The source CSV has no system/stakeholder hierarchy. This placeholder enables traceability without inventing a stakeholder requirement.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EPS System Requirements Baseline' occurs.
- **Then:** The EPS software requirements baseline shall be allocated to SWC_ElectricPowerSteering on ECU_EPS_Main.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-EPS-000

**Split into:** REQ-EPS-1028

**Open issues:** Placeholder system parent; replace with the real steering system/stakeholder requirement and confirm ASIL allocation.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-EPS-1028; the original ID retains part 1.

---

### REQ-EPS-1028 — EPS System Requirements Baseline — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The EPS software requirements baseline shall trace to the steering system/stakeholder requirements.

**Rationale:** The source CSV has no system/stakeholder hierarchy. This placeholder enables traceability without inventing a stakeholder requirement. Split from REQ-EPS-000.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EPS System Requirements Baseline — Part 2' occurs.
- **Then:** The EPS software requirements baseline shall trace to the steering system/stakeholder requirements.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-EPS-1028

**Split from:** `REQ-EPS-000`

**Open issues:** Split from REQ-EPS-000; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---
