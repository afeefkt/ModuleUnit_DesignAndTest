"""Two-stage MUD spec generation pipeline.

Replaces single-pass generation with a structured approach:

  Stage 1 — Skeleton (JSON)
    A single focused call extracts ALL element names and their metadata:
    ports, runnables, IRVs, CalPrm, DEM events.  The model only needs to
    output a structured JSON — no prose, no pseudo-code.  7b models handle
    this reliably.

  Stage 2 — Cross-Reference Map
    Pure-Python post-processing builds a lookup of every named element.
    No AI call needed.

  Stage 3 — Section 7 Pseudo-code (one JSON call per runnable)
    For each runnable the model receives:
      - The runnable name + its reads/writes/irvs/calparms (from skeleton)
      - The full port list (so exact Rte_Read() signatures can be used)
      - A few-shot example from the EPS reference document
    Produces numbered pseudo-code steps with exact Rte_*/Dem_*/WdgM_ calls.

  Stage 4 — Deterministic Validator (Python)
    Checks: every Rte_Read port name exists in Section 2, every CalPrm ref
    exists, every DEM event ID referenced in steps exists in dem_events.
    Produces a list of fixable discrepancies (no AI call).

  Stage 5 — Markdown Assembly (Jinja2-like template)
    Builds the 7-section MUD spec Markdown deterministically from the
    validated skeleton + section-7 objects.  No AI call.

Usage (from MudSpecGenerator):

    pipeline = MudSpecPipeline(backend, reviewer_backend, progress_callback)
    spec_md = await pipeline.generate(
        swc_name, description, asil, runnables, req_ids, requirements_text
    )
"""

from __future__ import annotations

import json
import logging
import re
import textwrap
from pathlib import Path
from typing import Optional

from mudtool.ai.mud_element_schemas import SECTION7_RUNNABLE_SCHEMA, SKELETON_SCHEMA

logger = logging.getLogger(__name__)

# ── Load AUTOSAR catalog ──────────────────────────────────────────────────────

def _load_catalog() -> dict:
    catalog_path = Path(__file__).parent.parent.parent.parent.parent / "knowledge" / "autosar_catalog.json"
    if catalog_path.exists():
        try:
            return json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback: minimal inline catalog
    return {
        "port_naming": {
            "PP_": "Provided Port", "RP_": "Required Port", "RP_CalPrm_": "Calibration Parameter"
        },
        "rte_api": {
            "Rte_Read(port, &var)": "Read from Required SR port",
            "Rte_Write(port, value)": "Write to Provided SR port",
            "Rte_IRead(port)": "Implicit read, returns value",
            "Rte_IWrite(port, value)": "Implicit write",
            "Rte_IrvRead(irv, &var)": "Read Inter-Runnable Variable",
            "Rte_IrvWrite(irv, value)": "Write Inter-Runnable Variable",
            "Rte_Prm(calprm)": "Read calibration parameter",
        },
        "dem_api": {
            "Dem_ReportErrorStatus(EventId, DEM_EVENT_STATUS_FAILED)": "Report fault active",
        },
    }

_CATALOG = _load_catalog()


def _load_reference() -> dict:
    """Load the EPS reference JSON produced by csv_to_reference_json.py (optional)."""
    ref_path = Path(__file__).parent.parent.parent.parent.parent / "knowledge" / "eps_reference.json"
    if ref_path.exists():
        try:
            return json.loads(ref_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

_REFERENCE = _load_reference()

# ── Stage 1 prompt ────────────────────────────────────────────────────────────

_SKELETON_SYSTEM = """You are an AUTOSAR SWC architect.
Output ONLY a single valid JSON object that matches the schema exactly.
Do NOT add prose, comments, markdown fences, or explanation.
Start your response with {{ and end with }}.

JSON schema to follow:
- swc_name: string
- asil: string (QM / ASIL-A / ASIL-B / ASIL-C / ASIL-D)
- description: string (one sentence)
- ports: array — every input/output/calibration port
  Each port: name(PP_*/RP_*/RP_CalPrm_*), direction(provided|required|calibration),
  interface(IF_SR_*/IF_CS_*/IF_Prm_*), data_element(DE_*), data_type, range, unit,
  period, description, [provider_swc], [default_value], [safe_state]
- runnables: array — every OS-scheduled runnable (RE_*)
  Each runnable: name, trigger(Init|Cyclic|DataReceived|...), period, asil, description,
  reads(list of RP_ port names), writes(list of PP_ port names),
  irvs_consumed, irvs_produced, calparms_used(list of RP_CalPrm_* names),
  sub_functions(list of internal helper function names), execution_order
- sub_functions: array — internal C helper functions
  Each: name, called_by (runnable name), description
- irvs: array — inter-runnable variables
  Each: name, data_type, range, unit, producer_runnable, consumer_runnable, [exclusive_area], description
- calparms: array — calibration parameters
  Each: name, port_name(RP_CalPrm_*), data_type, default_value, range, unit, used_by, description, memory_section
- dem_events: array — all DEM fault events
  Each: event_id(SWC_DEM_E_*), description, asil, trigger_condition, safe_state_reaction, dem_priority, related_runnable
- data_types: array — AUTOSAR application data types
  Each: name, base_type, range, unit, description

RULES:
- Port names: PP_ for provided, RP_ for required, RP_CalPrm_ for calibration parameters
- Interface names: IF_SR_ for sender/receiver, IF_CS_ for client/server, IF_Prm_ for calibration
- Data element names always start with DE_
- Every ASIL-C/D runnable must have at least one DEM event
- Include ALL ports, runnables, IRVs, and CalPrm you can derive from the requirements
- Do NOT include Section 7 pseudo-code — that comes later

CALPRM NAMING — STRICT:
  All calibration ports MUST start with "RP_CalPrm_" prefix.
  WRONG:  CP_BaseGain, MAX_TORQUE, RP_BaseGain, BaseGain
  RIGHT:  RP_CalPrm_BaseGain, RP_CalPrm_MaxTorque, RP_CalPrm_KFriction
  In the calparms[] array, the "port_name" field MUST start with "RP_CalPrm_".
  Required ports (RP_*) and CalPrm ports (RP_CalPrm_*) MUST NEVER share a name.
  ASIL-B / ASIL-C / ASIL-D modules MUST list at least one DEM event in dem_events[].
  Every dem_events[] entry MUST have an event_id starting with "SWC_DEM_E_".
"""

_SKELETON_USER_TMPL = """Generate the complete skeleton JSON for SWC: {swc_name}

CONTEXT:
- SWC Name: {swc_name}
- Description: {description}
- ASIL Level: {asil}
- Detected Runnables: {runnables}
- Linked Requirement IDs: {req_ids}

HINTS DETECTED IN REQUIREMENTS — your skeleton MUST include all of these
(rename CP_/CalPrm_ to the strict RP_CalPrm_ form, rename DTC_ to SWC_DEM_E_):
{hints_block}

REQUIREMENTS (extract all ports, IRVs, CalPrm, and DEM events from these):
{requirements_text}

Output ONLY the JSON object. No prose. No fences."""

# ── Stage 3 prompt (per runnable) ─────────────────────────────────────────────

_SECTION7_SYSTEM = """You are an AUTOSAR firmware engineer writing pseudo-code for a runnable.
Output ONLY a single valid JSON object.
Start with {{ and end with }}.

JSON schema:
- runnable_name: string
- reads: array of RP_ port names
- writes: array of PP_ port names
- irvs_consumed: array of IRV names
- irvs_produced: array of IRV names
- calparms_used: array of RP_CalPrm_* port names
- steps: array of {{step_num, label, code}} objects
  - step_num: integer starting at 1
  - label: short description e.g. "Guard: mode check", "Read inputs", "Compute output"
  - code: multi-line C-like pseudo-code string using exact Rte_ API calls below

RTE API to use (use these exact function name patterns):
  Rte_IRead(<port_name>)              — read RP_ port, returns value directly
  Rte_IWrite(<port_name>, <value>)    — write PP_ port
  Rte_IrvRead(<irv_name>, &<var>)     — read IRV
  Rte_IrvWrite(<irv_name>, <value>)   — write IRV
  Rte_Prm(<calparm_port>)             — read calibration parameter
  Dem_ReportErrorStatus(<event_id>, DEM_EVENT_STATUS_FAILED)  — report fault
  Dem_ReportErrorStatus(<event_id>, DEM_EVENT_STATUS_PASSED)  — clear fault
  WdgM_UpdateAliveCounter(<entity_id>) — watchdog alive report

PSEUDO-CODE RULES:
1. First step: Guard/mode check — if module not in correct state, write safe output and RETURN
2. Read all RP_ inputs in one step using Rte_IRead()
3. Validate inputs (range checks, NaN, plausibility) — on failure: write 0/safe to PP_ port, call Dem_ReportErrorStatus(), RETURN
4. Core computation step(s) using Rte_Prm() for calibrations and Rte_IrvRead/Write() for IRVs
5. Write PP_ output using Rte_IWrite() with clamp to safe range
6. Last step: WdgM_UpdateAliveCounter() for ASIL-C/D runnables

REFERENCE EXAMPLE (EPS RE_ControlTorque):
{few_shot_example}
"""

_SECTION7_USER_TMPL = """Generate Section 7 pseudo-code for runnable: {runnable_name}

RUNNABLE METADATA:
- Name: {runnable_name}
- Trigger: {trigger} | Period: {period} | ASIL: {asil}
- Description: {description}
- Reads (RP_ ports): {reads}
- Writes (PP_ ports): {writes}
- IRVs consumed: {irvs_consumed}
- IRVs produced: {irvs_produced}
- CalPrm used: {calparms_used}
- Sub-functions: {sub_functions}

ALL PORTS IN THIS SWC (use exact names):
{all_ports_summary}

ALL DEM EVENTS IN THIS SWC:
{dem_events_summary}

Output ONLY the JSON object."""


# ── Validation helpers ────────────────────────────────────────────────────────

def _validate_cross_refs(skeleton: dict, section7_map: dict[str, dict]) -> list[str]:
    """Deterministic cross-reference validation.

    Returns a list of human-readable issue strings (empty = all clean).
    """
    issues: list[str] = []

    # Build lookup sets
    port_names = {p["name"] for p in skeleton.get("ports", [])}
    calprm_names = {cp["port_name"] for cp in skeleton.get("calparms", [])}
    irv_names = {irv["name"] for irv in skeleton.get("irvs", [])}
    dem_ids = {e["event_id"] for e in skeleton.get("dem_events", [])}

    for runnable_name, s7 in section7_map.items():
        for port in s7.get("reads", []):
            if port and port not in port_names:
                issues.append(
                    f"[{runnable_name}] reads unknown port '{port}' — not in Section 2"
                )
        for port in s7.get("writes", []):
            if port and port not in port_names:
                issues.append(
                    f"[{runnable_name}] writes unknown port '{port}' — not in Section 2"
                )
        for irv in s7.get("irvs_consumed", []) + s7.get("irvs_produced", []):
            if irv and irv not in irv_names:
                issues.append(
                    f"[{runnable_name}] references unknown IRV '{irv}' — not in Section 4"
                )
        for cp in s7.get("calparms_used", []):
            if cp and cp not in calprm_names:
                issues.append(
                    f"[{runnable_name}] uses unknown CalPrm '{cp}' — not in Section 2.3"
                )
        # Check DEM event IDs in code blocks
        for step in s7.get("steps", []):
            code = step.get("code", "")
            for dem_ref in re.findall(r'SWC_DEM_E_[A-Z_]+', code):
                if dem_ref not in dem_ids:
                    issues.append(
                        f"[{runnable_name} step {step.get('step_num')}] "
                        f"DEM event '{dem_ref}' not defined in Section 6 — "
                        "add it to dem_events in skeleton"
                    )

    return issues


# ── Markdown assembly ─────────────────────────────────────────────────────────

def _assemble_markdown(skeleton: dict, section7_map: dict[str, dict],
                       validation_issues: list[str]) -> str:
    """Assemble the 7-section MUD spec Markdown from validated skeleton + section-7 data."""
    lines: list[str] = []
    swc_name = skeleton.get("swc_name", "UnknownSWC")

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append(f"# MUD Spec: {swc_name}")
    lines.append("")

    # ── Section 1 Overview ──────────────────────────────────────────────────
    lines.append("## 1. Overview")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| SWC Name | {swc_name} |")
    lines.append(f"| ASIL Level | {skeleton.get('asil', 'QM')} |")
    desc = skeleton.get("description", "")
    lines.append(f"| Description | {desc} |")
    runnable_names = ", ".join(r["name"] for r in skeleton.get("runnables", []))
    lines.append(f"| Runnables | {runnable_names} |")
    lines.append("")

    # ── Section 2 Ports ─────────────────────────────────────────────────────
    lines.append("## 2. Ports")
    lines.append("")

    pp_ports = [p for p in skeleton.get("ports", []) if p.get("direction") == "provided"]
    rp_ports = [p for p in skeleton.get("ports", []) if p.get("direction") == "required"]
    cal_ports = [p for p in skeleton.get("ports", []) if p.get("direction") == "calibration"]

    lines.append("### 2.1 Provided Ports (P-Ports)")
    lines.append("| Port Name | Interface | Data Element | Data Type | Range / Unit | Period | Description |")
    lines.append("|-----------|-----------|--------------|-----------|--------------|--------|-------------|")
    for p in pp_ports:
        range_unit = _fmt_range_unit(p)
        lines.append(
            f"| {p.get('name','')} | {p.get('interface','')} | {p.get('data_element','')} "
            f"| {p.get('data_type','')} | {range_unit} | {p.get('period','')} "
            f"| {p.get('description','')} |"
        )
    if not pp_ports:
        lines.append("| — | — | — | — | — | — | No provided ports defined |")
    lines.append("")

    lines.append("### 2.2 Required Ports (R-Ports)")
    lines.append("| Port Name | Interface | Data Element | Data Type | Range / Unit | Provider | Description |")
    lines.append("|-----------|-----------|--------------|-----------|--------------|----------|-------------|")
    for p in rp_ports:
        range_unit = _fmt_range_unit(p)
        provider = p.get("provider_swc", "—")
        lines.append(
            f"| {p.get('name','')} | {p.get('interface','')} | {p.get('data_element','')} "
            f"| {p.get('data_type','')} | {range_unit} | {provider} "
            f"| {p.get('description','')} |"
        )
    if not rp_ports:
        lines.append("| — | — | — | — | — | — | No required ports defined |")
    lines.append("")

    lines.append("### 2.3 Calibration Ports (CalPrm)")
    lines.append("| Port Name | Interface | Data Type | Default | Range | Description |")
    lines.append("|-----------|-----------|-----------|---------|-------|-------------|")
    for cp in skeleton.get("calparms", []):
        range_str = cp.get("range", "")
        unit = cp.get("unit", "")
        range_unit = f"{range_str} {unit}".strip() if unit and unit != "—" else range_str
        lines.append(
            f"| {cp.get('port_name','')} | IF_Prm_{cp.get('name','')} "
            f"| {cp.get('data_type','')} | {cp.get('default_value','')} "
            f"| {range_unit} | {cp.get('description','')} |"
        )
    if not skeleton.get("calparms"):
        lines.append("| — | — | — | — | — | No calibration parameters defined |")
    lines.append("")

    # ── Section 3 Runnables ─────────────────────────────────────────────────
    lines.append("## 3. Runnables")
    lines.append("")

    main_runnables = skeleton.get("runnables", [])
    sub_functions = skeleton.get("sub_functions", [])

    lines.append("### 3.1 Main Runnables (OS-scheduled via AUTOSAR RTE)")
    lines.append("| Runnable | Trigger | Period | ASIL | Description |")
    lines.append("|----------|---------|--------|------|-------------|")
    for r in main_runnables:
        lines.append(
            f"| {r.get('name','')} | {r.get('trigger','')} | {r.get('period','—')} "
            f"| {r.get('asil','')} | {r.get('description','')} |"
        )
    lines.append("")

    lines.append("### 3.2 Sub-Functions (internal C helpers called by main runnables)")
    lines.append("| Function | Called By | Description |")
    lines.append("|----------|-----------|-------------|")
    for sf in sub_functions:
        lines.append(
            f"| {sf.get('name','')} | {sf.get('called_by','')} | {sf.get('description','')} |"
        )
    if not sub_functions:
        lines.append("| — | — | No sub-functions defined |")
    lines.append("")

    # ── Section 4 IRVs ──────────────────────────────────────────────────────
    lines.append("## 4. Inter-Runnable Variables (IRV)")
    lines.append("| IRV Name | Data Type | Producer Runnable | Consumer Runnable | ExclusiveArea? | Description |")
    lines.append("|----------|-----------|-------------------|-------------------|----------------|-------------|")
    for irv in skeleton.get("irvs", []):
        ea = irv.get("exclusive_area", "—") or "—"
        lines.append(
            f"| {irv.get('name','')} | {irv.get('data_type','')} "
            f"| {irv.get('producer_runnable','')} | {irv.get('consumer_runnable','')} "
            f"| {ea} | {irv.get('description','')} |"
        )
    if not skeleton.get("irvs"):
        lines.append("| — | — | — | — | — | No IRVs defined |")
    lines.append("")

    # ── Section 5 Data Types ─────────────────────────────────────────────────
    lines.append("## 5. Data Types")
    lines.append("| Type Name | Base Type | Range | Unit | Description |")
    lines.append("|-----------|-----------|-------|------|-------------|")
    for dt in skeleton.get("data_types", []):
        lines.append(
            f"| {dt.get('name','')} | {dt.get('base_type','')} "
            f"| {dt.get('range','')} | {dt.get('unit','')} | {dt.get('description','')} |"
        )
    if not skeleton.get("data_types"):
        # Auto-generate from ports if data_types not in skeleton
        seen: set[str] = set()
        for p in skeleton.get("ports", []):
            dt_name = f"{p.get('data_element','').replace('DE_','')}_t"
            if dt_name not in seen:
                seen.add(dt_name)
                lines.append(
                    f"| {dt_name} | {p.get('data_type','float32')} "
                    f"| {p.get('range','')} | {p.get('unit','')} "
                    f"| {p.get('description','')} |"
                )
    lines.append("")

    # ── Section 6 Error Handling ─────────────────────────────────────────────
    lines.append("## 6. Error Handling & Safety")
    lines.append("")
    asil = skeleton.get("asil", "QM")
    lines.append(f"ASIL Level: {asil}")
    lines.append("")
    dem_events = skeleton.get("dem_events", [])
    if dem_events:
        lines.append("| DEM Event ID | Description | ASIL | Trigger | Safe-State Reaction |")
        lines.append("|-------------|-------------|------|---------|---------------------|")
        for ev in dem_events:
            lines.append(
                f"| {ev.get('event_id','')} | {ev.get('description','')} "
                f"| {ev.get('asil', asil)} | {ev.get('trigger_condition','')} "
                f"| {ev.get('safe_state_reaction','')} |"
            )
    else:
        lines.append("No DEM events defined.")
    lines.append("")

    if validation_issues:
        lines.append("### Cross-Reference Issues (auto-detected — fix in next regeneration)")
        for issue in validation_issues:
            lines.append(f"- ⚠ {issue}")
        lines.append("")

    # ── Section 7 Functional Description ────────────────────────────────────
    lines.append("## 7. Functional Description")
    lines.append("")

    for runnable in main_runnables:
        rname = runnable.get("name", "")
        s7 = section7_map.get(rname)

        lines.append(f"### {rname}")

        # Header comment block
        reads_str = ", ".join(s7.get("reads", runnable.get("reads", []))) if s7 else ", ".join(runnable.get("reads", []))
        writes_str = ", ".join(s7.get("writes", runnable.get("writes", []))) if s7 else ", ".join(runnable.get("writes", []))
        irvs_consumed = ", ".join((s7.get("irvs_consumed", []) if s7 else runnable.get("irvs_consumed", [])) or [])
        irvs_produced = ", ".join((s7.get("irvs_produced", []) if s7 else runnable.get("irvs_produced", [])) or [])
        calparms = ", ".join((s7.get("calparms_used", []) if s7 else runnable.get("calparms_used", [])) or [])

        lines.append(f"// Reads:  {reads_str or 'none'}")
        lines.append(f"// Writes: {writes_str or 'none'}")
        if irvs_consumed:
            lines.append(f"// IRVs consumed: {irvs_consumed}")
        if irvs_produced:
            lines.append(f"// IRVs produced: {irvs_produced}")
        if calparms:
            lines.append(f"// CalPrm used:   {calparms}")
        lines.append("")

        if s7 and s7.get("steps"):
            for step in s7["steps"]:
                snum = step.get("step_num", "?")
                label = step.get("label", "")
                code = step.get("code", "").strip()
                if label:
                    lines.append(f"{snum}. {label}:")
                else:
                    lines.append(f"{snum}.")
                # Indent code block
                for code_line in code.splitlines():
                    lines.append(f"   {code_line}")
        else:
            # Fallback: minimal stub when Section 7 generation failed
            lines.append(f"1. // TODO: Section 7 generation failed for {rname}")
            lines.append(f"   // reads={reads_str} writes={writes_str}")

        lines.append("")

    return "\n".join(lines)


def _fmt_range_unit(port: dict) -> str:
    rng = port.get("range", "")
    unit = port.get("unit", "")
    if unit and unit not in ("—", "-", ""):
        return f"{rng} {unit}".strip()
    return rng


# ── Requirements pre-population ───────────────────────────────────────────────

def _seed_from_requirements(requirements_text: str) -> dict:
    """Extract obvious named entities from raw requirements text via regex.

    These are HINTS — Stage 1 model can extend or correct them, but is
    pressured to acknowledge them rather than silently dropping them.
    """
    text = requirements_text or ""
    return {
        # DTC_* (legacy diagnostic codes, often used in OEM requirements)
        "dem_event_hints": sorted(set(re.findall(
            r"\bDTC_[A-Z][A-Z0-9_]+", text))),
        # SWC_DEM_E_* (strict AUTOSAR convention — already correct)
        "dem_event_strict": sorted(set(re.findall(
            r"\bSWC_DEM_E_[A-Z][A-Z0-9_]+", text))),
        "irv_hints": sorted(set(re.findall(
            r"\b(?:irv_|IRV_)[A-Za-z][A-Za-z0-9_]+", text))),
        "calprm_hints": sorted(set(re.findall(
            r"\b(?:CalPrm_|CP_)[A-Z][A-Za-z0-9_]+", text))),
        "runnable_hints": sorted(set(re.findall(
            r"\bRE_[A-Z][A-Za-z0-9_]+", text))),
    }


def _format_hints_block(hints: dict) -> str:
    """Format a hints dict as a multi-line user-prompt block.  Empty fields
    become 'none detected' so the placeholder still appears."""
    def fmt(items: list[str]) -> str:
        return ", ".join(items) if items else "(none detected)"

    dem_combined = sorted(set(hints.get("dem_event_hints", [])
                              + hints.get("dem_event_strict", [])))
    return (
        f"  DEM event IDs: {fmt(dem_combined)}\n"
        f"  IRVs:          {fmt(hints.get('irv_hints', []))}\n"
        f"  CalPrm:        {fmt(hints.get('calprm_hints', []))}\n"
        f"  Runnables:     {fmt(hints.get('runnable_hints', []))}"
    )


# ── Skeleton-quality checks (deterministic, used to trigger one retry) ────────

def _skeleton_problems(skeleton: dict, asil: str) -> list[str]:
    """Return a list of human-readable problems with the skeleton.
    Empty list = skeleton is acceptable."""
    problems: list[str] = []
    asil_safety = asil.upper() in ("ASIL-B", "ASIL-C", "ASIL-D")

    # Rule 1: ASIL-B/C/D must have at least one DEM event
    if asil_safety and not skeleton.get("dem_events"):
        problems.append(
            f"Module is {asil} but dem_events[] is empty. "
            "Add at least one DEM event derived from the requirements."
        )

    # Rule 2: every CalPrm port_name must start with RP_CalPrm_
    bad_calprm = [
        cp for cp in (skeleton.get("calparms") or [])
        if not str(cp.get("port_name", "")).startswith("RP_CalPrm_")
    ]
    if bad_calprm:
        names = ", ".join(cp.get("port_name", "?") for cp in bad_calprm[:5])
        problems.append(
            f"CalPrm port names must start with 'RP_CalPrm_'. "
            f"Wrong: {names}. Rename them to RP_CalPrm_<Name>."
        )

    # Rule 3: no port name shared between required ports and calibration ports
    rp_names = {p.get("name", "") for p in (skeleton.get("ports") or [])
                if p.get("direction") == "required"}
    cal_names = {p.get("name", "") for p in (skeleton.get("ports") or [])
                 if p.get("direction") == "calibration"}
    shared = (rp_names & cal_names) - {""}
    if shared:
        problems.append(
            f"Required ports and calibration ports cannot share names. "
            f"Conflict: {', '.join(sorted(shared))}. "
            "Rename calibration ports to use the RP_CalPrm_ prefix."
        )

    # Rule 4: every DEM event must have an SWC_DEM_E_ event_id
    bad_dem = [
        e for e in (skeleton.get("dem_events") or [])
        if not str(e.get("event_id", "")).startswith("SWC_DEM_E_")
    ]
    if bad_dem:
        names = ", ".join(e.get("event_id", "?") for e in bad_dem[:5])
        problems.append(
            f"DEM event IDs must start with 'SWC_DEM_E_'. Wrong: {names}."
        )

    return problems


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict | None:
    """Extract the outermost JSON object from a potentially messy LLM response."""
    if not raw:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    cleaned = re.sub(r"```(?:json)?", "", cleaned).strip().rstrip("`").strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end])
        except json.JSONDecodeError:
            pass

    # Try innermost valid JSON objects
    for m in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", cleaned, re.DOTALL):
        try:
            d = json.loads(m.group(0))
            if isinstance(d, dict):
                return d
        except json.JSONDecodeError:
            continue

    return None


# ── Pipeline class ────────────────────────────────────────────────────────────

class MudSpecPipeline:
    """Two-stage MUD spec generator with per-runnable Section 7 expansion.

    Produces CSV-quality documentation by decomposing generation into:
    Stage 1: JSON skeleton (all element names + metadata)
    Stage 3: per-runnable Section 7 pseudo-code with exact Rte_ calls
    Stage 4: deterministic cross-reference validation
    Stage 5: deterministic Markdown assembly
    """

    def __init__(self, backend, skeleton_backend=None, progress_callback=None):
        """
        Args:
            backend:           Default backend for all stages (Stage 3 always uses this).
            skeleton_backend:  Optional separate backend for Stage 1 skeleton.
                               If None, Stage 1 uses ``backend``.  Used to route
                               skeleton generation to a stronger reasoning model
                               (e.g. deepseek-r1:7b) without changing Stage 3.
            progress_callback: Optional callback(dict) for SSE progress events.
        """
        self._backend = backend
        self._skeleton_backend = skeleton_backend or backend
        self._progress = progress_callback

    def _emit(self, stage: str, message: str, progress: int = 0, **extra):
        if self._progress:
            self._progress({"stage": stage, "message": message, "progress": progress, **extra})

    # ─── Public entry point ────────────────────────────────────────────────

    async def generate(
        self,
        swc_name: str,
        description: str,
        asil: str,
        runnables: list[str],
        req_ids: list[str],
        requirements_text: str,
        temperature: float = 0.1,
    ) -> str:
        """Run all pipeline stages and return the assembled MUD spec Markdown."""

        self._emit("mud_spec", f"[Pipeline] Stage 1/5 — generating skeleton for {swc_name}…", 10)

        # ── Stage 1: Skeleton ──────────────────────────────────────────────
        skeleton = await self._stage1_skeleton(
            swc_name, description, asil, runnables, req_ids, requirements_text, temperature
        )

        if not skeleton:
            logger.warning("[Pipeline] Stage 1 skeleton failed — falling back to None")
            return ""   # caller falls back to single-pass

        self._emit("mud_spec", f"[Pipeline] Stage 1 complete — {len(skeleton.get('ports',[]))} ports, "
                   f"{len(skeleton.get('runnables',[]))} runnables", 35)

        # ── Stage 3: Section 7 per runnable ───────────────────────────────
        section7_map: dict[str, dict] = {}
        main_runnables = skeleton.get("runnables", [])
        total = len(main_runnables)

        for idx, runnable in enumerate(main_runnables, 1):
            rname = runnable.get("name", f"RE_{idx}")
            self._emit(
                "mud_spec",
                f"[Pipeline] Stage 3/{total} — Section 7 pseudo-code for {rname}…",
                35 + int(40 * idx / max(total, 1)),
            )
            s7 = await self._stage3_section7(skeleton, runnable, temperature)
            if s7:
                section7_map[rname] = s7
            else:
                logger.warning("[Pipeline] Stage 3 failed for %s — will use stub", rname)

        self._emit("mud_spec", f"[Pipeline] Stage 4 — cross-reference validation…", 78)

        # ── Stage 4: Cross-reference validation ───────────────────────────
        validation_issues = _validate_cross_refs(skeleton, section7_map)
        if validation_issues:
            logger.warning(
                "[Pipeline] %d cross-reference issue(s):\n%s",
                len(validation_issues),
                "\n".join(f"  {i}" for i in validation_issues),
            )

        self._emit(
            "mud_spec",
            f"[Pipeline] Stage 5 — assembling Markdown "
            f"({len(validation_issues)} cross-ref issue(s))…",
            85,
        )

        # ── Stage 5: Markdown assembly ─────────────────────────────────────
        spec_md = _assemble_markdown(skeleton, section7_map, validation_issues)

        self._emit("mud_spec", f"[Pipeline] Complete — {len(spec_md):,} chars generated", 92)
        logger.info(
            "[Pipeline] Generated spec for %s: %d chars, %d runnables, %d s7 entries, %d issues",
            swc_name, len(spec_md), total, len(section7_map), len(validation_issues),
        )
        return spec_md

    # ─── Stage 1 ──────────────────────────────────────────────────────────

    async def _stage1_skeleton(
        self,
        swc_name: str,
        description: str,
        asil: str,
        runnables: list[str],
        req_ids: list[str],
        requirements_text: str,
        temperature: float,
    ) -> dict | None:
        # ── Build system prompt with EPS reference few-shot ────────────────
        system_prompt = _SKELETON_SYSTEM
        if _REFERENCE:
            ref_lines = ["", "REFERENCE EXAMPLES (from a real AUTOSAR EPS SWC):", ""]
            ip = _REFERENCE.get("few_shot_prompts", {}).get("input_port_example", "")
            op = _REFERENCE.get("few_shot_prompts", {}).get("output_port_example", "")
            cp = _REFERENCE.get("few_shot_prompts", {}).get("calib_param_example", "")
            if ip:
                ref_lines.extend(["INPUT PORT EXAMPLE:", ip, ""])
            if op:
                ref_lines.extend(["OUTPUT PORT EXAMPLE:", op, ""])
            if cp:
                ref_lines.extend(["CALIB PARAM EXAMPLE:", cp, ""])
            system_prompt = _SKELETON_SYSTEM + "\n".join(ref_lines)

        # ── Pre-populate hints from raw requirements via regex ─────────────
        hints = _seed_from_requirements(requirements_text)
        hints_block = _format_hints_block(hints)
        logger.info(
            "[Pipeline/Stage1] Pre-pop hints: %d DEM, %d IRV, %d CalPrm, %d runnable",
            len(hints["dem_event_hints"]) + len(hints["dem_event_strict"]),
            len(hints["irv_hints"]),
            len(hints["calprm_hints"]),
            len(hints["runnable_hints"]),
        )

        user_prompt = _SKELETON_USER_TMPL.format(
            swc_name=swc_name,
            description=description,
            asil=asil,
            runnables=", ".join(runnables) if runnables else "not yet determined",
            req_ids=", ".join(req_ids) if req_ids else "all",
            hints_block=hints_block,
            requirements_text=requirements_text[:3000],
        )

        # Use the dedicated skeleton backend (may differ from generator backend)
        backend = self._skeleton_backend
        backend_name = getattr(backend, "backend_name", "?")
        logger.info("[Pipeline/Stage1] using backend %s for %s", backend_name, swc_name)

        skeleton = await self._call_skeleton(
            backend, system_prompt, user_prompt, temperature
        )
        if not skeleton:
            return None

        # ── Quality check + one retry on missing fields ────────────────────
        problems = _skeleton_problems(skeleton, asil)
        if problems:
            logger.warning(
                "[Pipeline/Stage1] First skeleton has %d problem(s) — retrying once. Problems:\n  %s",
                len(problems), "\n  ".join(problems),
            )
            self._emit(
                "mud_spec",
                f"[Pipeline] Stage 1 retry — fixing {len(problems)} skeleton issue(s)…",
                25,
            )
            retry_user_prompt = (
                user_prompt
                + "\n\n"
                + "═══════════════════════════════════════════════\n"
                + "PREVIOUS SKELETON HAD PROBLEMS — FIX ALL OF THESE:\n"
                + "\n".join(f"  - {p}" for p in problems)
                + "\n\n"
                + "Return the SAME JSON structure with these problems fixed.\n"
                + "Keep all correct fields from before; only fix the listed issues."
            )
            retried = await self._call_skeleton(
                backend, system_prompt, retry_user_prompt, max(temperature, 0.0)
            )
            if retried:
                still_bad = _skeleton_problems(retried, asil)
                if len(still_bad) < len(problems):
                    logger.info(
                        "[Pipeline/Stage1] Retry improved skeleton: %d → %d problems",
                        len(problems), len(still_bad),
                    )
                    skeleton = retried
                else:
                    logger.warning(
                        "[Pipeline/Stage1] Retry did not improve skeleton (%d problems remain).",
                        len(still_bad),
                    )

        # Final defaulting — ensure swc_name + asil are always set
        if not skeleton.get("swc_name"):
            skeleton["swc_name"] = swc_name
        if not skeleton.get("asil"):
            skeleton["asil"] = asil

        return skeleton

    async def _call_skeleton(
        self,
        backend,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> dict | None:
        """Single skeleton AI call + JSON extraction + key normalisation."""
        try:
            response = await backend.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=4096,
                response_format="json",
            )
            skeleton = _extract_json(response.content)
            if not skeleton:
                logger.warning(
                    "[Pipeline/Stage1] Failed to extract JSON from response: %s…",
                    response.content[:300],
                )
                return None

            # Ensure required keys exist
            for key in ("ports", "runnables", "irvs", "calparms", "dem_events"):
                if key not in skeleton:
                    skeleton[key] = []
            if "sub_functions" not in skeleton:
                skeleton["sub_functions"] = []
            if "data_types" not in skeleton:
                skeleton["data_types"] = []

            return skeleton

        except Exception as exc:
            logger.error("[Pipeline/Stage1] Exception: %s", exc, exc_info=True)
            return None

    # ─── Stage 3 ──────────────────────────────────────────────────────────

    async def _stage3_section7(
        self,
        skeleton: dict,
        runnable: dict,
        temperature: float,
    ) -> dict | None:
        rname = runnable.get("name", "")

        # Build port summary for context
        all_ports_summary = "\n".join(
            f"  {p['name']} ({p['direction']}) — {p.get('data_type','')} [{p.get('range','')} {p.get('unit','')}] — {p.get('description','')}"
            for p in skeleton.get("ports", [])
        ) or "  (none)"

        dem_events_summary = "\n".join(
            f"  {ev['event_id']} — {ev.get('description','')} — reaction: {ev.get('safe_state_reaction','')}"
            for ev in skeleton.get("dem_events", [])
        ) or "  (none)"

        # Prefer EPS reference few-shot over catalog fallback
        few_shot = (
            _REFERENCE.get("few_shot_prompts", {}).get("runnable_example")
            or _CATALOG.get("few_shot_runnable_pseudocode", {}).get("RE_ControlTorque_example")
            or "(not available)"
        )

        system_prompt = _SECTION7_SYSTEM.format(few_shot_example=few_shot)
        user_prompt = _SECTION7_USER_TMPL.format(
            runnable_name=rname,
            trigger=runnable.get("trigger", "Cyclic"),
            period=runnable.get("period", "—"),
            asil=runnable.get("asil", skeleton.get("asil", "QM")),
            description=runnable.get("description", ""),
            reads=", ".join(runnable.get("reads", [])) or "none",
            writes=", ".join(runnable.get("writes", [])) or "none",
            irvs_consumed=", ".join(runnable.get("irvs_consumed", [])) or "none",
            irvs_produced=", ".join(runnable.get("irvs_produced", [])) or "none",
            calparms_used=", ".join(runnable.get("calparms_used", [])) or "none",
            sub_functions=", ".join(runnable.get("sub_functions", [])) or "none",
            all_ports_summary=all_ports_summary,
            dem_events_summary=dem_events_summary,
        )

        try:
            response = await self._backend.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=2048,
                response_format="json",
            )
            s7 = _extract_json(response.content)
            if not s7:
                logger.warning(
                    "[Pipeline/Stage3] Failed to extract JSON for %s: %s…",
                    rname, response.content[:300],
                )
                return None

            # Ensure required keys
            for key in ("reads", "writes", "irvs_consumed", "irvs_produced", "calparms_used", "steps"):
                if key not in s7:
                    s7[key] = []
            if not s7.get("runnable_name"):
                s7["runnable_name"] = rname

            return s7

        except Exception as exc:
            logger.error("[Pipeline/Stage3] Exception for %s: %s", rname, exc, exc_info=True)
            return None
