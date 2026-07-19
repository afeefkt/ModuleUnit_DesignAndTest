"""Deterministic normalization for Section 7 runnable pseudo-code blocks.

This pass is intentionally conservative:
- only Section 7 runnable bodies are rewritten
- explicit control-flow syntax is normalized into machine-stable lines
- ambiguous prose is preserved and reported, not upgraded into invented logic
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


@dataclass
class Section7RunnableReport:
    runnable_name: str
    changed: bool
    warnings: list[str] = field(default_factory=list)
    control_structures: list[str] = field(default_factory=list)
    mixed_rewrites: int = 0
    ambiguous_lines: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Section7NormalizationResult:
    normalized_markdown: str
    warnings: list[str] = field(default_factory=list)
    runnable_reports: list[Section7RunnableReport] = field(default_factory=list)
    changed: bool = False
    succeeded: bool = True

    @property
    def normalized_runnable_count(self) -> int:
        return len(self.runnable_reports)

    @property
    def changed_runnable_count(self) -> int:
        return sum(1 for report in self.runnable_reports if report.changed)

    @property
    def warning_count(self) -> int:
        return len(self.warnings) + sum(len(report.warnings) for report in self.runnable_reports)

    def to_dict(self) -> dict:
        return {
            "normalized_markdown": self.normalized_markdown,
            "warnings": list(self.warnings),
            "runnable_reports": [report.to_dict() for report in self.runnable_reports],
            "changed": self.changed,
            "succeeded": self.succeeded,
            "normalized_runnable_count": self.normalized_runnable_count,
            "changed_runnable_count": self.changed_runnable_count,
            "warning_count": self.warning_count,
        }

    def summary(self) -> dict:
        return {
            "changed": self.changed,
            "succeeded": self.succeeded,
            "normalized_runnable_count": self.normalized_runnable_count,
            "changed_runnable_count": self.changed_runnable_count,
            "warning_count": self.warning_count,
        }


_SECTION_HEADING_RE = re.compile(
    r"(?ms)^##\s+7\.\s+Functional Description\s*$\n?(?P<body>.*?)(?=^##\s+\d+\.|\Z)"
)
_RUNNABLE_HEADING_RE = re.compile(r"(?m)^###\s+(.+?)\s*$")
_NUMBERED_STEP_RE = re.compile(r"^(?P<indent>\s*)(?P<num>\d+(?:\.\d+)*)\.\s+(?P<body>.*)$")
_CONTROL_PREFIXES = ("if ", "if(", "else if ", "else if(", "else", "while ", "while(", "for ", "for(", "switch ", "switch(", "case ", "default", "return")


def normalize_section7_markdown(markdown: str) -> Section7NormalizationResult:
    match = _SECTION_HEADING_RE.search(markdown or "")
    if not match:
        return Section7NormalizationResult(
            normalized_markdown=markdown or "",
            warnings=[],
            runnable_reports=[],
            changed=False,
            succeeded=True,
        )

    section_body = match.group("body")
    runnable_sections = _extract_runnable_sections(section_body)
    if not runnable_sections:
        return Section7NormalizationResult(
            normalized_markdown=markdown or "",
            warnings=[],
            runnable_reports=[],
            changed=False,
            succeeded=True,
        )

    rebuilt_parts: list[str] = []
    overall_warnings: list[str] = []
    reports: list[Section7RunnableReport] = []

    for heading, body in runnable_sections:
        normalized_body, report = _normalize_runnable_body(heading, body)
        rebuilt_parts.append(f"### {heading}\n{normalized_body}".rstrip())
        overall_warnings.extend(f"{heading}: {warning}" for warning in report.warnings)
        reports.append(report)

    rebuilt_section = "## 7. Functional Description\n\n" + "\n\n".join(rebuilt_parts).rstrip() + "\n"
    normalized_markdown = markdown[: match.start()] + rebuilt_section + markdown[match.end() :]
    changed = normalized_markdown != (markdown or "")

    return Section7NormalizationResult(
        normalized_markdown=normalized_markdown,
        warnings=overall_warnings,
        runnable_reports=reports,
        changed=changed,
        succeeded=True,
    )


def _extract_runnable_sections(section_body: str) -> list[tuple[str, str]]:
    matches = list(_RUNNABLE_HEADING_RE.finditer(section_body or ""))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_body)
        heading = match.group(1).strip()
        body = section_body[start:end].strip("\n")
        sections.append((heading, body))
    return sections


def _normalize_runnable_body(runnable_name: str, body: str) -> tuple[str, Section7RunnableReport]:
    warnings: list[str] = []
    control_structures: set[str] = set()
    mixed_rewrites = 0
    ambiguous_lines = 0
    changed = False

    lines = [line.rstrip() for line in (body or "").splitlines()]
    output_lines: list[str] = []
    blank_pending = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            blank_pending = True
            continue
        if blank_pending and output_lines and not output_lines[-1].startswith("//"):
            output_lines.append("")
        blank_pending = False

        if stripped.startswith("//"):
            output_lines.append(stripped)
            continue

        normalized_line, line_changed = _canonicalize_calls(line)
        line_changed = bool(line_changed)
        numbered = _NUMBERED_STEP_RE.match(normalized_line)

        if numbered:
            top_prefix = f"{numbered.group('num')}. "
            body_text = numbered.group("body").strip()
            body_lines, body_changed, body_mixed, body_ambiguous, body_controls, body_warnings = _normalize_statement_block(
                body_text,
                base_indent=1,
                allow_header_split=True,
            )
            mixed_rewrites += body_mixed
            ambiguous_lines += body_ambiguous
            control_structures.update(body_controls)
            warnings.extend(body_warnings)
            if body_lines:
                output_lines.append(f"{top_prefix}{body_lines[0]}")
                output_lines.extend(body_lines[1:])
            else:
                output_lines.append(f"{top_prefix}{body_text}")
            changed = changed or line_changed or body_changed or normalized_line != line
            continue

        body_lines, body_changed, body_mixed, body_ambiguous, body_controls, body_warnings = _normalize_statement_block(
            normalized_line.strip(),
            base_indent=_leading_indent_units(normalized_line),
            allow_header_split=False,
        )
        mixed_rewrites += body_mixed
        ambiguous_lines += body_ambiguous
        control_structures.update(body_controls)
        warnings.extend(body_warnings)
        output_lines.extend(body_lines or [normalized_line.strip()])
        changed = changed or line_changed or body_changed or normalized_line.strip() != stripped

    cleaned = _collapse_blank_lines(output_lines).strip()
    report = Section7RunnableReport(
        runnable_name=runnable_name,
        changed=(cleaned != (body or "").strip()),
        warnings=_dedupe_preserve_order(warnings),
        control_structures=sorted(control_structures),
        mixed_rewrites=mixed_rewrites,
        ambiguous_lines=ambiguous_lines,
    )
    return cleaned, report


def _normalize_statement_block(
    text: str,
    *,
    base_indent: int,
    allow_header_split: bool,
) -> tuple[list[str], bool, int, int, set[str], list[str]]:
    warnings: list[str] = []
    control_structures: set[str] = set()
    changed = False
    mixed_rewrites = 0
    ambiguous_lines = 0

    text = (text or "").strip()
    if not text:
        return [], False, 0, 0, set(), []

    if allow_header_split:
        header, tail = _split_header_from_inline_code(text)
        if header is not None and tail is not None:
            formatted_tail, tail_changed, tail_controls = _format_code_like_text(tail, base_indent=base_indent + 1)
            if formatted_tail:
                control_structures.update(tail_controls)
                mixed_rewrites += 1
                return [header] + formatted_tail, True or tail_changed, mixed_rewrites, 0, control_structures, warnings

    if text.lower().startswith("otherwise ") or text.lower().startswith("otherwise,"):
        action = re.sub(r"(?i)^otherwise[:,]?\s*", "", text).strip()
        if action:
            mixed_rewrites += 1
            changed = True
            return (
                ["Else", f"{'   ' * base_indent}{action}"],
                changed,
                mixed_rewrites,
                0,
                control_structures,
                warnings,
            )

    formatted, formatted_changed, found_controls = _format_code_like_text(text, base_indent=base_indent)
    if formatted:
        control_structures.update(found_controls)
        changed = formatted_changed or formatted != [text]
        return formatted, changed, mixed_rewrites, ambiguous_lines, control_structures, warnings

    if _looks_mixed_prose_and_code(text):
        ambiguous_lines += 1
        warnings.append(_describe_ambiguous_line(text))

    return [f"{'   ' * max(base_indent - 1, 0)}{text}" if base_indent > 0 else text], changed, mixed_rewrites, ambiguous_lines, control_structures, warnings


def _split_header_from_inline_code(text: str) -> tuple[str | None, str | None]:
    for index in range(len(text) - 1, -1, -1):
        if text[index] != ":":
            continue
        header = text[:index].strip()
        tail = text[index + 1 :].strip()
        if not header or not tail:
            continue
        if _looks_control_or_call(header):
            continue
        if not (_starts_explicit_code_structure(tail) or _looks_code_sequence(tail)):
            continue
        return f"{header}:", tail
    return None, None


def _format_code_like_text(text: str, *, base_indent: int) -> tuple[list[str], bool, set[str]]:
    tokens = _tokenize_code_like_text(text)
    if len(tokens) <= 1 and not _looks_control_or_call(tokens[0] if tokens else text):
        return [], False, set()

    lines: list[str] = []
    indent_level = base_indent
    control_structures: set[str] = set()

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        lower = token.lower()
        if token == "}":
            indent_level = max(base_indent, indent_level - 1)
            lines.append(f"{'   ' * indent_level}}}")
            continue
        if lower.startswith("else if"):
            control_structures.add("else_if")
        elif lower.startswith("if"):
            control_structures.add("if")
        elif lower.startswith("else"):
            control_structures.add("else")
        elif lower.startswith("while"):
            control_structures.add("while")
        elif lower.startswith("for"):
            control_structures.add("for")
        elif lower.startswith("switch"):
            control_structures.add("switch")
        elif lower.startswith("case"):
            control_structures.add("case")
        elif lower.startswith("default"):
            control_structures.add("default")
        elif lower.startswith("return"):
            control_structures.add("return")

        lines.append(f"{'   ' * indent_level}{token}")
        if token.endswith("{"):
            indent_level += 1

    return lines, len(lines) > 1 or "".join(token.strip() for token in tokens) != text.strip(), control_structures


def _tokenize_code_like_text(text: str) -> list[str]:
    working = (text or "").strip()
    working = re.sub(r"}\s*else\s+if", "}\nelse if", working, flags=re.IGNORECASE)
    working = re.sub(r"}\s*else\b", "}\nelse", working, flags=re.IGNORECASE)

    tokens: list[str] = []
    current: list[str] = []
    paren_depth = 0

    def flush_current(*, attach_brace: bool = False) -> None:
        if not current:
            return
        token = "".join(current).strip()
        current.clear()
        if not token:
            return
        if attach_brace:
            token = token + " {"
        tokens.append(token)

    for char in working:
        if char == "(":
            paren_depth += 1
            current.append(char)
            continue
        if char == ")":
            paren_depth = max(paren_depth - 1, 0)
            current.append(char)
            continue
        if char == "{" and paren_depth == 0:
            flush_current(attach_brace=True)
            continue
        if char == "}" and paren_depth == 0:
            flush_current()
            tokens.append("}")
            continue
        if char == ";" and paren_depth == 0:
            current.append(char)
            flush_current()
            continue
        if char == "\n" and paren_depth == 0:
            flush_current()
            continue
        current.append(char)

    flush_current()
    return [token for token in tokens if token]


def _canonicalize_calls(text: str) -> tuple[str, bool]:
    replacements = (
        (r"\bRte[_ ]?IRead\b", "Rte_IRead"),
        (r"\bRte[_ ]?IWrite\b", "Rte_IWrite"),
        (r"\bRte[_ ]?Read\b", "Rte_Read"),
        (r"\bRte[_ ]?Write\b", "Rte_Write"),
        (r"\bRte[_ ]?Call\b", "Rte_Call"),
        (r"\bRte[_ ]?Result\b", "Rte_Result"),
        (r"\bDem[_ ]?ReportErrorStatus\b", "Dem_ReportErrorStatus"),
        (r"\bDem[_ ]?SetEventStatus\b", "Dem_SetEventStatus"),
    )
    original = text
    updated = text
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, updated)
    return updated, updated != original


def _looks_code_like(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    if _looks_control_or_call(candidate):
        return True
    return bool(
        re.search(r"\b(?:Rte_[A-Za-z]\w*|Dem_[A-Za-z]\w*|return|SAFE_STATE)\b", candidate)
        or re.search(r"[=!<>]=|[<>]|&&|\|\|", candidate)
        or ("(" in candidate and ")" in candidate and ";" in candidate)
    )


def _starts_explicit_code_structure(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    lowered = candidate.lower()
    return lowered.startswith(_CONTROL_PREFIXES) or candidate.startswith(("Rte_", "Dem_"))


def _looks_code_sequence(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    if ";" in candidate and _looks_code_like(candidate):
        return True
    helper_call = re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)\s*;?", candidate)
    assignment = re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", candidate)
    return bool(helper_call or assignment)


def _looks_control_or_call(text: str) -> bool:
    candidate = (text or "").strip().lower()
    if not candidate:
        return False
    return candidate.startswith(_CONTROL_PREFIXES) or candidate.startswith(("rte_", "dem_"))


def _looks_mixed_prose_and_code(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    has_words = bool(re.search(r"[A-Za-z]{4,}", candidate))
    has_code = _looks_code_like(candidate)
    return has_words and has_code and not _looks_control_or_call(candidate)


def _describe_ambiguous_line(text: str) -> str:
    candidate = (text or "").strip()
    if ":" in candidate and _looks_code_like(candidate):
        return "left mixed prose/code line unchanged because header + inline code structure was ambiguous"
    if re.search(r"\botherwise\b", candidate, flags=re.IGNORECASE):
        return "left mixed prose/code line unchanged because implied else structure was ambiguous"
    return "left mixed prose/code line unchanged because structure was ambiguous"


def _leading_indent_units(text: str) -> int:
    spaces = len(text) - len(text.lstrip(" "))
    return max(1, spaces // 3 + 1)


def _collapse_blank_lines(lines: list[str]) -> str:
    collapsed: list[str] = []
    previous_blank = False
    for line in lines:
        if not line.strip():
            if not previous_blank:
                collapsed.append("")
            previous_blank = True
            continue
        collapsed.append(line.rstrip())
        previous_blank = False
    return "\n".join(collapsed)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


# ── Prose-detection gate (UI-D) ───────────────────────────────────────────────

_PROSE_SENTENCE_RE = re.compile(
    r"^[A-Z][a-z][\w ,'\-]+\.?\s*$"   # capitalised English sentence, no C operators
)


def _step_body_is_pure_prose(code: str) -> bool:
    """Return True if the step code block contains no C constructs — only prose.

    A step is pure prose when ALL of the following are true:
    - No Rte_/Dem_/WdgM_ API call
    - No C operators (=, ==, !=, >=, <=, <, >, &&, ||, !)
    - No control keyword (if, else, return, switch, while, for)
    - No semicolons
    """
    s = (code or "").strip()
    if not s:
        return True   # empty code body — treat as pure prose
    has_api   = bool(re.search(r"\b(?:Rte_|Dem_|WdgM_)[A-Za-z]", s))
    has_op    = bool(re.search(r"[=!<>]=|[<>!]|&&|\|\||;", s))
    has_ctrl  = bool(re.search(r"\b(?:if|else|return|switch|while|for)\s*[\(\{]?", s))
    has_assign = bool(re.search(r"[A-Za-z_]\w*\s*=\s*\S", s))
    return not (has_api or has_op or has_ctrl or has_assign)


def detect_pure_prose_steps(section7_markdown: str) -> list[dict]:
    """Scan Section 7 markdown for steps whose code body is pure English prose.

    Returns a list of dicts: {runnable, step_num, label, code_preview}.
    An empty list means all steps look code-like (good).

    This is called from MudSpecGenerator._apply_section7_normalization() and
    the result is surfaced as warnings in the SSE event so the UI can show a
    "⚠ N steps look like prose — regenerate recommended" badge.
    """
    match = _SECTION_HEADING_RE.search(section7_markdown or "")
    if not match:
        return []

    body = match.group("body")
    # Split into runnable sections
    runnable_chunks = re.split(r"(?m)^###\s+", body)
    flagged: list[dict] = []

    for chunk in runnable_chunks:
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        runnable_name = lines[0].strip() if lines else "?"
        current_num: str = ""
        current_label: str = ""
        code_lines: list[str] = []

        def _flush() -> None:
            if not current_num:
                return
            code = "\n".join(code_lines).strip()
            if _step_body_is_pure_prose(code):
                flagged.append({
                    "runnable": runnable_name,
                    "step_num": current_num,
                    "label": current_label,
                    "code_preview": (code[:80] + "…") if len(code) > 80 else code or "(empty)",
                })

        for line in lines[1:]:
            m = _NUMBERED_STEP_RE.match(line)
            if m:
                _flush()
                current_num = m.group("num")
                current_label = m.group("body").strip()
                code_lines = []
            elif current_num:
                code_lines.append(line)

        _flush()

    return flagged
