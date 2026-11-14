# FOC requirements — polished L2-oriented draft

> Status: **review draft**. Human approval required. Not certified.
> Source: `inputs/requirements/samples/Motcontrolcomp.csv` (unchanged).
> Requirements: **48** (44 retained/derived + 4 atomic split parts).

## How to read this document

Each requirement is atomic where possible. 4 compound requirements were split into 4 atomic parts; the original ID keeps part 1 and parts 2+ use `ARCH-REQ-1001..ARCH-REQ-1004`. Acceptance criteria are drafts derived from the source text. Open issues are decisions for the human reviewer, not hidden assumptions.

## Summary by allocation

| Allocation | Requirements |
|---|---|
| CurrCtrl | 8 |
| MtrMon | 16 |
| SpdCtrl | 6 |
| System | 18 |

## CurrCtrl

### ARCH-REQ-030 — Component: CurrCtrl

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** CurrCtrl shall convert d-axis and q-axis current errors into d-axis and q-axis voltage commands using the specified current-control algorithm with decoupling feedforward and voltage limiting.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Read currents -> errors -> PI d/q -> decoupling -> voltage limit -> write Vd/Vq; Level=Architecture; Subsystem=Current Control; InputInterfaces=IdRef; IqRef; IdFbk; IqFbk; VdcBus; OutputInterfaces=VdCmd; VqCmd; TimingOrTrigger=100 us; VerificationMethod=Unit test; MIL test; MUD_Flowchart_Derivation_Hint=Read currents -> errors -> PI d/q -> decoupling -> voltage limit -> write Vd/Vq. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: CurrCtrl' occurs.
- **Then:** CurrCtrl shall convert d-axis and q-axis current errors into d-axis and q-axis voltage commands using the specified current-control algorithm with decoupling feedforward and voltage limiting.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=CurrCtrl · test=TD-ARCH-REQ-030

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-031 — Component: CurrCtrl

**Type:** interface · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** CurrCtrl shall consume IqRef from SpdCtrl and IdRef from MTPA or zero-reference source.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Input merge block for IdRef/IqRef; Level=Architecture; Subsystem=Current Control; InputInterfaces=IqRef; IdRef; TimingOrTrigger=100 us; VerificationMethod=Interface review; integration test; MUD_Flowchart_Derivation_Hint=Input merge block for IdRef/IqRef. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The CurrCtrl component is running and the referenced producer/consumer ports are connected.
- **When:** Component: CurrCtrl is exercised at its defined update rate.
- **Then:** CurrCtrl shall consume IqRef from SpdCtrl and IdRef from MTPA or zero-reference source. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=CurrCtrl · test=TD-ARCH-REQ-031

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### ARCH-REQ-032 — Component: CurrCtrl

**Type:** interface · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** CurrCtrl shall output voltage commands to SVM/PWM using signed voltage command interfaces with defined scaling.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Output block to PWM/SVM; Level=Architecture; Subsystem=Current Control; OutputInterfaces=VdCmd; VqCmd; TimingOrTrigger=100 us; VerificationMethod=Interface review; integration test; MUD_Flowchart_Derivation_Hint=Output block to PWM/SVM. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The CurrCtrl component is running and the referenced producer/consumer ports are connected.
- **When:** Component: CurrCtrl is exercised at its defined update rate.
- **Then:** CurrCtrl shall output voltage commands to SVM/PWM using signed voltage command interfaces with defined scaling. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=CurrCtrl · test=TD-ARCH-REQ-032

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### ARCH-REQ-033 — Component: CurrCtrl

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** CurrCtrl shall limit the voltage vector magnitude according to DC bus voltage and configured voltage limit before publishing voltage commands.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: voltage magnitude > limit? yes -> scale Vd/Vq; Level=Architecture; Subsystem=Current Control; InputInterfaces=VdcBus; VoltLim; OutputInterfaces=VdCmd; VqCmd; TimingOrTrigger=100 us; VerificationMethod=Boundary test; HIL test; MUD_Flowchart_Derivation_Hint=Decision: voltage magnitude > limit? yes -> scale Vd/Vq. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Component: CurrCtrl' occurs.
- **Then:** CurrCtrl shall limit the voltage vector magnitude according to DC bus voltage and configured voltage limit before publishing voltage commands.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=CurrCtrl · test=TD-ARCH-REQ-033

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-034 — Component: CurrCtrl

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** CurrCtrl shall initialize d-axis and q-axis PI integrator states to zero and publish safe zero voltage commands at startup.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Startup safe output block; Level=Architecture; Subsystem=Current Control; InputInterfaces=IdFbk; IqFbk; IdRef; IqRef; VdcBus; OutputInterfaces=VdCmd; VqCmd; IdIntgState; IqIntgState; TimingOrTrigger=Startup; VerificationMethod=Startup unit test; MUD_Flowchart_Derivation_Hint=Startup safe output block. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: CurrCtrl' occurs.
- **Then:** CurrCtrl shall initialize d-axis and q-axis PI integrator states to zero and publish safe zero voltage commands at startup.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=CurrCtrl · test=TD-ARCH-REQ-034

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-035 — Component: CurrCtrl

**Type:** timing · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** CurrCtrl shall complete execution within its 100 us period budget.

**Rationale:** Derived from ARCH-REQ-000. Source notes: No blocking calls, no dynamic memory, fixed computation path; Level=Architecture; Subsystem=Current Control; TimingOrTrigger=100 us period; <30 us budget; VerificationMethod=Trace/profiler timing test; WCET review; MUD_Flowchart_Derivation_Hint=No blocking calls, no dynamic memory, fixed computation path; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The defined trigger occurs.
- **Then:** CurrCtrl shall complete execution within its 100 us period budget. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=CurrCtrl · test=TD-ARCH-REQ-035

**Split into:** ARCH-REQ-1001

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Cycle period is not specified; confirm the scheduling contract.; Split into ARCH-REQ-1001; the original ID retains part 1.

---

### ARCH-REQ-036 — Component: CurrCtrl

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** CurrCtrl shall expose d/q PI gains, electrical parameters, nominal DC voltage, and voltage limit as calibration parameters.

**Rationale:** d/q PI gains, electrical parameters, nominal DC voltage and voltage limit are exposed as calibration parameters.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** CurrCtrl shall expose d/q PI gains, electrical parameters, nominal DC voltage, and voltage limit as calibration parameters. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=CurrCtrl · test=TD-ARCH-REQ-036

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-1001 — Component: CurrCtrl — Part 2

**Type:** timing · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** CurrCtrl shall not exceed the allocated timing budget.

**Rationale:** Derived from ARCH-REQ-000. Source notes: No blocking calls, no dynamic memory, fixed computation path; Level=Architecture; Subsystem=Current Control; TimingOrTrigger=100 us period; <30 us budget; VerificationMethod=Trace/profiler timing test; WCET review; MUD_Flowchart_Derivation_Hint=No blocking calls, no dynamic memory, fixed computation path; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from ARCH-REQ-035.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The defined trigger occurs.
- **Then:** CurrCtrl shall not exceed the allocated timing budget. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=CurrCtrl · test=TD-ARCH-REQ-1001

**Split from:** `ARCH-REQ-035`

**Open issues:** Split from ARCH-REQ-035; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Cycle period is not specified; confirm the scheduling contract.

---

## MtrMon

### ARCH-REQ-040 — Component: MtrMon

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** MtrMon shall monitor phase-current-derived Id/Iq, DC bus voltage, speed, and motor temperature to determine motor protection status.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Monitor flow with separate electrical and thermal branches; Level=Architecture; Subsystem=Motor Monitoring; InputInterfaces=IdMon; IqMon; VdcMon; SpdMon; MtrT; OutputInterfaces=MtrProtSt; OcSt; OtSt; IqMaxOut; TimingOrTrigger=1 ms / 10 ms; VerificationMethod=Unit test; MIL/SIL test; MUD_Flowchart_Derivation_Hint=Monitor flow with separate electrical and thermal branches. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: MtrMon' occurs.
- **Then:** MtrMon shall monitor phase-current-derived Id/Iq, DC bus voltage, speed, and motor temperature to determine motor protection status.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-040

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-041 — Component: MtrMon

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** MtrMon shall detect overcurrent using the d/q current vector magnitude compared against calibrated overcurrent threshold.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: Id^2 + Iq^2 > IOcThd^2; Level=Architecture; Subsystem=Motor Monitoring; InputInterfaces=IdMon; IqMon; IOcThd; OutputInterfaces=OcSt; MtrProtSt; TimingOrTrigger=1 ms; VerificationMethod=Fault injection test; boundary test; MUD_Flowchart_Derivation_Hint=Decision: Id^2 + Iq^2 > IOcThd^2. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Component: MtrMon' occurs and persists for the specified debounce.
- **Then:** MtrMon shall detect overcurrent using the d/q current vector magnitude compared against calibrated overcurrent threshold. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-041

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-042 — Component: MtrMon

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** MtrMon shall detect DC bus overvoltage and undervoltage using calibrated thresholds and publish a fault status when thresholds are violated.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision blocks for Vdc > OV and Vdc < UV; Level=Architecture; Subsystem=Motor Monitoring; InputInterfaces=VdcMon; VdcOvThd; VdcUvThd; OutputInterfaces=MtrProtSt; IqMaxOut; TimingOrTrigger=1 ms; VerificationMethod=Fault injection test; boundary test; MUD_Flowchart_Derivation_Hint=Decision blocks for Vdc > OV and Vdc < UV. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Component: MtrMon' occurs and persists for the specified debounce.
- **Then:** MtrMon shall detect DC bus overvoltage and undervoltage using calibrated thresholds and publish a fault status when thresholds are violated. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-042

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-043 — Component: MtrMon

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** MtrMon shall detect overspeed using actual speed compared against a calibrated overspeed threshold.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: SpdMon > OsSpdThd; Level=Architecture; Subsystem=Motor Monitoring; InputInterfaces=SpdMon; OsSpdThd; OutputInterfaces=MtrProtSt; IqMaxOut; TimingOrTrigger=1 ms; VerificationMethod=Fault injection test; boundary test; MUD_Flowchart_Derivation_Hint=Decision: SpdMon > OsSpdThd. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Component: MtrMon' occurs.
- **Then:** MtrMon shall detect overspeed using actual speed compared against a calibrated overspeed threshold.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-043

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-044 — Component: MtrMon

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** MtrMon shall detect overtemperature with hysteresis to prevent status chattering.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: temp >= threshold -> OT active; temp <= threshold-hyst -> clear; Level=Architecture; Subsystem=Motor Monitoring; InputInterfaces=MtrT; TOtThd; TOtHyst; OutputInterfaces=OtSt; MtrProtSt; TimingOrTrigger=10 ms; VerificationMethod=Fault injection test; hysteresis test; MUD_Flowchart_Derivation_Hint=Decision: temp >= threshold -> OT active; temp <= threshold-hyst -> clear. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Component: MtrMon' occurs and persists for the specified debounce.
- **Then:** MtrMon shall detect overtemperature with hysteresis to prevent status chattering. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-044

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-045 — Component: MtrMon

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** MtrMon shall derate IqMaxOut based on motor temperature.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: hard fault? zero; warning/thermal? derate; else nominal; Level=Architecture; Subsystem=Motor Monitoring; InputInterfaces=MtrT; protection status; IqMaxNom; IqDerateSlope; OutputInterfaces=IqMaxOut; TimingOrTrigger=10 ms and fault update; VerificationMethod=Boundary test; HIL test; MUD_Flowchart_Derivation_Hint=Decision: hard fault? zero; warning/thermal? derate; else nominal; split into 2 atomic parts. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: MtrMon' occurs.
- **Then:** MtrMon shall derate IqMaxOut based on motor temperature.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-045

**Split into:** ARCH-REQ-1002

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into ARCH-REQ-1002; the original ID retains part 1.

---

### ARCH-REQ-046 — Component: MtrMon

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** MtrMon shall initialize protection states to non-fault default and publish nominal IqMaxOut at startup if input values are valid.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Startup monitor state initialization; Level=Architecture; Subsystem=Motor Monitoring; InputInterfaces=IdMon; IqMon; MtrT; VdcMon; OutputInterfaces=IqMaxOut; MtrProtSt; OcSt; OtSt; TimingOrTrigger=Startup; VerificationMethod=Startup unit test; MUD_Flowchart_Derivation_Hint=Startup monitor state initialization. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: MtrMon' occurs.
- **Then:** MtrMon shall initialize protection states to non-fault default and publish nominal IqMaxOut at startup if input values are valid.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-046

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-047 — Component: MtrMon

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** MtrMon shall expose thresholds for overcurrent, overtemperature, DC bus limits, overspeed, nominal Iq limit, and derating slope as calibration parameters.

**Rationale:** Overcurrent, overtemperature, DC-bus, overspeed, nominal Iq and derating parameters are exposed as calibration parameters.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** MtrMon shall expose thresholds for overcurrent, overtemperature, DC bus limits, overspeed, nominal Iq limit, and derating slope as calibration parameters. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-047

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-801 — Phase Current Sensor Loss

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When a phase-current measurement is invalid for more than 100 us, the motor controller shall disable current control and force the inverter to a safe state.

**Rationale:** The source monitors overcurrent but does not define the reaction to loss of a phase-current measurement.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Phase Current Sensor Loss' occurs and persists for the specified debounce.
- **Then:** When a phase-current measurement is invalid for more than 100 us, the motor controller shall disable current control and force the inverter to a safe state. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-801

**Open issues:** 100 us reaction and inverter safe state are proposed; confirm with the motor-control safety analysis.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-802 — PWM and Inverter Fault Reaction

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the PWM stage or inverter reports a fault, the motor controller shall disable PWM outputs and set the motor protection status to the hard-fault state.

**Rationale:** The source defines a protection reaction but not the PWM/inverter fault interface and hard-fault state.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'PWM and Inverter Fault Reaction' occurs and persists for the specified debounce.
- **Then:** When the PWM stage or inverter reports a fault, the motor controller shall disable PWM outputs and set the motor protection status to the hard-fault state. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-802

**Open issues:** Confirm the inverter fault signals and the safe PWM state.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-803 — DC Bus Fault Reaction

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the DC-bus voltage exceeds the calibrated overvoltage threshold or falls below the calibrated undervoltage threshold, the motor controller shall disable torque production and set the DC-bus fault status.

**Rationale:** The source detects DC-bus over/undervoltage but does not define the torque-disable reaction.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'DC Bus Fault Reaction' occurs and persists for the specified debounce.
- **Then:** When the DC-bus voltage exceeds the calibrated overvoltage threshold or falls below the calibrated undervoltage threshold, the motor controller shall disable torque production and set the DC-bus fault status. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-803

**Open issues:** Confirm the torque-disable reaction and recovery thresholds.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-804 — Motor Overtemperature Derating

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The motor controller shall derate the maximum q-axis current linearly from the calibrated derating start temperature to zero at the calibrated maximum temperature.

**Rationale:** The source defines a derating slope and hysteresis but not the full temperature-to-zero mapping.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Motor Overtemperature Derating' occurs.
- **Then:** The motor controller shall derate the maximum q-axis current linearly from the calibrated derating start temperature to zero at the calibrated maximum temperature.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-804

**Open issues:** Confirm the derating start/max temperatures and slope with the motor calibration.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-805 — Position and Speed Observer Fault

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** When the position or speed observer is invalid for more than 1 ms, the motor controller shall disable torque production and set a protection fault.

**Rationale:** The source uses the observer but does not define its fault detection or reaction.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Position and Speed Observer Fault' occurs and persists for the specified debounce.
- **Then:** When the position or speed observer is invalid for more than 1 ms, the motor controller shall disable torque production and set a protection fault. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1 ms` → 0.99, 1.0, 1.01

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-805

**Open issues:** Confirm the observer validity criteria and 1 ms reaction.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-808 — Fault Injection and Observability

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The motor controller shall expose test hooks to inject phase-current loss, inverter fault, DC-bus fault, overtemperature and observer faults.

**Rationale:** Verification of the protection mechanisms needs controllability and observability.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The motor controller shall expose test hooks to inject phase-current loss, inverter fault, DC-bus fault, overtemperature and observer faults. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-808

**Split into:** ARCH-REQ-1004

**Open issues:** Confirm the production-disable mechanism for the test hooks.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into ARCH-REQ-1004; the original ID retains part 1.

---

### ARCH-REQ-1002 — Component: MtrMon — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** MtrMon shall set IqMaxOut to zero for active hard faults.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: hard fault? zero; warning/thermal? derate; else nominal; Level=Architecture; Subsystem=Motor Monitoring; InputInterfaces=MtrT; protection status; IqMaxNom; IqDerateSlope; OutputInterfaces=IqMaxOut; TimingOrTrigger=10 ms and fault update; VerificationMethod=Boundary test; HIL test; MUD_Flowchart_Derivation_Hint=Decision: hard fault? zero; warning/thermal? derate; else nominal; split into 2 atomic parts. Rationale to be confirmed by the requirement owner. Split from ARCH-REQ-045.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: MtrMon — Part 2' occurs.
- **Then:** MtrMon shall set IqMaxOut to zero for active hard faults.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-1002

**Split from:** `ARCH-REQ-045`

**Open issues:** Split from ARCH-REQ-045; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-1004 — Fault Injection and Observability — Part 2

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The motor controller shall publish the resulting protection status.

**Rationale:** Verification of the protection mechanisms needs controllability and observability. Split from ARCH-REQ-808.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The motor controller shall publish the resulting protection status. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=MtrMon · test=TD-ARCH-REQ-1004

**Split from:** `ARCH-REQ-808`

**Open issues:** Split from ARCH-REQ-808; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## SpdCtrl

### ARCH-REQ-020 — Component: SpdCtrl

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SpdCtrl shall convert speed error into a q-axis current reference using the specified speed-control algorithm with ramping, deadband, saturation and anti-windup.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Read speed -> ramp ref -> error -> deadband -> PI -> saturate -> anti-windup -> write IqRef; Level=Architecture; Subsystem=Speed Control; InputInterfaces=SpdRef; SpdFbk; IqMaxIn; OutputInterfaces=IqRef; TimingOrTrigger=1 ms; VerificationMethod=Unit test; MIL test; MUD_Flowchart_Derivation_Hint=Read speed -> ramp ref -> error -> deadband -> PI -> saturate -> anti-windup -> write IqRef. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: SpdCtrl' occurs.
- **Then:** SpdCtrl shall convert speed error into a q-axis current reference using the specified speed-control algorithm with ramping, deadband, saturation and anti-windup.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=SpdCtrl · test=TD-ARCH-REQ-020

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-021 — Component: SpdCtrl

**Type:** interface · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SpdCtrl shall read actual motor speed from SpeedObserver and speed reference from AppMgr through explicit RTE sender-receiver ports.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Input block for SpdFbk and SpdRef; Level=Architecture; Subsystem=Speed Control; InputInterfaces=SpdFbk; SpdRef; TimingOrTrigger=1 ms; VerificationMethod=Interface review; unit test; MUD_Flowchart_Derivation_Hint=Input block for SpdFbk and SpdRef. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The SpdCtrl component is running and the referenced producer/consumer ports are connected.
- **When:** Component: SpdCtrl is exercised at its defined update rate.
- **Then:** SpdCtrl shall read actual motor speed from SpeedObserver and speed reference from AppMgr through explicit RTE sender-receiver ports. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=SpdCtrl · test=TD-ARCH-REQ-021

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### ARCH-REQ-022 — Component: SpdCtrl

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SpdCtrl shall limit IqRef to the lower of configured controller output limit and IqMaxIn from MtrMon.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Saturation block using min(controller limit, IqMaxIn); Level=Architecture; Subsystem=Speed Control; InputInterfaces=IqMaxIn; OutputInterfaces=IqRef; TimingOrTrigger=1 ms; VerificationMethod=Fault injection test; boundary test; MUD_Flowchart_Derivation_Hint=Saturation block using min(controller limit, IqMaxIn). Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Component: SpdCtrl' occurs.
- **Then:** SpdCtrl shall limit IqRef to the lower of configured controller output limit and IqMaxIn from MtrMon.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=SpdCtrl · test=TD-ARCH-REQ-022

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-023 — Component: SpdCtrl

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SpdCtrl shall initialize speed PI integrator to zero and initialize ramped speed reference with current feedback speed to avoid startup torque step.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Startup flow for state initialization; Level=Architecture; Subsystem=Speed Control; InputInterfaces=SpdFbk; OutputInterfaces=SpdCtrlIntgState; SpdRefRamped; TimingOrTrigger=Startup; VerificationMethod=Startup unit test; MUD_Flowchart_Derivation_Hint=Startup flow for state initialization. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: SpdCtrl' occurs.
- **Then:** SpdCtrl shall initialize speed PI integrator to zero and initialize ramped speed reference with current feedback speed to avoid startup torque step.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=SpdCtrl · test=TD-ARCH-REQ-023

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-024 — Component: SpdCtrl

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** SpdCtrl shall set IqRef to zero and reset the integrator when operation mode leaves Run.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: OpMod != Run -> reset state and output zero; Level=Architecture; Subsystem=Speed Control; InputInterfaces=OpMod; OutputInterfaces=IqRef; SpdCtrlIntgState; TimingOrTrigger=ModeSwitchEvent; VerificationMethod=Mode transition test; MUD_Flowchart_Derivation_Hint=Decision: OpMod != Run -> reset state and output zero. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: SpdCtrl' occurs.
- **Then:** SpdCtrl shall set IqRef to zero and reset the integrator when operation mode leaves Run.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=SpdCtrl · test=TD-ARCH-REQ-024

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-025 — Component: SpdCtrl

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** SpdCtrl shall expose speed controller gains, speed error dead zone, ramp rate, and anti-windup limit as calibration parameters.

**Rationale:** Speed-controller gains, dead zone, ramp rate and anti-windup limit are exposed as calibration parameters.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** SpdCtrl shall expose speed controller gains, speed error dead zone, ramp rate, and anti-windup limit as calibration parameters. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=SpdCtrl · test=TD-ARCH-REQ-025

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

## System

### ARCH-REQ-000 — Motor Control System Requirements Baseline

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The PMSM field-oriented-control architecture shall be allocated to the motor-control software components.

**Rationale:** The source CSV has no system/stakeholder hierarchy. This placeholder enables traceability without inventing a stakeholder requirement.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Motor Control System Requirements Baseline' occurs.
- **Then:** The PMSM field-oriented-control architecture shall be allocated to the motor-control software components.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-ARCH-REQ-000

**Split into:** ARCH-REQ-1003

**Open issues:** Placeholder system parent; replace with the real inverter/motor system requirement and confirm ASIL allocation.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Split into ARCH-REQ-1003; the original ID retains part 1.

---

### ARCH-REQ-001 — Component: System

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The architecture shall implement a closed-loop motor control chain from speed reference to voltage command using speed control, current control, and motor monitoring components.

**Rationale:** Top-level closed-loop motor control architecture. The source is an architecture specification, not a formal requirement baseline; the hardening pass makes it reviewable.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: System' occurs.
- **Then:** The architecture shall implement a closed-loop motor control chain from speed reference to voltage command using speed control, current control, and motor monitoring components.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-001

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Placeholder system parent ARCH-REQ-000; confirm the stakeholder/system requirement and ASIL allocation with the motor-control owner.

---

### ARCH-REQ-002 — Component: System

**Type:** interface · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The architecture shall route SpdCtrl IqRef output to CurrCtrl IqRef input without scaling loss.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Create connector check between SpdCtrl and CurrCtrl; Level=Architecture; Subsystem=PMSM FOC Control; InputInterfaces=IqRef from SpdCtrl; OutputInterfaces=IqRef to CurrCtrl; TimingOrTrigger=Every speed control update and consumed by current control; VerificationMethod=Interface review; integration test; MUD_Flowchart_Derivation_Hint=Create connector check between SpdCtrl and CurrCtrl. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The System component is running and the referenced producer/consumer ports are connected.
- **When:** Component: System is exercised at its defined update rate.
- **Then:** The architecture shall route SpdCtrl IqRef output to CurrCtrl IqRef input without scaling loss. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-002

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### ARCH-REQ-003 — Component: System

**Type:** interface · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The architecture shall route MtrMon IqMaxOut output to SpdCtrl IqMaxIn input to limit commanded q-axis current during warning or fault conditions.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision block: if protection active then reduce or block IqRef; Level=Architecture; Subsystem=PMSM FOC Control; InputInterfaces=IqMaxOut; OutputInterfaces=IqMaxIn; TimingOrTrigger=Updated by MtrMon and consumed by SpdCtrl; VerificationMethod=Interface review; fault injection test; MUD_Flowchart_Derivation_Hint=Decision block: if protection active then reduce or block IqRef. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The System component is running and the referenced producer/consumer ports are connected.
- **When:** Component: System is exercised at its defined update rate.
- **Then:** The architecture shall route MtrMon IqMaxOut output to SpdCtrl IqMaxIn input to limit commanded q-axis current during warning or fault conditions. The observed data type, unit, range, resolution and update rate match the interface definition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-003

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.

---

### ARCH-REQ-004 — Component: System

**Type:** timing · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** The architecture shall schedule CurrCtrl faster than SpdCtrl so that the inner current loop reacts before the outer speed loop changes IqRef.

**Rationale:** The scheduling relationship is a timing constraint; the source phrase 'because ... shall react' is made a single verifiable statement.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The defined trigger occurs.
- **Then:** The architecture shall schedule CurrCtrl faster than SpdCtrl so that the inner current loop reacts before the outer speed loop changes IqRef. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-004

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Cycle period is not specified; confirm the scheduling contract.; Ambiguous phrase remains; confirm the measurable condition with the requirement owner.

---

### ARCH-REQ-005 — Component: System

**Type:** timing · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** analysis

**Statement:** The architecture shall schedule electrical protection monitoring at 1 ms and thermal monitoring at 10 ms.

**Rationale:** Protection-monitoring periods are fixed at 1 ms and 10 ms.

**Acceptance criteria (draft):**

- **Given:** The runnable is enabled and the scheduler is running.
- **When:** The defined trigger occurs.
- **Then:** The architecture shall schedule electrical protection monitoring at 1 ms and thermal monitoring at 10 ms. The runnable completes within its deadline/WCET budget and publishes updated outputs.
- **Tolerance:** ±0.01 ms at the specified threshold; otherwise ±1 LSB of the referenced interface.

**Boundary values:**

- `1 ms` → 0.99, 1.0, 1.01
- `10 ms` → 9.99, 10.0, 10.01

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-005

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; Cycle period is not specified; confirm the scheduling contract.

---

### ARCH-REQ-006 — Component: System

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The architecture shall force torque-producing current request to a safe limited value when overcurrent, overtemperature, DC-link fault, or overspeed protection is active.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: fault active? yes -> IqMax=0 or derated; no -> nominal limit; Level=Architecture; Subsystem=PMSM FOC Control; InputInterfaces=OcSt; OtSt; VdcMon; SpdMon; OutputInterfaces=IqMaxOut; MtrProtSt; IqRef; TimingOrTrigger=Cyclic monitoring; VerificationMethod=Fault injection test; HIL test; MUD_Flowchart_Derivation_Hint=Decision: fault active? yes -> IqMax=0 or derated; no -> nominal limit. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Component: System' occurs and persists for the specified debounce.
- **Then:** The architecture shall force torque-producing current request to a safe limited value when overcurrent, overtemperature, DC-link fault, or overspeed protection is active. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-006

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-007 — Component: System

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The architecture shall provide explicit motor protection status to the system manager and fault manager.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision hierarchy for highest active fault code; Level=Architecture; Subsystem=PMSM FOC Control; InputInterfaces=Protection conditions; OutputInterfaces=MtrProtSt; OcSt; OtSt; TimingOrTrigger=1 ms / 10 ms; VerificationMethod=Interface review; integration test; MUD_Flowchart_Derivation_Hint=Decision hierarchy for highest active fault code. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in a valid operating mode and the referenced inputs are available.
- **When:** The fault/condition described by 'Component: System' occurs and persists for the specified debounce.
- **Then:** The architecture shall provide explicit motor protection status to the system manager and fault manager. The specified safe reaction is completed within the FTTI.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-007

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.; FTTI is not specified in the source requirement; confirm with the safety analysis.

---

### ARCH-REQ-008 — Component: System

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The architecture shall initialize all controller internal states before enabling cyclic control runnables.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Start -> initialize states -> set safe outputs -> end; Level=Architecture; Subsystem=PMSM FOC Control; OutputInterfaces=IqRef; VdCmd; VqCmd; IqMaxOut; status outputs; TimingOrTrigger=ECU startup; VerificationMethod=Startup test; code review; MUD_Flowchart_Derivation_Hint=Start -> initialize states -> set safe outputs -> end. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: System' occurs.
- **Then:** The architecture shall initialize all controller internal states before enabling cyclic control runnables.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-008

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-009 — Component: System

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The architecture shall reset or freeze controller integrators during non-run operation modes to avoid unintended torque after mode transition.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Decision: OpMod==Run? no -> reset/freeze integrator; Level=Architecture; Subsystem=PMSM FOC Control; InputInterfaces=OpMod; OutputInterfaces=IqRef; integrator states; TimingOrTrigger=On mode transition; VerificationMethod=Mode transition test; MUD_Flowchart_Derivation_Hint=Decision: OpMod==Run? no -> reset/freeze integrator. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: System' occurs.
- **Then:** The architecture shall reset or freeze controller integrators during non-run operation modes to avoid unintended torque after mode transition.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-009

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-010 — Component: System

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The architecture shall use typed sender-receiver interfaces with defined units, ranges, and computation methods for all cross-component signals.

**Rationale:** Typed sender-receiver interfaces with units, ranges and computation methods are a data-dictionary constraint.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The architecture shall use typed sender-receiver interfaces with defined units, ranges, and computation methods for all cross-component signals. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-010

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-011 — Component: System

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The architecture shall protect shared controller and monitor internal states using exclusive areas where states may be accessed by more than one runnable or event.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Enter exclusive area -> update state -> exit exclusive area; Level=Architecture; Subsystem=PMSM FOC Control; InputInterfaces=IRVs; OutputInterfaces=IRVs; TimingOrTrigger=During state read/write; VerificationMethod=Code review; concurrency test; MUD_Flowchart_Derivation_Hint=Enter exclusive area -> update state -> exit exclusive area. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: System' occurs.
- **Then:** The architecture shall protect shared controller and monitor internal states using exclusive areas where states may be accessed by more than one runnable or event.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-011

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-012 — Component: System

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The architecture shall avoid dynamic memory allocation inside cyclic control and protection runnables.

**Rationale:** Derived from ARCH-REQ-000. Source notes: Implementation constraint note; Level=Architecture; Subsystem=PMSM FOC Control; TimingOrTrigger=All cyclic runnables; VerificationMethod=Code review; static analysis; MUD_Flowchart_Derivation_Hint=Implementation constraint note. Rationale to be confirmed by the requirement owner.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: System' occurs.
- **Then:** The architecture shall avoid dynamic memory allocation inside cyclic control and protection runnables.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-012

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-060 — Component: System

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The architecture shall be verified by component integration tests covering nominal run, startup, mode transition, current limit, overcurrent, overtemperature, DC-link fault, and overspeed scenarios.

**Rationale:** Verification constraint: component integration tests cover nominal run, startup, mode transition, current limit, overcurrent, overtemperature, DC-link fault and overspeed.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: System' occurs.
- **Then:** The architecture shall be verified by component integration tests covering nominal run, startup, mode transition, current limit, overcurrent, overtemperature, DC-link fault, and overspeed scenarios.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-060

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-061 — Component: System

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** Each architecture requirement shall be traceable to one or more MUD flowchart steps, runnable requirements, ports, calibration parameters, and verification cases.

**Rationale:** Traceability constraint: each architecture requirement traces to MUD steps, runnable requirements, ports, calibration parameters and verification cases.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Component: System' occurs.
- **Then:** Each architecture requirement shall be traceable to one or more MUD flowchart steps, runnable requirements, ports, calibration parameters, and verification cases.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-061

**Open issues:** Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-806 — Calibration Verification

**Type:** safety · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** At startup and after a calibration update, the motor controller shall verify that every safety-relevant calibration parameter is within its declared range and consistent with the motor/inverter variant.

**Rationale:** The source exposes calibration parameters but does not require their verification.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The action condition described by 'Calibration Verification' occurs.
- **Then:** At startup and after a calibration update, the motor controller shall verify that every safety-relevant calibration parameter is within its declared range and consistent with the motor/inverter variant.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-806

**Open issues:** Define the safety-relevant calibration list and variant matrix.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-807 — Motor and Inverter Variant Configuration

**Type:** constraint · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** review

**Statement:** The motor controller shall select its pole-pair count, resistance, inductance, nominal DC voltage, current limits and derating parameters from a validated motor/inverter variant configuration.

**Rationale:** The source uses vehicle/motor-dependent parameters but does not define variant selection.

**Acceptance criteria (draft):**

- **Given:** The implementation and configuration are under static review/analysis.
- **When:** The constraint is checked.
- **Then:** The motor controller shall select its pole-pair count, resistance, inductance, nominal DC voltage, current limits and derating parameters from a validated motor/inverter variant configuration. The constraint is satisfied with no exceptions.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=ARCH-REQ-000 · design=System · test=TD-ARCH-REQ-807

**Open issues:** Define the variant matrix and configuration source.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---

### ARCH-REQ-1003 — Motor Control System Requirements Baseline — Part 2

**Type:** functional · **ASIL:** ASIL-B · **Priority:** must · **Status:** review · **Verification:** test

**Statement:** The PMSM field-oriented-control architecture shall trace to the inverter/motor system requirements.

**Rationale:** The source CSV has no system/stakeholder hierarchy. This placeholder enables traceability without inventing a stakeholder requirement. Split from ARCH-REQ-000.

**Acceptance criteria (draft):**

- **Given:** The AEB feature is in ACTIVE mode and the referenced inputs are valid.
- **When:** The event/condition described by 'Motor Control System Requirements Baseline — Part 2' occurs.
- **Then:** The PMSM field-oriented-control architecture shall trace to the inverter/motor system requirements.
- **Tolerance:** ±1 LSB of the referenced interface; otherwise exact match.

**Trace:** parent=— · design=System · test=TD-ARCH-REQ-1003

**Split from:** `ARCH-REQ-000`

**Open issues:** Split from ARCH-REQ-000; confirm atomicity and completeness with the requirement owner.; Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.

---
