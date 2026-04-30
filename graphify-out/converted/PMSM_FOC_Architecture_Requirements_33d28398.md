<!-- converted from PMSM_FOC_Architecture_Requirements.xlsx -->

## Sheet: 00_Overview
| AUTOSAR PMSM FOC Motor Control — Software Architecture Requirements Document |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Document Purpose: Architectural & Unit-Level Requirements for MUD Skill Testing — SpdCtrl | CurrCtrl | MtrMon |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Document Information |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Document ID | ARCH-PMSM-FOC-001 |  |  |  |  |  |  |  |  |  |  |  |  |
| Version | 1.0 |  |  |  |  |  |  |  |  |  |  |  |  |
| AUTOSAR Release | Classic Platform 4.4 |  |  |  |  |  |  |  |  |  |  |  |  |
| Safety Level | ASIL-B |  |  |  |  |  |  |  |  |  |  |  |  |
| Target HW | AURIX TC377 (6-phase IPMSM) |  |  |  |  |  |  |  |  |  |  |  |  |
| Prepared By | Architecture Team |  |  |  |  |  |  |  |  |  |  |  |  |
| Date | 2026-04-21 |  |  |  |  |  |  |  |  |  |  |  |  |
| Status | Draft — For MUD Skill Testing |  |  |  |  |  |  |  |  |  |  |  |  |
| Component Summary |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ID | Component ShortName | Long Name | SwCType | Runnables | R-Ports | P-Ports | CalPrm Count | IRV | ExclusiveArea | ASIL | Cycle Times | Depends On | Notes |
| C01 | SpdCtrl | Speed controller | AtomicSwComponentType | SpdCtrl_Init
SpdCtrl_1ms
SpdCtrl_OnModSwitch | SpdFbk
SpdRef
IqMaxIn
OpMod | IqRef | 5 params | SpdCtrlIntgState | EA_SpdIntg | ASIL-B | Init / 1ms / Event | MtrMon (IqMax) | Outer PI loop; anti-windup; mode-aware reset |
| C02 | CurrCtrl | Current controller | AtomicSwComponentType | CurrCtrl_Init
CurrCtrl_100us | IdFbk
IqFbk
IdRef
IqRef
VdcBus | VdCmd
VqCmd | 9 params | IdIntgState
IqIntgState | EA_CurrIntg | ASIL-B | Init / 100µs | SpdCtrl (IqRef) | Inner PI loop; decoupling FF; voltage limiting |
| C03 | MtrMon | Motor monitor | AtomicSwComponentType | MtrMon_Init
MtrMon_1ms
MtrMon_10ms | IdMon
IqMon
MtrT
VdcMon
SpdMon | IqMaxOut
MtrProtSt
OcSt
OtSt | 6 params | OcState
OtState | EA_MtrState | ASIL-B | Init / 1ms / 10ms | — (provides to SpdCtrl) | Protection; OC/OT detection; Iq derating |
| Signal Flow Summary |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Signal flow: SpdRef ──▶ [SpdCtrl] ──▶ IqRef ──▶ [CurrCtrl] ──▶ VdCmd/VqCmd ──▶ PWM/Inverter
             SpdFbk (observer) ────────────▶ [SpdCtrl] (feedback)
             IdFbk/IqFbk (ADC) ─────────────────▶ [CurrCtrl] (feedback)
             IdMon/IqMon/MtrT/VdcMon ──▶ [MtrMon] ──▶ IqMaxIn ──▶ [SpdCtrl] (protection) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Color Legend |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | R-Port (Require Port) — component reads this data |  |  |  |  |  |  |  |  |  |  |  |  |
|  | P-Port (Provide Port) — component writes this data |  |  |  |  |  |  |  |  |  |  |  |  |
|  | CalPrm — calibration parameter (online-tunable via XCP/A2L) |  |  |  |  |  |  |  |  |  |  |  |  |
|  | Runnable Entity — executable code block triggered by RTE event |  |  |  |  |  |  |  |  |  |  |  |  |
|  | InterRunnableVariable (IRV) — internal data between runnables |  |  |  |  |  |  |  |  |  |  |  |  |
|  | ExclusiveArea — concurrency protection region |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: 01_SigFlow
| ARCHITECTURE SIGNAL FLOW — Component Interaction Map |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Signal / Port Pair | From Component | From Port | Interface | Direction | To Component | To Port | Rate | Data Type | Physical Range | Description |  |  |  |  |  |  |  |
| SpdRef → SpdCtrl | AppMgr | SpdCmdOut | SpdN1 | → | SpdCtrl | SpdRef | 10 ms | uint16 | 0–12000 rpm | Operator speed command |  |  |  |  |  |  |  |
| SpdFbk → SpdCtrl | SpeedObs | SpdOut | SpdN1 | → | SpdCtrl | SpdFbk | 1 ms | uint16 | 0–15000 rpm | Actual speed feedback |  |  |  |  |  |  |  |
| SpdFbk → MtrMon | SpeedObs | SpdOut | SpdN1 | → | MtrMon | SpdMon | 1 ms | uint16 | 0–15000 rpm | Speed for overspeed check |  |  |  |  |  |  |  |
| IqMaxOut → SpdCtrl | MtrMon | IqMaxOut | MtrIqMax1 | → | SpdCtrl | IqMaxIn | 10 ms | float32 | 0–160 A | Protection-derived Iq limit |  |  |  |  |  |  |  |
| IqRef → CurrCtrl | SpdCtrl | IqRef | MtrIq1 | → | CurrCtrl | IqRef | 1 ms | float32 | −160–+160 A | Speed PI output → current ref |  |  |  |  |  |  |  |
| IdRef → CurrCtrl | MTPA/Const | IdRefOut | MtrId1 | → | CurrCtrl | IdRef | 1 ms | sint16 | −50–+50 A | d-axis ref (0 for SPMSM) |  |  |  |  |  |  |  |
| IdFbk → CurrCtrl | CurrentSens | IdOut | MtrId1 | → | CurrCtrl | IdFbk | 100 µs | sint16 | −160–+160 A | d-axis current feedback |  |  |  |  |  |  |  |
| IqFbk → CurrCtrl | CurrentSens | IqOut | MtrIq1 | → | CurrCtrl | IqFbk | 100 µs | sint16 | −160–+160 A | q-axis current feedback |  |  |  |  |  |  |  |
| VdcBus → CurrCtrl | VdcMeas | VdcOut | VdcBus1 | → | CurrCtrl | VdcBus | 1 ms | uint16 | 0–800 V | DC bus for voltage limiting |  |  |  |  |  |  |  |
| VdCmd → PWM | CurrCtrl | VdCmd | MtrVd1 | → | SVM/PWM | VdIn | 100 µs | sint16 | −400–+400 V | d-axis voltage to modulator |  |  |  |  |  |  |  |
| VqCmd → PWM | CurrCtrl | VqCmd | MtrVq1 | → | SVM/PWM | VqIn | 100 µs | sint16 | −400–+400 V | q-axis voltage to modulator |  |  |  |  |  |  |  |
| IdMon → MtrMon | CurrentSens | IdOut | MtrId1 | → | MtrMon | IdMon | 100 µs | sint16 | −160–+160 A | d-axis current monitoring |  |  |  |  |  |  |  |
| IqMon → MtrMon | CurrentSens | IqOut | MtrIq1 | → | MtrMon | IqMon | 100 µs | sint16 | −160–+160 A | q-axis current monitoring |  |  |  |  |  |  |  |
| MtrT → MtrMon | TempSens | MtrTOut | MtrT1 | → | MtrMon | MtrT | 10 ms | sint16 | −40–+200 °C | Motor temperature |  |  |  |  |  |  |  |
| VdcMon → MtrMon | VdcMeas | VdcOut | VdcBus1 | → | MtrMon | VdcMon | 1 ms | uint16 | 0–800 V | Vdc monitoring |  |  |  |  |  |  |  |
| MtrProtSt → SysMgr | MtrMon | MtrProtSt | MtrProtSt1 | → | SysMgr | MtrProtIn | 1 ms | uint8 | 0–7 | Aggregated protection status |  |  |  |  |  |  |  |
| OcSt → SafetyMon | MtrMon | OcSt | MtrOcSt1 | → | SafetyMon | OcIn | 1 ms | boolean | F/T | Overcurrent active flag |  |  |  |  |  |  |  |
| OtSt → SafetyMon | MtrMon | OtSt | MtrOtSt1 | → | SafetyMon | OtIn | 10 ms | boolean | F/T | Overtemperature active flag |  |  |  |  |  |  |  |
| OpMod → SpdCtrl | SysMgr | ModOut | OpMod1 | → | SpdCtrl | OpMod | Event | uint8 | 0–4 (enum) | Mode switch — resets PI integrator |  |  |  |  |  |  |  |
## Sheet: 02_SpdCtrl
| C01 — SpdCtrl  (Speed controller) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SwCType: AtomicSwComponentType  |  Safety: ASIL-B  |  Cycles: Init (once) | 1 ms (TimingEvent) | ModeSwitchEvent  |  Purpose: Outer PI speed control loop — computes Iq reference from speed error |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ■  PORTS AND INTERFACES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Port ShortName | Direction | Interface ShortName | Interface Type | Data Element | Impl. Type | Phys. Unit | Resolution | Min Value | Max Value | CompuMethod | Comm. Mode | Connected To | Description | ASIL |
| SPD-PORT-001 | SpdFbk | R-Port | SpdN1 | SenderReceiverInterface | Val | uint16 | rpm | 1 rpm/LSB | 0 | 15000 | SpdNIdentcl | Explicit | SpeedObserver SWC (P-Port SpdOut) | Actual motor mechanical speed from speed observer | ASIL-B |
| SPD-PORT-002 | SpdRef | R-Port | SpdN1 | SenderReceiverInterface | Val | uint16 | rpm | 1 rpm/LSB | 0 | 12000 | SpdNIdentcl | Explicit | AppMgr SWC (P-Port SpdCmdOut) | Speed reference command from application manager | ASIL-B |
| SPD-PORT-003 | IqMaxIn | R-Port | MtrIqMax1 | SenderReceiverInterface | Val | float32 | A | 0.001 A | 0.0 | 160.0 | ALnrl | Explicit | MtrMon (P-Port IqMaxOut) | Maximum Iq allowed — set by MtrMon based on protection state | ASIL-B |
| SPD-PORT-004 | OpMod | R-Port | OpMod1 | ModeSwitchInterface | OpModVal | uint8 | — | — | 0 | 4 | OpMod1 (TEXTTABLE: 0=Init 1=Idle 2=Run 3=Fault 4=CalMode) | Mode | SysMgr SWC (Mode Manager) | System operation mode — triggers integrator reset on mode change | ASIL-B |
| SPD-PORT-005 | IqRef | P-Port | MtrIq1 | SenderReceiverInterface | Val | float32 | A | 0.001 A | -160.0 | 160.0 | ALnrl | Explicit | CurrCtrl (R-Port IqRef) | q-axis current reference to current controller — output of speed PI | ASIL-B |
| ■  RUNNABLE ENTITIES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Runnable ShortName | RTE Event | Cycle / Condition | Ports Read | Ports Written | CalPrm Used | IRV Read | IRV Written | ExclusiveArea | Init Required | Return Type | Description | ASIL | Timing Budget | Notes |
| SPD-RUN-001 | SpdCtrl_Init | InitEvent | Once at ECU startup | SpdRef, SpdFbk | IqRef | SpdCtrlPrm (all) | — | SpdCtrlIntgState | — | Yes | void | Initialize speed PI integrator to zero, ramp state, set IqRef=0.0, read init CalPrm | ASIL-B | <100 µs | Must complete before first TimingEvent fires |
| SPD-RUN-002 | SpdCtrl_1ms | TimingEvent | 1 ms (1000 Hz) | SpdFbk, SpdRef, IqMaxIn | IqRef | Kp, Ki, AntiWindupLim, SpdErrDz, SpdRampRate | — | — | EA_SpdIntg | No | void | 1. Ramp SpdRef by SpdRampRate (rate limiter)
2. Compute spdErr = spdRefRamped - SpdFbk
3. Apply deadzone SpdErrDz
4. PI: pTerm=Kp*spdErr; iState+=Ki*spdErr*0.001s
5. Anti-windup: clamp iState to ±AntiWindupLim
6. IqRef = clamp(pTerm+iState, ±IqMaxIn) | ASIL-B | <50 µs | ExclusiveArea protects iState if future OS task split needed |
| SPD-RUN-003 | SpdCtrl_OnModSwitch | ModeSwitchEvent on OpMod | On mode transition | OpMod | IqRef | — | — | SpdCtrlIntgState | EA_SpdIntg | No | void | Reset PI integrator to 0 on transition to Init/Idle/Fault mode.
Set IqRef = 0.0. Prevents integrator windup on re-enable. | ASIL-B | <20 µs | Triggered by mode manager |
| ■  CALIBRATION PARAMETERS (CalPrm — ParameterInterface) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | CalPrm ShortName | Long Name | Impl. Type | Unit | Default Value | Min Value | Max Value | Resolution | A2L Access | Online Calibratable | CompuMethod | Used In Runnable | Physical Description | Impact if Wrong | Notes |
| SPD-CAL-001 | Kp | Speed controller proportional gain | float32 | A/rpm | 0.5 | 0.001 | 10.0 | 0.001 | Yes | Yes | ALnrl | SpdCtrl_1ms | P-gain of speed PI loop | Low: sluggish response. High: oscillation / instability | Tune with step response |
| SPD-CAL-002 | Ki | Speed controller integral gain | float32 | A/(rpm·s) | 0.1 | 0.001 | 5.0 | 0.001 | Yes | Yes | ALnrl | SpdCtrl_1ms | I-gain of speed PI loop; applied per 1ms sample | Low: steady-state error. High: integrator windup / oscillation |  |
| SPD-CAL-003 | AntiWindupLim | Integrator anti-windup saturation limit | float32 | A | 80.0 | 1.0 | 160.0 | 0.1 | Yes | Yes | ALnrl | SpdCtrl_1ms | Maximum absolute value of integrator state | Too low: limits performance. Too high: windup risk during saturation | Must be ≤ IqMax hardware limit |
| SPD-CAL-004 | SpdErrDz | Speed error deadzone | uint16 | rpm | 5 | 0 | 50 | 1 | Yes | Yes | SpdNIdentcl | SpdCtrl_1ms | Speed error below this is treated as zero (reduces jitter at steady-state) | Too high: large steady-state speed error | Set to 0 for precision apps |
| SPD-CAL-005 | SpdRampRate | Speed reference ramp rate | float32 | rpm/s | 1000.0 | 10.0 | 10000.0 | 1.0 | Yes | Yes | ALnrl | SpdCtrl_1ms | Maximum rate of change of speed reference (rate limiter) | Too low: slow accel. Too high: mechanical stress / current spikes | Applies to both accel and decel |
| ■  INTER-RUNNABLE VARIABLES (IRV) AND EXCLUSIVE AREAS |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Name | Type | Kind | Written By | Read By | Protected By EA | Data Description | Init Value | Size (bytes) | Persistence | ASIL | Notes |  |  |  |
| SPD-IRV-001 | SpdCtrlIntgState | float32 | IRV | SpdCtrl_1ms, SpdCtrl_OnModSwitch, SpdCtrl_Init | SpdCtrl_1ms | EA_SpdIntg | PI integrator state (accumulated integral term in A) | 0.0f | 4 | None (re-init on startup) | ASIL-B | ExclusiveArea required if runnables placed in different OS tasks |  |  |  |
| SPD-IRV-002 | SpdRefRamped | float32 | IRV | SpdCtrl_1ms | SpdCtrl_1ms | — | Rate-limited speed reference after ramp processing (rpm) | 0.0f | 4 | None | ASIL-B | Internal to _1ms only |  |  |  |
| SPD-EA-001 | EA_SpdIntg | — | ExclusiveArea | — | — | — | Protects SpdCtrlIntgState and SpdRefRamped against concurrent access | — | — | — | ASIL-B | Enter/Exit around IRV read-modify-write only |  |  |  |
## Sheet: 03_CurrCtrl
| C02 — CurrCtrl  (Current controller) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SwCType: AtomicSwComponentType  |  Safety: ASIL-B  |  Cycles: Init (once) | 100 µs (TimingEvent = 10 kHz inner loop)  |  Purpose: Inner PI current control loop — regulates Id and Iq via decoupled PI + voltage limiting |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ■  PORTS AND INTERFACES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Port ShortName | Direction | Interface ShortName | Interface Type | Data Element | Impl. Type | Phys. Unit | Resolution | Min Value | Max Value | CompuMethod | Comm. Mode | Connected To | Description | ASIL |
| CUR-PORT-001 | IdFbk | R-Port | MtrId1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -16000 | 16000 | MtrIdLnrl (×0.01 A/LSB) | Explicit | CurrentSens SWC (P-Port IdOut) | d-axis stator current feedback from ADC/Clarke-Park transform | ASIL-B |
| CUR-PORT-002 | IqFbk | R-Port | MtrIq1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -16000 | 16000 | MtrIqLnrl (×0.01 A/LSB) | Explicit | CurrentSens SWC (P-Port IqOut) | q-axis stator current feedback from ADC/Clarke-Park transform | ASIL-B |
| CUR-PORT-003 | IdRef | R-Port | MtrId1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -5000 | 5000 | MtrIdLnrl | Explicit | MTPA SWC or tied to 0 for SPMSM | d-axis current reference; 0 for SPMSM; MTPA-computed for IPMSM | ASIL-B |
| CUR-PORT-004 | IqRef | R-Port | MtrIq1 | SenderReceiverInterface | Val | float32 | A | 0.001 A | -160.0 | 160.0 | ALnrl | Explicit | SpdCtrl (P-Port IqRef) | q-axis current reference from speed controller | ASIL-B |
| CUR-PORT-005 | VdcBus | R-Port | VdcBus1 | SenderReceiverInterface | Val | uint16 | V×10 | 0.1 V/LSB | 0 | 8000 | VdcLnrl (×0.1 V/LSB) | Explicit | VdcMeas SWC (P-Port VdcOut) | DC bus voltage measurement for voltage normalisation in PI output | ASIL-B |
| CUR-PORT-006 | VdCmd | P-Port | MtrVd1 | SenderReceiverInterface | Val | sint16 | V×100 | 0.01 V/LSB | -40000 | 40000 | VdLnrl (×0.01 V/LSB) | Explicit | SVM/PWM SWC (R-Port VdIn) | d-axis voltage command to PWM/SVM block after PI + decoupling | ASIL-B |
| CUR-PORT-007 | VqCmd | P-Port | MtrVq1 | SenderReceiverInterface | Val | sint16 | V×100 | 0.01 V/LSB | -40000 | 40000 | VqLnrl (×0.01 V/LSB) | Explicit | SVM/PWM SWC (R-Port VqIn) | q-axis voltage command to PWM/SVM block after PI + decoupling | ASIL-B |
| ■  RUNNABLE ENTITIES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Runnable ShortName | RTE Event | Cycle / Condition | Ports Read | Ports Written | CalPrm Used | IRV Read | IRV Written | ExclusiveArea | Init Required | Return Type | Description | ASIL | Timing Budget | Notes |
| CUR-RUN-001 | CurrCtrl_Init | InitEvent | Once at ECU startup | IdRef, IqRef, IdFbk, IqFbk, VdcBus | VdCmd, VqCmd | CurrCtrlPrm (all) | — | IdIntgState, IqIntgState | — | Yes | void | Set IdIntgState=0, IqIntgState=0, VdCmd=0, VqCmd=0. Cache CalPrm to locals. | ASIL-B | <50 µs |  |
| CUR-RUN-002 | CurrCtrl_100us | TimingEvent | 100 µs (10 kHz) | IdFbk, IqFbk, IdRef, IqRef, VdcBus | VdCmd, VqCmd | KpId, KiId, KpIq, KiIq, VdcNom, VoltLim, Ld, Lq, Rs | — | IdIntgState, IqIntgState | EA_CurrIntg | No | void | 1. Read IdFbk, IqFbk (sint16 → float32 via ×0.01)
2. Read IqRef (float32), IdRef (sint16→float32)
3. Compute errors: idErr=IdRef-IdFbk; iqErr=IqRef-IqFbk
4. d-axis PI: Vd = KpId*idErr + IdIntg; IdIntg+=KiId*idErr*100e-6
5. q-axis PI: Vq = KpIq*iqErr + IqIntg; IqIntg+=KiIq*iqErr*100e-6
6. Decoupling FF: Vd -= omega*Lq*IqFbk; Vq += omega*Ld*IdFbk
7. Voltage circle limiting: if |Vdq|>VoltLim*Vdc/sqrt(3) → scale down
8. Convert float Vd/Vq → sint16 (×100) and write ports | ASIL-B | <30 µs | 10 kHz — tightest timing constraint in system. No dynamic memory. |
| ■  CALIBRATION PARAMETERS (CalPrm — ParameterInterface) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | CalPrm ShortName | Long Name | Impl. Type | Unit | Default Value | Min Value | Max Value | Resolution | A2L Access | Online Calibratable | CompuMethod | Used In Runnable | Physical Description | Impact if Wrong | Notes |
| CUR-CAL-001 | KpId | d-axis current PI proportional gain | float32 | V/A | 5.0 | 0.1 | 200.0 | 0.01 | Yes | Yes | VPerALnrl | CurrCtrl_100us | P-gain for d-axis PI controller | Low: slow Id tracking. High: oscillation — motor may destabilize |  |
| CUR-CAL-002 | KiId | d-axis current PI integral gain | float32 | V/(A·s) | 50.0 | 1.0 | 5000.0 | 0.1 | Yes | Yes | VPerALnrl | CurrCtrl_100us | I-gain for d-axis PI; per 100µs sample | Too high: integrator diverges. Too low: steady-state Id error |  |
| CUR-CAL-003 | KpIq | q-axis current PI proportional gain | float32 | V/A | 5.0 | 0.1 | 200.0 | 0.01 | Yes | Yes | VPerALnrl | CurrCtrl_100us | P-gain for q-axis PI controller | Low: slow torque response. High: oscillation | Usually same as KpId for SPMSM |
| CUR-CAL-004 | KiIq | q-axis current PI integral gain | float32 | V/(A·s) | 50.0 | 1.0 | 5000.0 | 0.1 | Yes | Yes | VPerALnrl | CurrCtrl_100us | I-gain for q-axis PI; per 100µs sample | Too high: torque ripple / oscillation |  |
| CUR-CAL-005 | VdcNom | Nominal DC bus voltage | float32 | V | 400.0 | 100.0 | 800.0 | 0.1 | Yes | No | VLnrl | CurrCtrl_100us | Nominal Vdc used for normalisation; not measured value | Wrong value → incorrect per-unit scaling of voltage commands | Set once at calibration |
| CUR-CAL-006 | VoltLim | Voltage limit factor | float32 | — | 0.90 | 0.50 | 0.98 | 0.01 | Yes | Yes | VoltLimIdentcl | CurrCtrl_100us | Fraction of Vdc/√3 used as voltage limit circle radius | Too high: overmodulation. Too low: reduced torque capability |  |
| CUR-CAL-007 | Ld | d-axis stator inductance | float32 | H | 0.00100 | 0.00001 | 0.05000 | 0.00001 | Yes | No | LdIdentcl | CurrCtrl_100us | d-axis inductance for cross-coupling decoupling feedforward | Wrong: residual cross-coupling oscillation | Identify via standstill test |
| CUR-CAL-008 | Lq | q-axis stator inductance | float32 | H | 0.00120 | 0.00001 | 0.05000 | 0.00001 | Yes | No | LqIdentcl | CurrCtrl_100us | q-axis inductance for cross-coupling decoupling feedforward | Wrong: cross-coupling oscillation at high speed | Lq > Ld for IPMSM |
| CUR-CAL-009 | Rs | Stator phase resistance | float32 | Ω | 0.100 | 0.001 | 5.000 | 0.001 | Yes | No | RsIdentcl | CurrCtrl_100us | Stator resistance for back-EMF compensation at low speed | Wrong: steady-state voltage offset at low speed | Temp-dependent; may need derating table |
| ■  INTER-RUNNABLE VARIABLES (IRV) AND EXCLUSIVE AREAS |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Name | Type | Kind | Written By | Read By | Protected By EA | Data Description | Init Value | Size (bytes) | Persistence | ASIL | Notes |  |  |  |
| CUR-IRV-001 | IdIntgState | float32 | IRV | CurrCtrl_100us, CurrCtrl_Init | CurrCtrl_100us | EA_CurrIntg | d-axis PI integrator accumulator (V) | 0.0f | 4 | None | ASIL-B |  |  |  |  |
| CUR-IRV-002 | IqIntgState | float32 | IRV | CurrCtrl_100us, CurrCtrl_Init | CurrCtrl_100us | EA_CurrIntg | q-axis PI integrator accumulator (V) | 0.0f | 4 | None | ASIL-B |  |  |  |  |
| CUR-EA-001 | EA_CurrIntg | — | ExclusiveArea | — | — | — | Protects IdIntgState and IqIntgState against concurrent access | — | — | — | ASIL-B | Not strictly needed if 100µs is only runnable — but kept for future-proofing |  |  |  |
## Sheet: 04_MtrMon
| C03 — MtrMon  (Motor monitor) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SwCType: AtomicSwComponentType  |  Safety: ASIL-B  |  Cycles: Init (once) | 1 ms (TimingEvent) | 10 ms (TimingEvent)  |  Purpose: Motor protection — overcurrent, overvoltage, overtemperature detection; Iq derating |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ■  PORTS AND INTERFACES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Port ShortName | Direction | Interface ShortName | Interface Type | Data Element | Impl. Type | Phys. Unit | Resolution | Min Value | Max Value | CompuMethod | Comm. Mode | Connected To | Description | ASIL |
| MON-PORT-001 | IdMon | R-Port | MtrId1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -16000 | 16000 | MtrIdLnrl | Explicit | CurrentSens SWC (P-Port IdOut) | d-axis current for overcurrent monitoring (same interface as CurrCtrl) | ASIL-B |
| MON-PORT-002 | IqMon | R-Port | MtrIq1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -16000 | 16000 | MtrIqLnrl | Explicit | CurrentSens SWC (P-Port IqOut) | q-axis current for overcurrent monitoring | ASIL-B |
| MON-PORT-003 | MtrT | R-Port | MtrT1 | SenderReceiverInterface | Val | sint16 | °C | 1°C/LSB | -40 | 200 | MtrTIdentcl | Explicit | TempSens SWC (P-Port MtrTOut) | Motor winding temperature from NTC sensor | ASIL-B |
| MON-PORT-004 | VdcMon | R-Port | VdcBus1 | SenderReceiverInterface | Val | uint16 | V×10 | 0.1 V/LSB | 0 | 8000 | VdcLnrl | Explicit | VdcMeas SWC (P-Port VdcOut) | DC bus voltage for over/undervoltage monitoring | ASIL-B |
| MON-PORT-005 | SpdMon | R-Port | SpdN1 | SenderReceiverInterface | Val | uint16 | rpm | 1 rpm/LSB | 0 | 15000 | SpdNIdentcl | Explicit | SpeedObserver SWC (P-Port SpdOut) | Actual speed for overspeed protection | ASIL-B |
| MON-PORT-006 | IqMaxOut | P-Port | MtrIqMax1 | SenderReceiverInterface | Val | float32 | A | 0.001 A | 0.0 | 160.0 | ALnrl | Explicit | SpdCtrl (R-Port IqMaxIn) | Maximum allowed Iq — derated by temperature, set to 0 on OC/OT fault | ASIL-B |
| MON-PORT-007 | MtrProtSt | P-Port | MtrProtSt1 | SenderReceiverInterface | St | uint8 | — | — | 0 | 7 | MtrProtSt1 (TEXTTABLE: 0=OK 1=OC_Warn 2=OT_Warn 3=OC_Fault 4=OT_Fault 5=OV_Fault 6=UV_Fault 7=OS_Fault) | Explicit | SysMgr SWC (R-Port MtrProtIn) | Aggregated motor protection status — highest active fault code | ASIL-B |
| MON-PORT-008 | OcSt | P-Port | MtrOcSt1 | SenderReceiverInterface | St | boolean | — | — | FALSE | TRUE | MtrOcSt1 (TEXTTABLE) | Explicit | SafetyMon SWC (R-Port OcIn), FaultMgr | TRUE = overcurrent condition active (|Idq|² > IOcThd²) | ASIL-B |
| MON-PORT-009 | OtSt | P-Port | MtrOtSt1 | SenderReceiverInterface | St | boolean | — | — | FALSE | TRUE | MtrOtSt1 (TEXTTABLE) | Explicit | SafetyMon SWC (R-Port OtIn), FaultMgr | TRUE = overtemperature condition active (with hysteresis) | ASIL-B |
| ■  RUNNABLE ENTITIES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Runnable ShortName | RTE Event | Cycle / Condition | Ports Read | Ports Written | CalPrm Used | IRV Read | IRV Written | ExclusiveArea | Init Required | Return Type | Description | ASIL | Timing Budget | Notes |
| MON-RUN-001 | MtrMon_Init | InitEvent | Once | IdMon, IqMon, MtrT, VdcMon | IqMaxOut, MtrProtSt, OcSt, OtSt | All MtrMon CalPrm | — | OcState, OtState | — | Yes | void | Set OcSt=FALSE, OtSt=FALSE, MtrProtSt=OK, IqMaxOut=IqMaxNom, init state IRVs | ASIL-B | <50 µs |  |
| MON-RUN-002 | MtrMon_1ms | TimingEvent | 1 ms | IdMon, IqMon, VdcMon, SpdMon | OcSt, MtrProtSt, IqMaxOut | IOcThd, VdcOvThd, VdcUvThd, OsSpdThd | OcState | OcState | EA_MtrState | No | void | 1. Read IdMon, IqMon → convert to float (×0.01)
2. Compute |Idq|=sqrt(Id²+Iq²); compare to IOcThd
3. OC detection with debounce counter (3 consecutive cycles)
4. If OC: OcSt=TRUE, IqMaxOut=0, MtrProtSt=OC_Fault
5. DC bus OV/UV check: VdcMon vs VdcOvThd and VdcUvThd
6. Overspeed check: SpdMon vs OsSpdThd
7. Update MtrProtSt with highest priority active fault | ASIL-B | <60 µs | sqrt() may need CORDIC approximation for ASIL-B |
| MON-RUN-003 | MtrMon_10ms | TimingEvent | 10 ms | MtrT | OtSt, IqMaxOut, MtrProtSt | TOtThd, TOtHyst, IqDerateSlope, IqMaxNom | OtState, OcState | OtState | EA_MtrState | No | void | 1. Read MtrT (sint16, °C)
2. OT detection with hysteresis:
   - Enter OT: T > TOtThd → OtSt=TRUE
   - Exit OT:  T < (TOtThd - TOtHyst) → OtSt=FALSE
3. Thermal derating: if T near threshold:
   IqAvail = IqMaxNom - IqDerateSlope*(T - (TOtThd - 20))
   Clamp IqAvail to [0, IqMaxNom]
4. If OcState=Fault → IqMaxOut=0 (OC overrides derating)
   Else: IqMaxOut = IqAvail
5. Update MtrProtSt (OT_Fault or OT_Warn) | ASIL-B | <40 µs | 10ms sufficient for thermal dynamics |
| ■  CALIBRATION PARAMETERS (CalPrm — ParameterInterface) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | CalPrm ShortName | Long Name | Impl. Type | Unit | Default Value | Min Value | Max Value | Resolution | A2L Access | Online Calibratable | CompuMethod | Used In Runnable | Physical Description | Impact if Wrong | Notes |
| MON-CAL-001 | IOcThd | Overcurrent peak threshold | float32 | A | 150.0 | 50.0 | 400.0 | 0.1 | Yes | No | ALnrl | MtrMon_1ms | Peak |Idq| threshold triggering overcurrent fault | Too low: nuisance trips. Too high: motor / inverter damage | Must be < hardware OC threshold |
| MON-CAL-002 | TOtThd | Overtemperature trip threshold | sint16 | °C | 120 | 80 | 150 | 1 | Yes | No | TIdentcl | MtrMon_10ms | Motor winding temperature triggering OT fault | Too high: insulation damage / winding failure | Check motor datasheet |
| MON-CAL-003 | TOtHyst | Overtemperature hysteresis | sint16 | °C | 10 | 2 | 30 | 1 | Yes | No | TIdentcl | MtrMon_10ms | Temperature must drop by this much below TOtThd to clear OT flag | Too small: chattering. Too large: delayed recovery |  |
| MON-CAL-004 | VdcOvThd | DC bus overvoltage threshold | uint16 | V×10 | 7500 | 4000 | 9000 | 1 | Yes | No | VdcLnrl | MtrMon_1ms | DC bus OV fault threshold (×0.1 → 750 V) | Too low: nuisance trips during regen. Too high: capacitor damage |  |
| MON-CAL-005 | VdcUvThd | DC bus undervoltage threshold | uint16 | V×10 | 3000 | 1000 | 4000 | 1 | Yes | No | VdcLnrl | MtrMon_1ms | DC bus UV fault threshold (×0.1 → 300 V) | Too high: spurious faults. Too low: controller brownout |  |
| MON-CAL-006 | IqDerateSlope | Iq thermal derating slope | float32 | A/°C | 2.0 | 0.1 | 20.0 | 0.01 | Yes | Yes | ALnrl | MtrMon_10ms | Rate at which IqMax is reduced per °C above derating start (TOtThd-20°C) | Too steep: aggressive derating. Too shallow: insufficient protection |  |
| ■  INTER-RUNNABLE VARIABLES (IRV) AND EXCLUSIVE AREAS |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| REQ-ID | Name | Type | Kind | Written By | Read By | Protected By EA | Data Description | Init Value | Size (bytes) | Persistence | ASIL | Notes |  |  |  |
| MON-IRV-001 | OcState | uint8 | IRV | MtrMon_1ms, MtrMon_Init | MtrMon_10ms, MtrMon_1ms | EA_MtrState | OC state machine (0=OK 1=Warning 2=Fault 3=Debounce) | 0U | 1 | None | ASIL-B |  |  |  |  |
| MON-IRV-002 | OtState | uint8 | IRV | MtrMon_10ms, MtrMon_Init | MtrMon_10ms, MtrMon_1ms | EA_MtrState | OT state machine (0=OK 1=Warning 2=Fault) | 0U | 1 | None | ASIL-B |  |  |  |  |
| MON-EA-001 | EA_MtrState | — | ExclusiveArea | — | — | — | Protects OcState and OtState between 1ms and 10ms runnables (different tasks) | — | — | — | ASIL-B | Critical: 1ms and 10ms are in different OS tasks on TC377 |  |  |  |
## Sheet: 05_AllPorts
| ALL PORTS — Consolidated Cross-Component Port View |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-ID | Component | Port ShortName | Direction | Interface ShortName | Interface Type | Data Element | Impl.Type | Unit | Resolution | Min | Max | CompuMethod | Comm.Mode | Connected From | Connected To | Description | ASIL |
| SPD-PORT-001 | SpdCtrl | SpdFbk | R-Port | SpdN1 | SenderReceiverInterface | Val | uint16 | rpm | 1 rpm/LSB | 0 | 15000 | SpdNIdentcl | Explicit | SpeedObserver SWC (P-Port SpdOut) | SpdCtrl | Actual motor mechanical speed from speed observer | ASIL-B |
| SPD-PORT-002 | SpdCtrl | SpdRef | R-Port | SpdN1 | SenderReceiverInterface | Val | uint16 | rpm | 1 rpm/LSB | 0 | 12000 | SpdNIdentcl | Explicit | AppMgr SWC (P-Port SpdCmdOut) | SpdCtrl | Speed reference command from application manager | ASIL-B |
| SPD-PORT-003 | SpdCtrl | IqMaxIn | R-Port | MtrIqMax1 | SenderReceiverInterface | Val | float32 | A | 0.001 A | 0.0 | 160.0 | ALnrl | Explicit | MtrMon (P-Port IqMaxOut) | SpdCtrl | Maximum Iq allowed — set by MtrMon based on protection state | ASIL-B |
| SPD-PORT-004 | SpdCtrl | OpMod | R-Port | OpMod1 | ModeSwitchInterface | OpModVal | uint8 | — | — | 0 | 4 | OpMod1 (TEXTTABLE: 0=Init 1=Idle 2=Run 3=Fault 4=CalMode) | Mode | SysMgr SWC (Mode Manager) | SpdCtrl | System operation mode — triggers integrator reset on mode change | ASIL-B |
| SPD-PORT-005 | SpdCtrl | IqRef | P-Port | MtrIq1 | SenderReceiverInterface | Val | float32 | A | 0.001 A | -160.0 | 160.0 | ALnrl | Explicit | SpdCtrl | CurrCtrl (R-Port IqRef) | q-axis current reference to current controller — output of speed PI | ASIL-B |
| CUR-PORT-001 | CurrCtrl | IdFbk | R-Port | MtrId1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -16000 | 16000 | MtrIdLnrl (×0.01 A/LSB) | Explicit | CurrentSens SWC (P-Port IdOut) | CurrCtrl | d-axis stator current feedback from ADC/Clarke-Park transform | ASIL-B |
| CUR-PORT-002 | CurrCtrl | IqFbk | R-Port | MtrIq1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -16000 | 16000 | MtrIqLnrl (×0.01 A/LSB) | Explicit | CurrentSens SWC (P-Port IqOut) | CurrCtrl | q-axis stator current feedback from ADC/Clarke-Park transform | ASIL-B |
| CUR-PORT-003 | CurrCtrl | IdRef | R-Port | MtrId1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -5000 | 5000 | MtrIdLnrl | Explicit | MTPA SWC or tied to 0 for SPMSM | CurrCtrl | d-axis current reference; 0 for SPMSM; MTPA-computed for IPMSM | ASIL-B |
| CUR-PORT-004 | CurrCtrl | IqRef | R-Port | MtrIq1 | SenderReceiverInterface | Val | float32 | A | 0.001 A | -160.0 | 160.0 | ALnrl | Explicit | SpdCtrl (P-Port IqRef) | CurrCtrl | q-axis current reference from speed controller | ASIL-B |
| CUR-PORT-005 | CurrCtrl | VdcBus | R-Port | VdcBus1 | SenderReceiverInterface | Val | uint16 | V×10 | 0.1 V/LSB | 0 | 8000 | VdcLnrl (×0.1 V/LSB) | Explicit | VdcMeas SWC (P-Port VdcOut) | CurrCtrl | DC bus voltage measurement for voltage normalisation in PI output | ASIL-B |
| CUR-PORT-006 | CurrCtrl | VdCmd | P-Port | MtrVd1 | SenderReceiverInterface | Val | sint16 | V×100 | 0.01 V/LSB | -40000 | 40000 | VdLnrl (×0.01 V/LSB) | Explicit | CurrCtrl | SVM/PWM SWC (R-Port VdIn) | d-axis voltage command to PWM/SVM block after PI + decoupling | ASIL-B |
| CUR-PORT-007 | CurrCtrl | VqCmd | P-Port | MtrVq1 | SenderReceiverInterface | Val | sint16 | V×100 | 0.01 V/LSB | -40000 | 40000 | VqLnrl (×0.01 V/LSB) | Explicit | CurrCtrl | SVM/PWM SWC (R-Port VqIn) | q-axis voltage command to PWM/SVM block after PI + decoupling | ASIL-B |
| MON-PORT-001 | MtrMon | IdMon | R-Port | MtrId1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -16000 | 16000 | MtrIdLnrl | Explicit | CurrentSens SWC (P-Port IdOut) | MtrMon | d-axis current for overcurrent monitoring (same interface as CurrCtrl) | ASIL-B |
| MON-PORT-002 | MtrMon | IqMon | R-Port | MtrIq1 | SenderReceiverInterface | Val | sint16 | A×100 | 0.01 A/LSB | -16000 | 16000 | MtrIqLnrl | Explicit | CurrentSens SWC (P-Port IqOut) | MtrMon | q-axis current for overcurrent monitoring | ASIL-B |
| MON-PORT-003 | MtrMon | MtrT | R-Port | MtrT1 | SenderReceiverInterface | Val | sint16 | °C | 1°C/LSB | -40 | 200 | MtrTIdentcl | Explicit | TempSens SWC (P-Port MtrTOut) | MtrMon | Motor winding temperature from NTC sensor | ASIL-B |
| MON-PORT-004 | MtrMon | VdcMon | R-Port | VdcBus1 | SenderReceiverInterface | Val | uint16 | V×10 | 0.1 V/LSB | 0 | 8000 | VdcLnrl | Explicit | VdcMeas SWC (P-Port VdcOut) | MtrMon | DC bus voltage for over/undervoltage monitoring | ASIL-B |
| MON-PORT-005 | MtrMon | SpdMon | R-Port | SpdN1 | SenderReceiverInterface | Val | uint16 | rpm | 1 rpm/LSB | 0 | 15000 | SpdNIdentcl | Explicit | SpeedObserver SWC (P-Port SpdOut) | MtrMon | Actual speed for overspeed protection | ASIL-B |
| MON-PORT-006 | MtrMon | IqMaxOut | P-Port | MtrIqMax1 | SenderReceiverInterface | Val | float32 | A | 0.001 A | 0.0 | 160.0 | ALnrl | Explicit | MtrMon | SpdCtrl (R-Port IqMaxIn) | Maximum allowed Iq — derated by temperature, set to 0 on OC/OT fault | ASIL-B |
| MON-PORT-007 | MtrMon | MtrProtSt | P-Port | MtrProtSt1 | SenderReceiverInterface | St | uint8 | — | — | 0 | 7 | MtrProtSt1 (TEXTTABLE: 0=OK 1=OC_Warn 2=OT_Warn 3=OC_Fault 4=OT_Fault 5=OV_Fault 6=UV_Fault 7=OS_Fault) | Explicit | MtrMon | SysMgr SWC (R-Port MtrProtIn) | Aggregated motor protection status — highest active fault code | ASIL-B |
| MON-PORT-008 | MtrMon | OcSt | P-Port | MtrOcSt1 | SenderReceiverInterface | St | boolean | — | — | FALSE | TRUE | MtrOcSt1 (TEXTTABLE) | Explicit | MtrMon | SafetyMon SWC (R-Port OcIn), FaultMgr | TRUE = overcurrent condition active (|Idq|² > IOcThd²) | ASIL-B |
| MON-PORT-009 | MtrMon | OtSt | P-Port | MtrOtSt1 | SenderReceiverInterface | St | boolean | — | — | FALSE | TRUE | MtrOtSt1 (TEXTTABLE) | Explicit | MtrMon | SafetyMon SWC (R-Port OtIn), FaultMgr | TRUE = overtemperature condition active (with hysteresis) | ASIL-B |
## Sheet: 06_AllRunnables
| ALL RUNNABLES — Consolidated Runnable Execution Overview |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-ID | Component | Runnable ShortName | RTE Event Type | Cycle / Condition | Ports Read | Ports Written | CalPrm Used | IRV Read | IRV Written | ExclusiveArea | Return Type | ASIL | Timing Budget | OS Task (example) | Notes |
| SPD-RUN-001 | SpdCtrl | SpdCtrl_Init | InitEvent | Once at ECU startup | SpdRef, SpdFbk | IqRef | SpdCtrlPrm (all) | — | SpdCtrlIntgState | — | void | ASIL-B | <100 µs | OsTask_Init | Must complete before first TimingEvent fires |
| SPD-RUN-002 | SpdCtrl | SpdCtrl_1ms | TimingEvent | 1 ms (1000 Hz) | SpdFbk, SpdRef, IqMaxIn | IqRef | Kp, Ki, AntiWindupLim, SpdErrDz, SpdRampRate | — | — | EA_SpdIntg | void | ASIL-B | <50 µs | OsTask_1ms | ExclusiveArea protects iState if future OS task split needed |
| SPD-RUN-003 | SpdCtrl | SpdCtrl_OnModSwitch | ModeSwitchEvent on OpMod | On mode transition | OpMod | IqRef | — | — | SpdCtrlIntgState | EA_SpdIntg | void | ASIL-B | <20 µs | OsTask_Event | Triggered by mode manager |
| CUR-RUN-001 | CurrCtrl | CurrCtrl_Init | InitEvent | Once at ECU startup | IdRef, IqRef, IdFbk, IqFbk, VdcBus | VdCmd, VqCmd | CurrCtrlPrm (all) | — | IdIntgState, IqIntgState | — | void | ASIL-B | <50 µs | OsTask_Init |  |
| CUR-RUN-002 | CurrCtrl | CurrCtrl_100us | TimingEvent | 100 µs (10 kHz) | IdFbk, IqFbk, IdRef, IqRef, VdcBus | VdCmd, VqCmd | KpId, KiId, KpIq, KiIq, VdcNom, VoltLim, Ld, Lq, Rs | — | IdIntgState, IqIntgState | EA_CurrIntg | void | ASIL-B | <30 µs | OsTask_100us | 10 kHz — tightest timing constraint in system. No dynamic memory. |
| MON-RUN-001 | MtrMon | MtrMon_Init | InitEvent | Once | IdMon, IqMon, MtrT, VdcMon | IqMaxOut, MtrProtSt, OcSt, OtSt | All MtrMon CalPrm | — | OcState, OtState | — | void | ASIL-B | <50 µs | OsTask_Init |  |
| MON-RUN-002 | MtrMon | MtrMon_1ms | TimingEvent | 1 ms | IdMon, IqMon, VdcMon, SpdMon | OcSt, MtrProtSt, IqMaxOut | IOcThd, VdcOvThd, VdcUvThd, OsSpdThd | OcState | OcState | EA_MtrState | void | ASIL-B | <60 µs | OsTask_1ms | sqrt() may need CORDIC approximation for ASIL-B |
| MON-RUN-003 | MtrMon | MtrMon_10ms | TimingEvent | 10 ms | MtrT | OtSt, IqMaxOut, MtrProtSt | TOtThd, TOtHyst, IqDerateSlope, IqMaxNom | OtState, OcState | OtState | EA_MtrState | void | ASIL-B | <40 µs | OsTask_10ms | 10ms sufficient for thermal dynamics |
## Sheet: 07_CalibParams
| ALL CALIBRATION PARAMETERS (CalPrm) — A2L / XCP Interface Reference |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-ID | Component | CalPrm ShortName | Long Name | Impl.Type | Unit | Default | Min | Max | Resolution | Online Cal? | A2L Export | CompuMethod | Used In Runnable | Physical Description | Impact if Wrong |
| SPD-CAL-001 | SpdCtrl | Kp | Speed controller proportional gain | float32 | A/rpm | 0.5 | 0.001 | 10.0 | 0.001 | Yes | Yes | ALnrl | SpdCtrl_1ms | P-gain of speed PI loop | Low: sluggish response. High: oscillation / instability |
| SPD-CAL-002 | SpdCtrl | Ki | Speed controller integral gain | float32 | A/(rpm·s) | 0.1 | 0.001 | 5.0 | 0.001 | Yes | Yes | ALnrl | SpdCtrl_1ms | I-gain of speed PI loop; applied per 1ms sample | Low: steady-state error. High: integrator windup / oscillation |
| SPD-CAL-003 | SpdCtrl | AntiWindupLim | Integrator anti-windup saturation limit | float32 | A | 80.0 | 1.0 | 160.0 | 0.1 | Yes | Yes | ALnrl | SpdCtrl_1ms | Maximum absolute value of integrator state | Too low: limits performance. Too high: windup risk during saturation |
| SPD-CAL-004 | SpdCtrl | SpdErrDz | Speed error deadzone | uint16 | rpm | 5 | 0 | 50 | 1 | Yes | Yes | SpdNIdentcl | SpdCtrl_1ms | Speed error below this is treated as zero (reduces jitter at steady-state) | Too high: large steady-state speed error |
| SPD-CAL-005 | SpdCtrl | SpdRampRate | Speed reference ramp rate | float32 | rpm/s | 1000.0 | 10.0 | 10000.0 | 1.0 | Yes | Yes | ALnrl | SpdCtrl_1ms | Maximum rate of change of speed reference (rate limiter) | Too low: slow accel. Too high: mechanical stress / current spikes |
| CUR-CAL-001 | CurrCtrl | KpId | d-axis current PI proportional gain | float32 | V/A | 5.0 | 0.1 | 200.0 | 0.01 | Yes | Yes | VPerALnrl | CurrCtrl_100us | P-gain for d-axis PI controller | Low: slow Id tracking. High: oscillation — motor may destabilize |
| CUR-CAL-002 | CurrCtrl | KiId | d-axis current PI integral gain | float32 | V/(A·s) | 50.0 | 1.0 | 5000.0 | 0.1 | Yes | Yes | VPerALnrl | CurrCtrl_100us | I-gain for d-axis PI; per 100µs sample | Too high: integrator diverges. Too low: steady-state Id error |
| CUR-CAL-003 | CurrCtrl | KpIq | q-axis current PI proportional gain | float32 | V/A | 5.0 | 0.1 | 200.0 | 0.01 | Yes | Yes | VPerALnrl | CurrCtrl_100us | P-gain for q-axis PI controller | Low: slow torque response. High: oscillation |
| CUR-CAL-004 | CurrCtrl | KiIq | q-axis current PI integral gain | float32 | V/(A·s) | 50.0 | 1.0 | 5000.0 | 0.1 | Yes | Yes | VPerALnrl | CurrCtrl_100us | I-gain for q-axis PI; per 100µs sample | Too high: torque ripple / oscillation |
| CUR-CAL-005 | CurrCtrl | VdcNom | Nominal DC bus voltage | float32 | V | 400.0 | 100.0 | 800.0 | 0.1 | No | Yes | VLnrl | CurrCtrl_100us | Nominal Vdc used for normalisation; not measured value | Wrong value → incorrect per-unit scaling of voltage commands |
| CUR-CAL-006 | CurrCtrl | VoltLim | Voltage limit factor | float32 | — | 0.90 | 0.50 | 0.98 | 0.01 | Yes | Yes | VoltLimIdentcl | CurrCtrl_100us | Fraction of Vdc/√3 used as voltage limit circle radius | Too high: overmodulation. Too low: reduced torque capability |
| CUR-CAL-007 | CurrCtrl | Ld | d-axis stator inductance | float32 | H | 0.00100 | 0.00001 | 0.05000 | 0.00001 | No | Yes | LdIdentcl | CurrCtrl_100us | d-axis inductance for cross-coupling decoupling feedforward | Wrong: residual cross-coupling oscillation |
| CUR-CAL-008 | CurrCtrl | Lq | q-axis stator inductance | float32 | H | 0.00120 | 0.00001 | 0.05000 | 0.00001 | No | Yes | LqIdentcl | CurrCtrl_100us | q-axis inductance for cross-coupling decoupling feedforward | Wrong: cross-coupling oscillation at high speed |
| CUR-CAL-009 | CurrCtrl | Rs | Stator phase resistance | float32 | Ω | 0.100 | 0.001 | 5.000 | 0.001 | No | Yes | RsIdentcl | CurrCtrl_100us | Stator resistance for back-EMF compensation at low speed | Wrong: steady-state voltage offset at low speed |
| MON-CAL-001 | MtrMon | IOcThd | Overcurrent peak threshold | float32 | A | 150.0 | 50.0 | 400.0 | 0.1 | No | Yes | ALnrl | MtrMon_1ms | Peak |Idq| threshold triggering overcurrent fault | Too low: nuisance trips. Too high: motor / inverter damage |
| MON-CAL-002 | MtrMon | TOtThd | Overtemperature trip threshold | sint16 | °C | 120 | 80 | 150 | 1 | No | Yes | TIdentcl | MtrMon_10ms | Motor winding temperature triggering OT fault | Too high: insulation damage / winding failure |
| MON-CAL-003 | MtrMon | TOtHyst | Overtemperature hysteresis | sint16 | °C | 10 | 2 | 30 | 1 | No | Yes | TIdentcl | MtrMon_10ms | Temperature must drop by this much below TOtThd to clear OT flag | Too small: chattering. Too large: delayed recovery |
| MON-CAL-004 | MtrMon | VdcOvThd | DC bus overvoltage threshold | uint16 | V×10 | 7500 | 4000 | 9000 | 1 | No | Yes | VdcLnrl | MtrMon_1ms | DC bus OV fault threshold (×0.1 → 750 V) | Too low: nuisance trips during regen. Too high: capacitor damage |
| MON-CAL-005 | MtrMon | VdcUvThd | DC bus undervoltage threshold | uint16 | V×10 | 3000 | 1000 | 4000 | 1 | No | Yes | VdcLnrl | MtrMon_1ms | DC bus UV fault threshold (×0.1 → 300 V) | Too high: spurious faults. Too low: controller brownout |
| MON-CAL-006 | MtrMon | IqDerateSlope | Iq thermal derating slope | float32 | A/°C | 2.0 | 0.1 | 20.0 | 0.01 | Yes | Yes | ALnrl | MtrMon_10ms | Rate at which IqMax is reduced per °C above derating start (TOtThd-20°C) | Too steep: aggressive derating. Too shallow: insufficient protection |
## Sheet: 08_SignalDict
| GLOBAL SIGNAL DICTIONARY — Inter-Component Data Exchange |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Signal Name | Interface Used | Data Element | Impl.Type | Unit | Physical Range | Provider SWC | Provider Port | Consumer SWC(s) | Consumer Port(s) | Update Rate | Description | ASIL | Remarks |
| SpdFbk | SpdN1 | Val | uint16 | rpm | 0–15000 rpm | SpeedObserver | SpdOut | SpdCtrl, MtrMon | SpdFbk / SpdMon | 1 ms | Actual motor mechanical speed from encoder-based observer | ASIL-B | Shared interface SpdN1 |
| SpdRef | SpdN1 | Val | uint16 | rpm | 0–12000 rpm | AppMgr | SpdCmdOut | SpdCtrl | SpdRef | 10 ms | Speed command from application state machine | ASIL-B | Rate-limited inside SpdCtrl |
| IqRef | MtrIq1 | Val | float32 | A | −160 to +160 A | SpdCtrl | IqRef | CurrCtrl | IqRef | 1 ms | q-axis current reference — output of speed PI controller | ASIL-B | Key inter-loop signal |
| IdFbk | MtrId1 | Val | sint16 | A×100 | −160 to +160 A | CurrentSens | IdOut | CurrCtrl, MtrMon | IdFbk / IdMon | 100 µs | d-axis current feedback from ADC + Clarke-Park | ASIL-B | Shared interface MtrId1 |
| IqFbk | MtrIq1 | Val | sint16 | A×100 | −160 to +160 A | CurrentSens | IqOut | CurrCtrl, MtrMon | IqFbk / IqMon | 100 µs | q-axis current feedback from ADC + Clarke-Park | ASIL-B | Shared interface MtrIq1 |
| IdRef | MtrId1 | Val | sint16 | A×100 | −50 to +50 A | MTPA / Const | IdRefOut | CurrCtrl | IdRef | 1 ms | d-axis current reference (0 for SPMSM; MTPA-computed for IPMSM) | ASIL-B | Constant 0 in basic config |
| VdcBus | VdcBus1 | Val | uint16 | V×10 | 0–800 V | VdcMeas | VdcOut | CurrCtrl, MtrMon | VdcBus / VdcMon | 1 ms | DC bus voltage measurement | ASIL-B | Shared interface VdcBus1 |
| VdCmd | MtrVd1 | Val | sint16 | V×100 | −400 to +400 V | CurrCtrl | VdCmd | SVM/PWM | VdIn | 100 µs | d-axis voltage command to space-vector modulator | ASIL-B |  |
| VqCmd | MtrVq1 | Val | sint16 | V×100 | −400 to +400 V | CurrCtrl | VqCmd | SVM/PWM | VqIn | 100 µs | q-axis voltage command to space-vector modulator | ASIL-B |  |
| MtrT | MtrT1 | Val | sint16 | °C | −40 to +200 °C | TempSens | MtrTOut | MtrMon | MtrT | 10 ms | Motor winding temperature from NTC | ASIL-B | Slow thermal time constant |
| IqMaxOut | MtrIqMax1 | Val | float32 | A | 0–160 A | MtrMon | IqMaxOut | SpdCtrl | IqMaxIn | 10 ms | Protection-derived Iq limit — derated by temperature; 0 on fault | ASIL-B | Key protection feedback |
| MtrProtSt | MtrProtSt1 | St | uint8 | — | 0–7 (enum) | MtrMon | MtrProtSt | SysMgr, FaultMgr | MtrProtIn | 1 ms | Aggregated motor protection status code | ASIL-B | 0=OK; higher=more severe |
| OcSt | MtrOcSt1 | St | boolean | — | FALSE/TRUE | MtrMon | OcSt | SafetyMon | OcIn | 1 ms | Overcurrent active flag | ASIL-B | Also triggers inverter shutdown via HW path |
| OtSt | MtrOtSt1 | St | boolean | — | FALSE/TRUE | MtrMon | OtSt | SafetyMon | OtIn | 10 ms | Overtemperature active flag (with hysteresis) | ASIL-B |  |
## Sheet: 09_DataTypes
| DATA TYPE DEFINITIONS — ApplicationDataType and ImplementationDataType |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AppDataType ShortName | Long Name | PhysicalDimension | CompuMethod | CompuMethod Type | Factor | Offset | Unit | ImplDataType | C Primitive | Min (raw) | Max (raw) | Used For |
| SpdN1 | Speed | — | SpdNIdentcl | IDENTICAL | 1 | 0 | rpm | uint16 | uint16 | 0 | 65535 | Motor speed signals |
| MtrId1 | Motor d-axis current | — | MtrIdLnrl | LINEAR | 0.01 | 0 | A | sint16 | sint16 | -16000 | 16000 | d-axis current: feedback, ref, monitor |
| MtrIq1 | Motor q-axis current | — | MtrIqLnrl | LINEAR | 0.01 | 0 | A | sint16/float32 | sint16 (fbk) float32 (ref) | −16000/−160.0 | 16000/160.0 | q-axis current signals |
| MtrIqMax1 | Max allowed q-axis current | — | ALnrl | LINEAR | 0.001 | 0 | A | float32 | float32 | 0.0 | 160.0 | Protection-derived Iq limit |
| VdcBus1 | DC bus voltage | M1L2T−3I−2 | VdcLnrl | LINEAR | 0.1 | 0 | V | uint16 | uint16 | 0 | 8000 | DC bus voltage meas / monitor |
| MtrVd1 | Motor d-axis voltage | M1L2T−3I−1 | VdLnrl | LINEAR | 0.01 | 0 | V | sint16 | sint16 | -40000 | 40000 | d-axis voltage command |
| MtrVq1 | Motor q-axis voltage | M1L2T−3I−1 | VqLnrl | LINEAR | 0.01 | 0 | V | sint16 | sint16 | -40000 | 40000 | q-axis voltage command |
| MtrT1 | Motor temperature | Θ1 | MtrTIdentcl | IDENTICAL | 1 | -40 | °C | sint16 | sint16 | -40 | 200 | Motor winding temperature |
| OpMod1 | Operation mode | — | OpMod1 | TEXTTABLE | — | — | — | uint8 | uint8 | 0 | 4 | System operation mode enum |
| MtrProtSt1 | Motor protection status | — | MtrProtSt1 | TEXTTABLE | — | — | — | uint8 | uint8 | 0 | 7 | Aggregated protection status |
| MtrOcSt1 | Overcurrent status | — | MtrOcSt1 | TEXTTABLE | — | — | — | boolean | boolean | 0 | 1 | OC flag |
| MtrOtSt1 | Overtemperature status | — | MtrOtSt1 | TEXTTABLE | — | — | — | boolean | boolean | 0 | 1 | OT flag |
| Sts1 | Generic boolean status | — | Sts1 | TEXTTABLE | — | — | — | boolean | boolean | 0 | 1 | Generic status flag |