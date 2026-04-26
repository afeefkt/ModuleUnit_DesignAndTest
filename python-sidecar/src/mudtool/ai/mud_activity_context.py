"""Helpers for building MUD-first activity-generation context."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RunnableContext:
    name: str
    trigger: str = ""
    period: str = ""
    asil: str = ""
    summary: str = ""
    functional_description: str = ""


@dataclass
class MudActivityContext:
    swc_name: str
    runnables: list[RunnableContext]
    rte_calls: list[str]
    helper_functions: list[str]
    raw_markdown: str

    @property
    def has_usable_flow_source(self) -> bool:
        # If we found ANY runnable name (even by raw-text scan), let activity
        # generation proceed. The activity generator + skill block can synthesise
        # a minimal flowchart from just the runnable name + RTE calls + helper
        # functions detected elsewhere in the markdown.
        return bool(self.runnables)

    @property
    def has_structured_flow_source(self) -> bool:
        return any(_parse_numbered_steps(r.functional_description) for r in self.runnables)

    def to_prompt_block(self) -> str:
        runnable_lines = []
        for runnable in self.runnables:
            meta = " | ".join(
                filter(
                    None,
                    [
                        f"trigger={runnable.trigger}" if runnable.trigger else "",
                        f"period={runnable.period}" if runnable.period else "",
                        f"asil={runnable.asil}" if runnable.asil else "",
                    ],
                )
            )
            if meta:
                runnable_lines.append(f"- {runnable.name} ({meta})")
            else:
                runnable_lines.append(f"- {runnable.name}")
            if runnable.summary:
                runnable_lines.append(f"  Summary: {runnable.summary}")
            if runnable.functional_description:
                # Preserve multi-line layout so the activity-diagram AI can
                # see each numbered step (Guard / Read / Validate / Compute /
                # Write / Watchdog) as a separate line and emit one node per
                # step.
                runnable_lines.append("  Functional flow:")
                for ln in runnable.functional_description.splitlines():
                    if ln.strip():
                        runnable_lines.append(f"    {ln}")

        rte_lines = "\n".join(f"- {call}" for call in self.rte_calls[:20]) or "- none detected"
        helper_lines = (
            "\n".join(f"- {name}" for name in self.helper_functions[:20])
            or "- none detected"
        )
        runnable_block = "\n".join(runnable_lines) or "- none detected"

        return (
            "AUTHORITATIVE MUD FLOW SOURCE\n"
            f"SWC: {self.swc_name or 'unknown'}\n\n"
            "RUNNABLES AND FLOW DETAILS:\n"
            f"{runnable_block}\n\n"
            "DETECTED RTE CALLS:\n"
            f"{rte_lines}\n\n"
            "DETECTED HELPER FUNCTIONS:\n"
            f"{helper_lines}\n\n"
            "RAW MUD SPEC EXCERPT:\n"
            f"{self.raw_markdown.strip()}"
        )


def build_mud_activity_context(markdown: str, module_context: str | None = None) -> MudActivityContext:
    swc_name = _extract_swc_name(markdown) or (module_context or "")
    # Try "3.1 Main Runnables" first (new split format), fall back to full "3. Runnables"
    section_3_text = _extract_section(markdown, "3.1 Main Runnables") or \
                     _extract_section(markdown, "3. Runnables")
    runnable_rows = _parse_markdown_table(section_3_text)
    runnable_map: dict[str, RunnableContext] = {}
    for row in runnable_rows:
        name = row[0].strip() if row else ""
        # Skip empty rows, separator rows, table header words, and sub-function entries
        # (sub-functions have parentheses like "ReadSensorInputs()" — they are C helpers,
        # not OS-scheduled runnables, so they should not appear in the runnable_map)
        if not name or name.startswith("-") or "(" in name or name in (
            "Runnable", "Function", "Helper", "Sub-Function"
        ):
            continue
        runnable_map[name] = RunnableContext(
            name=name,
            trigger=row[1].strip() if len(row) > 1 else "",
            period=row[2].strip() if len(row) > 2 else "",
            asil=row[3].strip() if len(row) > 3 else "",
            summary=row[4].strip() if len(row) > 4 else "",
        )

    for heading, body in _extract_subsections(_extract_section(markdown, "7. Functional Description")):
        name = heading.strip()
        if not name:
            continue
        runnable = runnable_map.setdefault(name, RunnableContext(name=name))
        # IMPORTANT: keep newlines intact — Section 7 pseudo-code is multi-line
        # numbered steps.  Collapsing whitespace via _normalize_ws() would turn
        # the entire pseudo-code into one giant unreadable string and the
        # activity-diagram AI would return nodes:[] → repair fallback produces
        # the placeholder Start → Action → End.
        runnable.functional_description = body.strip()

    # Last-resort: if structured parsing yielded nothing, extract RE_/Init_/Cyclic_ names
    # directly from the raw markdown text so activity diagrams can still be generated.
    if not runnable_map:
        for re_name in sorted(set(re.findall(r'\b(?:RE|Init|Cyclic|Task|Run|Periodic)_[A-Za-z][A-Za-z0-9_]*', markdown))):
            # Skip very short or obviously non-runnable matches
            if len(re_name) >= 4:
                runnable_map[re_name] = RunnableContext(name=re_name)

    rte_calls = sorted(set(re.findall(r"\bRte_(?:Read|Write|Call|Result)\w*(?:\([^)]*\))?", markdown)))
    helper_functions = sorted(_extract_helper_functions(markdown))

    return MudActivityContext(
        swc_name=swc_name,
        runnables=list(runnable_map.values()),
        rte_calls=rte_calls,
        helper_functions=helper_functions,
        raw_markdown=_trim_markdown(markdown),
    )


def synthesize_activity_diagrams_from_context(
    context: MudActivityContext,
    req_ids: list[str],
):
    """Build deterministic activity diagrams from Section 7 numbered steps.

    This is used as a fallback when the AI activity generator returns only a
    placeholder flow despite the MUD spec already containing structured runnable
    pseudo-code.
    """
    from mudtool.models.json_uml import (
        ActivityDiagram,
        ActivityEdge,
        ActivityNode,
        ActivityNodeType,
    )

    diagrams: list[ActivityDiagram] = []
    trace_reqs = list(req_ids or [])
    helper_names = set(context.helper_functions)

    for runnable in context.runnables:
        steps = _parse_numbered_steps(runnable.functional_description)
        if not steps:
            continue

        nodes: list[ActivityNode] = [
            ActivityNode(
                id="N_00",
                name="Start",
                node_type=ActivityNodeType.INITIAL,
                trace_reqs=trace_reqs[:1] if trace_reqs else [],
                description=f"Entry point for {runnable.name}",
                confidence=0.9,
            )
        ]
        edges: list[ActivityEdge] = []
        sub_diagrams: list[ActivityDiagram] = []
        prev_id = "N_00"
        sub_ids: set[str] = set()

        for idx, step in enumerate(steps, start=1):
            node_id = f"N_{idx:02d}"
            node_type = ActivityNodeType.ACTION
            callee = None
            description = _short_step_description(step)
            rte_meta = _extract_rte_metadata(step)
            if rte_meta:
                node_type = ActivityNodeType.CALL
            else:
                helper_name = _extract_helper_call(step, helper_names)
                if helper_name:
                    node_type = ActivityNodeType.FUNCTION_CALL
                    callee = helper_name
                elif "dem_reporterrorstatus" in step.lower() or "dem_seteventstatus" in step.lower():
                    node_type = ActivityNodeType.EXCEPTION

            nodes.append(
                ActivityNode(
                    id=node_id,
                    name=step,
                    node_type=node_type,
                    rte_call=rte_meta["rte_call"] if rte_meta else None,
                    port=rte_meta["port"] if rte_meta else None,
                    element=rte_meta["element"] if rte_meta else None,
                    callee=callee,
                    trace_reqs=trace_reqs,
                    description=description,
                    confidence=0.88,
                )
            )
            edges.append(ActivityEdge(id=f"E_{idx:02d}", source=prev_id, target=node_id))
            prev_id = node_id

            if callee and callee not in sub_ids:
                sub_ids.add(callee)
                sub_diagrams.append(
                    _make_helper_subdiagram(
                        swc_name=context.swc_name,
                        runnable_name=runnable.name,
                        callee=callee,
                        step_text=step,
                        req_ids=trace_reqs,
                    )
                )

        final_id = f"N_{len(steps) + 1:02d}"
        nodes.append(
            ActivityNode(
                id=final_id,
                name="End",
                node_type=ActivityNodeType.FINAL,
                trace_reqs=trace_reqs[:1] if trace_reqs else [],
                description=f"Exit point for {runnable.name}",
                confidence=0.9,
            )
        )
        edges.append(ActivityEdge(id=f"E_{len(steps) + 1:02d}", source=prev_id, target=final_id))

        diagrams.append(
            ActivityDiagram(
                name=f"{runnable.name} Code Flow",
                owner_swc=context.swc_name or None,
                owner_runnable=runnable.name,
                source_requirements=trace_reqs,
                nodes=nodes,
                edges=edges,
                sub_diagrams=sub_diagrams,
            )
        )

    return diagrams


def _extract_swc_name(markdown: str) -> str:
    m = re.search(r"^#\s*MUD Spec:\s*(.+)$", markdown, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r"\|\s*SWC Name\s*\|\s*([^|]+)\|", markdown, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extract_section(markdown: str, heading: str) -> str:
    base_heading = _normalize_heading_title(heading)
    lines = markdown.splitlines()
    in_section = False
    section_level = 0
    content = []
    for line in lines:
        m = re.match(r'^(#+)\s+(.*)', line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            clean_title = _normalize_heading_title(title)
            if in_section:
                if level <= section_level:
                    break
                else:
                    content.append(line)
            else:
                if clean_title.lower().startswith(base_heading.lower()):
                    in_section = True
                    section_level = level
        elif in_section:
            content.append(line)
    return "\n".join(content).strip()


def _extract_subsections(section_text: str) -> list[tuple[str, str]]:
    if not section_text:
        return []
    matches = list(
        re.finditer(r"^#{3,6}\s+(.+)$", section_text, flags=re.MULTILINE)
    )
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section_text)
        sections.append((match.group(1).strip(), section_text[start:end].strip()))
    return sections


def _parse_markdown_table(section_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if "|" not in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", " "} for cell in cells) or all(not cell for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if len(rows) > 1 else []


def _extract_helper_functions(markdown: str) -> set[str]:
    names = set()
    for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", markdown):
        if name in {"if", "for", "while", "switch", "return"}:
            continue
        if name.startswith(("Rte_", "Dem_", "RE_", "SWC_", "PP_", "RP_", "IF_")):
            continue
        if "_" not in name and not re.search(r"[A-Z]", name):
            continue
        names.add(name)
    return names


def _trim_markdown(markdown: str, limit: int = 4000) -> str:
    text = markdown.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "\n...[truncated]"


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_heading_title(title: str) -> str:
    normalized = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", title or "")
    return normalized.strip(": ").strip("sS")


def _parse_numbered_steps(text: str) -> list[str]:
    steps: list[str] = []
    current: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        numbered = re.match(r"^\d+\.\s*(.+)$", line)
        if numbered:
            if current:
                steps.append(_normalize_ws(" ".join(current)))
            current = [numbered.group(1).strip()]
        elif current:
            current.append(line)
    if current:
        steps.append(_normalize_ws(" ".join(current)))
    return steps


def _extract_rte_metadata(step: str) -> dict[str, str] | None:
    m = re.search(r"\b(Rte_(?:Read|Write|Call|Result)\w*)\s*\(\s*([A-Z]{2}_[A-Za-z0-9_]+)", step)
    if not m:
        return None
    rte_call = m.group(1)
    port = m.group(2)
    element = ""
    parts = port.split("_", 2)
    if len(parts) >= 3:
        element = parts[2]
    return {"rte_call": rte_call, "port": port, "element": element}


def _extract_helper_call(step: str, helper_names: set[str]) -> str | None:
    for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", step):
        if name.startswith(("Rte_", "Dem_")):
            continue
        if helper_names and name in helper_names:
            return name
        if "_" in name or re.search(r"[A-Z]", name):
            return name
    return None


def _short_step_description(step: str) -> str:
    trimmed = _normalize_ws(step)
    if len(trimmed) <= 72:
        return trimmed
    return trimmed[:69].rstrip() + "..."


def _make_helper_subdiagram(
    swc_name: str,
    runnable_name: str,
    callee: str,
    step_text: str,
    req_ids: list[str],
):
    from mudtool.models.json_uml import (
        ActivityDiagram,
        ActivityEdge,
        ActivityNode,
        ActivityNodeType,
    )

    return ActivityDiagram(
        name=f"{callee} Code Flow",
        function_name=callee,
        parent_diagram=f"{runnable_name} Code Flow",
        owner_swc=swc_name or None,
        source_requirements=list(req_ids),
        nodes=[
            ActivityNode(
                id="N_00",
                name="Start",
                node_type=ActivityNodeType.INITIAL,
                trace_reqs=req_ids[:1] if req_ids else [],
                description=f"Entry point for {callee}",
                confidence=0.85,
            ),
            ActivityNode(
                id="N_01",
                name=step_text,
                node_type=ActivityNodeType.ACTION,
                trace_reqs=list(req_ids),
                description=f"Helper logic for {callee}",
                confidence=0.8,
            ),
            ActivityNode(
                id="N_02",
                name="End",
                node_type=ActivityNodeType.FINAL,
                trace_reqs=req_ids[:1] if req_ids else [],
                description=f"Exit point for {callee}",
                confidence=0.85,
            ),
        ],
        edges=[
            ActivityEdge(id="E_01", source="N_00", target="N_01"),
            ActivityEdge(id="E_02", source="N_01", target="N_02"),
        ],
    )
