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

    review = await review_spec(module, requirements_text_, mud_spec_markdown, iteration=1)
    improved = mud_spec_markdown

    for round_no in range(max_rounds):
        if review.approved and review.error_count == 0 and review.warning_count == 0:
            break
        if progress:
            progress({"stage": "mud_review", "round": round_no + 1,
                      "errors": review.error_count, "warnings": review.warning_count})
        improved = await gen.regenerate_spec(
            swc_name=module.swc_name,
            asil=module.asil,
            requirements_text=requirements_text_,
            current_spec_markdown=improved,
            review=review,
            temperature=min(0.1, round_no * 0.05),
            progress_callback=progress,
        )
        post = await review_spec(module, requirements_text_, improved, iteration=round_no + 2)
        comparison = compare_review_results(review, post)
        review = post
        if comparison.get("repeated_issue_count", 0) > 0:
            unresolved = build_unresolved_review(comparison, post)
            improved = await gen.regenerate_spec(
                swc_name=module.swc_name,
                asil=module.asil,
                requirements_text=requirements_text_,
                current_spec_markdown=improved,
                review=unresolved,
                temperature=0.15,
                progress_callback=progress,
                repair_attempt=True,
            )
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
