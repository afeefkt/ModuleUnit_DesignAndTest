"""Mermaid Syntax Linter - validates generated Mermaid text before export.

Pure Python, zero external dependencies. Catches common issues that cause
silent blank rendering in the web UI or malformed draw.io exports.

Pipeline position:
    ... → Validate → [Mermaid Lint] → Trace → Export → Visual QA
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from mudtool.models.json_uml import DiagramType


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class LintResult:
    """Result of a Mermaid syntax lint pass."""
    diagram_key: str
    diagram_type: str
    valid: bool = True
    errors: list[str] = field(default_factory=list)    # Blocking - won't render
    warnings: list[str] = field(default_factory=list)  # Non-blocking - may look wrong
    auto_fixed: bool = False                            # True if fixed_text differs
    fixed_text: Optional[str] = None                   # Auto-corrected Mermaid text

    def to_summary(self) -> dict:
        return {
            "diagram_key": self.diagram_key,
            "diagram_type": self.diagram_type,
            "valid": self.valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "auto_fixed": self.auto_fixed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ── Linter ────────────────────────────────────────────────────────────────────

class MermaidLinter:
    """Validates and auto-corrects Mermaid diagram text.

    Checks:
      - Correct diagram type declaration header
      - Defined vs referenced node IDs (orphan edge detection)
      - Decision nodes have ≥ 2 outgoing edges
      - Start / End nodes present (activity diagrams)
      - Linear-only structure warning (no branching despite decision nodes)
      - Common parser-breaking characters in labels
      - State machine initial state ([*] --> ...) present
      - Sequence diagram undeclared participants

    Auto-fixes:
      - C logical-or (||) in edge labels → " OR "
      - Invalid 'title' keyword in stateDiagram-v2
      - graph TD → flowchart TD for activity diagrams
      - Excess blank lines
    """

    # Mermaid reserved words - do not flag as undefined nodes
    _KEYWORDS = frozenset({
        "classDef", "class", "subgraph", "end", "style",
        "linkStyle", "flowchart", "graph", "sequenceDiagram",
        "stateDiagram", "classDiagram", "direction",
    })

    # Expected diagram header patterns per type
    _HEADERS: dict[DiagramType, re.Pattern] = {
        DiagramType.ACTIVITY:      re.compile(r"^flowchart\s+(TD|LR|TB|BT|RL)", re.IGNORECASE),
        DiagramType.SEQUENCE:      re.compile(r"^sequenceDiagram", re.IGNORECASE),
        DiagramType.STATE_MACHINE: re.compile(r"^stateDiagram", re.IGNORECASE),
        DiagramType.CLASS:         re.compile(r"^classDiagram", re.IGNORECASE),
        DiagramType.COMPONENT:     re.compile(r"^graph\s+(TD|LR|TB|BT|RL)", re.IGNORECASE),
    }

    def lint(
        self,
        mermaid_text: str,
        diagram_type: DiagramType,
        diagram_key: str = "",
    ) -> LintResult:
        """Lint Mermaid text for a given diagram type.

        Always returns a LintResult. If the text is empty, sets valid=False
        immediately. Otherwise runs header + type-specific checks then auto-fix.
        """
        result = LintResult(
            diagram_key=diagram_key,
            diagram_type=diagram_type.value,
        )

        if not mermaid_text or not mermaid_text.strip():
            result.valid = False
            result.errors.append(
                "Empty Mermaid text - diagram generation produced no renderable output."
            )
            return result

        text = mermaid_text.strip()

        # 1. Header check
        result = self._check_header(text, diagram_type, result)
        if not result.valid:
            # Can't do structural checks without a valid header
            result.fixed_text = self._auto_fix(text, diagram_type)
            result.auto_fixed = result.fixed_text != text
            return result

        # 2. Type-specific structural checks
        if diagram_type == DiagramType.ACTIVITY:
            result = self._check_flowchart(text, result)
        elif diagram_type == DiagramType.SEQUENCE:
            result = self._check_sequence(text, result)
        elif diagram_type == DiagramType.STATE_MACHINE:
            result = self._check_state_machine(text, result)
        elif diagram_type == DiagramType.COMPONENT:
            result = self._check_flowchart(text, result)  # graph TD same rules

        # 3. Auto-fix
        fixed = self._auto_fix(text, diagram_type)
        if fixed != text:
            result.fixed_text = fixed
            result.auto_fixed = True

        return result

    def lint_all(
        self,
        diagrams: dict[str, str],
        diagram_type_map: Optional[dict[str, DiagramType]] = None,
    ) -> dict[str, LintResult]:
        """Lint all diagrams in a key→mermaid_text dict.

        diagram_type_map maps key → DiagramType.
        If not provided, type is inferred from the key prefix.
        """
        results: dict[str, LintResult] = {}
        for key, text in diagrams.items():
            if diagram_type_map and key in diagram_type_map:
                dt = diagram_type_map[key]
            else:
                prefix = key.split("_")[0]
                try:
                    dt = DiagramType(prefix)
                except ValueError:
                    dt = DiagramType.ACTIVITY
            results[key] = self.lint(text, dt, diagram_key=key)
        return results

    # ── Header check ─────────────────────────────────────────────────────────

    def _check_header(
        self, text: str, diagram_type: DiagramType, result: LintResult
    ) -> LintResult:
        pattern = self._HEADERS.get(diagram_type)
        if pattern and not pattern.match(text):
            # Attempt to detect the actual header for a better error message
            first_line = text.splitlines()[0].strip()
            result.valid = False
            result.errors.append(
                f"Invalid diagram header: got '{first_line[:60]}' - "
                f"expected {diagram_type.value} diagram "
                f"(e.g. '{list(self._HEADERS[diagram_type].pattern.split('|')[0][:20])}…')."
            )
        return result

    # ── Flowchart (activity / component) ─────────────────────────────────────

    def _check_flowchart(self, text: str, result: LintResult) -> LintResult:
        content_lines = [
            line for line in text.splitlines()
            if line.strip() and not line.strip().startswith("%%")
            and not line.strip().startswith("classDef")
            and not line.strip().startswith("class ")
        ]

        # ── Collect defined node IDs ──────────────────────────────────────────
        # Node declaration patterns: id[...], id{...}, id(...), id[[...]], id[/...], id((..))
        node_decl_re = re.compile(
            r"^\s+(\w+)\s*(?:"
            r"\[{1,2}[^\]]*\]{1,2}"   # [...] or [[...]]
            r"|\{[^}]*\}"              # {...}
            r"|\([^)]*\)"              # (...)
            r"|>\s*[^\]]*\]"           # >[...]
            r"|/[^/]*/?"              # /.../
            r"|\(\([^)]*\)\)"          # ((...))
            r")"
        )
        defined_ids: set[str] = set()
        for line in content_lines:
            m = node_decl_re.match(line)
            if m:
                nid = m.group(1)
                if nid not in self._KEYWORDS:
                    defined_ids.add(nid)

        # ── Collect referenced IDs from edges ─────────────────────────────────
        # Handles: A --> B, A -->|label| B, A -- text --> B
        edge_re = re.compile(r"\b(\w+)\s*(?:--[->|]+(?:\|[^|]*\|)?\s*(\w+))")
        referenced: set[str] = set()
        for line in content_lines:
            for m in edge_re.finditer(line):
                src = m.group(1)
                tgt = m.group(2)
                if src and src not in self._KEYWORDS:
                    referenced.add(src)
                if tgt and tgt not in self._KEYWORDS:
                    referenced.add(tgt)

        # ── Undefined node check ──────────────────────────────────────────────
        undefined = referenced - defined_ids
        if undefined:
            result.valid = False
            result.errors.append(
                f"Edge(s) reference undefined node ID(s): {', '.join(sorted(undefined))} "
                "- Mermaid will ignore these edges (likely missing node declarations)."
            )

        # ── Start / End presence ──────────────────────────────────────────────
        has_start = bool(re.search(r"[Ss]tart", text))
        has_end = bool(re.search(r"\bEnd\b", text))
        if not has_start:
            result.warnings.append(
                "No 'Start' node detected - activity diagram should begin with a Start node."
            )
        if not has_end:
            result.warnings.append(
                "No 'End' node detected - activity diagram should terminate with an End node."
            )

        # ── Decision node branch count check ─────────────────────────────────
        decision_re = re.compile(r"^\s+(\w+)\{")
        decision_ids: set[str] = set()
        for line in content_lines:
            m = decision_re.match(line)
            if m:
                decision_ids.add(m.group(1))

        for did in decision_ids:
            outgoing = re.findall(
                rf"^\s+{re.escape(did)}\s*-->", text, re.MULTILINE
            )
            if len(outgoing) < 2:
                result.warnings.append(
                    f"Decision node '{did}' has only {len(outgoing)} outgoing edge(s) "
                    f"- need at least 2 (Yes/No or True/False branches)."
                )

        # ── Linear-structure warning ──────────────────────────────────────────
        if decision_ids:
            total_edges = len(re.findall(r"-->", text))
            if total_edges > 0 and total_edges <= len(defined_ids):
                result.warnings.append(
                    f"Diagram has {len(decision_ids)} decision node(s) but only "
                    f"{total_edges} edge(s) for {len(defined_ids)} node(s) - "
                    "branching paths may be missing."
                )

        return result

    # ── Sequence ─────────────────────────────────────────────────────────────

    def _check_sequence(self, text: str, result: LintResult) -> LintResult:
        declared = set(re.findall(r"^\s*participant\s+(\w+)", text, re.MULTILINE))
        # Messages: A->>B or A-->B or A->B
        msg_re = re.compile(r"\b(\w+)\s*[-=]{1,2}>+\s*(\w+)\s*:", re.MULTILINE)
        used: set[str] = set()
        for m in msg_re.finditer(text):
            used.add(m.group(1))
            used.add(m.group(2))

        common_kw = {"Note", "loop", "alt", "else", "opt", "par", "critical", "break", "end"}
        used -= common_kw

        undefined = used - declared
        if undefined:
            result.warnings.append(
                f"Sequence uses undeclared participant(s): {', '.join(sorted(undefined))} "
                "- declare them with 'participant X as X' at the top."
            )

        if not declared:
            result.errors.append(
                "No 'participant' declarations found - sequence diagram will be empty."
            )
            result.valid = False

        return result

    # ── State Machine ─────────────────────────────────────────────────────────

    def _check_state_machine(self, text: str, result: LintResult) -> LintResult:
        if "[*]" not in text:
            result.errors.append(
                "State machine has no initial state - "
                "Mermaid requires '[*] --> StateName' to mark the entry point."
            )
            result.valid = False

        # Check for at least one transition
        transitions = re.findall(r"--\s*>", text)
        if len(transitions) < 2:
            result.warnings.append(
                f"Only {len(transitions)} transition(s) detected - "
                "state machine diagrams should have multiple transitions."
            )

        return result

    # ── Auto-fix ──────────────────────────────────────────────────────────────

    def _auto_fix(self, text: str, diagram_type: DiagramType) -> str:
        fixed = text

        # Fix 1: C logical-or in edge guard labels (|| breaks flowchart parser)
        fixed = re.sub(r"-->\|(.*?)\|\|", r"-->|\1 OR |", fixed)
        fixed = re.sub(r"\|\|(.*?)\|", r"| OR \1|", fixed)

        # Fix 2: 'title' keyword is not valid in stateDiagram-v2
        if diagram_type == DiagramType.STATE_MACHINE:
            fixed = re.sub(r"^\s*title\s+.*$", "", fixed, flags=re.MULTILINE)

        # Fix 3: 'graph TD' → 'flowchart TD' for activity diagrams
        if diagram_type == DiagramType.ACTIVITY and fixed.strip().startswith("graph TD"):
            fixed = fixed.replace("graph TD", "flowchart TD", 1)

        # Fix 4: Unescaped parentheses in bare labels (common AI mistake)
        # Matches:  nodeId[some (text) here]  →  nodeId["some (text) here"]
        fixed = re.sub(
            r'(\w+)\[([^"\]]*\([^"\]]*\)[^"\]]*)\]',
            lambda m: f'{m.group(1)}["{m.group(2)}"]',
            fixed,
        )

        # Fix 5: Collapse excess blank lines
        fixed = re.sub(r"\n{3,}", "\n\n", fixed)

        return fixed.strip()
