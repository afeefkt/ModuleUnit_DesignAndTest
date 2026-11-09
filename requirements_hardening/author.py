"""Author agent: turn an imported requirement into a hardened L2-oriented draft.

This MVP uses deterministic role logic plus a curated override file. The
architecture is deliberately agent-shaped: the Author only proposes fields, and
a separate Reviewer and deterministic exporter validate the result. An LLM
adapter can be added later without changing the contracts.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .parser import extract_interfaces, extract_numbers, extract_period_ms, extract_ports, extract_runnables, extract_standards
from .schema import clean_text, ensure_sentence, sort_key


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_overrides(set_name: str = "aeb", path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path or Path(__file__).parent / "data" / f"{set_name}_overrides.json")
    data = _load_json(path)
    return data.get("requirements", data)


def load_new_requirements(set_name: str = "aeb", path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(path or Path(__file__).parent / "data" / f"{set_name}_new_requirements.json")
    data = _load_json(path)
    return data.get("requirements", [])


def load_splits(set_name: str = "aeb", path: str | Path | None = None) -> dict[str, list[str]]:
    path = Path(path or Path(__file__).parent / "data" / f"{set_name}_splits.json")
    data = _load_json(path)
    return data.get("splits", {})


def load_set_config(set_name: str = "aeb") -> dict[str, Any]:
    path = Path(__file__).parent / "data" / f"{set_name}_config.json"
    return _load_json(path)


def _decimals(raw: str) -> int:
    if "." not in raw:
        return 0
    return len(raw.split(".", 1)[1])


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _boundary_values(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in extract_numbers(text):
        raw = str(item["value"])
        decimals = _decimals(raw)
        if decimals == 0:
            eps = 1.0
        else:
            eps = 10 ** (-max(decimals, 2))
        values = [round(item["value"] - eps, 6), item["value"], round(item["value"] + eps, 6)]
        out.append({
            "parameter": item["raw"],
            "unit": item["unit"],
            "values": values,
        })
    return out


def _tolerance(text: str) -> str:
    m = re.search(r"resolution\s+([0-9.]+)\s*([A-Za-z%/°]+)", text or "", flags=re.IGNORECASE)
    if m:
        return f"±{m.group(1)} {m.group(2)} (one resolution step)"
    nums = extract_numbers(text)
    if nums:
        n = nums[0]
        decimals = _decimals(str(n["value"]))
        eps = 10 ** (-max(decimals, 2)) if decimals else 1.0
        return f"±{eps} {n['unit']} at the specified threshold; otherwise ±1 LSB of the referenced interface."
    return "±1 LSB of the referenced interface; otherwise exact match."


def _parse_range(raw: str) -> tuple[float | None, float | None, str]:
    raw = clean_text(raw)
    m = re.match(r"±\s*([0-9.]+)\s*([A-Za-z%/°]+)", raw)
    if m:
        value = float(m.group(1))
        return -value, value, m.group(2)
    m = re.match(r"(-?[0-9.]+)\s*(?:–|-|to|\.\.)\s*([+-]?[0-9.]+)\s*([A-Za-z%/°]+)", raw)
    if m:
        return float(m.group(1)), float(m.group(2)), m.group(3)
    m = re.match(r"up to\s+([0-9.]+)\s*([A-Za-z]+)", raw)
    if m:
        return 0.0, float(m.group(1)), m.group(2)
    return None, None, ""


def _parse_port_details(text: str, port: str) -> dict[str, Any]:
    idx = text.find(port)
    segment = text[idx: idx + 240] if idx >= 0 else text
    paren = re.search(rf"{re.escape(port)}\s*\(([^)]*)\)", text)
    if paren:
        segment = paren.group(1)
    rng = re.search(r"(?:range\s+)?(±\s*[0-9.]+\s*[A-Za-z%/°]+|up to\s+[0-9.]+\s*[A-Za-z]+|-?[0-9.]+\s*(?:–|-|to|\.\.)\s*[+-]?[0-9.]+\s*[A-Za-z%/°]+)", segment, flags=re.IGNORECASE)
    resolution = re.search(r"resolution\s+([0-9.]+\s*[A-Za-z%/°]+)", segment, flags=re.IGNORECASE)
    dtype = re.search(r"\b(float32|uint16|sint16|uint8|int8|boolean|struct|enum)\b", segment, flags=re.IGNORECASE)
    rate = re.search(r"(\d+(?:\.\d+)?)\s*(ms|s)\b", segment, flags=re.IGNORECASE)
    min_v, max_v, unit = _parse_range(rng.group(1)) if rng else (None, None, "")
    return {
        "port": port,
        "direction": "provided" if port.startswith("PP_") else "required",
        "interface": "",
        "data_type": dtype.group(1) if dtype else "",
        "unit": unit,
        "min": min_v,
        "max": max_v,
        "resolution": clean_text(resolution.group(1)) if resolution else "",
        "rate": f"{rate.group(1)} {rate.group(2)}" if rate else "",
        "raw": clean_text(segment)[:240],
    }


def _interfaces(req: dict[str, Any]) -> list[dict[str, Any]]:
    text = req.get("statement", "")
    ports = extract_ports(text)
    ifaces = extract_interfaces(text)
    global_rng = re.search(r"range\s+([^,.;]+)", text, flags=re.IGNORECASE)
    global_res = re.search(r"resolution\s+([^,.;]+)", text, flags=re.IGNORECASE)
    global_type = re.search(r"\b(float32|uint16|sint16|uint8|int8|boolean|struct|enum)\b", text, flags=re.IGNORECASE)
    global_rate = re.search(r"(\d+(?:\.\d+)?)\s*(ms|s)\s*(?:cycle|update|period)?", text, flags=re.IGNORECASE)
    out: list[dict[str, Any]] = []
    for port in ports:
        item = _parse_port_details(text, port)
        item["interface"] = ifaces[0] if ifaces else ""
        if item["min"] is None and global_rng:
            item["min"], item["max"], item["unit"] = _parse_range(global_rng.group(1))
        if (not item["resolution"] or item["resolution"] == "0") and global_res:
            item["resolution"] = clean_text(global_res.group(1))
        if not item["data_type"] and global_type:
            item["data_type"] = global_type.group(1)
        if not item["rate"] and global_rate:
            item["rate"] = f"{global_rate.group(1)} {global_rate.group(2)}"
        out.append(item)
    if not out and req.get("type") == "interface":
        item = {
            "port": "",
            "direction": "",
            "interface": ifaces[0] if ifaces else "",
            "data_type": global_type.group(1) if global_type else "",
            "unit": "",
            "min": None,
            "max": None,
            "resolution": clean_text(global_res.group(1)) if global_res else "",
            "rate": "",
            "raw": clean_text(text),
        }
        if global_rng:
            item["min"], item["max"], item["unit"] = _parse_range(global_rng.group(1))
        out.append(item)
    return out


def _timing(req: dict[str, Any]) -> dict[str, Any]:
    text = req.get("statement", "")
    period = extract_period_ms(text)
    runnables = extract_runnables(text)
    trigger = "cyclic"
    if re.search(r"event|on\s+data|on\s+startup|on\s+transition|initiali[sz]", text, flags=re.IGNORECASE):
        trigger = "event"
    if req.get("type") == "timing" and period is None and len(runnables) > 1 and trigger == "cyclic":
        trigger = "multi-runnable budget"
    wcet = None
    m = re.search(r"within\s+(\d+(?:\.\d+)?)\s*ms", text, flags=re.IGNORECASE)
    if m:
        wcet = float(m.group(1))
    return {
        "trigger": trigger,
        "period_ms": period,
        "deadline_ms": period if period is not None else wcet,
        "wcet_ms": wcet,
        "jitter_ms": None,
    }


def _is_fault_condition(text: str) -> bool:
    return bool(re.search(
        r"\b(fault|failure|timeout|mismatch|deviation|watchdog|unavailable|invalid|plausibility|loss|"
        r"overcurrent|overtemperature|overvoltage|undervoltage|exceed|stuck|weld)\b",
        text, flags=re.IGNORECASE,
    ))


def _safe_state(req: dict[str, Any]) -> tuple[str, str]:
    text = req.get("statement", "").lower()
    if not _is_fault_condition(req.get("statement", "")):
        return ("Not applicable; this is an action requirement, not a fault reaction.", "Apply the specified action within the stated timing.")
    if "opencontactors" in text or ("contactor" in text and "open" in text):
        return ("Contactors open, power limits zeroed, DTC stored.", "Open contactors; zero power limit; report DTC.")
    if "failsafe" in text or "fail-safe" in text or "fail_safe" in text:
        return ("FAILSAFE mode with controlled braking as specified.", "Enter FAILSAFE mode and command the specified controlled braking.")
    if "degraded" in text:
        return ("DEGRADED mode with the specified reduced function.", "Enter DEGRADED mode and limit the function as specified.")
    if "warning" in text:
        return ("Warning active; automatic braking follows the specified risk level.", "Raise the specified warning and maintain/withhold braking as specified.")
    return ("Safe state defined by the fault reaction; confirm in safety analysis.", "Apply the specified fault reaction.")


def _rationale(req: dict[str, Any]) -> str:
    existing = clean_text(req.get("rationale", ""))
    if existing:
        return existing
    notes = clean_text(req.get("notes", ""))
    parent = ", ".join(req.get("parent_ids", [])) or "the AEB system context"
    base = f"Derived from {parent}."
    if notes:
        return f"{base} Source notes: {notes}. Rationale to be confirmed by the requirement owner."
    return f"{base} Rationale to be confirmed by the requirement owner."


def _acceptance(req: dict[str, Any]) -> dict[str, Any]:
    text = req.get("statement", "")
    rid = req.get("id", "")
    title = req.get("title", "")
    rtype = req.get("type", "functional")
    numbers = extract_numbers(text)
    ports = extract_ports(text)
    ifaces = extract_interfaces(text)
    period = extract_period_ms(text)
    boundaries = _boundary_values(text)
    tol = _tolerance(text)

    if rtype == "interface":
        given = f"The {req.get('allocated_to') or 'AEB'} component is running and the referenced producer/consumer ports are connected."
        when = f"{title} is exercised at its defined update rate."
        then = f"{text} The observed data type, unit, range, resolution and update rate match the interface definition."
    elif rtype == "timing":
        given = "The runnable is enabled and the scheduler is running."
        when = f"The {_num(period) + ' ms' if period is not None else 'defined'} trigger occurs."
        then = f"{text} The runnable completes within its deadline/WCET budget and publishes updated outputs."
    elif rtype == "safety" and _is_fault_condition(text):
        given = "The AEB feature is in a valid operating mode and the referenced inputs are available."
        when = f"The fault/condition described by '{title}' occurs and persists for the specified debounce."
        then = f"{text} The specified safe reaction is completed within the FTTI."
    elif rtype == "safety":
        given = "The AEB feature is in ACTIVE mode and the referenced inputs are valid."
        when = f"The action condition described by '{title}' occurs."
        then = f"{text}"
    elif rtype == "constraint":
        given = "The implementation and configuration are under static review/analysis."
        when = "The constraint is checked."
        then = f"{text} The constraint is satisfied with no exceptions."
    else:
        given = "The AEB feature is in ACTIVE mode and the referenced inputs are valid."
        when = f"The event/condition described by '{title}' occurs."
        then = f"{text}"

    inputs = [n["raw"] for n in numbers]
    if ports:
        inputs.append("Ports: " + ", ".join(ports))
    if ifaces:
        inputs.append("Interfaces: " + ", ".join(ifaces))
    return {
        "given": given,
        "when": when,
        "then": then,
        "inputs": inputs,
        "expected_outputs": [ensure_sentence(text)] if text else [],
        "tolerance": tol,
        "boundary_values": boundaries,
    }


def _verification_method(req: dict[str, Any]) -> str:
    rtype = req.get("type")
    if rtype in {"functional", "safety"}:
        return "test"
    if rtype == "interface":
        return "review"
    if rtype == "timing":
        return "analysis"
    if rtype == "constraint":
        return "review"
    return "review"


def _open_issues(req: dict[str, Any], ac: dict[str, Any], interfaces: list[dict[str, Any]], timing: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    text = req.get("statement", "").lower()
    if req.get("asil", "QM") != "QM":
        issues.append("Placeholder safety goal/FSR/TSR confirmation required; the ASIL value and goal are sample assumptions, not HARA results.")
    if req.get("type") == "safety" and _is_fault_condition(req.get("statement", "")) and req.get("ftti_ms") is None:
        issues.append("FTTI is not specified in the source requirement; confirm with the safety analysis.")
    if req.get("type") == "interface":
        incomplete = [
            i for i in interfaces
            if not i.get("data_type") or i.get("min") is None or i.get("max") is None or not i.get("unit")
        ]
        if incomplete:
            issues.append("Interface data is incomplete (type/unit/min/max/resolution); confirm against the data dictionary.")
    if req.get("type") == "timing" and timing.get("period_ms") is None and timing.get("trigger") == "cyclic":
        issues.append("Cycle period is not specified; confirm the scheduling contract.")
    if any(p in text for p in ["one control cycle", "full charge cycle", "appropriate", "sufficient", "fast", "robust"]):
        issues.append("Ambiguous phrase remains; confirm the measurable condition with the requirement owner.")
    if re.search(r"\b(should|could)\b", text) and req.get("type") == "safety":
        issues.append("Safety requirement uses a non-mandatory priority; confirm whether it is safety-critical.")
    if re.search(r"\bshall\b", req.get("statement", ""), flags=re.IGNORECASE) and len(re.findall(r"\bshall\b", req.get("statement", ""), flags=re.IGNORECASE)) > 1:
        issues.append("Compound statement (more than one 'shall'); split candidate for the next revision.")
    return issues


def _apply_known_conflict_issues(req: dict[str, Any]) -> list[str]:
    rid = req.get("id")
    mapping = {
        "REQ-AEB-002": "Conflict with REQ-AEB-209: pedestrian FCW remains active below 10 km/h. The automatic braking exception is clarified in the statement; confirm with the feature owner.",
        "REQ-AEB-209": "Conflict with REQ-AEB-002: automatic braking is deactivated below 10 km/h but pedestrian FCW remains active. Confirm the exception and the warning/braking split.",
        "REQ-AEB-308": "Behaviour below 10 km/h is undefined in the source. Proposed: command 0 m/s2 and keep FCW active; confirm with the safety/feature owner.",
        "REQ-AEB-005": "The source says 'one control cycle'; the controller cycle is 10 ms (REQ-AEB-301). Confirmed in the statement, but confirm for every mode.",
        "REQ-AEB-303": "FULL demand 9.0 m/s2 exceeds the UNECE R152 minimum 5.0 m/s2. Rationale: performance target; confirm calibration and homologation intent.",
        "REQ-AEB-310": "Source priority is 'should' for a false-braking mitigation. Confirm whether it is safety-relevant and whether it must be 'must'.",
    }
    out = []
    if rid in mapping:
        out.append(mapping[rid])
    return out


def _safety_goal_for(req: dict[str, Any]) -> str:
    module = str(req.get("allocated_to", "")).lower()
    if "hmi" in module:
        return "TBD-SG-AEB-HMI"
    if "safetymonitor" in module:
        return "TBD-SG-AEB-SAFETY"
    if "sensorfusion" in module or "riskassessor" in module:
        return "TBD-SG-AEB-PERCEPTION"
    if "vehiclestate" in module:
        return "TBD-SG-AEB-EGO"
    if "brakeactuator" in module or "controller" in module:
        return "TBD-SG-AEB-BRAKE"
    if "mtrmon" in module:
        return "TBD-SG-MC-MONITOR"
    if "currctrl" in module:
        return "TBD-SG-MC-CURRENT"
    if "spdctrl" in module:
        return "TBD-SG-MC-SPEED"
    if "battery" in module:
        return "TBD-SG-BMS"
    if "powersteering" in module or "eps" in module:
        return "TBD-SG-EPS"
    src = str((req.get("provenance") or {}).get("source_file", "")).lower()
    if "aeb" in src:
        return "TBD-SG-AEB-SYSTEM"
    if "bms" in src:
        return "TBD-SG-BMS-SYSTEM"
    if "eps" in src:
        return "TBD-SG-EPS-SYSTEM"
    if "motcontrol" in src or "foc" in src:
        return "TBD-SG-MC-SYSTEM"
    return "TBD-SG-SYSTEM"


def harden(req: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    out = dict(req)
    override = overrides.get(str(req.get("id", "")), {})

    # Apply curated fields; preserve original when no override.
    for key, value in override.items():
        if key in {"statement", "title", "rationale", "verification_method", "priority", "status",
                   "safety_goal_id", "ftti_ms", "safe_state", "fault_reaction", "implementation_constraint",
                   "constraint_rationale", "design_notes", "type", "asil", "level"}:
            out[key] = value

    out["version"] = "0.1.0"
    out["status"] = override.get("status", "review")
    out["statement"] = ensure_sentence(out.get("statement", ""))
    out["rationale"] = override.get("rationale") or _rationale(out)
    out["verification_method"] = override.get("verification_method") or _verification_method(out)
    out["acceptance_criteria"] = override.get("acceptance_criteria") or _acceptance(out)
    out["interfaces"] = override.get("interfaces", _interfaces(out))
    out["timing"] = override.get("timing", _timing(out))
    if out.get("type") == "safety":
        safe_state, fault_reaction = _safe_state(out)
        out["safe_state"] = override.get("safe_state", safe_state)
        out["fault_reaction"] = override.get("fault_reaction", fault_reaction)
    elif out.get("type") == "constraint" and not out.get("constraint_rationale"):
        out["constraint_rationale"] = "Constraint retained because it bounds the implementation; verify by review/static analysis."
    if out.get("asil", "QM") != "QM":
        out["safety_goal_id"] = override.get("safety_goal_id", _safety_goal_for(out))
    out["links"] = dict(out.get("links") or {})
    out["links"]["design"] = sorted(set(out.get("links", {}).get("design", []) + extract_runnables(out.get("statement", "")) + ([out.get("allocated_to")] if out.get("allocated_to") else [])))
    out["links"]["test"] = [f"TD-{out['id']}"]
    out["links"]["standards"] = sorted(set(out.get("links", {}).get("standards", []) + extract_standards(out.get("statement", "") + " " + out.get("notes", ""))))
    out["open_issues"] = list(dict.fromkeys(
        (out.get("open_issues") or [])
        + _open_issues(out, out["acceptance_criteria"], out["interfaces"], out["timing"])
        + _apply_known_conflict_issues(out)
        + override.get("open_issues", [])
    ))
    out["change_history"] = (out.get("change_history") or []) + [{
        "version": "0.1.0",
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "change": "Hardened draft generated by requirements_hardening",
        "source": "Author agent (deterministic MVP)",
        "review": "pending",
    }]
    return out


def _split_sentences(text: str) -> list[str]:
    protected = re.sub(r"(?i)\b(e\.g|i\.e|etc|vs|no)\.", r"\1<DOT>", text or "")
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]


def _split_clause(sentence: str) -> list[str]:
    for pattern in [
        r";\s*",
        r",?\s+and\s+(?=shall\b)",
        r",?\s+and\s+(?=(?:the|a|an|it|they)\s+[^.]*\bshall\b)",
        r",?\s+and\s+(?=[A-Z][A-Za-z0-9_]*\s+shall\b)",
        r"\s+but\s+(?=shall\b|[A-Z][A-Za-z0-9_]*\s+shall\b)",
    ]:
        candidates = [c.strip() for c in re.split(pattern, sentence, flags=re.IGNORECASE) if c.strip()]
        if len(candidates) > 1 and all(re.search(r"\bshall\b", c, re.IGNORECASE) for c in candidates):
            return candidates
    return [sentence.strip()]


def auto_split_statement(text: str) -> list[str]:
    """Best-effort atomic split for sets without a curated split map."""
    text = ensure_sentence(text)
    segments: list[str] = []
    for sentence in _split_sentences(text):
        segments.extend(_split_clause(sentence))

    merged: list[str] = []
    for segment in segments:
        if not re.search(r"\bshall\b", segment, re.IGNORECASE) and merged:
            merged[-1] = merged[-1].rstrip() + " " + segment.strip()
        else:
            merged.append(segment.strip())

    if len(merged) < 2:
        return [text]

    first = merged[0]
    subject_match = re.search(r"^(.*?)\s+shall\b", first, re.IGNORECASE)
    subject = subject_match.group(1).strip() if subject_match else ""
    safe_subject = bool(subject) and not re.match(r"(?i)^(during|in|when|if|while|after|before)\b", subject)

    cleaned: list[str] = []
    for idx, segment in enumerate(merged):
        if idx > 0 and safe_subject:
            if re.match(r"^(It|They)\s+shall\b", segment, re.IGNORECASE):
                segment = re.sub(r"^(It|They)\s+shall\b", subject + " shall", segment, flags=re.IGNORECASE)
            elif re.match(r"^shall\b", segment, re.IGNORECASE):
                segment = subject + " " + segment
        segment = ensure_sentence(segment)
        if segment and segment[0].islower():
            segment = segment[0].upper() + segment[1:]
        cleaned.append(segment)

    if len(cleaned) < 2 or any(len(x) < 15 or not re.search(r"\bshall\b", x, re.IGNORECASE) for x in cleaned):
        return [text]
    return cleaned


def _make_split_child(parent: dict[str, Any], statement: str, part_no: int, child_id: str) -> dict[str, Any]:
    child = dict(parent)
    child["id"] = child_id
    child["title"] = f"{parent.get('title', '')} — Part {part_no}"
    child["statement"] = statement
    child["status"] = "review"
    child["version"] = "0.1.0"
    child["parent_ids"] = list(parent.get("parent_ids", []))
    child["child_ids"] = []
    child["split_from"] = parent.get("id", "")
    child["split_part"] = part_no
    child["links"] = {
        "design": list((parent.get("links") or {}).get("design", [])),
        "test": [],
        "code": [],
        "standards": list((parent.get("links") or {}).get("standards", [])),
    }
    child["provenance"] = dict(parent.get("provenance") or {})
    child["provenance"]["original_id"] = parent.get("id", "")
    child["provenance"]["generated_by"] = "requirements_hardening.split"
    child["original"] = {}
    child["notes"] = f"Split from {parent.get('id', '')}, part {part_no}."
    child["open_issues"] = [f"Split from {parent.get('id', '')}; confirm atomicity and completeness with the requirement owner."]
    child["change_history"] = []
    child["acceptance_criteria"] = {}
    child["interfaces"] = []
    child["timing"] = {}
    child["safe_state"] = ""
    child["fault_reaction"] = ""
    child["rationale"] = (parent.get("rationale", "") + f" Split from {parent.get('id', '')}.").strip()
    return harden(child, {})


def harden_all(requirements: list[dict[str, Any]], overrides: dict[str, Any] | None = None, set_name: str = "aeb") -> list[dict[str, Any]]:
    overrides = overrides if overrides is not None else load_overrides(set_name)
    splits = load_splits(set_name)
    config = load_set_config(set_name)
    root_parent = str(config.get("root_parent", "")).strip()
    child_prefix = str(config.get("child_prefix", "")).strip() or f"REQ-{set_name.upper()}"
    split_ids = set(splits)

    local_overrides: dict[str, Any] = {}
    for key, value in overrides.items():
        if key in split_ids:
            value = {k: v for k, v in value.items() if k != "statement"}
        local_overrides[key] = value

    bases: list[dict[str, Any]] = [dict(req) for req in requirements]
    bases.extend(_new_requirement_bases(set_name))

    if root_parent:
        for base in bases:
            if base.get("id") == root_parent:
                continue
            if base.get("level") in {"software", "unit"} and not base.get("parent_ids"):
                base["parent_ids"] = [root_parent]

    split_parts: dict[str, list[str]] = {}
    for base in bases:
        rid = str(base.get("id", ""))
        # A curated statement override is applied before the split decision so
        # that an intentionally-simplified statement is not re-split from the
        # original compound text.
        override_statement = local_overrides.get(rid, {}).get("statement")
        if override_statement:
            base["statement"] = override_statement
        if rid in splits:
            parts = splits[rid]
        else:
            parts = auto_split_statement(base.get("statement", ""))
        if len(parts) > 1:
            base["statement"] = parts[0]
            base["notes"] = (base.get("notes", "") + f"; split into {len(parts)} atomic parts").strip("; ")
            split_parts[rid] = parts[1:]

    hardened = [harden(base, local_overrides) for base in bases]
    by_id = {r["id"]: r for r in hardened}
    next_id = 1001
    for parent_id, parts in split_parts.items():
        parent = by_id.get(parent_id)
        if not parent:
            continue
        children: list[str] = []
        for idx, statement in enumerate(parts, start=2):
            child_id = f"{child_prefix}-{next_id}"
            next_id += 1
            child = _make_split_child(parent, statement, idx, child_id)
            children.append(child_id)
            hardened.append(child)
        parent["child_ids"] = sorted(set(parent.get("child_ids", []) + children))
        parent["split_into"] = children
        parent["open_issues"] = list(dict.fromkeys(
            parent.get("open_issues", [])
            + [f"Split into {', '.join(children)}; the original ID retains part 1."]
        ))
        parent["change_history"] = parent.get("change_history", []) + [{
            "version": "0.1.0",
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "change": f"Split into {len(children)} atomic requirements",
            "source": "Author agent (split)",
            "review": "pending",
        }]
    return sorted(hardened, key=sort_key)


def _new_requirement_bases(set_name: str = "aeb") -> list[dict[str, Any]]:
    new = load_new_requirements(set_name)
    out = []
    for item in new:
        base = {
            "id": item["id"],
            "title": item["title"],
            "statement": item["statement"],
            "type": item.get("type", "functional"),
            "level": item.get("level", "software"),
            "allocated_to": item.get("allocated_to", "System"),
            "asil": item.get("asil", "QM"),
            "priority": item.get("priority", "must"),
            "status": "review",
            "version": "0.1.0",
            "rationale": item.get("rationale", ""),
            "source": item.get("source", "Gap analysis"),
            "parent_ids": item.get("parent_ids", []),
            "links": {"design": item.get("links", {}).get("design", []), "test": [], "code": [], "standards": item.get("standards", [])},
            "open_issues": item.get("open_issues", ["Proposed by gap analysis; human approval required."]),
            "provenance": {
                "source_file": "gap_analysis",
                "source_row": 0,
                "original_id": item["id"],
                "input_hash": "",
                "generated_by": "requirements_hardening.author.gap_hunter",
            },
            "original": {},
            "notes": item.get("notes", ""),
            "design_notes": "",
            "implementation_constraint": item.get("implementation_constraint", False),
            "constraint_rationale": item.get("constraint_rationale", ""),
            "change_history": [],
        }
        out.append(base)
    return out
