# AEB — Automatic Emergency Braking: architecture requirements (DOORS export)

> Input set for the **MUD_MUT** pipeline (`inputs/requirements/aeb/aeb_requirements.csv`).
> 66 requirements, multi-SWC, DOORS "Export View" CSV. Companion to `aeb_requirements.csv`.

---

## 1. Why this topic

The repo's existing samples are single-SWC control/safety components (BMS, EPS, PMSM-FOC,
ADAS sensor fusion). AEB is a **decentralised AUTOSAR safety chain** — *sense → assess → decide →
actuate → monitor* — that forces the pipeline to:

- **split requirements across multiple SWCs** (module planning is genuinely exercised),
- cover **all five `req_type`s** (`functional`, `interface`, `timing`, `safety`, `constraint`),
- produce **many unit-testable functions** (`TTC_Compute`, `ObjectAssociation`, `DecelRateLimiter`,
  `DriverOverrideDetect`, `PressureMap`, `E2E_Verify`, `SensorPlausibilityCheck`).

It is also the *canonical* driver-assistance safety feature, with published regulatory requirements
(UNECE R152) and industry test thresholds, so every number below is traceable rather than invented.

---

## 2. Standards & sources (research summary)

| Source | What it gives us | Used in |
|---|---|---|
| **UNECE R152** (Advanced Emergency Braking Systems) | System must detect an imminent forward collision, warn the driver, and activate service braking; **emergency braking demand ≥ 5.0 m/s²**; collision warning uses **≥ 2 modalities** (acoustic/haptic/optical) and must occur **no later than braking onset**; system active **≥ 10–60 km/h**; homologation tests at **20/42/60 km/h**; car-to-pedestrian (ped crossing at 5 km/h) and car-to-bicycle (15 km/h) scenarios. | REQ-AEB-001…007, 204, 303, 702 |
| **ISO 22839** (Forward Vehicle Collision Mitigation, 2013) | Definition of forward collision mitigation and speed-reduction performance framing. | context for 201–209 |
| **ISO 26262** (functional safety) | ASIL assignment: the brake-actuation chain is ASIL-C/D; HMI/comfort functions QM–B. | ASIL column throughout |
| **Industry TTC literature** (e.g. MDPI *Appl. Sci.*, *ASSESS* project) | Typical calibration: **FCW at TTC ≈ 2.6 s**, **partial braking ≈ 1.6 s (~40 %)**, **full braking ≈ 0.6 s (~100 %)**. R152 is performance-based; these thresholds are the widely used engineering defaults. | REQ-AEB-204/205/206/207/303 |
| **NHTSA FMVSS 127** (2024 final rule) | US parallel: test speeds up to 80 km/h, FCW must include **both** auditory and visual onset. | reference only (not encoded) |
| **IBM DOORS / DOORS Next CSV export** | CSV "Export View" columns: `Object Identifier`, `Absolute Number`, `Object Heading`, `Object Text`, `Object Level`, plus user-defined attributes. | header layout (see §4) |

Sources (retrieved 2026-10-10): `unece.org` R152r2E / R152am1e, `atic-ts.com` AEBS homologation
summary, `nhtsa.gov` FMVSS 127 final rule, `federalregister.gov` 2024-09054,
`researchgate`/`mdpi.com` TTC-threshold literature.

> **Note on thresholds:** TTC values 2.6 / 1.6 / 0.6 s and the 40 % / 100 % braking split are
> engineering **calibration defaults** from literature, not R152 normative numbers (R152 only fixes
> the ≥ 5.0 m/s² emergency demand and the ≥ 2-modality warning). They are encoded as calibration
> parameters so a calibrator can change them without touching the design.

---

## 3. Architecture

```
                    ┌──────────────────────────────────────────────────────────────┐
                    │  SWC_AEB_SensorFusion  RE_FuseObjects (10 ms)                │
   RP_RadarObjects──┤    radar + camera object lists → fused object list           │
   RP_CameraObjects─┤    time-align · associate · plausibility · timeout flags     │
                    └───────────────┬──────────────────────────────────────────────┘
                                    │ PP_FusedObjects
                    ┌───────────────▼──────────────────────────────────────────────┐
                    │  SWC_AEB_RiskAssessor  RE_AssessCollisionRisk (20 ms)        │
                    │    TTC · critical-object selection · FCW/partial/full        │
                    │    thresholds · collision probability                        │
                    └───────────────┬──────────────────────────────────────────────┘
                                    │ PP_RiskAssessment (risk_level, TTC, prob)
                    ┌───────────────▼──────────────────────────────────────────────┐
                    │  SWC_AEB_Controller  RE_ArbitrateBrakeDemand (10 ms)         │
                    │    arbitration · decel map · rate-limit · driver override    │
                    │    pre-fill · ABS coordination · failsafe demand             │
                    └───────────────┬──────────────────────────────────────────────┘
                                    │ PP_BrakeDemand (decel, mode, E2E counter)
                    ┌───────────────▼──────────────────────────────────────────────┐
                    │  SWC_AEB_BrakeActuator  RE_CommandBrake (5 ms)               │
                    │    decel→pressure map · ramp · feedback check · saturation   │
                    └───────────────┬──────────────────────────────────────────────┘
                                    │ PP_BrakePressure (to booster / ABS)
                                    ▼
    SWC_AEB_VehicleState  RE_UpdateEgoMotion (10 ms)   ──►  PP_VehicleState
    SWC_AEB_SafetyMonitor RE_MonitorSafety   (5 ms)    ──►  PP_SafetyStatus (E2E, WD, mode)
    SWC_AEB_HMI           RE_UpdateWarning  (event)    ──►  PP_HMIWarning
```

### SWC / runnable / requirement summary

| SWC | Runnable(s) | Reqs | IDs |
|---|---|---|---|
| System (baseline) | — | 8 | REQ-AEB-001…008 |
| SWC_AEB_SensorFusion | RE_FuseObjects, RE_TrackAssociate | 10 | REQ-AEB-101…110 |
| SWC_AEB_RiskAssessor | RE_AssessCollisionRisk | 9 | REQ-AEB-201…209 |
| SWC_AEB_Controller | RE_ArbitrateBrakeDemand | 12 | REQ-AEB-301…312 |
| SWC_AEB_BrakeActuator | RE_CommandBrake | 8 | REQ-AEB-401…408 |
| SWC_AEB_SafetyMonitor | RE_MonitorSafety | 9 | REQ-AEB-501…509 |
| SWC_AEB_VehicleState | RE_UpdateEgoMotion | 6 | REQ-AEB-601…606 |
| SWC_AEB_HMI | RE_UpdateWarning | 4 | REQ-AEB-701…704 |

**Totals:** 66 requirements · 8 modules · type = 26 functional / 15 safety / 13 interface /
6 timing / 6 constraint · ASIL = 48 D / 14 B / 4 C · priority = 65 must / 1 should.

---

## 4. DOORS export column mapping

The CSV header mimics a DOORS **"Export View"** spreadsheet export. MUD_MUT's importer
(`mud-tool/.../importers/base.py` `DEFAULT_COLUMN_MAPPING`) maps these headers to canonical fields:

| CSV header (DOORS) | Canonical field | Notes |
|---|---|---|
| `Object Identifier` | `req_id` | DOORS module-unique identifier; we use `REQ-AEB-###`. |
| `Object Heading` | `title` | short title (DOORS "Object Heading"). |
| `Object Text` | `description` | full requirement text (DOORS "Object Text") — primary AI input. |
| `Object Level` | *(ignored)* | DOORS indentation level (1 = baseline, 2 = SWC) — cosmetic, harmless. |
| `Allocated To` | `module_hint` | target SWC (DOORS custom attribute "Allocated To"). |
| `ASIL` | `safety_level` | `QM`/`ASIL-A…D`. |
| `Priority` | `priority` | `must`/`should`/`could`/`won't` (MoSCoW). |
| `Status` | `status` | `approved` (all rows are ready for design). |
| `Type` | `req_type` | `functional`/`interface`/`timing`/`safety`/`constraint`. |
| `Parent_ID` | `parent_id` | hierarchy link (SWC rows → `REQ-AEB-001`). |
| `Notes` | `notes` | rationale / standard reference / `req_type=` hint. |

**Deliberate omission:** `Absolute Number` and `Object Short Text` are *not* included. The importer
maps multiple aliases to the same canonical field and the last column wins, so `Absolute Number`
alongside `Object Identifier` would silently overwrite the ID (and `Object Short Text` would
overwrite the title). One header per canonical field keeps the import deterministic — verified with
`ImporterFactory.import_file(...)`: **66 rows, 0 errors, 0 warnings.**

---

## 5. Traceability (requirement → runnable → unit-test target)

Every requirement description names its owning runnable and the concrete function/constant it
governs, so MUD flow-chart generation and CppUTest generation have unambiguous targets. Example
map (representative, not exhaustive):

| Requirement | Runnable | Key unit-testable functions / checks |
|---|---|---|
| REQ-AEB-104 | RE_FuseObjects | `TimeAlign()` (drop > 200 ms) |
| REQ-AEB-105 | RE_TrackAssociate | `Associate()` (0.5 m / 2.0 m/s gates) |
| REQ-AEB-107 | RE_FuseObjects | `IsPlausible()` (range/speed/probability reject) |
| REQ-AEB-202 | RE_AssessCollisionRisk | `TTC_Compute()` (TTC = dist / rel_speed, ≤0 → TTC_MAX) |
| REQ-AEB-203 | RE_AssessCollisionRisk | `SelectCriticalObject()` (ego-path half-width) |
| REQ-AEB-204/205/206 | RE_AssessCollisionRisk | threshold + hysteresis latching |
| REQ-AEB-207 | RE_AssessCollisionRisk | `CollisionProbability()` (piecewise-linear) |
| REQ-AEB-303 | RE_ArbitrateBrakeDemand | demand map (0/0/4/9 m/s²) |
| REQ-AEB-304 | RE_ArbitrateBrakeDemand | `DecelRateLimiter()` (15 m/s³) |
| REQ-AEB-305 | RE_ArbitrateBrakeDemand | `DriverOverrideDetect()` (10 bar / 80 %) |
| REQ-AEB-309 | RE_ArbitrateBrakeDemand | 16-bit E2E demand counter rollover |
| REQ-AEB-402/403/407 | RE_CommandBrake | `PressureMap()`, ramp (200/300 bar/s), clamp [0,250] |
| REQ-AEB-502/503 | RE_MonitorSafety | `SensorPlausibilityCheck()`, `E2E_Verify()` |
| REQ-AEB-606 | RE_UpdateEgoMotion | `StandstillDetect()` hysteresis |

---

## 6. How to use it

```bash
# one-click full chain (local preset)
python -m mudmut_core.chain \
    --requirements inputs/requirements/aeb/aeb_requirements.csv \
    --swc SWC_AEB_Controller --preset local-fast

# or run the whole multi-SWC feature via the Streamlit UI (Full Chain page)
./launch.sh
```

Because the file is a multi-SWC set, plan modules (`planner` stage) will first group requirements
into SWCs, then generate a MUD per SWC. For a focused run pick one SWC with `--swc` (e.g.
`SWC_AEB_Controller` is the richest with 12 requirements and the most unit-testable functions).
