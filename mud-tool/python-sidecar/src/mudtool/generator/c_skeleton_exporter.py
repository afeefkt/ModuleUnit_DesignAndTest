"""C-code skeleton generator from ActivityDiagram JSON.

Walks the node/edge graph in topological order and emits a `.c` template
with proper C constructs for each node type:
  - action    → assignment statement
  - call      → RTE API call
  - decision  → if/else block
  - exception → DEM / fault handling
  - function_call → function invocation

Trace comments reference requirement IDs for traceability.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityNodeType,
    AnyDiagram,
    GenerationResult,
)

logger = logging.getLogger(__name__)


# Guard labels that are not valid C conditions and must be replaced with the
# decision node's own condition label.
_NON_CONDITION_GUARDS: frozenset[str] = frozenset({
    "yes", "no", "y", "n", "true", "false",
    "else", "default", "otherwise", "then",
    "conditiontrue", "conditionfalse",
    "conditionmet", "conditionnotmet",
})


def _decision_condition(guard: Optional[str], decision_name: Optional[str]) -> str:
    """Return a real C condition for a decision branch.

    Uses the edge guard when it is an actual C expression; otherwise falls back
    to the decision node's own label (which, in synthesized flowcharts, *is* the
    condition, e.g. ``l_u8ModeCmd == 1``).
    """
    g = (guard or "").strip()
    if g.startswith("[") and g.endswith("]"):
        g = g[1:-1].strip()
    norm = re.sub(r"[^a-z0-9]+", "", g.lower())
    if g and norm not in _NON_CONDITION_GUARDS:
        return g
    name = (decision_name or "").strip()
    if name:
        return name
    return "1"


class CSkeletonExporter:
    """Export ActivityDiagram JSON to C-code skeleton files."""

    def export_diagram(self, diagram: ActivityDiagram, *, as_helper: bool = False) -> str:
        """Generate C skeleton code for a single ActivityDiagram.

        ``as_helper=True`` emits a ``static`` helper function body (used for
        sub-diagrams) without the repeated include/comment header.
        """
        lines: list[str] = []

        if not as_helper:
            # Header comment
            lines.append(f"/* Generated from: {diagram.name} */")
            if diagram.source_requirements:
                lines.append(f"/* Requirements: {', '.join(diagram.source_requirements)} */")
            if diagram.provenance:
                lines.append(f"/* Model: {diagram.provenance.ai_model}, confidence: {diagram.provenance.confidence} */")
            lines.append("")

            # Includes
            lines.append('#include "Rte_Type.h"')
            if diagram.owner_swc:
                lines.append(f'#include "Rte_{diagram.owner_swc}.h"')
            lines.append("")

            # Forward declare any helper functions from sub_diagrams
            for sub in diagram.sub_diagrams:
                fname = sub.function_name or sub.name.replace(" Code Flow", "")
                lines.append(f"static void {fname}(void);  /* see sub-diagram */")
            if diagram.sub_diagrams:
                lines.append("")

            # Collect variable declarations by scanning node names
            variables = self._extract_variables(diagram)
            if variables:
                lines.append("/* Local variables */")
                for var_type, var_name in sorted(variables):
                    lines.append(f"static {var_type} {var_name};")
                lines.append("")

        # Function signature
        if as_helper:
            func_name = diagram.function_name or diagram.name.replace(" Code Flow", "")
            lines.append(f"static void {func_name}(void)")
        else:
            func_name = diagram.owner_runnable or diagram.name.replace(" Code Flow", "")
            lines.append(f"void {func_name}(void)")
        lines.append("{")
        self._emit_body(diagram, lines)
        lines.append("}")
        lines.append("")

        # Emit sub-diagrams as static helpers
        for sub in diagram.sub_diagrams:
            lines.append("")
            lines.append(self.export_diagram(sub, as_helper=True))

        return "\n".join(lines)

    def export_result(self, result: GenerationResult) -> dict[str, str]:
        """Export all ActivityDiagrams in a GenerationResult.

        Returns: {diagram_name: c_code_string}
        """
        output: dict[str, str] = {}
        for diagram in result.diagrams:
            if isinstance(diagram, ActivityDiagram) and not diagram.parent_diagram:
                name = diagram.name or "diagram"
                safe_name = name.replace(" ", "_").replace("/", "_")
                output[safe_name] = self.export_diagram(diagram)
        return output

    def _emit_body(self, diagram: ActivityDiagram, lines: list[str]) -> None:
        """Emit the function body for ``diagram`` into ``lines`` (indented once)."""
        # Build adjacency for topological walk
        outgoing: dict[str, list[str]] = defaultdict(list)
        edge_guards: dict[tuple[str, str], str] = {}
        for edge in diagram.edges:
            outgoing[edge.source].append(edge.target)
            if edge.guard:
                g = edge.guard.strip()
                if g.startswith("[") and g.endswith("]"):
                    g = g[1:-1]
                edge_guards[(edge.source, edge.target)] = g

        node_map = {n.id: n for n in diagram.nodes}

        # Find initial node
        initial_id = None
        for n in diagram.nodes:
            if n.node_type == ActivityNodeType.INITIAL:
                initial_id = n.id
                break

        if initial_id:
            self._last_trace = None
            visited: set[str] = set()
            self._walk_node(
                initial_id, node_map, outgoing, edge_guards,
                lines, indent=1, visited=visited,
            )

    def _find_join(self, node_id: str, node_map: dict, outgoing: dict) -> Optional[str]:
        """Find the first merge/join node common to all branches of a decision.

        This is the node where the if/else branches reconverge; code after it
        must be emitted once, after the branch blocks (not inside them).
        """
        targets = outgoing.get(node_id, [])
        if len(targets) < 2:
            return None

        def reachable(start: str) -> set[str]:
            seen: set[str] = set()
            stack = [start]
            while stack:
                n = stack.pop()
                if n in seen:
                    continue
                seen.add(n)
                for t in outgoing.get(n, []):
                    if t not in seen:
                        stack.append(t)
            return seen

        branch_sets = [reachable(t) for t in targets]
        if not branch_sets:
            return None
        common = set.intersection(*branch_sets)
        if not common:
            return None

        # Prefer an explicit merge/join node (emits no code) over the final node.
        joins = [
            n for n in common
            if node_map.get(n) and node_map[n].node_type in (ActivityNodeType.MERGE, ActivityNodeType.JOIN)
        ]
        if joins:
            return sorted(joins)[0]
        return None

    def _walk_node(
        self,
        node_id: str,
        node_map: dict,
        outgoing: dict,
        edge_guards: dict,
        lines: list[str],
        indent: int,
        visited: set[str],
        stop_at: Optional[str] = None,
    ) -> None:
        """Recursively walk the node graph and emit C code.

        ``stop_at`` is the reconvergence (merge/join) node: when reached, the
        walk stops without emitting or marking it, so the caller emits it once
        after the decision branches.
        """
        if node_id == stop_at:
            return
        if node_id in visited:
            return
        visited.add(node_id)

        node = node_map.get(node_id)
        if not node:
            return

        pad = "    " * indent
        trace = f"/* [{', '.join(node.trace_reqs)}] */" if node.trace_reqs else ""
        # A trace comment applies to the statements below it, so repeat it only
        # when the requirement set changes — otherwise every line of a runnable
        # whose nodes share one long requirement list is buried under it.
        trace_line = trace if trace and trace != getattr(self, "_last_trace", None) else ""
        if trace:
            self._last_trace = trace

        if node.node_type == ActivityNodeType.INITIAL:
            # Skip — just walk to next
            pass

        elif node.node_type == ActivityNodeType.FINAL:
            lines.append(f"{pad}return; {trace_line}".rstrip())
            return

        elif node.node_type == ActivityNodeType.CALL:
            desc = f"  /* {node.description} */" if node.description else ""
            if trace_line:
                lines.append(f"{pad}{trace_line}")
            lines.append(f"{pad}{node.name};{desc}")

        elif node.node_type == ActivityNodeType.ACTION:
            desc = f"  /* {node.description} */" if node.description else ""
            if trace_line:
                lines.append(f"{pad}{trace_line}")
            lines.append(f"{pad}{node.name};{desc}")

        elif node.node_type == ActivityNodeType.FUNCTION_CALL:
            callee = (node.callee or node.name or "").strip()
            if callee.endswith("()"):
                callee = callee[:-2]
            if trace_line:
                lines.append(f"{pad}{trace_line}")
            lines.append(f"{pad}{callee}();  /* -> {callee}() */")

        elif node.node_type == ActivityNodeType.EXCEPTION:
            if trace_line:
                lines.append(f"{pad}{trace_line}")
            lines.append(f"{pad}{node.name};  /* FAULT */")

        elif node.node_type == ActivityNodeType.DECISION:
            targets = outgoing.get(node_id, [])
            join = self._find_join(node_id, node_map, outgoing)
            if len(targets) >= 2:
                # First branch = the "yes"/primary condition, second = else.
                condition = _decision_condition(
                    edge_guards.get((node_id, targets[0])), node.name
                )
                if trace_line:
                    lines.append(f"{pad}{trace_line}")
                lines.append(f"{pad}if ({condition})")
                lines.append(f"{pad}{{")
                self._walk_node(targets[0], node_map, outgoing, edge_guards, lines, indent + 1, visited, stop_at=join)
                lines.append(f"{pad}}}")
                lines.append(f"{pad}else")
                lines.append(f"{pad}{{")
                self._walk_node(targets[1], node_map, outgoing, edge_guards, lines, indent + 1, visited, stop_at=join)
                lines.append(f"{pad}}}")
                # Handle any remaining targets (switch-like)
                for t in targets[2:]:
                    guard_n = _decision_condition(edge_guards.get((node_id, t)), node.name)
                    lines.append(f"{pad}/* else if ({guard_n}) */")
                    lines.append(f"{pad}{{")
                    self._walk_node(t, node_map, outgoing, edge_guards, lines, indent + 1, visited, stop_at=join)
                    lines.append(f"{pad}}}")
                # Continue after the reconvergence point (emitted once).
                if join is not None:
                    self._walk_node(join, node_map, outgoing, edge_guards, lines, indent, visited)
                return  # Don't continue with outgoing — already walked
            else:
                # Single outgoing from decision (shouldn't happen but handle gracefully)
                lines.append(f"{pad}/* decision: {node.name} */ {trace_line}".rstrip())

        elif node.node_type == ActivityNodeType.MERGE:
            # Merge point — just continue (no code emitted)
            pass

        # Walk outgoing edges (unless decision already handled them)
        if node.node_type != ActivityNodeType.DECISION:
            for target_id in outgoing.get(node_id, []):
                self._walk_node(target_id, node_map, outgoing, edge_guards, lines, indent, visited, stop_at=stop_at)

    def _extract_variables(self, diagram: ActivityDiagram) -> list[tuple[str, str]]:
        """Scan node names for MISRA-C Hungarian variable patterns and return (type, name) pairs."""
        type_map = {
            "f32": "float32",
            "f64": "float64",
            "u8": "uint8",
            "u16": "uint16",
            "u32": "uint32",
            "s8": "sint8",
            "s16": "sint16",
            "s32": "sint32",
            "b": "boolean",
        }

        pattern = re.compile(r"\bl_([a-z]\w*?)([A-Z]\w*)")
        seen: set[str] = set()
        variables: list[tuple[str, str]] = []

        for node in diagram.nodes:
            for m in pattern.finditer(node.name):
                prefix = m.group(1)
                full_name = f"l_{prefix}{m.group(2)}"
                if full_name not in seen:
                    seen.add(full_name)
                    c_type = type_map.get(prefix, "uint32")
                    variables.append((c_type, full_name))

        return variables
