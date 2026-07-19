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
from collections import defaultdict
from typing import Optional

from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityNodeType,
    AnyDiagram,
    GenerationResult,
)

logger = logging.getLogger(__name__)


class CSkeletonExporter:
    """Export ActivityDiagram JSON to C-code skeleton files."""

    def export_diagram(self, diagram: ActivityDiagram) -> str:
        """Generate C skeleton code for a single ActivityDiagram."""
        lines: list[str] = []

        # Header comment
        lines.append(f"/* Generated from: {diagram.name} */")
        if diagram.source_requirements:
            lines.append(f"/* Requirements: {', '.join(diagram.source_requirements)} */")
        if diagram.provenance:
            lines.append(f"/* Model: {diagram.provenance.ai_model}, confidence: {diagram.provenance.confidence} */")
        lines.append("")

        # Includes
        lines.append("#include \"Rte_Type.h\"")
        if diagram.owner_swc:
            lines.append(f"#include \"Rte_{diagram.owner_swc}.h\"")
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
        func_name = diagram.owner_runnable or diagram.name.replace(" Code Flow", "")
        lines.append(f"void {func_name}(void)")
        lines.append("{")

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
            visited: set[str] = set()
            self._walk_node(
                initial_id, node_map, outgoing, edge_guards,
                lines, indent=1, visited=visited,
            )

        lines.append("}")
        lines.append("")

        # Generate sub-diagram function bodies
        for sub in diagram.sub_diagrams:
            lines.append("")
            lines.append(self.export_diagram(sub))

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

    def _walk_node(
        self,
        node_id: str,
        node_map: dict,
        outgoing: dict,
        edge_guards: dict,
        lines: list[str],
        indent: int,
        visited: set[str],
    ) -> None:
        """Recursively walk the node graph and emit C code."""
        if node_id in visited:
            return
        visited.add(node_id)

        node = node_map.get(node_id)
        if not node:
            return

        pad = "    " * indent
        trace = f"/* [{', '.join(node.trace_reqs)}] */" if node.trace_reqs else ""

        if node.node_type == ActivityNodeType.INITIAL:
            # Skip — just walk to next
            pass

        elif node.node_type == ActivityNodeType.FINAL:
            lines.append(f"{pad}return; {trace}")
            return

        elif node.node_type == ActivityNodeType.CALL:
            desc = f"  /* {node.description} */" if node.description else ""
            lines.append(f"{pad}{trace}")
            lines.append(f"{pad}{node.name};{desc}")

        elif node.node_type == ActivityNodeType.ACTION:
            desc = f"  /* {node.description} */" if node.description else ""
            lines.append(f"{pad}{trace}")
            lines.append(f"{pad}{node.name};{desc}")

        elif node.node_type == ActivityNodeType.FUNCTION_CALL:
            callee = node.callee or node.name
            lines.append(f"{pad}{trace}")
            lines.append(f"{pad}{node.name};  /* -> {callee}() */")

        elif node.node_type == ActivityNodeType.EXCEPTION:
            lines.append(f"{pad}{trace}")
            lines.append(f"{pad}{node.name};  /* FAULT */")

        elif node.node_type == ActivityNodeType.DECISION:
            targets = outgoing.get(node_id, [])
            if len(targets) >= 2:
                # First target with guard = if branch, second = else
                guard_1 = edge_guards.get((node_id, targets[0]), node.name)
                lines.append(f"{pad}{trace}")
                lines.append(f"{pad}if ({guard_1})")
                lines.append(f"{pad}{{")
                self._walk_node(targets[0], node_map, outgoing, edge_guards, lines, indent + 1, visited)
                lines.append(f"{pad}}}")
                lines.append(f"{pad}else")
                lines.append(f"{pad}{{")
                self._walk_node(targets[1], node_map, outgoing, edge_guards, lines, indent + 1, visited)
                lines.append(f"{pad}}}")
                # Handle any remaining targets (switch-like)
                for t in targets[2:]:
                    guard_n = edge_guards.get((node_id, t), "/* else */")
                    lines.append(f"{pad}/* else if ({guard_n}) */")
                    lines.append(f"{pad}{{")
                    self._walk_node(t, node_map, outgoing, edge_guards, lines, indent + 1, visited)
                    lines.append(f"{pad}}}")
                return  # Don't continue with outgoing — already walked
            else:
                # Single outgoing from decision (shouldn't happen but handle gracefully)
                lines.append(f"{pad}/* decision: {node.name} */ {trace}")

        elif node.node_type == ActivityNodeType.MERGE:
            # Merge point — just continue (no code emitted)
            pass

        # Walk outgoing edges (unless decision already handled them)
        if node.node_type != ActivityNodeType.DECISION:
            for target_id in outgoing.get(node_id, []):
                self._walk_node(target_id, node_map, outgoing, edge_guards, lines, indent, visited)

    def _extract_variables(self, diagram: ActivityDiagram) -> list[tuple[str, str]]:
        """Scan node names for MISRA-C Hungarian variable patterns and return (type, name) pairs."""
        import re

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
