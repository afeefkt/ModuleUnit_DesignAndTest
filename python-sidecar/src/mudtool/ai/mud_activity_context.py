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
class NumberedStep:
    text: str
    depth: int = 1
    kind: str = "action"


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
        return any(_parse_numbered_step_entries(r.functional_description) for r in self.runnables)

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

    rte_calls = sorted(
        set(
            re.findall(
                r"\bRte_(?:IRead|IWrite|Read|Write|Call|Result|Receive|Send|Switch)\w*(?:\([^)]*\))?",
                markdown,
            )
        )
    )
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
        steps = _parse_numbered_step_entries(runnable.functional_description)
        if not steps:
            continue
        helper_call_counts = _count_helper_calls(steps, helper_names)

        builder = _ActivityGraphBuilder(
            swc_name=context.swc_name,
            runnable_name=runnable.name,
            req_ids=trace_reqs,
            helper_names=helper_names,
            helper_call_counts=helper_call_counts,
        )
        start_id = builder.add_node(
            name="Start",
            node_type=ActivityNodeType.INITIAL,
            trace_reqs=trace_reqs[:1] if trace_reqs else [],
            description=f"Entry point for {runnable.name}",
            confidence=0.9,
            node_id="N_00",
        )
        _, exits = builder.emit_block(
            steps,
            0,
            min_depth=min(step.depth for step in steps),
            pending=[(start_id, None)],
            stop_kinds=set(),
        )

        final_id = builder.add_node(
            name="End",
            node_type=ActivityNodeType.FINAL,
            trace_reqs=trace_reqs[:1] if trace_reqs else [],
            description=f"Exit point for {runnable.name}",
            confidence=0.9,
        )
        builder.connect_pending(exits + builder.terminal_exits, final_id)

        diagrams.append(
            ActivityDiagram(
                name=f"{runnable.name} Code Flow",
                owner_swc=context.swc_name or None,
                owner_runnable=runnable.name,
                source_requirements=trace_reqs,
                nodes=builder.nodes,
                edges=builder.edges,
                sub_diagrams=builder.sub_diagrams,
            )
        )

    return diagrams


class _ActivityGraphBuilder:
    def __init__(
        self,
        swc_name: str,
        runnable_name: str,
        req_ids: list[str],
        helper_names: set[str],
        helper_call_counts: dict[str, int],
    ) -> None:
        from mudtool.models.json_uml import ActivityEdge, ActivityNode, ActivityNodeType

        self.ActivityNode = ActivityNode
        self.ActivityEdge = ActivityEdge
        self.ActivityNodeType = ActivityNodeType
        self.swc_name = swc_name
        self.runnable_name = runnable_name
        self.req_ids = list(req_ids)
        self.helper_names = set(helper_names)
        self.helper_call_counts = dict(helper_call_counts)
        self.nodes: list[ActivityNode] = []
        self.edges: list[ActivityEdge] = []
        self.sub_diagrams = []
        self._sub_ids: set[str] = set()
        self._node_counter = 1
        self._edge_counter = 1
        self.terminal_exits: list[tuple[str, str | None]] = []

    def add_node(
        self,
        name: str,
        node_type,
        *,
        node_id: str | None = None,
        trace_reqs: list[str] | None = None,
        description: str | None = None,
        confidence: float = 0.88,
        rte_call: str | None = None,
        port: str | None = None,
        element: str | None = None,
        callee: str | None = None,
    ) -> str:
        node_id = node_id or f"N_{self._node_counter:02d}"
        if node_id != "N_00":
            self._node_counter += 1
        self.nodes.append(
            self.ActivityNode(
                id=node_id,
                name=name,
                node_type=node_type,
                rte_call=rte_call,
                port=port,
                element=element,
                callee=callee,
                trace_reqs=list(trace_reqs if trace_reqs is not None else self.req_ids),
                description=description,
                confidence=confidence,
            )
        )
        return node_id

    def add_edge(
        self,
        source: str,
        target: str,
        *,
        guard: str | None = None,
        label: str | None = None,
    ) -> None:
        self.edges.append(
            self.ActivityEdge(
                id=f"E_{self._edge_counter:02d}",
                source=source,
                target=target,
                guard=guard,
                label=label,
            )
        )
        self._edge_counter += 1

    def connect_pending(self, pending: list[tuple[str, str | None]], target: str) -> None:
        for source, guard in pending:
            self.add_edge(source, target, guard=guard)

    def emit_block(
        self,
        steps: list[NumberedStep],
        index: int,
        *,
        min_depth: int,
        pending: list[tuple[str, str | None]],
        stop_kinds: set[str],
    ) -> tuple[int, list[tuple[str, str | None]]]:
        exits = list(pending)
        while index < len(steps):
            step = steps[index]
            if step.depth < min_depth:
                break
            if step.depth > min_depth:
                index, exits = self.emit_block(
                    steps,
                    index,
                    min_depth=step.depth,
                    pending=exits,
                    stop_kinds=set(),
                )
                continue
            if step.kind in stop_kinds:
                break
            index, exits = self.emit_statement(steps, index, exits, step.depth)
        return index, exits

    def emit_statement(
        self,
        steps: list[NumberedStep],
        index: int,
        pending: list[tuple[str, str | None]],
        depth: int,
    ) -> tuple[int, list[tuple[str, str | None]]]:
        kind = steps[index].kind
        if kind == "if":
            return self.emit_if(steps, index, pending, depth)
        if kind in {"while", "for", "until"}:
            return self.emit_loop(steps, index, pending, depth)
        if kind == "switch":
            return self.emit_switch(steps, index, pending, depth)
        if kind == "return":
            self.emit_return_step(steps[index].text, pending)
            return index + 1, []
        node_pending = self.emit_action_step(steps[index].text, pending)
        return index + 1, [node_pending]

    def emit_action_step(
        self,
        step_text: str,
        pending: list[tuple[str, str | None]],
    ) -> tuple[str, str | None]:
        node_type = self.ActivityNodeType.ACTION
        callee = None
        description = _short_step_description(step_text)
        display_name = _compact_step_label(step_text)
        rte_meta = _extract_rte_metadata(step_text)
        if rte_meta:
            node_type = self.ActivityNodeType.CALL
            display_name = _compact_step_label(step_text, prefer_explicit_call=True)
        else:
            helper_name = _extract_helper_call(step_text, self.helper_names)
            if helper_name:
                node_type = self.ActivityNodeType.FUNCTION_CALL
                callee = helper_name
                display_name = _compact_step_label(step_text, prefer_helper_name=helper_name)
            elif "dem_reporterrorstatus" in step_text.lower() or "dem_seteventstatus" in step_text.lower():
                node_type = self.ActivityNodeType.EXCEPTION
                display_name = _compact_step_label(step_text, prefer_explicit_call=True)
        node_id = self.add_node(
            name=display_name,
            node_type=node_type,
            rte_call=rte_meta["rte_call"] if rte_meta else None,
            port=rte_meta["port"] if rte_meta else None,
            element=rte_meta["element"] if rte_meta else None,
            callee=callee,
            description=description,
            confidence=0.88,
        )
        self.connect_pending(pending, node_id)
        if callee and callee not in self._sub_ids and self._should_emit_helper_subdiagram(callee, step_text, pending):
            self._sub_ids.add(callee)
            self.sub_diagrams.append(
                _make_helper_subdiagram(
                    swc_name=self.swc_name,
                    runnable_name=self.runnable_name,
                    callee=callee,
                    step_text=step_text,
                    req_ids=self.req_ids,
                )
            )
        return (node_id, None)

    def _should_emit_helper_subdiagram(
        self,
        callee: str,
        step_text: str,
        pending: list[tuple[str, str | None]],
    ) -> bool:
        if self.helper_call_counts.get(callee, 0) > 1:
            return True
        if any(guard for _source, guard in pending if guard):
            return True
        if _step_has_multiple_substantive_ops(step_text):
            return True
        if _contains_structural_hint(step_text):
            return True
        return False

    def emit_return_step(
        self,
        step_text: str,
        pending: list[tuple[str, str | None]],
    ) -> None:
        node_id = self.add_node(
            name=step_text,
            node_type=self.ActivityNodeType.ACTION,
            description=_short_step_description(step_text),
            confidence=0.88,
        )
        self.connect_pending(pending, node_id)
        self.terminal_exits.append((node_id, None))

    def emit_if(
        self,
        steps: list[NumberedStep],
        index: int,
        pending: list[tuple[str, str | None]],
        depth: int,
    ) -> tuple[int, list[tuple[str, str | None]]]:
        def _merge_branch_exits(
            exits: list[tuple[str, str | None]],
            *,
            merge_name: str = "Merge",
            merge_description: str = "Branch merge",
        ) -> list[tuple[str, str | None]]:
            live_exits = list(exits)
            if len(live_exits) >= 2:
                merge_id = self.add_node(
                    name=merge_name,
                    node_type=self.ActivityNodeType.MERGE,
                    description=merge_description,
                    confidence=0.86,
                )
                self.connect_pending(live_exits, merge_id)
                return [(merge_id, None)]
            if len(live_exits) == 1:
                return live_exits
            return []

        rte_meta = _extract_rte_metadata(steps[index].text)
        decision_id = self.add_node(
            name=_strip_control_prefix(steps[index].text),
            node_type=self.ActivityNodeType.DECISION,
            description=_short_step_description(steps[index].text),
            confidence=0.9,
            rte_call=rte_meta["rte_call"] if rte_meta else None,
            port=rte_meta["port"] if rte_meta else None,
            element=rte_meta["element"] if rte_meta else None,
        )
        self.connect_pending(pending, decision_id)
        index += 1

        # Use the actual condition expression as the branch guard so the
        # rendered diagram shows e.g. "[l_f32Torque > LIMIT]" rather than the
        # generic "[true]" / "[false]" labels.
        condition_text = _strip_control_prefix(steps[index - 1].text)
        condition_text = re.sub(r"^\s*if\s*\(?\s*", "", condition_text, flags=re.IGNORECASE).strip().rstrip(")")
        true_guard  = f"[{condition_text}]" if condition_text else "[true]"
        false_guard = "[else]"

        index, true_exits, _ = self.emit_branch_body(
            steps,
            index,
            depth,
            pending=[(decision_id, true_guard)],
            stop_kinds={"else_if", "else", "end_if"},
        )
        branch_exits = list(true_exits)
        false_pending = [(decision_id, false_guard)]

        while index < len(steps) and steps[index].depth == depth and steps[index].kind == "else_if":
            rte_meta = _extract_rte_metadata(steps[index].text)
            else_if_condition = _strip_control_prefix(steps[index].text)
            else_if_condition = re.sub(
                r"^\s*(?:else\s+if|elseif|if)\s*\(?\s*",
                "",
                else_if_condition,
                flags=re.IGNORECASE,
            ).strip().rstrip(")")
            else_if_decision = self.add_node(
                name=else_if_condition or _strip_control_prefix(steps[index].text),
                node_type=self.ActivityNodeType.DECISION,
                description=_short_step_description(steps[index].text),
                confidence=0.9,
                rte_call=rte_meta["rte_call"] if rte_meta else None,
                port=rte_meta["port"] if rte_meta else None,
                element=rte_meta["element"] if rte_meta else None,
            )
            self.connect_pending(false_pending, else_if_decision)
            index += 1
            elseif_true_guard = f"[{else_if_condition}]" if else_if_condition else "[true]"
            index, elseif_exits, _ = self.emit_branch_body(
                steps,
                index,
                depth,
                pending=[(else_if_decision, elseif_true_guard)],
                stop_kinds={"else_if", "else", "end_if"},
            )
            elseif_false_pending = [(else_if_decision, "[else]")]
            remaining_chain = index < len(steps) and steps[index].depth == depth and steps[index].kind in {"else_if", "else"}
            if remaining_chain:
                merged_exits = _merge_branch_exits(
                    elseif_exits + elseif_false_pending,
                    merge_name="Else-if merge",
                    merge_description="Else-if branch merge",
                )
                branch_exits.extend(merged_exits)
                false_pending = merged_exits
            else:
                branch_exits.extend(elseif_exits)
                false_pending = elseif_false_pending

        if index < len(steps) and steps[index].depth == depth and steps[index].kind == "else":
            index += 1
            index, else_exits, _ = self.emit_branch_body(
                steps,
                index,
                depth,
                pending=false_pending,
                stop_kinds={"end_if"},
            )
            branch_exits.extend(else_exits)
        else:
            branch_exits.extend(false_pending)

        if index < len(steps) and steps[index].depth == depth and steps[index].kind == "end_if":
            index += 1
        return index, _merge_branch_exits(branch_exits)

    def emit_loop(
        self,
        steps: list[NumberedStep],
        index: int,
        pending: list[tuple[str, str | None]],
        depth: int,
    ) -> tuple[int, list[tuple[str, str | None]]]:
        loop_step = steps[index]
        rte_meta = _extract_rte_metadata(loop_step.text)
        decision_id = self.add_node(
            name=_strip_control_prefix(loop_step.text),
            node_type=self.ActivityNodeType.DECISION,
            description=_short_step_description(loop_step.text),
            confidence=0.9,
            rte_call=rte_meta["rte_call"] if rte_meta else None,
            port=rte_meta["port"] if rte_meta else None,
            element=rte_meta["element"] if rte_meta else None,
        )
        self.connect_pending(pending, decision_id)
        index += 1

        stop_kinds = {"end_loop"}
        if loop_step.kind == "until":
            stop_kinds = {"end_loop", "until"}
        loop_condition = _strip_control_prefix(loop_step.text)
        loop_guard = f"[{loop_condition}]" if loop_condition else "[loop]"
        index, body_exits, consumed = self.emit_branch_body(
            steps,
            index,
            depth,
            pending=[(decision_id, loop_guard)],
            stop_kinds=stop_kinds,
        )
        if consumed:
            for source, _guard in body_exits:
                self.add_edge(source, decision_id)

        if index < len(steps) and steps[index].depth == depth and steps[index].kind in stop_kinds:
            index += 1

        merge_id = self.add_node(
            name="Loop exit",
            node_type=self.ActivityNodeType.MERGE,
            description="Loop exit",
            confidence=0.86,
        )
        self.add_edge(decision_id, merge_id, guard="[done]")
        return index, [(merge_id, None)]

    def emit_switch(
        self,
        steps: list[NumberedStep],
        index: int,
        pending: list[tuple[str, str | None]],
        depth: int,
    ) -> tuple[int, list[tuple[str, str | None]]]:
        rte_meta = _extract_rte_metadata(steps[index].text)
        decision_id = self.add_node(
            name=_strip_control_prefix(steps[index].text),
            node_type=self.ActivityNodeType.DECISION,
            description=_short_step_description(steps[index].text),
            confidence=0.9,
            rte_call=rte_meta["rte_call"] if rte_meta else None,
            port=rte_meta["port"] if rte_meta else None,
            element=rte_meta["element"] if rte_meta else None,
        )
        self.connect_pending(pending, decision_id)
        index += 1
        branch_exits: list[tuple[str, str | None]] = []

        while index < len(steps) and steps[index].depth >= depth:
            if steps[index].depth < depth:
                break
            if steps[index].depth == depth and steps[index].kind in {"case", "default"}:
                guard = _switch_guard(steps[index].text)
                index += 1
                index, case_exits, _ = self.emit_branch_body(
                    steps,
                    index,
                    depth,
                    pending=[(decision_id, guard)],
                    stop_kinds={"case", "default", "end_switch"},
                )
                branch_exits.extend(case_exits)
                continue
            break

        if not branch_exits:
            branch_exits.append((decision_id, "[default]"))

        if index < len(steps) and steps[index].depth == depth and steps[index].kind == "end_switch":
            index += 1

        merge_id = self.add_node(
            name="Merge",
            node_type=self.ActivityNodeType.MERGE,
            description="Switch merge",
            confidence=0.86,
        )
        self.connect_pending(branch_exits, merge_id)
        return index, [(merge_id, None)]

    def emit_branch_body(
        self,
        steps: list[NumberedStep],
        index: int,
        depth: int,
        pending: list[tuple[str, str | None]],
        stop_kinds: set[str],
    ) -> tuple[int, list[tuple[str, str | None]], bool]:
        if index >= len(steps):
            return index, pending, False
        if steps[index].depth > depth:
            next_index, exits = self.emit_block(
                steps,
                index,
                min_depth=steps[index].depth,
                pending=pending,
                stop_kinds=stop_kinds,
            )
            return next_index, exits, next_index > index
        if steps[index].depth == depth and steps[index].kind not in stop_kinds:
            next_index, exits = self.emit_statement(steps, index, pending, depth)
            return next_index, exits, True
        return index, pending, False


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
    return [step.text for step in _parse_numbered_step_entries(text)]


def _parse_numbered_step_entries(text: str) -> list[NumberedStep]:
    steps: list[NumberedStep] = []
    current_header: str | None = None
    current_body_lines: list[str] = []
    current_depth = 1
    for raw_line in (text or "").splitlines():
        if not raw_line.strip():
            continue
        numbered = re.match(r"^(\s*)(\d+(?:\.\d+)*)(?:[.)])\s*(.+)$", raw_line)
        if numbered:
            if current_header is not None:
                steps.extend(_expand_numbered_step_block(current_header, current_body_lines, current_depth))
            current_depth = max(1, len(numbered.group(2).split(".")))
            current_header = numbered.group(3).strip()
            current_body_lines = []
        elif current_header is not None:
            current_body_lines.append(raw_line.rstrip())
    if current_header is not None:
        steps.extend(_expand_numbered_step_block(current_header, current_body_lines, current_depth))
    return steps


def _expand_numbered_step_block(header: str, body_lines: list[str], base_depth: int) -> list[NumberedStep]:
    header_text = _normalize_ws(header)
    body_lines = [line.rstrip() for line in body_lines if line.strip()]
    if not body_lines:
        return [
            NumberedStep(
                text=header_text,
                depth=base_depth,
                kind=_classify_step_kind(header_text),
            )
        ]

    expanded = _parse_pseudocode_block_lines(body_lines, base_depth + 1)
    if expanded:
        if not _looks_like_container_heading(header_text):
            expanded.insert(
                0,
                NumberedStep(
                    text=header_text,
                    depth=base_depth,
                    kind=_classify_step_kind(header_text),
                ),
            )
        return expanded

    merged = _normalize_ws(" ".join([header_text, *body_lines]))
    return [
        NumberedStep(
            text=merged,
            depth=base_depth,
            kind=_classify_step_kind(merged),
        )
    ]


def _parse_pseudocode_block_lines(lines: list[str], base_depth: int) -> list[NumberedStep]:
    steps: list[NumberedStep] = []
    depth_offset = 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("//"):
            continue

        # Process closing braces before the current statement so "} else {" lands
        # back on the parent branch depth.
        while line.startswith("}"):
            depth_offset = max(0, depth_offset - 1)
            line = line[1:].strip()
        if not line:
            continue

        opens_block = line.endswith("{")
        if opens_block:
            line = line[:-1].rstrip()
        line = line.rstrip(";").strip()
        if not line:
            if opens_block:
                depth_offset += 1
            continue

        normalized = _normalize_control_line(line)
        if normalized:
            steps.append(
                NumberedStep(
                    text=normalized,
                    depth=max(1, base_depth + depth_offset),
                    kind=_classify_step_kind(normalized),
                )
            )

        if opens_block:
            depth_offset += 1

        leading_match = re.match(r"^\s*}*", raw_line)
        leading_closes = leading_match.group(0).count("}") if leading_match else 0
        trailing_closes = max(0, raw_line.count("}") - leading_closes)
        if trailing_closes > 0 and not raw_line.strip().startswith("}"):
            depth_offset = max(0, depth_offset - trailing_closes)

    return steps


def _looks_like_container_heading(text: str) -> bool:
    lowered = _normalize_ws(text).lower()
    if lowered.startswith("//"):
        return True
    return lowered.endswith(":") or lowered in {
        "read inputs",
        "validate inputs",
        "core computation step",
        "core computation step(s)",
        "write pp_ output",
        "last step",
        "watchdog update",
    }


def _normalize_control_line(text: str) -> str:
    cleaned = _normalize_ws(text)
    replacements = [
        (r"^else\s+if\s*\((.+)\)$", r"Else if \1"),
        (r"^if\s*\((.+)\)$", r"If \1"),
        (r"^while\s*\((.+)\)$", r"While \1"),
        (r"^for\s*\((.+)\)$", r"For \1"),
        (r"^switch\s*\((.+)\)$", r"Switch \1"),
        (r"^case\s+(.+):?$", r"Case \1"),
        (r"^default\s*:?\s*$", "Default"),
    ]
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        if updated != cleaned:
            return updated.strip()
    return cleaned


def _classify_step_kind(step: str) -> str:
    lowered = _normalize_ws(step).lower()
    if re.match(r"^(else\s+if|elseif)\b", lowered):
        return "else_if"
    if re.match(r"^if\b", lowered):
        return "if"
    if re.match(r"^else\b", lowered):
        return "else"
    if re.match(r"^(end\s*if|endif)\b", lowered):
        return "end_if"
    if re.match(r"^while\b", lowered):
        return "while"
    if re.match(r"^until\b", lowered):
        return "until"
    if re.match(r"^(for\s+each|for\s+all|for\b)", lowered):
        return "for"
    if re.match(r"^(end\s*while|endwhile|end\s*for|endfor|end\s*loop|endloop)\b", lowered):
        return "end_loop"
    if re.match(r"^switch\b", lowered):
        return "switch"
    if re.match(r"^case\b", lowered):
        return "case"
    if re.match(r"^default\b", lowered):
        return "default"
    if re.match(r"^(end\s*switch|endswitch)\b", lowered):
        return "end_switch"
    if re.match(r"^return\b", lowered):
        return "return"
    # Implicit decision patterns — AUTOSAR pseudo-code sometimes writes
    # guards without the literal "if" keyword. Treated as decisions ONLY
    # when a C comparison operator is present in the same line so that
    # pure-English summaries like "Check if torque OK" stay as actions
    # (avoids English text leaking into decision-node names downstream).
    _IMPLICIT_IF_PATTERNS = (
        r"^(?:validate|check|verify|determine|guard)\b[^a-z]*[A-Za-z_]\w*\s*(?:>|<|==|!=|>=|<=|&&|\|\|)",
    )
    for p in _IMPLICIT_IF_PATTERNS:
        if re.search(p, lowered):
            return "if"
    return "action"


def _strip_control_prefix(step: str) -> str:
    text = _normalize_ws(step)
    patterns = [
        r"^(?:else\s+if|elseif)\s+",
        r"^if\s+",
        r"^while\s+",
        r"^until\s+",
        r"^(?:for\s+each|for\s+all|for)\s+",
        r"^switch\s+",
        r"^case\s+",
        r"^default\s*:?\s*",
        r"^(?:end\s*if|endif|end\s*while|endwhile|end\s*for|endfor|end\s*switch|endswitch)\s*",
    ]
    for pattern in patterns:
        updated = re.sub(pattern, "", text, flags=re.IGNORECASE)
        if updated != text:
            text = updated
            break
    return text.strip(" :") or _normalize_ws(step)


def _switch_guard(step: str) -> str:
    lowered = _normalize_ws(step)
    if _classify_step_kind(lowered) == "default":
        return "[default]"
    return f"[{_strip_control_prefix(step)}]"


def _extract_rte_metadata(step: str) -> dict[str, str] | None:
    m = re.search(
        r"\b(Rte_(?:IRead|IWrite|Read|Write|Call|Result|Receive|Send|Switch)\w*)\s*\(\s*([A-Z]{2}_[A-Za-z0-9_]+)",
        step,
    )
    if not m:
        return None
    rte_call = _normalize_rte_call_name(m.group(1))
    port = m.group(2)
    element = _infer_element_name(port, step, rte_call)
    return {"rte_call": rte_call, "port": port, "element": element}


def _normalize_rte_call_name(rte_call: str) -> str:
    raw = (rte_call or "").strip()
    if not raw:
        return raw
    if raw.startswith("Rte_"):
        return raw
    if raw.startswith("IRead"):
        return "Rte_IRead"
    if raw.startswith("IWrite"):
        return "Rte_IWrite"
    return f"Rte_{raw}"


def _infer_element_name(port: str, step: str, rte_call: str) -> str:
    parts = port.split("_", 2)
    if len(parts) >= 3 and parts[2]:
        return parts[2]

    if rte_call in {"Rte_IRead", "Rte_Read", "Rte_Receive", "Rte_Result"}:
        m = re.search(rf"{re.escape(rte_call)}\s*\(\s*{re.escape(port)}\s*,\s*&?\s*([A-Za-z_][A-Za-z0-9_]*)", step)
        if m:
            return m.group(1)

    if rte_call in {"Rte_IWrite", "Rte_Write", "Rte_Send", "Rte_Switch"}:
        m = re.search(rf"{re.escape(rte_call)}\s*\(\s*{re.escape(port)}\s*,\s*([^)]+)\)", step)
        if m:
            expr = m.group(1).strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", expr):
                return expr

    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return ""


def _extract_helper_call(step: str, helper_names: set[str]) -> str | None:
    for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", step):
        if name.startswith(("Rte_", "Dem_")):
            continue
        if helper_names and name in helper_names:
            return name
        if "_" in name or re.search(r"[A-Z]", name):
            return name
    return None


def _count_helper_calls(steps: list[NumberedStep], helper_names: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in steps:
        helper = _extract_helper_call(step.text, helper_names)
        if not helper:
            continue
        counts[helper] = counts.get(helper, 0) + 1
    return counts


def _compact_step_label(
    step: str,
    *,
    prefer_explicit_call: bool = False,
    prefer_helper_name: str | None = None,
) -> str:
    trimmed = _normalize_ws(step)
    if not trimmed:
        return trimmed

    if prefer_helper_name:
        assign = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.+$", trimmed)
        if assign:
            return f"{assign.group(1)} = {prefer_helper_name}(...)"
        return f"{prefer_helper_name}(...)"

    if prefer_explicit_call:
        return trimmed

    header, tail = _split_heading_prefix(trimmed)
    candidate = _normalize_ws(tail or trimmed)
    if len(candidate) <= 72:
        return candidate

    assign = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", candidate)
    if assign:
        lhs = assign.group(1)
        rhs = assign.group(2)
        helper = _extract_helper_call(rhs, set())
        if helper:
            return f"{lhs} = {helper}(...)"
        return f"{lhs} = ..."

    call = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(", candidate)
    if call:
        return f"{call.group(1)}(...)"

    if header:
        return f"{header}: ..."
    return candidate[:69].rstrip() + "..."


def _short_step_description(step: str) -> str:
    trimmed = _normalize_ws(step)
    if not trimmed:
        return trimmed

    header, tail = _split_heading_prefix(trimmed)
    target = _normalize_ws(tail or trimmed)

    if _extract_rte_metadata(target):
        return target

    helper = _extract_helper_call(target, set())
    if helper:
        assign = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.+$", target)
        if assign:
            return f"{assign.group(1)} = {helper}(...)"
        return f"{helper}(...)"

    if len(target) <= 56:
        return target
    compact = target[:53].rstrip() + "..."
    if header:
        return f"{header}: {compact}"
    return compact


def _split_heading_prefix(step: str) -> tuple[str | None, str | None]:
    parts = step.split(":", 1)
    if len(parts) != 2:
        return None, None
    head = parts[0].strip()
    tail = parts[1].strip()
    if not head or not tail:
        return None, None
    if _classify_step_kind(head) != "action":
        return None, None
    return head, tail


def _step_has_multiple_substantive_ops(step: str) -> bool:
    candidate = _normalize_ws(step)
    _header, tail = _split_heading_prefix(candidate)
    candidate = tail or candidate
    if candidate.count(";") >= 1:
        return True
    if candidate.count("&&") >= 1 or candidate.count("||") >= 1:
        return True
    if candidate.count(",") >= 2 and "(" not in candidate:
        return True
    return False


def _contains_structural_hint(step: str) -> bool:
    lowered = f" {_normalize_ws(step).lower()} "
    hints = (" if ", " else ", " while ", " for ", " switch ", " case ", " return ", " loop ", " guard ")
    return any(hint in lowered for hint in hints)


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
                name=_compact_step_label(step_text, prefer_helper_name=callee),
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
