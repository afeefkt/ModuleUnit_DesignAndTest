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


def _safe_comment(text: str) -> str:
    """Text that cannot open or close a C comment (nested comments make gcc warn)."""
    return (text or "").replace("/*", "/ *").replace("*/", "* /")


def _desc_comment(description: str | None, name: str | None) -> str:
    """A trailing comment, skipped when it only repeats the statement."""
    desc = (description or "").strip()
    stmt = (name or "").rstrip(";").strip()
    head = desc.rstrip(".").rstrip(";").strip()
    if not desc or head == stmt or (desc.endswith("...") and stmt.startswith(desc[:-3].rstrip())):
        return ""          # it only repeats (or truncates) the statement
    return f"  /* {_safe_comment(desc)} */"


def _call_args(text: str, callee: str) -> str:
    """The argument list the design wrote for ``callee(...)`` (empty if none); nested brackets allowed.

    Every occurrence is tried, so a shortened label such as ``ApplyRamp(...)`` does not hide the
    real argument list written elsewhere in ``text``.
    """
    import re
    text = text or ""
    for m in re.finditer(rf"\b{re.escape(callee)}\s*\(", text):
        depth, start = 1, m.end()
        for i in range(start, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    args = text[start:i].strip()
                    if args and args not in ("void", "..."):
                        return args
                    break
    return ""


_C_KEYWORD_STMTS = {"return", "break", "continue"}


def _is_step_title(stmt: str) -> bool:
    """``Guard`` / ``Read inputs`` / ``Validate calibration``: words only, no C syntax."""
    import re
    s = re.sub(r"\s*\[[A-Z][A-Z0-9_,\s-]*\d\]\s*$", "", (stmt or "").strip())   # "Guard [REQ-X-1]"
    if not s or s in _C_KEYWORD_STMTS:
        return False
    if re.search(r"[=()\[\];{}<>!+*%&|^~]", s):
        return False
    words = s.split()
    # A single identifier with an underscore or digits could be a macro call site; keep it as code.
    if len(words) == 1 and re.search(r"[_0-9]", s):
        return False
    # Words plus prose punctuation: "Guard — module not ready", "Read/validate inputs: speed".
    return bool(re.fullmatch(r"[A-Za-z][\w\-',.:/]*(?:\s+[\w\-–—',.:/]+)*", s))


def _is_self_call(stmt: str, func: str | None) -> bool:
    import re
    return bool(func) and bool(re.match(rf"^\s*{re.escape(func)}\s*\(", stmt or ""))


def _helper_name(sub) -> str:
    return sub.function_name or sub.name.replace(" Code Flow", "")


def _split_args(args: str) -> list[str]:
    """Top-level comma-separated arguments of ``args`` (nested brackets and strings are not split)."""
    parts, depth, quote, cur = [], 0, "", []
    for ch in args:
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


def _helper_signatures(diagrams) -> dict[str, list[str]]:
    """``{helper: [parameter declaration, ...]}`` for helpers (sub-diagrams with a body) the design
    always calls with the same number of arguments and never with a result (``x = f(a)``).

    The helper is then generated with those parameters instead of ``void f(void)``, so the arguments
    the design passes are not dropped. A parameter is ``float64`` unless some call passes the name of
    a function (e.g. a runnable used as a watchdog checkpoint id): that one is a function pointer,
    and a plain ``0`` is a valid null pointer there.
    """
    import re
    seen: dict[str, list[list[str]]] = {}       # helper → the argument lists of its call sites
    lhs_calls: set[str] = set()
    bodies: set[str] = set()
    functions: set[str] = set()

    def walk(diagram) -> None:
        if diagram.owner_runnable:
            functions.add(diagram.owner_runnable)
        if diagram.function_name:
            functions.add(diagram.function_name)
        for sub in diagram.sub_diagrams:
            if not _is_empty_helper(sub):
                bodies.add(_helper_name(sub))
            walk(sub)
        for node in diagram.nodes:
            if node.node_type != ActivityNodeType.FUNCTION_CALL:
                continue
            callee = (node.callee or node.name or "").strip()
            callee = callee[:-2] if callee.endswith("()") else callee
            text = f"{node.code or ''} {node.name or ''} {node.description or ''}"
            if node.code and "=" in node.code.split(callee, 1)[0]:
                lhs_calls.add(callee)
            args = _call_args(text, callee)
            seen.setdefault(callee, []).append(_split_args(args) if args else [])

    for diagram in diagrams:
        walk(diagram)
    out: dict[str, list[str]] = {}
    for name, calls in seen.items():
        counts = {len(c) for c in calls}
        if name not in bodies or name in lhs_calls or len(counts) != 1 or 0 in counts:
            continue
        decls = []
        for i in range(next(iter(counts))):
            is_fn = any(re.fullmatch(r"[A-Za-z_]\w*", c[i]) and c[i] in functions for c in calls)
            decls.append(f"void (*a{i})(void)" if is_fn else f"float64 a{i}")
        out[name] = decls
    return out


def _params(decls: list[str] | None) -> str:
    return ", ".join(decls) if decls else "void"


def _is_empty_helper(sub) -> bool:
    """True when every working node of a helper sub-diagram only calls the helper itself."""
    import re
    name = _helper_name(sub)
    structural = {ActivityNodeType.INITIAL, ActivityNodeType.FINAL, ActivityNodeType.MERGE,
                  ActivityNodeType.JOIN, ActivityNodeType.FORK}
    work = [n for n in sub.nodes if n.node_type not in structural]
    if not work:
        return True
    self_call = re.compile(rf"\b{re.escape(name)}\s*\(")
    return all(self_call.search(f"{n.code or ''} {n.name or ''}") or (n.callee or "") == name for n in work)


def _empty_helper_note(func: str) -> str:
    return f"/* TODO(design): the MUD calls {func}() but never describes its body */"


def _drop_unreachable_returns(body: list[str]) -> list[str]:
    """Remove a ``return;`` that directly follows another one (dead code)."""
    out: list[str] = []
    last_code = ""
    for line in body:
        code = line.split("/*", 1)[0].strip()
        if code == "return;" and last_code == "return;":
            continue
        out.append(line)
        if code:
            last_code = code
    return out


class CSkeletonExporter:
    """Export ActivityDiagram JSON to C-code skeleton files."""

    _helper_params: dict[str, list[str]] = {}    # replaced, never mutated (see _helper_signatures)
    _helper_params_all = None

    def export_diagram(self, diagram: ActivityDiagram, *, as_helper: bool = False) -> str:
        """Generate C skeleton code for a single ActivityDiagram.

        ``as_helper=True`` emits a ``static`` helper function body (used for
        sub-diagrams) without the repeated include/comment header.
        """
        lines: list[str] = []

        # A sub-diagram whose only content is a call to itself has no body worth generating:
        # drop it, so the parent keeps the design's full call (arguments + result) as an external helper.
        real_subs = [s for s in diagram.sub_diagrams if not _is_empty_helper(s)]
        if not as_helper:
            # Helpers that get a generated body (sub-diagrams) are called as void(void), or take the
            # parameters the design passes; any other helper keeps the design's call statement.
            self._helper_bodies = {_helper_name(sub) for sub in real_subs}
            if getattr(self, "_helper_params_all", None) is None:       # exported on its own, not via export_result
                self._helper_params = _helper_signatures([diagram])
            # Header comment
            lines.append(f"/* Generated from: {diagram.name} */")
            if diagram.source_requirements:
                lines.append(f"/* Requirements: {', '.join(diagram.source_requirements)} */")
            else:
                lines.append("/* TODO(trace): the design names no requirement IDs for this runnable */")
            if diagram.provenance:
                lines.append(f"/* Model: {diagram.provenance.ai_model}, confidence: {diagram.provenance.confidence} */")
            lines.append("")

            # Includes
            lines.append('#include "Rte_Type.h"')
            if diagram.owner_swc:
                lines.append(f'#include "Rte_{diagram.owner_swc}.h"')
            lines.append("")

            # Forward declare any helper functions from sub_diagrams
            # Helpers have external linkage so the unit tests can call (and link) them.
            for sub in real_subs:
                lines.append(f"void {_helper_name(sub)}({_params(self._helper_params.get(_helper_name(sub)))});"
                             "  /* see sub-diagram */")
            if real_subs:
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
        else:
            func_name = diagram.owner_runnable or diagram.name.replace(" Code Flow", "")
        lines.append(f"void {func_name}({_params(self._helper_params.get(func_name) if as_helper else None)})")
        lines.append("{")
        body: list[str] = []
        outer_func = getattr(self, "_current_func", None)
        self._current_func = func_name
        try:
            self._emit_body(diagram, body)
        finally:
            self._current_func = outer_func
        lines.extend(_drop_unreachable_returns(body))
        lines.append("}")
        lines.append("")

        # Emit sub-diagrams as helper functions — each helper once per export: a helper used by
        # two runnables is defined with the first and only declared with the second.
        emitted = getattr(self, "_emitted_helpers", None)
        for sub in real_subs:
            name = _helper_name(sub)
            if emitted is not None:
                if name in emitted:
                    continue
                emitted.add(name)
            lines.append("")
            lines.append(self.export_diagram(sub, as_helper=True))

        return "\n".join(lines)

    def export_result(self, result: GenerationResult) -> dict[str, str]:
        """Export all ActivityDiagrams in a GenerationResult.

        Returns: {diagram_name: c_code_string}
        """
        output: dict[str, str] = {}
        # The same runnable can be in the result more than once (a retried generation appends
        # its diagrams): the last one wins, as before, and only that one is exported.
        top: dict[str, ActivityDiagram] = {}
        for diagram in result.diagrams:
            if isinstance(diagram, ActivityDiagram) and not diagram.parent_diagram:
                name = diagram.name or "diagram"
                top[name.replace(" ", "_").replace("/", "_")] = diagram
        self._emitted_helpers = set()
        # One signature per helper across all runnables: a helper shared by two runnables is
        # defined once, so both must agree on its parameters.
        self._helper_params = self._helper_params_all = _helper_signatures(top.values())
        try:
            for safe_name, diagram in top.items():
                output[safe_name] = self.export_diagram(diagram)
        finally:
            self._emitted_helpers = None
            self._helper_params_all = None
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
            # The NEAREST common merge, not the alphabetically first id: with ids up to N_104, "N_100" sorts
            # before "N_24", which put everything between the two merges inside the first if-body.
            from collections import deque
            wanted = set(joins)
            seen: set[str] = set()
            queue = deque(targets)
            while queue:
                n = queue.popleft()
                if n in seen:
                    continue
                seen.add(n)
                if n in wanted:
                    return n
                queue.extend(outgoing.get(n, []))
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
            stmt = (node.code or node.name).rstrip(";")
            desc = _desc_comment(node.description, stmt)
            if trace_line:
                lines.append(f"{pad}{trace_line}")
            lines.append(f"{pad}{stmt};{desc}")

        elif node.node_type == ActivityNodeType.ACTION:
            stmt = (node.code or node.name).rstrip(";")
            if trace_line:
                lines.append(f"{pad}{trace_line}")
            if _is_self_call(stmt, getattr(self, "_current_func", None)):
                lines.append(f"{pad}{_empty_helper_note(self._current_func)}")
            elif not node.code and _is_step_title(stmt):
                # A step heading ("Guard", "Read inputs") is a label, not C: keep it as a comment.
                lines.append(f"{pad}/* {_safe_comment(stmt)} */")
            else:
                desc = _desc_comment(node.description, stmt)
                lines.append(f"{pad}{stmt};{desc}")

        elif node.node_type == ActivityNodeType.FUNCTION_CALL:
            callee = (node.callee or node.name or "").strip()
            if callee.endswith("()"):
                callee = callee[:-2]
            if trace_line:
                lines.append(f"{pad}{trace_line}")
            if callee and callee == getattr(self, "_current_func", None):
                # The sub-diagram only "calls itself": the MUD never described the helper's body.
                lines.append(f"{pad}{_empty_helper_note(callee)}")
            elif callee in self._helper_params and _call_args(f"{node.code or ''} {node.name or ''} {node.description or ''}", callee):
                # The helper takes the parameters the design passes: keep the call whole.
                args = _call_args(f"{node.code or ''} {node.name or ''} {node.description or ''}", callee)
                lines.append(f"{pad}{callee}({args});")
            elif node.code and callee not in getattr(self, "_helper_bodies", set()):
                # No body is generated here for this helper: keep the design's statement whole
                # (arguments and result), the helper is declared and stubbed as an external function.
                lines.append(f"{pad}{node.code.rstrip(';')};  /* external helper {callee}() */")
            else:
                # Helpers are emitted as void(void); say so when the design passed arguments or used
                # the result, so the dropped data flow is visible (and counted by the compile quality gate).
                design_text = f"{node.code or ''} {node.name or ''} {node.description or ''}"
                args = _call_args(design_text, callee)
                lhs = node.code.split("=", 1)[0].strip() if node.code and "=" in node.code.split(callee, 1)[0] else ""
                if args or lhs:
                    parts = []
                    if args:
                        parts.append(f"passes ({_safe_comment(args)})")
                    if lhs:
                        parts.append(f"assigns the result to {lhs}")
                    note = f"  /* TODO(args): the design {' and '.join(parts)} — {callee} is generated as void(void) */"
                else:
                    note = f"  /* -> {callee}() */"
                lines.append(f"{pad}{callee}();{note}")

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
                # When this decision's join is also the enclosing decision's join (an else-if chain), the
                # continuation belongs to the outer level: keep stop_at so it is not emitted inside the
                # inner else block (a write after "if a {..} else if b {..}" landed in the last else).
                if join is not None:
                    self._walk_node(join, node_map, outgoing, edge_guards, lines, indent, visited, stop_at=stop_at)
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
