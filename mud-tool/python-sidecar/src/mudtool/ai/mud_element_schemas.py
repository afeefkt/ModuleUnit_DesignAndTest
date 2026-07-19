"""JSON schemas for per-element MUD spec generation.

Each schema is passed as the ``format`` parameter to Ollama so that the
local model is forced to produce valid JSON.  These are used by the
two-stage pipeline (Stage 1 skeleton + Stage 3 section-7 expansion).
"""

from __future__ import annotations

# ── Stage-1 Skeleton schema ───────────────────────────────────────────────────
# The skeleton captures all element *names* and their key attributes.
# Section 7 pseudo-code is intentionally absent at this stage — it is
# generated later (Stage 3) once we have the full port/IRV/CalPrm name map.

SKELETON_SCHEMA: dict = {
    "type": "object",
    "required": ["swc_name", "asil", "description", "ports", "runnables", "irvs", "calparms", "dem_events"],
    "properties": {
        "swc_name": {"type": "string"},
        "asil": {"type": "string"},
        "description": {"type": "string"},
        "ports": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "direction", "interface", "data_element", "data_type", "range", "unit", "period", "description"],
                "properties": {
                    "name":         {"type": "string", "description": "AUTOSAR port name (PP_*/RP_* convention)"},
                    "direction":    {"type": "string", "enum": ["provided", "required", "calibration"]},
                    "interface":    {"type": "string", "description": "AUTOSAR interface name (IF_SR_*/IF_CS_*/IF_Prm_*)"},
                    "data_element": {"type": "string", "description": "Data element name (DE_*)"},
                    "data_type":    {"type": "string"},
                    "range":        {"type": "string"},
                    "unit":         {"type": "string"},
                    "period":       {"type": "string"},
                    "description":  {"type": "string"},
                    "provider_swc": {"type": "string", "description": "For required ports: which SWC provides this"},
                    "default_value":{"type": "string", "description": "For calibration ports: default value"},
                    "safe_state":   {"type": "string", "description": "Fail-safe output value for ASIL ports"}
                }
            }
        },
        "runnables": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "trigger", "period", "asil", "description", "reads", "writes"],
                "properties": {
                    "name":          {"type": "string", "description": "Runnable name (RE_* convention)"},
                    "trigger":       {"type": "string", "enum": ["Init", "Cyclic", "DataReceived", "DataSendCompleted", "ModeSwitched", "Error"]},
                    "period":        {"type": "string"},
                    "asil":          {"type": "string"},
                    "description":   {"type": "string"},
                    "reads":         {"type": "array", "items": {"type": "string"}, "description": "RP_ port names this runnable reads"},
                    "writes":        {"type": "array", "items": {"type": "string"}, "description": "PP_ port names this runnable writes"},
                    "irvs_consumed": {"type": "array", "items": {"type": "string"}},
                    "irvs_produced": {"type": "array", "items": {"type": "string"}},
                    "calparms_used": {"type": "array", "items": {"type": "string"}},
                    "sub_functions": {"type": "array", "items": {"type": "string"}, "description": "Internal C helper function names called by this runnable"},
                    "execution_order":{"type": "integer"}
                }
            }
        },
        "sub_functions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "called_by", "description"],
                "properties": {
                    "name":        {"type": "string"},
                    "called_by":   {"type": "string"},
                    "description": {"type": "string"}
                }
            }
        },
        "irvs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "data_type", "range", "producer_runnable", "consumer_runnable", "description"],
                "properties": {
                    "name":              {"type": "string"},
                    "data_type":         {"type": "string"},
                    "range":             {"type": "string"},
                    "unit":              {"type": "string"},
                    "producer_runnable": {"type": "string"},
                    "consumer_runnable": {"type": "string"},
                    "exclusive_area":    {"type": "string", "description": "ExclusiveArea name if shared across OS tasks"},
                    "description":       {"type": "string"}
                }
            }
        },
        "calparms": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "port_name", "data_type", "default_value", "range", "unit", "used_by", "description"],
                "properties": {
                    "name":          {"type": "string"},
                    "port_name":     {"type": "string", "description": "RP_CalPrm_* port name"},
                    "data_type":     {"type": "string"},
                    "default_value": {"type": "string"},
                    "range":         {"type": "string"},
                    "unit":          {"type": "string"},
                    "used_by":       {"type": "array", "items": {"type": "string"}},
                    "description":   {"type": "string"},
                    "memory_section":{"type": "string"}
                }
            }
        },
        "dem_events": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["event_id", "description", "trigger_condition", "safe_state_reaction"],
                "properties": {
                    "event_id":            {"type": "string", "description": "SWC_DEM_E_* format"},
                    "description":         {"type": "string"},
                    "asil":                {"type": "string"},
                    "trigger_condition":   {"type": "string"},
                    "safe_state_reaction": {"type": "string"},
                    "dem_priority":        {"type": "string"},
                    "related_runnable":    {"type": "string"}
                }
            }
        },
        "data_types": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "base_type", "range", "unit", "description"],
                "properties": {
                    "name":        {"type": "string"},
                    "base_type":   {"type": "string"},
                    "range":       {"type": "string"},
                    "unit":        {"type": "string"},
                    "description": {"type": "string"}
                }
            }
        }
    }
}

# ── Stage-3 Section-7 pseudo-code schema per runnable ────────────────────────
# One JSON object per runnable — the "steps" field contains the numbered
# pseudo-code lines that go into Section 7 of the final Markdown document.

SECTION7_RUNNABLE_SCHEMA: dict = {
    "type": "object",
    "required": ["runnable_name", "reads", "writes", "irvs_consumed", "irvs_produced", "calparms_used", "steps"],
    "properties": {
        "runnable_name":  {"type": "string"},
        "reads":          {"type": "array", "items": {"type": "string"}},
        "writes":         {"type": "array", "items": {"type": "string"}},
        "irvs_consumed":  {"type": "array", "items": {"type": "string"}},
        "irvs_produced":  {"type": "array", "items": {"type": "string"}},
        "calparms_used":  {"type": "array", "items": {"type": "string"}},
        "steps": {
            "type": "array",
            "description": "Ordered pseudo-code steps — each step has a label and code block",
            "items": {
                "type": "object",
                "required": ["step_num", "label", "code"],
                "properties": {
                    "step_num": {"type": "integer"},
                    "label":    {"type": "string", "description": "Short description e.g. 'Guard: mode check'"},
                    "code":     {"type": "string", "description": "Multi-line C-like pseudo-code with Rte_Read/Write/Irv/Prm calls"}
                }
            }
        },
        "sub_function_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "called_in_step": {"type": "integer"},
                    "description": {"type": "string"}
                }
            }
        }
    }
}
