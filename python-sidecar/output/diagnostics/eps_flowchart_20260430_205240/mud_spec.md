# MUD Spec: SWC_ElectricPowerSteering

## 1. Overview
| Field | Value |
|-------|-------|
| SWC Name | SWC_ElectricPowerSteering |
| ASIL Level | ASIL-D |
| Description | SWC_ElectricPowerSteering handles ePS SWC Architecture. |
| Runnables | RE_ControlTorque, RE_MonitorSafety, RE_Initialize, RE_HandleModeChange, RE_DiagnosticUpdate |

## 2. Ports

### 2.1 Provided Ports (P-Ports)
| Port Name | Interface | Data Element | Data Type | Range / Unit | Period | Description |
|-----------|-----------|--------------|-----------|--------------|--------|-------------|
| PP_MotorCurrentDemand | IF_SR_MotorCurrent | DE_MotorCurrentDemand | int16 | [-32768, 32767] A |  | Motor current demand to be sent to motor controller |
| PP_EPSStatus | IF_SR_EPSStatus | DE_EPSStatus | uint8 | [0, 3] |  | EPS status to be sent to upper layers |
| PP_AssistLevel | IF_SR_AssistLevel | DE_AssistLevel | uint8 | [0, 100] % |  | Assist level to be sent to upper layers |

### 2.2 Required Ports (R-Ports)
| Port Name | Interface | Data Element | Data Type | Range / Unit | Provider | Description |
|-----------|-----------|--------------|-----------|--------------|----------|-------------|
| RP_VehicleSpeed | IF_SR_VehicleSpeed | DE_VehicleSpeed | uint16 | [0, 255] km/h | — | Vehicle speed from CAN signal |
| RP_IgnitionStatus | IF_SR_IgnitionStatus | DE_IgnitionStatus | uint8 | [0, 1] | — | Ignition status from CAN signal |
| RP_YawRate | IF_SR_YawRate | DE_YawRate | int16 | [-32768, 32767] deg/s | — | Yaw rate from CAN signal |
| RP_TorqueSensorPrimary | IF_SR_TorqueSensor | DE_TorqueSensorPrimary | int16 | [-32768, 32767] Nm | — | Torque sensor primary signal from CAN signal |
| RP_TorqueSensorSecondary | IF_SR_TorqueSensor | DE_TorqueSensorSecondary | int16 | [-32768, 32767] Nm | — | Torque sensor secondary signal from CAN signal |
| RP_MotorTemperature | IF_SR_Temperature | DE_MotorTemperature | uint8 | [0, 255] °C | — | Motor temperature from CAN signal |

### 2.3 Calibration Ports (CalPrm)
| Port Name | Interface | Data Type | Default | Range | Description |
|-----------|-----------|-----------|---------|-------|-------------|
| — | — | — | — | — | No calibration parameters defined |

## 3. Runnables

### 3.1 Main Runnables (OS-scheduled via AUTOSAR RTE)
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_ControlTorque | Cyclic | 5ms | ASIL-D | Computes torque assist demand and writes motor current output. |
| RE_MonitorSafety | Cyclic | 10ms | ASIL-D | Performs plausibility checks and updates diagnostics. |
| RE_Initialize | Init |  | ASIL-D | Initializes the SWC on ECU startup. |
| RE_HandleModeChange | DataReceivedEvent |  | ASIL-D | Handles mode transitions based on IgnitionStatus_CAN signal. |
| RE_DiagnosticUpdate | DataReceivedEvent |  | ASIL-D | Updates active DTCs to NVM via NvM_WriteBlock. |

### 3.2 Sub-Functions (internal C helpers called by main runnables)
| Function | Called By | Description |
|----------|-----------|-------------|
| — | — | No sub-functions defined |

## 4. Inter-Runnable Variables (IRV)
| IRV Name | Data Type | Producer Runnable | Consumer Runnable | ExclusiveArea? | Description |
|----------|-----------|-------------------|-------------------|----------------|-------------|
| — | — | — | — | — | No IRVs defined |

## 5. Data Types
| Type Name | Base Type | Range | Unit | Description |
|-----------|-----------|-------|------|-------------|
| VehicleSpeed_t | uint16 | [0, 255] | km/h | Vehicle speed from CAN signal |
| IgnitionStatus_t | uint8 | [0, 1] |  | Ignition status from CAN signal |
| YawRate_t | int16 | [-32768, 32767] | deg/s | Yaw rate from CAN signal |
| TorqueSensorPrimary_t | int16 | [-32768, 32767] | Nm | Torque sensor primary signal from CAN signal |
| TorqueSensorSecondary_t | int16 | [-32768, 32767] | Nm | Torque sensor secondary signal from CAN signal |
| MotorTemperature_t | uint8 | [0, 255] | °C | Motor temperature from CAN signal |
| MotorCurrentDemand_t | int16 | [-32768, 32767] | A | Motor current demand to be sent to motor controller |
| EPSStatus_t | uint8 | [0, 3] |  | EPS status to be sent to upper layers |
| AssistLevel_t | uint8 | [0, 100] | % | Assist level to be sent to upper layers |

## 6. Error Handling & Safety

ASIL Level: ASIL-D

| DEM Event ID | Description | ASIL | Trigger | Safe-State Reaction |
|-------------|-------------|------|---------|---------------------|
| SWC_DEM_E_EPS_CAN_TIMEOUT | CAN communication timeout detected. | ASIL-D | RP_VehicleSpeed == 0 && RP_TorqueSensorPrimary == 0 | Set EPS status to FAIL_SAFE and clear all DTCs. |
| SWC_DEM_E_EPS_OVERCURRENT | Overcurrent detected in motor. | ASIL-D | PP_MotorCurrentDemand > 32767 | Set EPS status to FAIL_SAFE and clear all DTCs. |
| SWC_DEM_E_EPS_OVERHEAT | Motor temperature exceeds safe limit. | ASIL-D | RP_MotorTemperature > 100 | Set EPS status to FAIL_SAFE and clear all DTCs. |
| SWC_DEM_E_EPS_SENSOR_FAIL | One or more sensors fail. | ASIL-D | RP_VehicleSpeed == 0 || RP_TorqueSensorPrimary == 0 || RP_TorqueSensorSecondary == 0 || RP_MotorTemperature == 255 | Set EPS status to FAIL_SAFE and clear all DTCs. |
| SWC_DEM_E_EPS_MIN_ASSIST_HIGH_SPEED | Assist exceeds maximum limit at high speed. | ASIL-D | RP_VehicleSpeed >= 120 && PP_MotorCurrentDemand > 32767 * 0.1 | Set EPS status to FAIL_SAFE and clear all DTCs. |

## 7. Functional Description

### RE_ControlTorque
// Reads:  RP_VehicleSpeed, RP_TorqueSensorPrimary
// Writes: PP_MotorCurrentDemand, PP_AssistLevel
**1. Guard**
```c
   if (RP_IgnitionStatus != 1) {
   Rte_IWrite(PP_MotorCurrentDemand, 0);
   Rte_IWrite(PP_AssistLevel, 0);
   return;
}
```

**2. Read inputs**
```c
uint16 vehicleSpeed = Rte_IRead(RP_VehicleSpeed);
int16 torqueSensorPrimary = Rte_IRead(RP_TorqueSensorPrimary);
```

**3. Validate**
```c
   if (vehicleSpeed < 0 || vehicleSpeed > 255) {
   Rte_IWrite(PP_MotorCurrentDemand, 0);
   Rte_IWrite(PP_AssistLevel, 0);
   Dem_ReportErrorStatus(SWC_DEM_E_EPS_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED);
   return;
}
   if (torqueSensorPrimary < -32768 || torqueSensorPrimary > 32767) {
   Rte_IWrite(PP_MotorCurrentDemand, 0);
   Rte_IWrite(PP_AssistLevel, 0);
   Dem_ReportErrorStatus(SWC_DEM_E_EPS_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED);
   return;
}
```

**4. Compute**
```c
// Placeholder for computation logic
int16 motorCurrentDemand = torqueSensorPrimary * 0.5;
uint8 assistLevel = (torqueSensorPrimary > 0) ? 100 : 0;
```

**5. Write outputs**
```c
   Rte_IWrite(PP_MotorCurrentDemand, motorCurrentDemand);
   Rte_IWrite(PP_AssistLevel, assistLevel);
```

**6. Watchdog update**
```c
WdgM_UpdateAliveCounter(WDG_ENTITY_RE_CONTROL_TORQUE);
```

### RE_MonitorSafety
// Reads:  RP_IgnitionStatus, RP_YawRate
// Writes: none
**1. Guard**
```c
   if (Rte_IRead(RP_IgnitionStatus) == 0) {
   Rte_IWrite(PP_EPSStatus, 3);
   Dem_ReportErrorStatus(SWC_DEM_E_EPS_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED);
   return;
}
```

**2. Read inputs**
```c
uint16 vehicleSpeed = Rte_IRead(RP_VehicleSpeed);
int16 yawRate = Rte_IRead(RP_YawRate);
```

**3. Validate**
```c
   if (vehicleSpeed < 0 || vehicleSpeed > 255) {
   Rte_IWrite(PP_EPSStatus, 3);
   Dem_ReportErrorStatus(SWC_DEM_E_EPS_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED);
   return;
}
   if (yawRate < -32768 || yawRate > 32767) {
   Rte_IWrite(PP_EPSStatus, 3);
   Dem_ReportErrorStatus(SWC_DEM_E_EPS_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED);
   return;
}
```

**4. Compute**
```c
// Placeholder for computation logic
   if (yawRate > 1000 && vehicleSpeed > 50) {
   Rte_IWrite(PP_EPSStatus, 3);
   Dem_ReportErrorStatus(SWC_DEM_E_EPS_MIN_ASSIST_HIGH_SPEED, DEM_EVENT_STATUS_FAILED);
   return;
}
```

**5. Write outputs**
```c
// No output ports to write
```

**6. Watchdog update**
```c
WdgM_UpdateAliveCounter(1);
```

### RE_Initialize
// Reads:  none
// Writes: PP_EPSStatus
**1. Set EPS status to INIT**
```c
   Rte_IWrite(PP_EPSStatus, EPS_STATUS_INIT);
```

**2. Report initialization complete**
```c
WdgM_UpdateAliveCounter(WDG_ENTITY_ID_RE);
```

### RE_HandleModeChange
// Reads:  RP_IgnitionStatus
// Writes: none
**1. Guard: mode check**
```c
   if (Rte_IRead(RP_IgnitionStatus) != 1) {
PP_EPSStatus = FAIL_SAFE;
   Dem_ReportErrorStatus(SWC_DEM_E_EPS_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED);
   return;
}
```

**2. Read inputs**
```c
uint8 ignition_status = Rte_IRead(RP_IgnitionStatus);
```

**3. Validate**
```c
   if (ignition_status != 1) {
PP_EPSStatus = FAIL_SAFE;
   Dem_ReportErrorStatus(SWC_DEM_E_EPS_SENSOR_FAIL, DEM_EVENT_STATUS_FAILED);
   return;
}
```

**4. Compute**
```c
// No computation needed for this example
```

**5. Write outputs**
```c
// No outputs to write for this example
```

**6. Watchdog update**
```c
WdgM_UpdateAliveCounter(ENTITY_ID);
```

### RE_DiagnosticUpdate
// Reads:  none
// Writes: PP_EPSStatus
**1. Guard**
```c
   if (Rte_IRead(RP_IgnitionStatus) != 1) {
      Rte_IWrite(PP_EPSStatus, 0);
      return;
}
```

**2. Read inputs**
```c
// No inputs to read
```

**3. Validate**
```c
// No validation needed
```

**4. Compute**
```c
// No computation needed
```

**5. Write outputs**
```c
   Rte_IWrite(PP_EPSStatus, 1);
```

**6. Watchdog update**
```c
WdgM_UpdateAliveCounter(WDG_ENTITY_ID_RE_DiagnosticUpdate);
```
