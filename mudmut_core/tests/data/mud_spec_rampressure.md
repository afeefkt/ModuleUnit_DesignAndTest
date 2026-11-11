# MUD Spec: SWC_AEB_BrakeActuator

## 1. Overview
| Field | Value |
|-------|-------|
| SWC Name | SWC_AEB_BrakeActuator |
| ASIL Level | ASIL-D |
| Description | Converts deceleration demand into a ramped, saturated brake pressure command and verifies pressure feedback. |
| Runnables | RE_RampPressure |

## 2. Ports

### 2.1 Provided Ports (P-Ports)
| Port Name | Interface | Data Element | Data Type | Range / Unit | Period | Description |
|-----------|-----------|--------------|-----------|--------------|--------|-------------|
| PP_BrakePressure | IF_SR_Pressure | DE_BrakePressure | AEB_BrakePressureType | 0..250 bar | 5 ms | Commanded brake pressure output with 0.1 bar resolution. |
| PP_BrakeActuationStatus | IF_SR_ActuationStatus | DE_BrakeActuationStatus | AEB_ActuationStatusType | 0..3 enum | 5 ms | Actuation health status flag published with the brake pressure command. |
| PP_BrakeActuationFault | IF_SR_BrakeActuationFault | DE_BrakeActuationFault | AEB_BrakeFaultType | 0..1 boolean | 5 ms | Brake actuation fault notification to SWC_AEB_SafetyMonitor. |

### 2.2 Required Ports (R-Ports)
| Port Name | Interface | Data Element | Data Type | Range / Unit | Provider | Description |
|-----------|-----------|--------------|-----------|--------------|----------|-------------|
| RP_DecelerationDemand | IF_SR_DecelerationDemand | DE_DecelerationDemand | AEB_DecelerationDemandType | 0..12 m/s2 | SWC_AEB_TargetDeceleration | Deceleration demand input from the AEB planner. |
| RP_BrakePressureFeedback | IF_SR_PressureFeedback | DE_BrakePressureFeedback | AEB_BrakePressureType | 0..300 bar | BrakeBooster | Achieved brake pressure feedback from the brake booster. |

### 2.3 Calibration Ports (CalPrm)
| Port Name | Interface | Data Type | Default | Range | Description |
|-----------|-----------|-----------|---------|-------|-------------|
| RP_CalPrm_KVehMass | IF_Prm_RP_CalPrm_KVehMass | AEB_VehicleMassType | 1500.0 | 1000..2500 kg | Calibrated vehicle mass used in the pressure mapping equation. |
| RP_CalPrm_KBrakeGain | IF_Prm_RP_CalPrm_KBrakeGain | AEB_BrakeGainType | 75.0 | 1.0..200.0 m/s2 per bar | Calibrated brake gain used to convert deceleration demand to brake pressure. |
| RP_CalPrm_RampApplyRate | IF_Prm_RP_CalPrm_RampApplyRate | AEB_RampRateType | 200.0 | 0..500 bar/s | Maximum brake pressure application ramp rate. |
| RP_CalPrm_RampReleaseRate | IF_Prm_RP_CalPrm_RampReleaseRate | AEB_RampRateType | 300.0 | 0..600 bar/s | Maximum brake pressure release ramp rate. |
| RP_CalPrm_FeedbackDeviationThreshold | IF_Prm_RP_CalPrm_FeedbackDeviationThreshold | AEB_PressureThresholdType | 15.0 | 1..50 bar | Brake pressure feedback deviation threshold for fault reporting. |
| RP_CalPrm_PMax | IF_Prm_RP_CalPrm_PMax | AEB_PressureThresholdType | 250.0 | 100..300 bar | Maximum allowed commanded brake pressure. |
| RP_CalPrm_MinActivePressure | IF_Prm_RP_CalPrm_MinActivePressure | AEB_PressureThresholdType | 1.0 | 0..5 bar | Minimum active pressure; commands below this value are treated as 0 bar. |
| RP_CalPrm_FeedbackDebounceTime | IF_Prm_RP_CalPrm_FeedbackDebounceTime | AEB_DebounceTimeType | 0.05 | 0.01..0.2 s | Debounce time before a persistent feedback deviation is reported. |

## 3. Runnables

### 3.1 Main Runnables (OS-scheduled via AUTOSAR RTE)
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_RampPressure | Cyclic | 5 ms | ASIL-D | Ramps the target brake pressure toward the desired value using calibrated apply and release rates. |

### 3.2 Sub-Functions (internal C helpers called by main runnables)
| Function | Called By | Description |
|----------|-----------|-------------|
| SF_InitActuator | RE_Init | Initializes actuator state, validates calibration parameters, and writes safe default outputs. |
| SF_MapDecelToPressure | RE_MapPressure | Implements P_target = decel_demand * K_veh_mass / K_brake_gain. |
| SF_RampPressure | RE_RampPressure | Limits brake pressure change to the calibrated apply and release ramp rates. |
| SF_SaturatePressure | RE_SaturatePressure | Clamps commanded pressure to [0, P_MAX] and treats pressures below the minimum active threshold as 0 bar. |
| SF_CheckPressureFeedback | RE_CheckBrakeFeedback | Computes pressure deviation, applies debounce timing, and sets the feedback fault flag. |
| SF_PublishBrakeCommand | RE_CommandBrake | Publishes final pressure and actuation status and enforces 0 bar IDLE output when braking is not active. |

## 4. Inter-Runnable Variables (IRV)
| IRV Name | Data Type | Producer Runnable | Consumer Runnable | ExclusiveArea? | Description |
|----------|-----------|-------------------|-------------------|----------------|-------------|
| IRV_InitComplete | boolean | RE_Init | RE_CommandBrake | EA_InitState | Set after successful initialization and gates normal brake command publishing. |
| IRV_TargetPressure | AEB_BrakePressureType | RE_MapPressure | RE_RampPressure | EA_PressureComputation | Target brake pressure computed from deceleration demand. |
| IRV_RampedPressure | AEB_BrakePressureType | RE_RampPressure | RE_SaturatePressure | EA_PressureComputation | Rate-limited brake pressure before saturation. |
| IRV_PreviousRampedPressure | AEB_BrakePressureType | RE_RampPressure | RE_RampPressure | EA_RampState | Previous ramped pressure value used for rate limiting. |
| IRV_SaturatedPressure | AEB_BrakePressureType | RE_SaturatePressure | RE_CheckBrakeFeedback | EA_PressureComputation | Saturated brake pressure used by the feedback check. |
| IRV_FinalBrakePressure | AEB_BrakePressureType | RE_SaturatePressure | RE_CommandBrake | EA_PressureComputation | Final saturated brake pressure to be published. |
| IRV_PressureDeviation | float32 | RE_CheckBrakeFeedback | RE_CommandBrake | EA_FeedbackCheck | Absolute or signed difference between commanded and feedback pressure. |
| IRV_FeedbackFaultActive | boolean | RE_CheckBrakeFeedback | RE_CommandBrake | EA_FeedbackCheck | Indicates that a persistent brake feedback deviation fault is active. |
| IRV_FeedbackDeviationTimer | uint16 | RE_CheckBrakeFeedback | RE_CheckBrakeFeedback | EA_FeedbackCheck | Debounce timer for persistent brake pressure feedback deviation. |

## 5. Data Types
| Type Name | Base Type | Range | Unit | Description |
|-----------|-----------|-------|------|-------------|
| AEB_DecelerationDemandType | float32 | 0..12 | m/s2 | Deceleration demand from the AEB function. |
| AEB_BrakePressureType | float32 | 0..300 | bar | Brake pressure value with 0.1 bar resolution. |
| AEB_ActuationStatusType | uint8 | 0..3 | enum | Brake actuation status: 0=IDLE, 1=ACTIVE, 2=FAULT, 3=INIT. |
| AEB_BrakeFaultType | uint8 | 0..1 | boolean | Brake actuation fault flag. |
| AEB_VehicleMassType | float32 | 1000..2500 | kg | Calibrated vehicle mass value. |
| AEB_BrakeGainType | float32 | 1.0..200.0 | m/s2 per bar | Calibrated brake gain value. |
| AEB_RampRateType | float32 | 0..600 | bar/s | Calibrated pressure ramp rate. |
| AEB_PressureThresholdType | float32 | 0..300 | bar | Calibrated pressure threshold value. |
| AEB_DebounceTimeType | float32 | 0..1 | s | Calibrated time debounce value. |
| AEB_FeedbackDeviationTimerType | uint16 | 0..1000 | ms | Feedback deviation debounce timer value. |

## 6. Error Handling & Safety

ASIL Level: ASIL-D

| DEM Event ID | Description | ASIL | Trigger | Safe-State Reaction |
|-------------|-------------|------|---------|---------------------|
| SWC_DEM_E_CalibrationInvalid | Calibration parameters for vehicle mass, brake gain, ramp rates, thresholds, or maximum pressure are out of range during initialization. | ASIL-D | RE_Init detects any calibrated parameter outside its configured range. | Command 0 bar, set actuation status to INIT/IDLE, and report brake actuation fault. |
| SWC_DEM_E_PressureMappingFault | Pressure mapping produced a non-finite or out-of-range target brake pressure. | ASIL-D | RE_MapPressure output is NaN, infinite, or outside the valid pressure range before ramping. | Set target pressure to 0 bar and request safe brake command. |
| SWC_DEM_E_RampRateFault | Brake pressure ramp exceeded the calibrated apply or release rate. | ASIL-D | RE_RampPressure detects a pressure change greater than the calibrated apply or release rate limit. | Clamp the pressure to the rate limit and hold the last safe pressure command. |
| SWC_DEM_E_PressureSaturationFault | Saturated brake pressure command is outside the valid actuator range. | ASIL-D | RE_SaturatePressure output is outside [0, P_MAX] or its input is invalid. | Set commanded pressure to 0 bar and set actuation status to FAULT. |
| SWC_DEM_E_BrakeFeedbackDeviation | Brake pressure feedback deviates from the commanded pressure beyond threshold for longer than the debounce time. | ASIL-D | Absolute difference between RP_BrakePressureFeedback and commanded pressure exceeds RP_CalPrm_FeedbackDeviationThreshold for longer than RP_CalPrm_FeedbackDebounceTime. | Set PP_BrakeActuationFault to 1, command 0 bar if deviation persists, and notify SWC_AEB_SafetyMonitor. |
| SWC_DEM_E_BrakeCommandFault | Brake command publishing detected invalid state or missing initialization. | ASIL-D | RE_CommandBrake runs without initialization complete or with an invalid final pressure or status. | Publish 0 bar, set status to FAULT, and set the actuation fault flag. |

## 7. Functional Description

### RE_RampPressure
// Reads:  none
// Writes: none
// IRVs consumed: IRV_TargetPressure, IRV_PreviousRampedPressure
// IRVs produced: IRV_RampedPressure, IRV_PreviousRampedPressure
// CalPrm used:   RP_CalPrm_RampApplyRate, RP_CalPrm_RampReleaseRate
**1. Guard**
```c
      if (Rte_IrvRead(IRV_TargetPressure, &l_targetPressure) != RTE_E_OK) {
         Rte_IrvWrite(IRV_RampedPressure, 0.0f);
         Rte_IrvWrite(IRV_PreviousRampedPressure, 0.0f);
         return;
}
```

**2. Read inputs**
```c
l_prevRamped = Rte_IrvRead(IRV_PreviousRampedPressure);
      if (l_prevRamped < 0.0f) {
   l_prevRamped = 0.0f;
}
```

**3. Validate**
```c
      if (l_targetPressure < 0.0f || l_targetPressure > 300.0f) {
         Dem_ReportErrorStatus(SWC_DEM_E_PressureMappingFault, DEM_EVENT_STATUS_FAILED);
         Rte_IrvWrite(IRV_RampedPressure, 0.0f);
         Rte_IrvWrite(IRV_PreviousRampedPressure, 0.0f);
         return;
}
```

**4. Compute**
```c
l_applyRate = Rte_Prm(RP_CalPrm_RampApplyRate);
l_releaseRate = Rte_Prm(RP_CalPrm_RampReleaseRate);
l_delta = l_targetPressure - l_prevRamped;
      if (l_delta > 0.0f) {
   l_maxStep = l_applyRate * 0.005f;
         if (l_delta > l_maxStep) {
      l_ramped = l_prevRamped + l_maxStep;
      }
         else {
      l_ramped = l_targetPressure;
   }
   }
      else if (l_delta < 0.0f) {
   l_maxStep = l_releaseRate * 0.005f;
         if (-l_delta > l_maxStep) {
      l_ramped = l_prevRamped - l_maxStep;
      }
         else {
      l_ramped = l_targetPressure;
   }
   }
      else {
   l_ramped = l_targetPressure;
}
```

**5. Write outputs**
```c
      if (l_ramped < 0.0f) {
   l_ramped = 0.0f;
   }
      else if (l_ramped > 300.0f) {
   l_ramped = 300.0f;
}
      Rte_IrvWrite(IRV_RampedPressure, l_ramped);
      Rte_IrvWrite(IRV_PreviousRampedPressure, l_ramped);
```

**6. Watchdog**
```c
WdgM_UpdateAliveCounter(WDGM_ENTITY_RE_RampPressure);
```

