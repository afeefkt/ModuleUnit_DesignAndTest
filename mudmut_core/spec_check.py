"""Sanity check of a generated MUD spec before the slow stages run.

Small models sometimes write a spec whose Section 7 has no real logic (only callback stubs such
as ``l_Rte_Call(Rte_Cbk_X, 0)``) or that names a different SWC than the plan. Everything after
that (flow, C code, tests) would be built on nothing, so the chain stops early with a reason.
"""

from __future__ import annotations

import re
from typing import Any

_NAME_RE = re.compile(r"^#\s*MUD Spec:\s*([A-Za-z_]\w*)", re.M)
_TABLE_NAME_RE = re.compile(r"^\|\s*SWC Name\s*\|\s*([A-Za-z_]\w*)\s*\|", re.M)


def check_spec(spec_md: str, swc: str) -> dict[str, Any]:
    """Return ``{ok, name_in_spec, name_matches, runnables, usable, placeholder, empty, problems}``."""
    from mudtool.ai.mud_activity_context import build_mud_activity_context, runnable_flow_quality

    ctx = build_mud_activity_context(spec_md or "", swc)
    m = _NAME_RE.search(spec_md or "") or _TABLE_NAME_RE.search(spec_md or "")
    name_in_spec = m.group(1) if m else ""
    usable: list[str] = []
    placeholder: list[str] = []
    empty: list[str] = []
    for r in ctx.runnables:   # the same strict rule the AI activity step enforces
        {"logic": usable, "placeholder": placeholder, "empty": empty}[runnable_flow_quality(r)].append(r.name)
    problems: list[str] = []
    if not ctx.runnables:
        problems.append("Section 7 describes no runnables.")
    elif not usable:
        problems.append(
            f"Section 7 has no implementable logic: {len(placeholder)} runnable(s) contain only placeholder "
            f"calls (e.g. Rte_Cbk_* stubs) and {len(empty)} have no steps."
        )
    name_matches = not name_in_spec or name_in_spec == swc
    never_set: dict[str, list[str]] = {}
    undescribed: dict[str, list[str]] = {}
    for r in ctx.runnables:
        missing = read_but_never_set(r.functional_description)
        if missing:
            never_set[r.name] = missing
        helpers = undescribed_helpers(r.functional_description, {x.name for x in ctx.runnables})
        if helpers:
            undescribed[r.name] = helpers
    return {
        "ok": not problems,
        "name_in_spec": name_in_spec,
        "name_matches": name_matches,
        "runnables": len(ctx.runnables),
        "usable": usable,
        "placeholder": placeholder,
        "empty": empty,
        "never_set": never_set,
        "undescribed_helpers": undescribed,
        "problems": problems,
    }


def gap_count(result: dict[str, Any]) -> int:
    """Number of concrete design gaps a targeted spec repair can fix."""
    return (sum(len(v) for v in (result.get("never_set") or {}).values())
            + sum(len(v) for v in (result.get("undescribed_helpers") or {}).values())
            + len(result.get("placeholder") or []) + len(result.get("empty") or []))


_LOCAL_RE = re.compile(r"\bl_[A-Za-z0-9_]+\b")
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_KNOWN_CALL_PREFIXES = ("Rte_", "Dem_", "WdgM_", "SchM_", "Det_", "NvM_", "Com_", "Os_")
_C_WORDS = {"if", "while", "for", "switch", "return", "sizeof"}


def read_but_never_set(text: str) -> list[str]:
    """Local ``l_*`` variables a runnable's Section 7 reads but never assigns.

    ``Rte_Read(RP_X, &l_v)`` and ``l_v = …`` / ``l_v += …`` count as setting it. A read of a
    never-set local is a design gap (the C would use a zero/garbage value).
    """
    code = re.sub(r"//[^\n]*", "", text or "")
    out: list[str] = []
    for name in dict.fromkeys(_LOCAL_RE.findall(code)):
        n = re.escape(name)
        assigned = re.search(rf"\b{n}\s*(\[[^\]]*\])?\s*([-+*/|&^%]|<<|>>)?=(?!=)", code) or \
            re.search(rf"&\s*{n}\b|\b{n}\s*(\+\+|--)|(\+\+|--)\s*{n}\b", code)
        if not assigned:
            out.append(name)
    return out


def undescribed_helpers(text: str, runnables: set[str]) -> list[str]:
    """Sub-functions a runnable calls that are not AUTOSAR/BSW APIs, the C library or another runnable.

    Their logic is not written anywhere in Section 7, so they become empty functions.
    """
    from mudmut_core.compilable import STDLIB_FUNCS

    code = re.sub(r"//[^\n]*", "", text or "")
    out: list[str] = []
    for name in dict.fromkeys(_CALL_RE.findall(code)):
        if name in _C_WORDS or name in STDLIB_FUNCS or name in runnables or name.startswith(_KNOWN_CALL_PREFIXES):
            continue
        out.append(name)
    return out


def warnings_for(result: dict[str, Any], swc: str) -> list[str]:
    """Non-fatal findings worth showing in the run report."""
    out: list[str] = []
    if not result.get("name_matches"):
        out.append(f"The MUD spec is titled '{result['name_in_spec']}' but the plan's component is '{swc}'.")
    if result.get("usable") and (result.get("placeholder") or result.get("empty")):
        weak = result.get("placeholder", []) + result.get("empty", [])
        out.append(f"Spec Section 7 has no real logic for {len(weak)} runnable(s): {', '.join(weak[:8])}"
                   + (" …" if len(weak) > 8 else ""))
    for runnable, names in (result.get("never_set") or {}).items():
        out.append(f"Spec: {runnable} reads {', '.join(names)} but never sets it — the C will use 0.")
    for runnable, names in (result.get("undescribed_helpers") or {}).items():
        out.append(f"Spec: {runnable} calls {', '.join(n + '()' for n in names)} whose logic is not written "
                   "anywhere — it becomes an empty function.")
    return out
