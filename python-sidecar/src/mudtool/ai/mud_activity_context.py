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
                runnable_lines.append(
                    f"  Functional flow: {runnable.functional_description.strip()}"
                )

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
        runnable.functional_description = _normalize_ws(body)

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


def _extract_swc_name(markdown: str) -> str:
    m = re.search(r"^#\s*MUD Spec:\s*(.+)$", markdown, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r"\|\s*SWC Name\s*\|\s*([^|]+)\|", markdown, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extract_section(markdown: str, heading: str) -> str:
    base_heading = re.sub(r'^\d+\.\s*', '', heading).strip('sS')
    lines = markdown.splitlines()
    in_section = False
    section_level = 0
    content = []
    for line in lines:
        m = re.match(r'^(#+)\s+(.*)', line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            clean_title = re.sub(r'^\d+\.\s*', '', title).strip(': ').strip('sS')
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
