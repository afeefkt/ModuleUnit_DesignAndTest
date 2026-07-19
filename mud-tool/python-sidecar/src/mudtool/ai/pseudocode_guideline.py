"""AUTOSAR Section 7 pseudo-code style guide — single source of truth.

Every Section 7 prompt (single-pass _GEN_SYSTEM_PROMPT, two-stage
_SECTION7_SYSTEM, _REGEN_SYSTEM_PROMPT) imports the constants below so the
rules and examples never drift across files.

The "golden rule" block goes at the TOP of each prompt — small (7B) models
attend strongly to the first and last tokens, so placing the priority rule
first makes it materially harder for the model to ignore.
"""

from __future__ import annotations


# ── The Golden Rule (TOP of every Section 7 prompt) ─────────────────────────
PSEUDO_CODE_GOLDEN_RULE = """
══════════════════════════════════════════════════════════════════════
🚨 SECTION 7 PSEUDO-CODE — HIGHEST PRIORITY RULE (READ FIRST)
══════════════════════════════════════════════════════════════════════
Every numbered step in Section 7 MUST emit C-LIKE PSEUDO-CODE inside a
fenced ```c code block — NOT English narrative prose.

A step is REJECTED and the spec REGENERATED if ANY of these are true:
  · The code body contains no Rte_*, Dem_*, or WdgM_* call
  · The code body contains no C operator (=, ==, !=, <, >, &&, ||, ;)
  · The code body contains no control keyword (if, else, return, switch)
  · The code body is a single English sentence
  · The code is NOT inside a ```c fenced block

This rule OVERRIDES brevity, readability, or stylistic preference.
══════════════════════════════════════════════════════════════════════
"""


# ── Required API patterns ──────────────────────────────────────────────────
REQUIRED_API_PATTERNS = """
EVERY step.code MUST use these exact API patterns:
  Rte_Read(RP_<Port>, &<lvar>);              — read a sender-receiver input
  Rte_IRead(RP_<Port>);                       — read implicit (returns value directly)
  Rte_Write(PP_<Port>, <value>);              — write a sender-receiver output
  Rte_IWrite(PP_<Port>, <value>);             — write implicit
  Rte_Call(RP_<Port>_<Op>, <args>);           — client-server call
  Rte_IrvRead(IRV_<Name>, &<lvar>);           — read inter-runnable variable
  Rte_IrvWrite(IRV_<Name>, <value>);          — write inter-runnable variable
  Rte_Prm(RP_CalPrm_<Name>);                  — read calibration constant
  Dem_ReportErrorStatus(SWC_DEM_E_<Code>, DEM_EVENT_STATUS_FAILED);
  WdgM_UpdateAliveCounter(WDG_<Entity>);
"""


# ── Local variable naming convention ────────────────────────────────────────
LOCAL_VAR_NAMING = """
LOCAL VARIABLE NAMING (mandatory, follow l_<type><Name>):
  l_f32<Name>   — float32     (l_f32Speed, l_f32Torque)
  l_u8<Name>    — uint8       (l_u8RetryCount)
  l_u16<Name>   — uint16
  l_u32<Name>   — uint32
  l_s16<Name>   — int16
  l_bool<Name>  — boolean     (l_boolValid)
  l_e<Name>     — enum        (l_eMode)
"""


# ── Before/After contrast (forces the model to see the failure mode) ────────
BEFORE_AFTER_EXAMPLE = """
EXAMPLE — exactly how to convert prose into valid pseudo-code:

❌ REJECTED (pure prose — this output causes automatic regeneration):
  1. Calculate d-axis and q-axis current errors from references and measurements.
  2. Apply PI control to generate voltage commands with decoupling.
  3. Limit voltage magnitude to safe value.
  4. If a protection fault is active, set output to zero.

✅ REQUIRED (C-like pseudo-code in ```c fenced block, every step has ≥1 Rte_/op/keyword):

### RE_Control
// Reads:  RP_IqRef, RP_IdRef, RP_IqMaxOut, RP_IdMeas, RP_IqMeas
// Writes: PP_VoltageCmd
// IRVs consumed: irvDcBusVoltage, irvFaultStatus
// IRVs produced: irvVdRef, irvVqRef
// CalPrm used:   RP_CalPrm_KpD, RP_CalPrm_KiD, RP_CalPrm_KpQ, RP_CalPrm_KiQ,
//                RP_CalPrm_VoltageLimit

1. Guard
```c
if (irvFaultStatus != FAULT_NONE) {
   Rte_Write(PP_VoltageCmd, 0.0F);
   l_f32IntegD = 0.0F;
   l_f32IntegQ = 0.0F;
   return;
}
```

2. Read inputs
```c
Rte_Read(RP_IqRef, &l_f32IqRef);
Rte_Read(RP_IdRef, &l_f32IdRef);
Rte_Read(RP_IqMeas, &l_f32IqMeas);
Rte_Read(RP_IdMeas, &l_f32IdMeas);
```

3. Compute errors
```c
l_f32ErrD = l_f32IdRef - l_f32IdMeas;
l_f32ErrQ = l_f32IqRef - l_f32IqMeas;
```

4. PI control with anti-windup
```c
l_f32IntegD = l_f32IntegD + Rte_Prm(RP_CalPrm_KiD) * l_f32ErrD;
l_f32IntegQ = l_f32IntegQ + Rte_Prm(RP_CalPrm_KiQ) * l_f32ErrQ;
l_f32VdRaw  = Rte_Prm(RP_CalPrm_KpD) * l_f32ErrD + l_f32IntegD;
l_f32VqRaw  = Rte_Prm(RP_CalPrm_KpQ) * l_f32ErrQ + l_f32IntegQ;
```

5. Voltage magnitude limit
```c
l_f32VMag = sqrtf(l_f32VdRaw * l_f32VdRaw + l_f32VqRaw * l_f32VqRaw);
if (l_f32VMag > Rte_Prm(RP_CalPrm_VoltageLimit)) {
   l_f32Scale = Rte_Prm(RP_CalPrm_VoltageLimit) / l_f32VMag;
   l_f32VdRaw = l_f32VdRaw * l_f32Scale;
   l_f32VqRaw = l_f32VqRaw * l_f32Scale;
}
```

6. Write outputs
```c
Rte_IrvWrite(IRV_VdRef, l_f32VdRaw);
Rte_IrvWrite(IRV_VqRef, l_f32VqRaw);
Rte_Write(PP_VoltageCmd, l_f32VMag);
```
"""


# ── Final reminder (END of every Section 7 prompt — sandwich pattern) ───────
FINAL_REMINDER = """
══════════════════════════════════════════════════════════════════════
FINAL REMINDER — Section 7 prose causes AUTOMATIC REGENERATION.
Every step's code body MUST be a ```c fenced block with real C code:
  · Real Rte_/Dem_/WdgM_ calls with exact port names
  · Real assignments using l_<type><Name> locals
  · Real if/else/return/switch keywords with { } braces
NO English sentences. NO arrow shorthand. NO "calculate X" or "apply Y".
══════════════════════════════════════════════════════════════════════
"""


# Combined block for direct prompt injection at the TOP of a prompt
SECTION7_GUIDELINE_BLOCK = (
    PSEUDO_CODE_GOLDEN_RULE
    + "\n" + REQUIRED_API_PATTERNS
    + "\n" + LOCAL_VAR_NAMING
    + "\n" + BEFORE_AFTER_EXAMPLE
)
