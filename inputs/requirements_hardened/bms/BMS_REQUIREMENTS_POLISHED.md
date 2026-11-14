# BMS requirements — polished L2-oriented draft

> Status: **review draft**. Human approval required. Not certified.
> Source: `inputs/requirements/samples/bms_requirements.csv` (unchanged).
> Requirements: **62** (42 retained/derived + 20 atomic split parts).

## How to read this document

Each requirement is atomic where possible. 17 compound requirements were split into 20 atomic parts; the original ID keeps part 1 and parts 2+ use `REQ-BMS-1001..REQ-BMS-1020`. Acceptance criteria are drafts derived from the source text. Open issues are decisions for the human reviewer, not hidden assumptions.

## Summary by allocation

| Allocation | Requirements |
|---|---|
| SWC_BatteryManagement | 60 |
| System | 2 |

## SWC_BatteryManagement

### REQ-BMS-001 — BMS SWC Architecture

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC_BatteryManagement shall be implemented as an AUTOSAR ApplicationSWC containing all battery state estimation, cell balancing, thermal management, and contactor control logic for the high-voltage traction battery pack.

**Rationale:** BMS software architecture allocation. The source CSV has no system/stakeholder hierarchy; a placeholder parent REQ-BMS-000 is injected for traceability.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'BMS SWC Architecture' occurs.
- **Then:** SWC_BatteryManagement shall be implemented as an AUTOSAR ApplicationSWC containing all battery state estimation, cell balancing, thermal management, and contactor control logic for the high-voltage traction battery pack.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-001

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Placeholder system parent REQ-BMS-000; confirm the stakeholder/system requirement and ASIL allocation with the BMS owner.

---

### REQ-BMS-002 — SOC Estimation Runnable

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** RE_EstimateSOC shall execute cyclically every 10 ms and compute the battery State-of-Charge using the specified SOC estimation method, writing the result to PP_SOCPercent.

**Rationale:** The source mandates a 10 ms SOC runnable and an EKF-based estimator. The helper-function names are design details and are recorded in design_notes.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 10 ms trigger occurs.
- **Then:** RE_EstimateSOC shall execute cyclically every 10 ms and compute the battery State-of-Charge using the specified SOC estimation method, writing the result to PP_SOCPercent. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-BMS-000 · design=RE_EstimateSOC, SWC_BatteryManagement · test=TD-REQ-BMS-002

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Confirm the SOC estimation algorithm, equivalent-circuit parameters and validation tolerance with the BMS algorithm owner.

---

### REQ-BMS-003 — Cell Balancing Runnable

**Type:** timing · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** RE_BalanceCells shall execute cyclically every 100 ms to compare individual cell voltages and activate passive bleed resistors on cells above the mean.

**Rationale:** The source defines a 100 ms balancing runnable; helper names are design details.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 100 ms trigger occurs.
- **Then:** RE_BalanceCells shall execute cyclically every 100 ms to compare individual cell voltages and activate passive bleed resistors on cells above the mean. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100 ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-BMS-000 · design=RE_BalanceCells, SWC_BatteryManagement · test=TD-REQ-BMS-003

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-004 — Thermal Management Runnable

**Type:** timing · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** RE_ManageThermal shall execute cyclically every 50 ms to compute the battery temperature gradient, control the cooling pump PWM duty cycle, and apply power derating when thermal limits are approached.

**Rationale:** The source defines a 50 ms thermal-management runnable. Helper names are design details.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 50 ms trigger occurs.
- **Then:** RE_ManageThermal shall execute cyclically every 50 ms to compute the battery temperature gradient, control the cooling pump PWM duty cycle, and apply power derating when thermal limits are approached. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `50 ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-BMS-000 · design=RE_ManageThermal, SWC_BatteryManagement · test=TD-REQ-BMS-004

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-005 — Safety Monitor Runnable

**Type:** timing · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** RE_MonitorSafety shall execute cyclically every 5 ms to perform overcurrent, overvoltage, undervoltage, and overtemperature plausibility checks and set the corresponding DTC within the same 5 ms execution when a fault is detected.

**Rationale:** The source requires a 5 ms safety monitor and same-cycle fault reporting. OpenContactors() is the fault reaction, specified separately.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The 5 ms trigger occurs.
- **Then:** RE_MonitorSafety shall execute cyclically every 5 ms to perform overcurrent, overvoltage, undervoltage, and overtemperature plausibility checks and set the corresponding DTC within the same 5 ms execution when a fault is detected. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01
- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-005

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-006 — Contactor Control Runnable

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ControlContactors shall execute on a DataReceivedEvent of VehicleReadyStatus to manage the precharge and main-contactor sequence (OPEN, PRECHARGE, MAIN_CLOSE) and verify the contactor state after each transition.

**Rationale:** The source defines the contactor sequence and state verification. Helper names are design details.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Contactor Control Runnable' occurs.
- **Then:** RE_ControlContactors shall execute on a DataReceivedEvent of VehicleReadyStatus to manage the precharge and main-contactor sequence (OPEN, PRECHARGE, MAIN_CLOSE) and verify the contactor state after each transition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=RE_ControlContactors, SWC_BatteryManagement · test=TD-REQ-BMS-006

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-007 — Initialization Runnable

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_Initialize shall execute once on ECU startup to read the last known SOC from NVM, perform a cell voltage scan, validate sensor signals, and set the SWC state to INIT only after RAM CRC and ROM CRC-32 self-tests complete.

**Rationale:** Startup initialization including NVM read, sensor validation and self-tests. The source uses NvM_ReadBlock; the block name is a design detail.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Initialization Runnable' occurs.
- **Then:** RE_Initialize shall execute once on ECU startup to read the last known SOC from NVM, perform a cell voltage scan, validate sensor signals, and set the SWC state to INIT only after RAM CRC and ROM CRC-32 self-tests complete.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `-32 s` → -32.01, -32.0, -31.99

**Trace:** parent=REQ-BMS-000 · design=RE_Initialize, SWC_BatteryManagement · test=TD-REQ-BMS-007

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-010 — Required Ports

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC shall declare: RP_PackCurrent (SR IF_SR_Current, range ±500 A, res 0.1 A, 10 ms cycle via CAN ID 0x610), RP_CellVoltages (SR IF_SR_CellArray, 96 cells × float32, 100 ms), RP_CellTemperatures (SR IF_SR_TempArray, 32 NTC sensors × float32, 50 ms), RP_VehicleReadyStatus (SR IF_SR_VehicleReady, boolean, event-driven), RP_AmbientTemperature (SR IF_SR_Temperature, float32, 1 s).

**Rationale:** Required-port declaration. The source bundles five ports in one requirement; the data dictionary must confirm each interface.

**Acceptance criteria (draft):**

- **Given:** The SWC_BatteryManagement component is running and the referenced producer/consumer ports are connected.
- **When:** Required Ports is exercised at its defined update rate.
- **Then:** SWC shall declare: RP_PackCurrent (SR IF_SR_Current, range ±500 A, res 0.1 A, 10 ms cycle via CAN ID 0x610), RP_CellVoltages (SR IF_SR_CellArray, 96 cells × float32, 100 ms), RP_CellTemperatures (SR IF_SR_TempArray, 32 NTC sensors × float32, 50 ms), RP_VehicleReadyStatus (SR IF_SR_VehicleReady, boolean, event-driven), RP_AmbientTemperature (SR IF_SR_Temperature, float32, 1 s). The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 A at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `500 A` → 499.99, 500.0, 500.01
- `0.1 A` → 0.09, 0.1, 0.11
- `10 ms` → 9.99, 10.0, 10.01
- `100 ms` → 99.99, 100.0, 100.01
- `32 N` → 31.99, 32.0, 32.01
- `50 ms` → 49.99, 50.0, 50.01
- `1 s` → 0.99, 1.0, 1.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-010

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface requirement bundles five ports; split into per-port requirements in the next revision and confirm ranges/resolutions against the DDS.

---

### REQ-BMS-011 — Provided Ports

**Type:** interface · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SWC shall declare: PP_SOCPercent (SR IF_SR_SOC, range 0.0–100.0 %, res 0.01 %, 10 ms), PP_SOHPercent (SR IF_SR_SOH, range 0.0–100.0 %, res 0.1 %, 1 s), PP_PackPowerLimit (SR IF_SR_PowerLimits, struct {f32ChargeLimitW, f32DischargeLimitW}, 50 ms), PP_BMSStatus (SR IF_SR_BMSStatus, struct {u8Mode, u8ActiveDTCs, u8BalancingActive}, 10 ms), PP_ContactorState (SR IF_SR_Contactor, enum {OPEN, PRECHARGE, CLOSED}, event-driven).

**Rationale:** Provided-port declaration. The source bundles five ports in one requirement; the data dictionary must confirm each interface.

**Acceptance criteria (draft):**

- **Given:** The SWC_BatteryManagement component is running and the referenced producer/consumer ports are connected.
- **When:** Provided Ports is exercised at its defined update rate.
- **Then:** SWC shall declare: PP_SOCPercent (SR IF_SR_SOC, range 0.0–100.0 %, res 0.01 %, 10 ms), PP_SOHPercent (SR IF_SR_SOH, range 0.0–100.0 %, res 0.1 %, 1 s), PP_PackPowerLimit (SR IF_SR_PowerLimits, struct {f32ChargeLimitW, f32DischargeLimitW}, 50 ms), PP_BMSStatus (SR IF_SR_BMSStatus, struct {u8Mode, u8ActiveDTCs, u8BalancingActive}, 10 ms), PP_ContactorState (SR IF_SR_Contactor, enum {OPEN, PRECHARGE, CLOSED}, event-driven). The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100.0 %` → 99.99, 100.0, 100.01
- `0.01 %` → 0.0, 0.01, 0.02
- `10 ms` → 9.99, 10.0, 10.01
- `100.0 %` → 99.99, 100.0, 100.01
- `0.1 %` → 0.09, 0.1, 0.11
- `1 s` → 0.99, 1.0, 1.01
- `50 ms` → 49.99, 50.0, 50.01
- `8M` → 7.99, 8.0, 8.01
- `8A` → 7.99, 8.0, 8.01
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-011

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.; Interface requirement bundles five ports; split into per-port requirements in the next revision and confirm ranges/resolutions against the DDS.

---

### REQ-BMS-020 — EKF State Prediction

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** EKF_Predict() shall propagate the state vector [SOC, V_RC1, V_RC2] forward using the specified equivalent-circuit model and calibrated parameters.

**Rationale:** Derived from REQ-BMS-000. Source notes: ECM = 2nd-order RC equivalent circuit model; tau1=30s, tau2=300s typical; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EKF State Prediction' occurs.
- **Then:** EKF_Predict() shall propagate the state vector [SOC, V_RC1, V_RC2] forward using the specified equivalent-circuit model and calibrated parameters.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-020

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-021 — EKF Measurement Update

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** EKF_Update() shall compute the Kalman gain and correct the state estimate using the measured pack voltage and the specified equivalent-circuit model.

**Rationale:** Derived from REQ-BMS-000. Source notes: OCV(SOC) is a 101-point lookup table stored as calibration ROM array; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'EKF Measurement Update' occurs.
- **Then:** EKF_Update() shall compute the Kalman gain and correct the state estimate using the measured pack voltage and the specified equivalent-circuit model.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-021

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-022 — SOC Clamping

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SOC_Clamp() shall ensure the final SOC estimate is clamped to the range [SOC_MIN = 5.0 %, SOC_MAX = 95.0 %] before writing to PP_SOCPercent.

**Rationale:** SOC clamping protects the usable window and triggers a DTC when the raw estimate leaves 5-95% for 10 consecutive cycles.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'SOC Clamping' occurs.
- **Then:** SOC_Clamp() shall ensure the final SOC estimate is clamped to the range [SOC_MIN = 5.0 %, SOC_MAX = 95.0 %] before writing to PP_SOCPercent.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5.0 %` → 4.99, 5.0, 5.01
- `95.0 %` → 94.99, 95.0, 95.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-022

**Split into:** REQ-BMS-1001

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1001; the original ID retains part 1.

---

### REQ-BMS-023 — Current Integration Backup

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When V_meas is unavailable (sensor timeout > 20 ms), RE_EstimateSOC shall fall back to pure coulomb counting: SOC(k+1) = SOC(k) - (I_pack * DT) / Q_nom and set bit[0] of PP_BMSStatus.u8Mode to indicate degraded estimation.

**Rationale:** Coulomb-counting fallback when the voltage measurement is unavailable; the 2% SOC/hour error is the source's stated accuracy target.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Current Integration Backup' occurs.
- **Then:** When V_meas is unavailable (sensor timeout > 20 ms), RE_EstimateSOC shall fall back to pure coulomb counting: SOC(k+1) = SOC(k) - (I_pack * DT) / Q_nom and set bit[0] of PP_BMSStatus.u8Mode to indicate degraded estimation.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `20 ms` → 19.99, 20.0, 20.01
- `8M` → 7.99, 8.0, 8.01

**Trace:** parent=REQ-BMS-000 · design=RE_EstimateSOC, SWC_BatteryManagement · test=TD-REQ-BMS-023

**Split into:** REQ-BMS-1002

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1002; the original ID retains part 1.

---

### REQ-BMS-030 — Cell Delta Calculation

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** CalcCellDelta() shall compute V_mean = sum(V_cell[i], i=0..95) / 96 and V_delta[i] = V_cell[i] - V_mean for each of the 96 cells. Cells with V_delta[i] > BALANCE_THRESHOLD_V (15 mV) are marked as candidates in l_u8BalanceMask bitmask (96 bits = 12 bytes).

**Rationale:** Derived from REQ-BMS-000. Source notes: BALANCE_THRESHOLD_V stored as calibration constant in ROM; req_type=FUNCTIONAL. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Cell Delta Calculation' occurs.
- **Then:** CalcCellDelta() shall compute V_mean = sum(V_cell[i], i=0..95) / 96 and V_delta[i] = V_cell[i] - V_mean for each of the 96 cells. Cells with V_delta[i] > BALANCE_THRESHOLD_V (15 mV) are marked as candidates in l_u8BalanceMask bitmask (96 bits = 12 bytes).
- **Tolerance:** ±0.01 a at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `96 a` → 95.99, 96.0, 96.01
- `15 m` → 14.99, 15.0, 15.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-030

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-031 — Balancing Cell Selection Limit

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SelectBalanceCells() shall limit the number of simultaneously active bleed resistors to MAX_SIMULTANEOUS_BALANCE = 8 to prevent excessive heat generation.

**Rationale:** Limits simultaneous bleed resistors to 8 to bound heat generation and selects the highest-delta cells when more than 8 are candidates.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Balancing Cell Selection Limit' occurs.
- **Then:** SelectBalanceCells() shall limit the number of simultaneously active bleed resistors to MAX_SIMULTANEOUS_BALANCE = 8 to prevent excessive heat generation.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-031

**Split into:** REQ-BMS-1003

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1003; the original ID retains part 1.

---

### REQ-BMS-032 — Balance Relay Control

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SetBalanceRelays() shall write the selected l_u8BalanceMask to the cell monitoring IC via SPI within 1 ms of being called.

**Rationale:** Balancing is inhibited above 5 A pack current to prevent measurement interference; the 1 ms SPI write is a timing constraint.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Balance Relay Control' occurs.
- **Then:** SetBalanceRelays() shall write the selected l_u8BalanceMask to the cell monitoring IC via SPI within 1 ms of being called.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1 ms` → 0.99, 1.0, 1.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-032

**Split into:** REQ-BMS-1004

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1004; the original ID retains part 1.

---

### REQ-BMS-040 — Temperature Gradient Calculation

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** CalcTempGradient() shall compute T_max = max(T_cell[i], i=0..31), T_min = min(T_cell[i], i=0..31), and T_gradient = T_max - T_min.

**Rationale:** Derived from REQ-BMS-000. Source notes: High gradient indicates cooling blockage or cell degradation; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Temperature Gradient Calculation' occurs.
- **Then:** CalcTempGradient() shall compute T_max = max(T_cell[i], i=0..31), T_min = min(T_cell[i], i=0..31), and T_gradient = T_max - T_min.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-040

**Split into:** REQ-BMS-1005

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1005; the original ID retains part 1.

---

### REQ-BMS-041 — Cooling PWM Control

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SetCoolingPWM() shall compute the PWM duty cycle for the cooling pump as: duty_cycle = K_COOL_P * (T_max - T_TARGET_K) + K_COOL_I * integral_error, where T_TARGET_K = 298.15 K (25 °C), K_COOL_P = 5.0 %/K, K_COOL_I = 0.1 %/(K·s).

**Rationale:** Derived from REQ-BMS-000. Source notes: PI controller; integral windup protection: clamp integral when output saturated; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Cooling PWM Control' occurs.
- **Then:** SetCoolingPWM() shall compute the PWM duty cycle for the cooling pump as: duty_cycle = K_COOL_P * (T_max - T_TARGET_K) + K_COOL_I * integral_error, where T_TARGET_K = 298.15 K (25 °C), K_COOL_P = 5.0 %/K, K_COOL_I = 0.1 %/(K·s).
- **Tolerance:** ±0.01 °C at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `25 °C` → 24.99, 25.0, 25.01
- `5.0 %` → 4.99, 5.0, 5.01
- `0.1 %` → 0.09, 0.1, 0.11

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-041

**Split into:** REQ-BMS-1006

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1006; the original ID retains part 1.

---

### REQ-BMS-042 — Thermal Power Derating

**Type:** safety · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ManageThermal shall compute power derating factor: derate = 1.0 - clamp((T_max - T_DERATE_START_K) / T_DERATE_RANGE_K, 0.0, 1.0), where T_DERATE_START_K = 313.15 K (40 °C), T_DERATE_RANGE_K = 20 K. PP_PackPowerLimit.f32DischargeLimitW = P_MAX_W * derate. P_MAX_W = 150000 W (150 kW).

**Rationale:** Derived from REQ-BMS-000. Source notes: Linear derating from 100% at 40 °C to 0% at 60 °C; req_type=SAFETY. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Thermal Power Derating' occurs.
- **Then:** RE_ManageThermal shall compute power derating factor: derate = 1.0 - clamp((T_max - T_DERATE_START_K) / T_DERATE_RANGE_K, 0.0, 1.0), where T_DERATE_START_K = 313.15 K (40 °C), T_DERATE_RANGE_K = 20 K. PP_PackPowerLimit.f32DischargeLimitW = P_MAX_W * derate. P_MAX_W = 150000 W (150 kW).
- **Tolerance:** ±0.01 °C at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `40 °C` → 39.99, 40.0, 40.01

**Trace:** parent=REQ-BMS-000 · design=RE_ManageThermal, SWC_BatteryManagement · test=TD-REQ-BMS-042

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-050 — Overcurrent Detection

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall check I_pack against I_MAX_DISCHARGE = 300 A and I_MAX_CHARGE = -150 A every 5 ms.

**Rationale:** Overcurrent protection thresholds are 300 A discharge and -150 A charge with a 10 ms debounce. These are narrower than the port range of +/-500 A and must be reconciled with the fuse and sensor range.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Overcurrent Detection' occurs.
- **Then:** RE_MonitorSafety shall check I_pack against I_MAX_DISCHARGE = 300 A and I_MAX_CHARGE = -150 A every 5 ms.
- **Tolerance:** ±0.01 A at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `300 A` → 299.99, 300.0, 300.01
- `-150 A` → -150.01, -150.0, -149.99
- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-050

**Split into:** REQ-BMS-1007

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Reconcile I_MAX_DISCHARGE = 300 A / I_MAX_CHARGE = -150 A with the RP_PackCurrent range +/-500 A and the 500 A fuse; confirm the protection hierarchy.; Split into REQ-BMS-1007; the original ID retains part 1.

---

### REQ-BMS-051 — Overvoltage / Undervoltage Detection

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall check every cell voltage against V_CELL_MAX = 4.20 V and V_CELL_MIN = 2.50 V every 5 ms.

**Rationale:** Cell over/undervoltage protection at 4.20 V / 2.50 V with a two-cycle debounce.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Overvoltage / Undervoltage Detection' occurs.
- **Then:** RE_MonitorSafety shall check every cell voltage against V_CELL_MAX = 4.20 V and V_CELL_MIN = 2.50 V every 5 ms.
- **Tolerance:** ±0.01 V at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `4.20 V` → 4.19, 4.2, 4.21
- `2.50 V` → 2.49, 2.5, 2.51
- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-051

**Split into:** REQ-BMS-1008

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1008; the original ID retains part 1.

---

### REQ-BMS-052 — Overtemperature Detection

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall check T_max against T_CELL_MAX_K = 333.15 K (60 °C) every 5 ms.

**Rationale:** Overtemperature protection at 60 C with a 20 ms debounce; recovery is intentionally manual for a thermal event.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Overtemperature Detection' occurs.
- **Then:** RE_MonitorSafety shall check T_max against T_CELL_MAX_K = 333.15 K (60 °C) every 5 ms.
- **Tolerance:** ±0.01 °C at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `60 °C` → 59.99, 60.0, 60.01
- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-052

**Split into:** REQ-BMS-1009, REQ-BMS-1010

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1009, REQ-BMS-1010; the original ID retains part 1.

---

### REQ-BMS-053 — Open Contactor Function

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** OpenContactors() shall set PP_ContactorState = OPEN, zero the discharge and charge power limits, report the triggering DTC to DEM, and persist the fault record to NVM within the 5 ms RE_MonitorSafety window.

**Rationale:** The source defines a four-step fault reaction within the 5 ms safety-monitor window. NVM persistence inside 5 ms may require a deferred-write mechanism.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Open Contactor Function' occurs and persists for the specified debounce.
- **Then:** OpenContactors() shall set PP_ContactorState = OPEN, zero the discharge and charge power limits, report the triggering DTC to DEM, and persist the fault record to NVM within the 5 ms RE_MonitorSafety window. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-053

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Confirm whether NVM persistence can complete within 5 ms or whether a deferred/queued write is required; the timing budget must be verified.

---

### REQ-BMS-060 — Precharge Sequence

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_ControlContactors shall implement the precharge sequence when VehicleReadyStatus transitions from OFF to ON: (1) Close precharge relay, set PP_ContactorState = PRECHARGE; (2) Monitor V_DC_link via RP_DCLinkVoltage; (3) When V_DC_link >= 0.95 * V_pack_nominal close main contactor; (4) Open precharge relay, set PP_ContactorState = CLOSED. Sequence timeout = 2 s; abort to OPEN if exceeded.

**Rationale:** Precharge sequence with a 2 s timeout and abort-to-OPEN behaviour.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Precharge Sequence' occurs.
- **Then:** RE_ControlContactors shall implement the precharge sequence when VehicleReadyStatus transitions from OFF to ON: (1) Close precharge relay, set PP_ContactorState = PRECHARGE; (2) Monitor V_DC_link via RP_DCLinkVoltage; (3) When V_DC_link >= 0.95 * V_pack_nominal close main contactor; (4) Open precharge relay, set PP_ContactorState = CLOSED. Sequence timeout = 2 s; abort to OPEN if exceeded.
- **Tolerance:** ±0.01 s at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `2 s` → 1.99, 2.0, 2.01

**Trace:** parent=REQ-BMS-000 · design=RE_ControlContactors, SWC_BatteryManagement · test=TD-REQ-BMS-060

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-061 — Contactor State Verification

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** VerifyContactorState() shall read back the physical contactor status from the contactor feedback pins via RP_ContactorFeedback and compare against the commanded state.

**Rationale:** Contactor feedback mismatch for more than 50 ms is treated as a weld fault and drives FAIL_SAFE.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Contactor State Verification' occurs.
- **Then:** VerifyContactorState() shall read back the physical contactor status from the contactor feedback pins via RP_ContactorFeedback and compare against the commanded state.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-061

**Split into:** REQ-BMS-1011, REQ-BMS-1012

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1011, REQ-BMS-1012; the original ID retains part 1.

---

### REQ-BMS-070 — SOH Estimation

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_EstimateSOC shall update State-of-Health after each charge from 10 % SOC to 90 % SOC by computing Q_meas = integral(I_pack * DT) over that window and setting SOH = (Q_meas / Q_nom_new) * 100 %, where Q_nom_new = 100 Ah.

**Rationale:** SOH is updated per defined 10-90% SOC charge window; the charge-window definition must be confirmed.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'SOH Estimation' occurs.
- **Then:** RE_EstimateSOC shall update State-of-Health after each charge from 10 % SOC to 90 % SOC by computing Q_meas = integral(I_pack * DT) over that window and setting SOH = (Q_meas / Q_nom_new) * 100 %, where Q_nom_new = 100 Ah.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 %` → 9.99, 10.0, 10.01
- `90 %` → 89.99, 90.0, 90.01
- `100 %` → 99.99, 100.0, 100.01
- `100 A` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-BMS-000 · design=RE_EstimateSOC, SWC_BatteryManagement · test=TD-REQ-BMS-070

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Confirm the 10-90% SOC charge window, the 100 Ah rated capacity and the SOH accuracy target.

---

### REQ-BMS-080 — DTC SOC Limit Exceeded

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC_BMS_SOC_LIMIT (0xB10003) shall be reported via Dem_ReportErrorStatus when the raw SOC estimate exceeds SOC_MAX = 95 % or falls below SOC_MIN = 5 % for 10 consecutive 10 ms cycles.

**Rationale:** SOC-limit DTC reporting with snapshot data.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC SOC Limit Exceeded' occurs.
- **Then:** DTC_BMS_SOC_LIMIT (0xB10003) shall be reported via Dem_ReportErrorStatus when the raw SOC estimate exceeds SOC_MAX = 95 % or falls below SOC_MIN = 5 % for 10 consecutive 10 ms cycles.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `95 %` → 94.99, 95.0, 95.01
- `5 %` → 4.99, 5.0, 5.01
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-080

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Confirm the snapshot data set and the 10-cycle debounce.

---

### REQ-BMS-081 — DTC Healing

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** All healable DTCs (0xB10001 through 0xB10007 excluding overtemp latch 0xB10002) shall be cleared automatically after 5 consecutive fault-free evaluation cycles.

**Rationale:** Healable DTCs clear after 5 fault-free cycles; the overtemperature latch is intentionally excluded.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Healing' occurs.
- **Then:** All healable DTCs (0xB10001 through 0xB10007 excluding overtemp latch 0xB10002) shall be cleared automatically after 5 consecutive fault-free evaluation cycles.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-081

**Split into:** REQ-BMS-1013

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1013; the original ID retains part 1.

---

### REQ-BMS-090 — E2E Protection

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** All safety-relevant CAN input signals (RP_PackCurrent, RP_CellVoltages, RP_CellTemperatures) shall be protected by AUTOSAR E2E Profile 2.

**Rationale:** E2E Profile 2 protection on safety-relevant CAN inputs; a counter mismatch triggers a CAN-timeout DTC after 3 consecutive failures.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'E2E Protection' occurs.
- **Then:** All safety-relevant CAN input signals (RP_PackCurrent, RP_CellVoltages, RP_CellTemperatures) shall be protected by AUTOSAR E2E Profile 2.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-090

**Split into:** REQ-BMS-1014

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1014; the original ID retains part 1.

---

### REQ-BMS-091 — Watchdog Supervision

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** RE_MonitorSafety shall trigger the hardware watchdog via Rte_Call every 5 ms.

**Rationale:** Hardware watchdog trigger every 5 ms; a missed trigger resets the ECU and the reset cause is persisted as a DTC.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Supervision' occurs and persists for the specified debounce.
- **Then:** RE_MonitorSafety shall trigger the hardware watchdog via Rte_Call every 5 ms. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 ms` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-091

**Split into:** REQ-BMS-1015, REQ-BMS-1016

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.; Split into REQ-BMS-1015, REQ-BMS-1016; the original ID retains part 1.

---

### REQ-BMS-801 — Cell Voltage Sensor Loss Safe State

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When a cell-voltage measurement channel is invalid or lost for more than 100 ms, the BMS shall enter a safe state that inhibits charging and limits discharge power to zero.

**Rationale:** The source defines plausibility checks but not the system-level safe state for loss of a cell-voltage channel.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Cell Voltage Sensor Loss Safe State' occurs and persists for the specified debounce.
- **Then:** When a cell-voltage measurement channel is invalid or lost for more than 100 ms, the BMS shall enter a safe state that inhibits charging and limits discharge power to zero. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100 ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-801

**Open issues:** 100 ms reaction time is proposed; confirm with the BMS safety analysis.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-BMS-802 — Contactor Weld Detection

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the commanded contactor state is OPEN but the feedback indicates CLOSED for more than 100 ms, the BMS shall set a contactor-weld DTC and inhibit precharge.

**Rationale:** The source detects a feedback mismatch but does not specify the weld-specific reaction or precharge inhibition.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Contactor Weld Detection' occurs and persists for the specified debounce.
- **Then:** When the commanded contactor state is OPEN but the feedback indicates CLOSED for more than 100 ms, the BMS shall set a contactor-weld DTC and inhibit precharge. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `100 ms` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-802

**Open issues:** Confirm the weld-detection window and precharge inhibit behaviour.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-BMS-803 — Insulation Fault Reaction

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the pack insulation resistance falls below the calibrated threshold, the BMS shall set an insulation fault, inhibit charging, and limit discharge power to the calibrated safe value.

**Rationale:** Insulation monitoring is not covered by the source set but is required for a high-voltage traction battery.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Insulation Fault Reaction' occurs and persists for the specified debounce.
- **Then:** When the pack insulation resistance falls below the calibrated threshold, the BMS shall set an insulation fault, inhibit charging, and limit discharge power to the calibrated safe value. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-803

**Open issues:** Add the insulation-monitoring requirement source and confirm the threshold/safe power values.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-BMS-804 — Thermal Propagation Warning

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the cell temperature gradient exceeds the calibrated propagation threshold for more than 500 ms, the BMS shall set a thermal-propagation warning and request controlled shutdown.

**Rationale:** The source detects a temperature gradient but does not define a propagation-specific warning/shutdown reaction.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Thermal Propagation Warning' occurs.
- **Then:** When the cell temperature gradient exceeds the calibrated propagation threshold for more than 500 ms, the BMS shall set a thermal-propagation warning and request controlled shutdown.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `500 ms` → 499.99, 500.0, 500.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-804

**Open issues:** Confirm the propagation threshold and 500 ms reaction with the battery safety analysis.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-805 — SOC and SOH Plausibility

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The BMS shall validate the SOC and SOH estimates against the voltage-based and charge-integration references.

**Rationale:** The source defines clamping and SOH estimation but not a cross-check/plausibility requirement for the estimates.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'SOC and SOH Plausibility' occurs.
- **Then:** The BMS shall validate the SOC and SOH estimates against the voltage-based and charge-integration references.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-805

**Split into:** REQ-BMS-1018

**Open issues:** Confirm the calibrated SOC/SOH plausibility tolerance and the fault reaction.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1018; the original ID retains part 1.

---

### REQ-BMS-806 — Cell Balancing Fault Handling

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When a balance relay or bleed-resistor feedback indicates a stuck-on or open circuit for more than 200 ms, the BMS shall disable balancing and set a balancing fault DTC.

**Rationale:** The source commands balancing but does not define the fault reaction for a failed balance relay.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Cell Balancing Fault Handling' occurs and persists for the specified debounce.
- **Then:** When a balance relay or bleed-resistor feedback indicates a stuck-on or open circuit for more than 200 ms, the BMS shall disable balancing and set a balancing fault DTC. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `200 ms` → 199.99, 200.0, 200.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-806

**Open issues:** Confirm the relay feedback mechanism and 200 ms detection window.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-BMS-807 — Diagnostic Freeze Frame and Persistence

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The BMS shall capture a freeze frame for each safety-relevant DTC containing pack current, pack voltage, cell voltage extrema, temperature extrema and SOC at the time of the fault, and persist it in NVM.

**Rationale:** The source names DTCs but does not define freeze-frame content or persistence.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Diagnostic Freeze Frame and Persistence' occurs.
- **Then:** The BMS shall capture a freeze frame for each safety-relevant DTC containing pack current, pack voltage, cell voltage extrema, temperature extrema and SOC at the time of the fault, and persist it in NVM.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-807

**Open issues:** Confirm the freeze-frame data set and NVM block layout.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-808 — Calibration Verification

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** At startup and after a calibration update, the BMS shall verify that every safety-relevant calibration parameter is within its declared range and consistent with the battery variant.

**Rationale:** The source exposes many calibration constants but does not require their verification.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Calibration Verification' occurs.
- **Then:** At startup and after a calibration update, the BMS shall verify that every safety-relevant calibration parameter is within its declared range and consistent with the battery variant.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-808

**Open issues:** Define the safety-relevant calibration list, ranges and variant matrix.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-809 — Software and Calibration Update Integrity

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The BMS shall only accept authenticated and integrity-protected software and calibration updates.

**Rationale:** A safety-critical high-voltage controller needs update integrity; the source set does not address cybersecurity.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The BMS shall only accept authenticated and integrity-protected software and calibration updates. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-809

**Split into:** REQ-BMS-1019

**Open issues:** Develop the full ISO 21434 cybersecurity requirements; this is a placeholder.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1019; the original ID retains part 1.

---

### REQ-BMS-810 — Battery Variant Configuration

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The BMS shall select cell count, capacity, chemistry, voltage limits and thermal limits from a validated battery-variant configuration.

**Rationale:** The source assumes 96 cells and a 100 Ah pack; other variants need explicit configuration handling.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The BMS shall select cell count, capacity, chemistry, voltage limits and thermal limits from a validated battery-variant configuration. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-810

**Open issues:** Define the variant matrix and configuration source.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-811 — Fault Injection and Observability

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The BMS shall expose test hooks to inject cell-sensor loss, contactor weld, insulation, thermal-gradient and plausibility faults.

**Rationale:** Verification of the safety mechanisms needs controllability and observability.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The BMS shall expose test hooks to inject cell-sensor loss, contactor weld, insulation, thermal-gradient and plausibility faults. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-811

**Split into:** REQ-BMS-1020

**Open issues:** Confirm the production-disable mechanism for the test hooks.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1020; the original ID retains part 1.

---

### REQ-BMS-1001 — SOC Clamping — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** DTC_BMS_SOC_LIMIT shall be set when the raw SOC estimate exceeds 95.0 % or falls below 5.0 % for more than 10 consecutive cycles.

**Rationale:** SOC clamping protects the usable window and triggers a DTC when the raw estimate leaves 5-95% for 10 consecutive cycles. Split from REQ-BMS-022.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'SOC Clamping — Part 2' occurs.
- **Then:** DTC_BMS_SOC_LIMIT shall be set when the raw SOC estimate exceeds 95.0 % or falls below 5.0 % for more than 10 consecutive cycles.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `95.0 %` → 94.99, 95.0, 95.01
- `5.0 %` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1001

**Split from:** `REQ-BMS-022`

**Open issues:** Split from REQ-BMS-022; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1002 — Current Integration Backup — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Coulomb counting accumulation error shall not exceed ±2% SOC per hour.

**Rationale:** Coulomb-counting fallback when the voltage measurement is unavailable; the 2% SOC/hour error is the source's stated accuracy target. Split from REQ-BMS-023.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Current Integration Backup — Part 2' occurs.
- **Then:** Coulomb counting accumulation error shall not exceed ±2% SOC per hour.
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `2%` → 1.99, 2.0, 2.01

**Trace:** parent=REQ-BMS-000 · design=RE_EstimateSOC, SWC_BatteryManagement · test=TD-REQ-BMS-1002

**Split from:** `REQ-BMS-023`

**Open issues:** Split from REQ-BMS-023; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1003 — Balancing Cell Selection Limit — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If more than 8 cells exceed the threshold, the 8 cells with highest V_delta shall be selected.

**Rationale:** Limits simultaneous bleed resistors to 8 to bound heat generation and selects the highest-delta cells when more than 8 are candidates. Split from REQ-BMS-031.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Balancing Cell Selection Limit — Part 2' occurs.
- **Then:** If more than 8 cells exceed the threshold, the 8 cells with highest V_delta shall be selected.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1003

**Split from:** `REQ-BMS-031`

**Open issues:** Split from REQ-BMS-031; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1004 — Balance Relay Control — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Balancing shall be inhibited (all relays open) when pack current I_pack > 5 A (charging or discharging) to prevent measurement interference.

**Rationale:** Balancing is inhibited above 5 A pack current to prevent measurement interference; the 1 ms SPI write is a timing constraint. Split from REQ-BMS-032.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Balance Relay Control — Part 2' occurs.
- **Then:** Balancing shall be inhibited (all relays open) when pack current I_pack > 5 A (charging or discharging) to prevent measurement interference.
- **Tolerance:** ±0.01 A at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `5 A` → 4.99, 5.0, 5.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1004

**Split from:** `REQ-BMS-032`

**Open issues:** Split from REQ-BMS-032; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1005 — Temperature Gradient Calculation — Part 2

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If T_gradient > TEMP_GRADIENT_LIMIT_K (8 K) for more than 5 consecutive 50 ms cycles, DTC_BMS_TEMP_GRADIENT (0xB10006) shall be set.

**Rationale:** Derived from REQ-BMS-000. Source notes: High gradient indicates cooling blockage or cell degradation; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-BMS-040.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Temperature Gradient Calculation — Part 2' occurs.
- **Then:** If T_gradient > TEMP_GRADIENT_LIMIT_K (8 K) for more than 5 consecutive 50 ms cycles, DTC_BMS_TEMP_GRADIENT (0xB10006) shall be set.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `50 ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1005

**Split from:** `REQ-BMS-040`

**Open issues:** Split from REQ-BMS-040; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1006 — Cooling PWM Control — Part 2

**Type:** functional · **ASIL:** ASIL-C · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Duty cycle shall be clamped to [PWM_MIN = 0 %, PWM_MAX = 100 %].

**Rationale:** Derived from REQ-BMS-000. Source notes: PI controller; integral windup protection: clamp integral when output saturated; req_type=FUNCTIONAL; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from REQ-BMS-041.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Cooling PWM Control — Part 2' occurs.
- **Then:** Duty cycle shall be clamped to [PWM_MIN = 0 %, PWM_MAX = 100 %].
- **Tolerance:** ±0.01 % at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `0 %` → -0.01, 0.0, 0.01
- `100 %` → 99.99, 100.0, 100.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1006

**Split from:** `REQ-BMS-041`

**Open issues:** Split from REQ-BMS-041; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1007 — Overcurrent Detection — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If I_pack > I_MAX_DISCHARGE or I_pack < I_MAX_CHARGE for more than 2 consecutive cycles (10 ms debounce), OpenContactors() shall be called and DTC_BMS_OVERCURRENT (0xB10001) set.

**Rationale:** Overcurrent protection thresholds are 300 A discharge and -150 A charge with a 10 ms debounce. These are narrower than the port range of +/-500 A and must be reconciled with the fuse and sensor range. Split from REQ-BMS-050.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Overcurrent Detection — Part 2' occurs.
- **Then:** If I_pack > I_MAX_DISCHARGE or I_pack < I_MAX_CHARGE for more than 2 consecutive cycles (10 ms debounce), OpenContactors() shall be called and DTC_BMS_OVERCURRENT (0xB10001) set.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-1007

**Split from:** `REQ-BMS-050`

**Open issues:** Split from REQ-BMS-050; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1008 — Overvoltage / Undervoltage Detection — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If any cell exceeds V_CELL_MAX or drops below V_CELL_MIN for 2 consecutive cycles, OpenContactors() shall be called and the corresponding DTC DTC_BMS_OVERVOLTAGE (0xB10004) or DTC_BMS_UNDERVOLTAGE (0xB10005) set.

**Rationale:** Cell over/undervoltage protection at 4.20 V / 2.50 V with a two-cycle debounce. Split from REQ-BMS-051.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Overvoltage / Undervoltage Detection — Part 2' occurs.
- **Then:** If any cell exceeds V_CELL_MAX or drops below V_CELL_MIN for 2 consecutive cycles, OpenContactors() shall be called and the corresponding DTC DTC_BMS_OVERVOLTAGE (0xB10004) or DTC_BMS_UNDERVOLTAGE (0xB10005) set.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-1008

**Split from:** `REQ-BMS-051`

**Open issues:** Split from REQ-BMS-051; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1009 — Overtemperature Detection — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If T_max exceeds T_CELL_MAX_K for 4 consecutive cycles (20 ms), OpenContactors() shall be called and DTC_BMS_OVERTEMP (0xB10002) set.

**Rationale:** Overtemperature protection at 60 C with a 20 ms debounce; recovery is intentionally manual for a thermal event. Split from REQ-BMS-052.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Overtemperature Detection — Part 2' occurs.
- **Then:** If T_max exceeds T_CELL_MAX_K for 4 consecutive cycles (20 ms), OpenContactors() shall be called and DTC_BMS_OVERTEMP (0xB10002) set.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `20 ms` → 19.99, 20.0, 20.01

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-1009

**Split from:** `REQ-BMS-052`

**Open issues:** Split from REQ-BMS-052; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1010 — Overtemperature Detection — Part 3

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Recovery shall require manual service reset; automatic recovery is inhibited.

**Rationale:** Overtemperature protection at 60 C with a 20 ms debounce; recovery is intentionally manual for a thermal event. Split from REQ-BMS-052.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Overtemperature Detection — Part 3' occurs.
- **Then:** Recovery shall require manual service reset; automatic recovery is inhibited.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-1010

**Split from:** `REQ-BMS-052`

**Open issues:** Split from REQ-BMS-052; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1011 — Contactor State Verification — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** If commanded != actual for more than 50 ms, DTC_BMS_CONTACTOR_WELD (0xB10007) shall be set.

**Rationale:** Contactor feedback mismatch for more than 50 ms is treated as a weld fault and drives FAIL_SAFE. Split from REQ-BMS-061.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Contactor State Verification — Part 2' occurs.
- **Then:** If commanded != actual for more than 50 ms, DTC_BMS_CONTACTOR_WELD (0xB10007) shall be set.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `50 ms` → 49.99, 50.0, 50.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1011

**Split from:** `REQ-BMS-061`

**Open issues:** Split from REQ-BMS-061; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1012 — Contactor State Verification — Part 3

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The system shall transition to FAIL_SAFE mode.

**Rationale:** Contactor feedback mismatch for more than 50 ms is treated as a weld fault and drives FAIL_SAFE. Split from REQ-BMS-061.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Contactor State Verification — Part 3' occurs.
- **Then:** The system shall transition to FAIL_SAFE mode.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1012

**Split from:** `REQ-BMS-061`

**Open issues:** Split from REQ-BMS-061; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1013 — DTC Healing — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** Healing counters shall be reset on each fault recurrence.

**Rationale:** Healable DTCs clear after 5 fault-free cycles; the overtemperature latch is intentionally excluded. Split from REQ-BMS-081.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'DTC Healing — Part 2' occurs.
- **Then:** Healing counters shall be reset on each fault recurrence.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1013

**Split from:** `REQ-BMS-081`

**Open issues:** Split from REQ-BMS-081; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1014 — E2E Protection — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** E2E counter mismatch on RP_PackCurrent shall trigger DTC_BMS_CAN_TIMEOUT (0xB10008) after 3 consecutive failures at 10 ms cycle.

**Rationale:** E2E Profile 2 protection on safety-relevant CAN inputs; a counter mismatch triggers a CAN-timeout DTC after 3 consecutive failures. Split from REQ-BMS-090.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'E2E Protection — Part 2' occurs and persists for the specified debounce.
- **Then:** E2E counter mismatch on RP_PackCurrent shall trigger DTC_BMS_CAN_TIMEOUT (0xB10008) after 3 consecutive failures at 10 ms cycle. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1014

**Split from:** `REQ-BMS-090`

**Open issues:** Split from REQ-BMS-090; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-BMS-1015 — Watchdog Supervision — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** A missed watchdog trigger shall cause the ASIL-D hardware watchdog to reset the ECU.

**Rationale:** Hardware watchdog trigger every 5 ms; a missed trigger resets the ECU and the reset cause is persisted as a DTC. Split from REQ-BMS-091.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Supervision — Part 2' occurs and persists for the specified debounce.
- **Then:** A missed watchdog trigger shall cause the ASIL-D hardware watchdog to reset the ECU. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-1015

**Split from:** `REQ-BMS-091`

**Open issues:** Split from REQ-BMS-091; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-BMS-1016 — Watchdog Supervision — Part 3

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** On restart, the SWC shall detect the watchdog reset cause via McuResetCause register and set DTC_BMS_WATCHDOG (0xB10009).

**Rationale:** Hardware watchdog trigger every 5 ms; a missed trigger resets the ECU and the reset cause is persisted as a DTC. Split from REQ-BMS-091.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Watchdog Supervision — Part 3' occurs and persists for the specified debounce.
- **Then:** On restart, the SWC shall detect the watchdog reset cause via McuResetCause register and set DTC_BMS_WATCHDOG (0xB10009). The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=RE_MonitorSafety, SWC_BatteryManagement · test=TD-REQ-BMS-1016

**Split from:** `REQ-BMS-091`

**Open issues:** Split from REQ-BMS-091; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-BMS-1018 — SOC and SOH Plausibility — Part 2

**Type:** safety · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The BMS shall flag a plausibility fault when the deviation exceeds the calibrated tolerance.

**Rationale:** The source defines clamping and SOH estimation but not a cross-check/plausibility requirement for the estimates. Split from REQ-BMS-805.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'SOC and SOH Plausibility — Part 2' occurs and persists for the specified debounce.
- **Then:** The BMS shall flag a plausibility fault when the deviation exceeds the calibrated tolerance. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1018

**Split from:** `REQ-BMS-805`

**Open issues:** Split from REQ-BMS-805; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### REQ-BMS-1019 — Software and Calibration Update Integrity — Part 2

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The BMS shall record a fault when verification fails.

**Rationale:** A safety-critical high-voltage controller needs update integrity; the source set does not address cybersecurity. Split from REQ-BMS-809.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The BMS shall record a fault when verification fails. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1019

**Split from:** `REQ-BMS-809`

**Open issues:** Split from REQ-BMS-809; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### REQ-BMS-1020 — Fault Injection and Observability — Part 2

**Type:** constraint · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The BMS shall publish the resulting mode and DTC bitmask.

**Rationale:** Verification of the safety mechanisms needs controllability and observability. Split from REQ-BMS-811.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The BMS shall publish the resulting mode and DTC bitmask. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=REQ-BMS-000 · design=SWC_BatteryManagement · test=TD-REQ-BMS-1020

**Split from:** `REQ-BMS-811`

**Open issues:** Split from REQ-BMS-811; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## System

### REQ-BMS-000 — BMS System Requirements Baseline

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The BMS software requirements baseline shall be allocated to SWC_BatteryManagement on ECU_BMS_Main.

**Rationale:** The source CSV has no system/stakeholder hierarchy. This placeholder enables traceability without inventing a stakeholder requirement.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'BMS System Requirements Baseline' occurs.
- **Then:** The BMS software requirements baseline shall be allocated to SWC_BatteryManagement on ECU_BMS_Main.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-BMS-000

**Split into:** REQ-BMS-1017

**Open issues:** Placeholder system parent; replace with the real battery system/stakeholder requirement and confirm ASIL allocation.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into REQ-BMS-1017; the original ID retains part 1.

---

### REQ-BMS-1017 — BMS System Requirements Baseline — Part 2

**Type:** functional · **ASIL:** ASIL-D · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The BMS software requirements baseline shall trace to the battery system/stakeholder requirements.

**Rationale:** The source CSV has no system/stakeholder hierarchy. This placeholder enables traceability without inventing a stakeholder requirement. Split from REQ-BMS-000.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'BMS System Requirements Baseline — Part 2' occurs.
- **Then:** The BMS software requirements baseline shall trace to the battery system/stakeholder requirements.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-REQ-BMS-1017

**Split from:** `REQ-BMS-000`

**Open issues:** Split from REQ-BMS-000; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---
