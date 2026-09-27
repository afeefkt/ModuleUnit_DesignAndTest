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

    def export_diagram(self, diagram: ActivityDiagram, _nested: bool = False) -> str:
        """Generate C skeleton code for a single ActivityDiagram.

        ``_nested`` is set for sub-diagrams: they are emitted as ``static``
        helper functions inside the parent file, without repeating the
        ``#include`` lines or the file-scope variable declarations.
        """
        lines: list[str] = []

        # Header comment
        lines.append(f"/* Generated from: {diagram.name} */")
        if diagram.source_requirements:
            lines.append(f"/* Requirements: {', '.join(diagram.source_requirements)} */")
        if diagram.provenance and not _nested:
            lines.append(f"/* Model: {diagram.provenance.ai_model}, confidence: {diagram.provenance.confidence} */")
        lines.append("")

        # Includes
        if not _nested:
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
        variables = [] if _nested else self._extract_variables_all(diagram)
        if variables:
            lines.append("/* Local variables */")
            for var_type, var_name in sorted(variables):
                lines.append(f"static {var_type} {var_name};")
            lines.append("")

        # Function signature
        # Sub-diagrams are the static helpers forward-declared by the parent
        if _nested:
            func_name = diagram.function_name or diagram.name.replace(" Code Flow", "")
            lines.append(f"static void {func_name}(void)")
        else:
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
                lines, indent=1, visited=visited, stop_at=None,
            )

        lines.append("}")
        lines.append("")

        # Generate sub-diagram function bodies
        for sub in diagram.sub_diagrams:
            lines.append("")
            lines.append(self.export_diagram(sub, _nested=True))

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
        stop_at: Optional[str],
    ) -> None:
        """Recursively walk the node graph and emit C code.

        ``stop_at`` is the join node of the enclosing decision: a branch stops
        there so the code after the join is emitted once, after the if/else,
        instead of inside whichever branch happened to reach it first.
        """
        if node_id == stop_at or node_id in visited:
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
            targets = list(outgoing.get(node_id, []))
            if len(targets) >= 2:
                targets = self._order_branches(node_id, targets, edge_guards)
                join = self._find_join(node_id, targets, outgoing)
                cond = self._condition(node, edge_guards.get((node_id, targets[0])))

                def walk_branch(target: str) -> None:
                    self._walk_node(
                        target, node_map, outgoing, edge_guards, lines,
                        indent + 1, visited, join,
                    )

                lines.append(f"{pad}{trace}")
                lines.append(f"{pad}if ({cond})")
                lines.append(f"{pad}{{")
                walk_branch(targets[0])
                lines.append(f"{pad}}}")
                # Middle targets become else-if; the last one is the else
                for t in targets[1:-1]:
                    guard_n = edge_guards.get((node_id, t)) or "/* condition */"
                    lines.append(f"{pad}else if ({guard_n})")
                    lines.append(f"{pad}{{")
                    walk_branch(t)
                    lines.append(f"{pad}}}")
                lines.append(f"{pad}else")
                lines.append(f"{pad}{{")
                walk_branch(targets[-1])
                lines.append(f"{pad}}}")
                # Code after the join runs for every branch — emit it once, here
                if join:
                    self._walk_node(
                        join, node_map, outgoing, edge_guards, lines,
                        indent, visited, stop_at,
                    )
                return
            else:
                # Single outgoing from decision (shouldn't happen but handle gracefully)
                lines.append(f"{pad}/* decision: {node.name} */ {trace}")

        elif node.node_type == ActivityNodeType.MERGE:
            # Merge point — just continue (no code emitted)
            pass

        # Walk outgoing edges (unless decision already handled them)
        if node.node_type != ActivityNodeType.DECISION:
            for target_id in outgoing.get(node_id, []):
                self._walk_node(
                    target_id, node_map, outgoing, edge_guards, lines,
                    indent, visited, stop_at,
                )

    _TRUE_GUARDS = {"yes", "true", "y", "ok", "valid"}
    _FALSE_GUARDS = {"no", "false", "n", "else", "otherwise", "nok", "invalid"}

    def _order_branches(
        self, node_id: str, targets: list[str], edge_guards: dict
    ) -> list[str]:
        """Put a yes/true branch first and a no/else branch last."""
        def rank(t: str) -> int:
            g = (edge_guards.get((node_id, t)) or "").strip().lower()
            if g in self._TRUE_GUARDS:
                return 0
            if g in self._FALSE_GUARDS:
                return 2
            return 1
        return sorted(targets, key=rank)

    def _condition(self, node, guard: Optional[str]) -> str:
        """C condition for the first branch.

        An expression guard (e.g. ``u16Volt > MAX``) is used as-is; a bare
        yes/no guard means the question lives in the decision node's name.
        """
        g = (guard or "").strip()
        if g and g.lower() not in self._TRUE_GUARDS | self._FALSE_GUARDS:
            return g
        cond = (node.name or "/* condition */").strip().rstrip("?").strip()
        if g.lower() in self._FALSE_GUARDS:
            cond = f"!({cond})"
        return cond

    @staticmethod
    def _find_join(
        node_id: str, targets: list[str], outgoing: dict
    ) -> Optional[str]:
        """Nearest node reachable from every branch — the if/else join point."""
        def distances(start: str) -> dict[str, int]:
            dist = {start: 0}
            queue = [start]
            while queue:
                cur = queue.pop(0)
                for nxt in outgoing.get(cur, []):
                    if nxt != node_id and nxt not in dist:
                        dist[nxt] = dist[cur] + 1
                        queue.append(nxt)
            return dist

        per_branch = [distances(t) for t in targets]
        common = set(per_branch[0]).intersection(*per_branch[1:])
        if not common:
            return None
        return min(common, key=lambda n: (max(d[n] for d in per_branch), n))

    def _extract_variables_all(self, diagram: ActivityDiagram) -> list[tuple[str, str]]:
        """Variables of the diagram and all its sub-diagrams, declared once at file scope."""
        found: dict[str, str] = {}
        stack = [diagram]
        while stack:
            d = stack.pop()
            for var_type, var_name in self._extract_variables(d):
                found.setdefault(var_name, var_type)
            stack.extend(d.sub_diagrams)
        return [(t, n) for n, t in found.items()]

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
