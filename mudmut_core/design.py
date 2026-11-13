"""MUD (design half): requirements → plan → spec → review → activity → export.

Every function runs in-process against the mud-tool library; the orchestrator
is a cached singleton, so repeated calls share one backend/client.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

from mudmut_core import env


def _orchestrator():
    env.ensure_environment()
    env.export_provider_keys()
    from mudtool.api.dependencies import get_orchestrator
    return get_orchestrator()


# ── requirements ─────────────────────────────────────────────────────────────
def import_requirements(file_path: str | Path, column_mapping: Optional[dict[str, str]] = None):
    """Auto-detect the format and import a requirement file.

    ``column_mapping`` (optional) maps canonical fields (``req_id``, ``title``,
    ``description`` …) to the source column names, overriding auto-detection.
    """
    env.ensure_environment()
    from mudtool.importers.factory import ImporterFactory
    return ImporterFactory.import_file(Path(file_path), column_mapping=column_mapping or None)


def requirements_text(reqs) -> str:
    """Render a RequirementSet (or list of Requirement) to the AI input text.

    Format matches the web UI::

        [REQ-1] (functional) Title
          Description: text
    """
    items = reqs.requirements if hasattr(reqs, "requirements") else list(reqs)
    lines: list[str] = []
    for r in items:
        req_type = getattr(r.req_type, "value", str(r.req_type)) if getattr(r, "req_type", None) else "functional"
        lines.append(f"[{r.req_id}] ({req_type}) {r.title or ''}")
        lines.append(f"  Description: {r.description or ''}")
    return "\n".join(lines)


def requirements_to_dicts(reqs) -> list[dict[str, Any]]:
    """Serialize a RequirementSet (or list) to JSON-able dicts for persistence."""
    items = reqs.requirements if hasattr(reqs, "requirements") else list(reqs)
    out: list[dict[str, Any]] = []
    for r in items:
        d = r.model_dump() if hasattr(r, "model_dump") else dict(r)
        if "req_type" in d and hasattr(d["req_type"], "value"):
            d["req_type"] = d["req_type"].value
        out.append(d)
    return out


# ── module planning ──────────────────────────────────────────────────────────
async def plan_modules(text: str, temperature: float = 0.2):
    env.ensure_environment()
    from mudtool.ai.module_planner import ModulePlanner
    return await ModulePlanner(_orchestrator()).plan_modules(text, temperature=temperature)


# ── MUD spec ─────────────────────────────────────────────────────────────────
_STRAY_LANG_LINE_RE = re.compile(r"(?m)^(```[ \t]*(?:c|cpp|c\+\+)[ \t]*)\n[ \t]*(?:c|C|cpp|c\+\+)[ \t]*\n")


def clean_spec_markdown(markdown: str) -> str:
    """Drop the language tag the model repeats as the first line of a code block (``` c / ``c`` / ```).

    The stray line is not C, so it garbles the Section 7 steps and the reviewer reports the runnable as
    truncated. Only a line that is just the language name directly after the opening fence is removed.
    """
    return _STRAY_LANG_LINE_RE.sub(r"\1\n", markdown or "")


async def generate_mud_spec(
    module,
    requirements_text_: str,
    *,
    mode: str = "two_stage",
    progress: Optional[Callable[[dict], None]] = None,
) -> str:
    env.ensure_environment()
    from mudtool.ai.mud_spec_generator import MudSpecGenerator
    gen = MudSpecGenerator(_orchestrator())
    return await gen.generate_spec(
        swc_name=module.swc_name,
        description=module.description,
        asil=module.asil,
        runnables=module.runnables,
        req_ids=module.req_ids,
        requirements_text=requirements_text_,
        progress_callback=progress,
        pipeline_mode=mode,
    )


async def review_spec(
    module,
    requirements_text_: str,
    mud_spec_markdown: str,
    *,
    iteration: int = 1,
):
    env.ensure_environment()
    from mudtool.ai.mud_spec_generator import MudSpecGenerator
    gen = MudSpecGenerator(_orchestrator())
    return await gen.review_spec(
        swc_name=module.swc_name,
        asil=module.asil,
        req_ids=module.req_ids,
        requirements_text=requirements_text_,
        mud_spec_markdown=mud_spec_markdown,
        temperature=0.0,
        iteration=iteration,
    )


# ── per-runnable review repair ───────────────────────────────────────────────
# A review finding is fixed in the runnable it names, by rewriting only that runnable's "### RE_X" subsection.
# Rewriting the whole 25-38k-char spec in one answer hit the model's output cap and was discarded, so the
# findings stayed open (AEB r34-r38); a subsection is a few k chars, which also suits small models.
_SECTION7_HEAD_RE = re.compile(r"^##\s*7\b", re.M)
_NEXT_TOP_RE = re.compile(r"^##\s*\d", re.M)


def runnable_subsection(spec_md: str, name: str) -> tuple[int, int] | None:
    """(start, end) of the "### <name>" subsection inside Section 7, or None."""
    m7 = _SECTION7_HEAD_RE.search(spec_md or "")
    if not m7:
        return None
    nxt = _NEXT_TOP_RE.search(spec_md, m7.end())
    s7_end = nxt.start() if nxt else len(spec_md)
    m = re.search(rf"^###\s+{re.escape(name)}\b[^\n]*\n", spec_md[m7.end():s7_end], re.M)
    if not m:
        return None
    start = m7.end() + m.start()
    rest = spec_md[m7.end() + m.end():s7_end]
    m_next = re.search(r"^###\s+", rest, re.M)
    end = m7.end() + m.end() + (m_next.start() if m_next else len(rest))
    return start, end


def review_issues_by_runnable(review, names: list[str]) -> dict[str, list[str]]:
    """Errors and warnings of a review grouped by the Section 7 runnable they name (first mention wins)."""
    out: dict[str, list[str]] = {}
    for issue in getattr(review, "issues", []) or []:
        if getattr(issue, "severity", "") not in ("error", "warning"):
            continue
        text = f"{getattr(issue, 'section', '')} {getattr(issue, 'message', '')}"
        hit = next((n for n in names if re.search(rf"\b{re.escape(n)}\b", text)), None)
        if hit:
            out.setdefault(hit, []).append(f"[{issue.severity}] {issue.message}")
    # An uncovered requirement blocks approval on its own (deterministic rule); the reviewer's gap text
    # usually names the runnable that should implement it.
    for gap in getattr(review, "coverage_gaps", []) or []:
        hit = next((n for n in names if re.search(rf"\b{re.escape(n)}\b", str(gap))), None)
        if hit:
            out.setdefault(hit, []).append(f"[uncovered requirement] {gap}")
    return out


def _spec_model_chat(prompt: str, *, max_tokens: int = 6000) -> str:
    env.ensure_environment()
    from mudmut_core import agents
    from mudmut_core.llm import chat_blocking, get_providers
    st = agents.get_stages().get("mud_spec_generator", {})
    provider = get_providers().get(st.get("provider") or "ollama")
    if provider is None or not st.get("model"):
        return ""
    try:
        return chat_blocking(provider, st["model"], [{"role": "user", "content": prompt}],
                             max_tokens=max_tokens, temperature=0.1, timeout=300)
    except Exception as exc:  # noqa: BLE001 - a failed repair keeps the spec unchanged
        print(f"[mudmut_core] runnable repair call failed: {exc}")
        return ""


def repair_runnables_from_review(module, requirements_text_: str, spec_md: str, review,
                                 *, max_runnables: int = 4) -> tuple[str, list[str]]:
    """Rewrite only the Section 7 subsections the review's findings name. Returns (spec, repaired names).

    A subsection is replaced only when the answer is that runnable's subsection, the runnable keeps
    implementable logic and the deterministic spec check does not get worse."""
    from mudmut_core import spec_check
    names = [n for n in re.findall(r"^###\s+(RE_\w+)", spec_md or "", re.M)]
    grouped = review_issues_by_runnable(review, names)
    if not grouped:
        return spec_md, []
    m7 = _SECTION7_HEAD_RE.search(spec_md)
    context = spec_md[:m7.start()] if m7 else ""
    current, repaired = spec_md, []
    for name, issues in list(grouped.items())[:max_runnables]:
        span = runnable_subsection(current, name)
        if not span:
            continue
        old = current[span[0]:span[1]]
        prompt = (
            f"You maintain the MUD specification of {module.swc_name}. A reviewer found these problems in "
            f"runnable {name}:\n" + "\n".join(f"- {i}" for i in issues[:10]) +
            "\n\nRewrite ONLY the Section 7 subsection of " + name + " so every problem is fixed. Keep its format "
            "exactly: the '### " + name + "' heading, the // Reads / Writes / IRVs / CalPrm header comments, and "
            "numbered **N. Label** steps with ```c code blocks, one C statement per line, scalar locals only, "
            "status and value of a read kept apart (l_st = Rte_IrvRead(IRV_X, &l_x)), no reads of PP_ output ports, "
            "and only this runnable's own outputs written. Use only the ports, IRVs, CalPrm and DEM events "
            "declared in Sections 1-6. Return ONLY the subsection, starting with '### " + name + "'.\n\n"
            f"REQUIREMENTS:\n{requirements_text_[:12000]}\n\nSECTIONS 1-6 (declarations):\n{context[:20000]}\n\n"
            f"CURRENT SUBSECTION:\n{old}"
        )
        answer = _spec_model_chat(prompt)
        answer = re.sub(r"^```(?:markdown|md)?\s*\n|\n```\s*$", "", (answer or "").strip())
        if not re.match(rf"###\s+{re.escape(name)}\b", answer):
            print(f"[mudmut_core] runnable repair for {name}: answer is not the subsection ({answer[:60]!r})")
            continue
        candidate = current[:span[0]] + answer.rstrip() + "\n\n" + current[span[1]:]
        before = spec_check.check_spec(current, module.swc_name, getattr(module, "runnables", None))
        after = spec_check.check_spec(candidate, module.swc_name, getattr(module, "runnables", None))
        if (name in after["usable"] and len(after["usable"]) >= len(before["usable"])
                and spec_check.gap_count(after) <= spec_check.gap_count(before)):
            current = candidate
            repaired.append(name)
            print(f"[mudmut_core] runnable repair kept for {name} ({len(issues)} finding(s))")
        else:
            print(f"[mudmut_core] runnable repair rejected for {name}: gaps {spec_check.gap_count(before)} -> "
                  f"{spec_check.gap_count(after)}, usable {name in after['usable']}")
    return current, repaired


async def review_and_improve(
    module,
    requirements_text_: str,
    mud_spec_markdown: str,
    *,
    max_rounds: int = 1,
    progress: Optional[Callable[[dict], None]] = None,
):
    """Review the spec and, if not clean, regenerate + re-review up to ``max_rounds``.

    Returns ``(improved_markdown, review_result)``.
    """
    env.ensure_environment()
    from mudtool.ai.mud_spec_generator import MudSpecGenerator, build_unresolved_review, compare_review_results
    gen = MudSpecGenerator(_orchestrator())

    from mudmut_core import spec_check

    def _broken(prev: str, new: str) -> str:
        """Why a regeneration must not replace ``prev`` ('' when it may). An empty or cut-off rewrite was
        reviewed as 'specification body is empty' (r34: coverage 0 %, 5 errors) and became the verdict."""
        new_clean = clean_spec_markdown(new or "")
        if len(new_clean.strip()) < max(200, len(prev.strip()) // 2):
            return f"rewrite has {len(new_clean.strip())} chars (previous {len(prev.strip())})"
        return spec_check.rewrite_problem(prev, new_clean)

    review = await review_spec(module, requirements_text_, mud_spec_markdown, iteration=1)
    improved = mud_spec_markdown

    for round_no in range(max_rounds):
        if review.approved and review.error_count == 0 and review.warning_count == 0:
            break
        if progress:
            progress({"stage": "mud_review", "round": round_no + 1,
                      "errors": review.error_count, "warnings": review.warning_count})
        # First fix what the findings name, runnable by runnable (small answers, never cut off).
        patched, fixed_names = repair_runnables_from_review(module, requirements_text_, improved, review)
        if fixed_names:
            if progress:
                progress({"stage": "mud_review", "message": f"runnable repair: {', '.join(fixed_names)}"})
            improved = patched
            review = await review_spec(module, requirements_text_, improved, iteration=round_no + 2)
            continue
        candidate = await gen.regenerate_spec(
            swc_name=module.swc_name,
            asil=module.asil,
            requirements_text=requirements_text_,
            current_spec_markdown=improved,
            review=review,
            temperature=min(0.1, round_no * 0.05),
            progress_callback=progress,
        )
        problem = _broken(improved, candidate)
        if problem:
            if progress:
                progress({"stage": "mud_review", "message": f"regeneration discarded: {problem}"})
            break                                   # keep the previous spec AND the review that belongs to it
        improved = candidate
        post = await review_spec(module, requirements_text_, improved, iteration=round_no + 2)
        comparison = compare_review_results(review, post)
        review = post
        if comparison.get("repeated_issue_count", 0) > 0:
            unresolved = build_unresolved_review(comparison, post)
            candidate = await gen.regenerate_spec(
                swc_name=module.swc_name,
                asil=module.asil,
                requirements_text=requirements_text_,
                current_spec_markdown=improved,
                review=unresolved,
                temperature=0.15,
                progress_callback=progress,
                repair_attempt=True,
            )
            problem = _broken(improved, candidate)
            if problem:
                if progress:
                    progress({"stage": "mud_review", "message": f"repair regeneration discarded: {problem}"})
                break
            improved = candidate
            review = await review_spec(module, requirements_text_, improved, iteration=round_no + 3)

    return improved, review


def spec_check_issues(check: dict) -> list[tuple[str, str]]:
    """``(severity, message)`` repair instructions from :func:`mudmut_core.spec_check.check_spec`."""
    issues: list[tuple[str, str]] = []
    for runnable, names in (check.get("never_set") or {}).items():
        issues.append(("error", f"{runnable} reads {', '.join(names)} but never assigns it. Assign it earlier "
                                "in the same runnable (e.g. from an Rte_Read or an IRV) or remove the read."))
    for runnable, names in (check.get("undescribed_helpers") or {}).items():
        issues.append(("error", f"{runnable} calls {', '.join(n + '()' for n in names)} but the logic of these "
                                "functions is written nowhere. Replace each call with the C statements it "
                                "performs, inline in the step."))
    for runnable, ports in (check.get("whole_port_writes") or {}).items():
        issues.append(("error", f"{runnable} writes {', '.join(ports)} as a whole although Section 2.1 gives "
                                "it several data elements. Write each element: Rte_IWrite_<Port>_<DataElement>(value)."))
    for runnable, names in (check.get("unwritten_outputs") or {}).items():
        issues.append(("error", f"{runnable} declares {', '.join(names)} as its output(s) but no step writes them. "
                                "Write each one (Rte_IrvWrite / Rte_IWrite) on every path, or remove it from the header."))
    for runnable, names in (check.get("lost_state_locals") or {}).items():
        issues.append(("error", f"{runnable} keeps cross-cycle state in local(s) {', '.join(names)} (incremented each "
                                "call but never stored): a cyclic runnable starts with a fresh local, so the timer / "
                                "counter never advances. Read it from its IRV at the start and Rte_IrvWrite it back."))
    for item, writers in (check.get("multi_writers") or {}).items():
        issues.append(("error", f"{item} is written by several runnables ({', '.join(writers)}). Keep exactly one "
                                "writer (its producer); the others read it."))
    for runnable, names in (check.get("undeclared_irvs") or {}).items():
        issues.append(("error", f"{runnable} uses IRV(s) {', '.join(names)} that the Section 4 IRV table does not "
                                "declare. Add a row for each (type, producer, consumer) or use a declared IRV."))
    for runnable, names in (check.get("status_overwrites") or {}).items():
        issues.append(("error", f"{runnable} assigns the return STATUS of a read to the value it reads "
                                f"({', '.join(n + ' = Rte_...Read(..., &' + n + ')' for n in names)}): the status 0 "
                                "overwrites the value. Use a separate status local: l_st = Rte_IrvRead(IRV_X, &l_x);"))
    for runnable, ports in (check.get("output_reads") or {}).items():
        issues.append(("error", f"{runnable} reads its own provided output port(s) {', '.join(ports)}. An output "
                                "must not be read back: keep the value in an IRV and read the IRV instead."))
    for runnable, items in (check.get("stray_comments") or {}).items():
        issues.append(("error", f"{runnable} has broken comment markers ({'; '.join(items[:3])}). Every /* needs its */ "
                                "on the same line, and a step must be either a C statement or a comment, never a "
                                "comment fragment glued to code."))
    for runnable, items in (check.get("struct_locals") or {}).items():
        issues.append(("error", f"{runnable} uses struct-typed locals or member access on locals "
                                f"({'; '.join(items[:4])}). Replace each with one scalar local per element "
                                "(e.g. l_cmdPressure, l_cmdStatus) and write each element with its own "
                                "Rte_Write_<port>_<element>(...) call."))
    for name in check.get("missing_planned") or []:
        issues.append(("error", f"The module plan names runnable {name} but Section 7 has no '### {name}' entry "
                                "of its own (it was folded into another runnable as a sub-function). Add a "
                                f"'### {name}' subsection with its Guard / Read / Validate / Compute / Write steps "
                                "and call it from its parent, keeping all existing runnables unchanged."))
    for runnable in (check.get("placeholder") or []) + (check.get("empty") or []):
        issues.append(("error", f"{runnable} has no implementable pseudo-code steps. Write its Guard / Read / "
                                "Validate / Compute / Write steps as C statements."))
    return issues


async def repair_spec_from_check(
    module,
    requirements_text_: str,
    mud_spec_markdown: str,
    check: dict,
    *,
    progress: Optional[Callable[[dict], None]] = None,
) -> str:
    """One targeted regeneration that fixes the deterministic spec-check findings.

    Returns the (possibly unchanged) spec. The caller re-checks it and keeps the better one.
    """
    issues = spec_check_issues(check)
    if not issues:
        return mud_spec_markdown
    # Per runnable first: every spec-check message names its runnable, and a subsection rewrite is never cut
    # off. The whole-spec rewrite below was discarded in 2 of 3 spec-only samples (gaps 7 -> 21, 5 -> 5).
    from mudmut_core import spec_check as _sc
    findings = SimpleNamespace(issues=[SimpleNamespace(severity=s, section="7", message=m) for s, m in issues],
                               coverage_gaps=[])
    patched, fixed = repair_runnables_from_review(module, requirements_text_, mud_spec_markdown, findings,
                                                  max_runnables=7)
    if fixed:
        sc_patched = _sc.check_spec(patched, module.swc_name, getattr(module, "runnables", None))
        if not _sc.gap_count(sc_patched):
            return patched
        mud_spec_markdown, issues = patched, spec_check_issues(sc_patched)
    env.ensure_environment()
    from mudtool.ai.mud_spec_generator import MudSpecGenerator, ReviewIssue, SpecReviewResult
    gen = MudSpecGenerator(_orchestrator())
    review = SpecReviewResult(
        approved=False, coverage_pct=0,
        issues=[ReviewIssue(severity=s, section="7. Functional Description", message=m) for s, m in issues],
    )
    return await gen.regenerate_spec(
        swc_name=module.swc_name,
        asil=module.asil,
        requirements_text=requirements_text_,
        current_spec_markdown=mud_spec_markdown,
        review=review,
        temperature=0.1,
        progress_callback=progress,
        repair_attempt=True,
    )


# ── activity diagram ─────────────────────────────────────────────────────────
async def generate_activity(
    requirements,
    mud_spec_markdown: str,
    swc: str,
    *,
    use_ai: bool = True,
    progress: Optional[Callable[[dict], None]] = None,
):
    """Generate the Activity / Code-Flow diagram(s) from the MUD spec Section 7.

    ``use_ai=False`` skips the model and builds the flow deterministically from
    Section 7 (the same builder that is the fallback when the model fails).
    """
    env.ensure_environment()
    from mudtool.ai.activity_from_mud import _generate_activity_from_mud

    request = SimpleNamespace(
        mud_spec_markdown=mud_spec_markdown,
        module_context=swc,
        existing_swcs=None,
        temperature=0.1,
        autosar_compliant=True,
        # call_signature → node labels are C calls (Rte_Read_...(&l_x)), so the
        # exported skeleton keeps real statements instead of prose to be stubbed.
        activity_label_style="call_signature",
        activity_source="mud_spec",
        use_ai_activity=use_ai,
    )
    reqs = list(requirements.requirements) if hasattr(requirements, "requirements") else list(requirements)
    return await _generate_activity_from_mud(_orchestrator(), reqs, request, progress_callback=progress)


# ── export ───────────────────────────────────────────────────────────────────
def export(result) -> dict[str, Any]:
    """Export a GenerationResult to C skeletons and Mermaid (inline) diagrams."""
    env.ensure_environment()
    from mudtool.generator.c_skeleton_exporter import CSkeletonExporter
    from mudtool.generator.mermaid_exporter import MermaidExporter
    return {
        "c": CSkeletonExporter().export_result(result),
        "mermaid": MermaidExporter().export_result_inline(result),
    }


def run(coro):
    """Run an async coroutine to completion on the shared event loop."""
    from mudmut_core import aio
    return aio.run_sync(coro)
