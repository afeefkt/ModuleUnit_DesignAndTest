"""Flow-chart quality score for the generated activity diagrams.

Scores an activity ``GenerationResult`` against the MUD spec's Section 7 and the module's
requirements, combines it with an optional AI judge and an optional render check, and gates at 80 %.

Deterministic parts (each 0-100):
- ``structure``    — initial/final nodes, reachability, decision branching, dangling edges
- ``requirements`` — fraction of the module's requirement IDs that appear on a node/diagram
- ``fidelity``     — fraction of the spec's Section 7 statements present on some node

Optional parts:
- ``render`` — 100 when the diagram renders to an image, 0 when it cannot (only when ``render`` is given)
- ``judge``  — an AI judge's 0-100 score (50 % of the total when present)

Score = mean of the deterministic parts; if a judge is present, score = (deterministic + judge) / 2.
Pass = score >= 80. Nothing here claims requirement *verification* — it scores the design.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional

from mudtool.models.json_uml import ActivityDiagram, ActivityNodeType, GenerationResult

THRESHOLD = 80


# ── normalization helpers ─────────────────────────────────────────────────────
def _norm(text: str) -> str:
    """Whitespace-collapsed, trailing-semicolon-stripped form for fuzzy statement matching."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if t.endswith(";"):
        t = t[:-1].rstrip()
    return t


def _list_of(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(x) for x in value]
    return [str(value)]


# ── deterministic checks ──────────────────────────────────────────────────────
def _activity_diagrams(result: GenerationResult) -> list[ActivityDiagram]:
    return [d for d in result.diagrams if isinstance(d, ActivityDiagram)]


def structure_score(diagrams: list[ActivityDiagram]) -> tuple[float, list[str]]:
    score = 100.0
    problems: list[str] = []
    for d in diagrams:
        node_ids = {n.id for n in d.nodes}
        initials = [n for n in d.nodes if n.node_type == ActivityNodeType.INITIAL]
        finals = [n for n in d.nodes if n.node_type == ActivityNodeType.FINAL]
        if not initials:
            problems.append(f"{d.name}: no initial node"); score -= 20
        elif len(initials) > 1:
            problems.append(f"{d.name}: {len(initials)} initial nodes"); score -= 20
        if not finals:
            problems.append(f"{d.name}: no final node"); score -= 20
        outgoing: dict[str, int] = {}
        for e in d.edges:
            outgoing[e.source] = outgoing.get(e.source, 0) + 1
        for n in d.nodes:
            if n.node_type == ActivityNodeType.DECISION and outgoing.get(n.id, 0) < 2:
                problems.append(f"{d.name}: decision {n.id} has fewer than 2 exits"); score -= 20
        reachable = {e.target for e in d.edges} | {n.id for n in initials}
        for n in d.nodes:
            if n.id not in reachable and n.node_type != ActivityNodeType.INITIAL:
                problems.append(f"{d.name}: node {n.id} is unreachable"); score -= 20
        for e in d.edges:
            if e.source not in node_ids or e.target not in node_ids:
                problems.append(f"{d.name}: edge {e.id} references a missing node"); score -= 20
    return max(0.0, score), problems


def requirement_coverage(diagrams: list[ActivityDiagram], requirement_ids: list[str]) -> tuple[float, list[str]]:
    covered: set[str] = set()
    for d in diagrams:
        covered.update(d.source_requirements or [])
        for n in d.nodes:
            covered.update(n.trace_reqs or [])
    if not requirement_ids:
        return 100.0, []
    hit = [r for r in requirement_ids if r in covered]
    missing = [r for r in requirement_ids if r not in covered]
    return round(100.0 * len(hit) / len(requirement_ids)), missing


_SECTION7_BLOCK_RE = re.compile(r"```c\s*\n(.*?)```", re.S)
_SKIP_LINE_RE = re.compile(r"^(if|else|for|while|switch|case|return|default|do)\b")


def section7_statements(spec_md: str) -> list[str]:
    """The assign/call statements of every C block in Section 7 (control-flow keywords dropped)."""
    steps: list[str] = []
    for m in _SECTION7_BLOCK_RE.finditer(spec_md or ""):
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line or line in ("{", "}") or line.startswith(("//", "#", "/*", "*")):
                continue
            if _SKIP_LINE_RE.match(line):
                continue
            if line.endswith(";"):
                line = line[:-1].rstrip()
            if line:
                steps.append(line)
    return steps


def fidelity_score(diagrams: list[ActivityDiagram], spec_md: str) -> tuple[float, list[str]]:
    steps = section7_statements(spec_md)
    node_texts: list[str] = []
    for d in diagrams:
        for n in d.nodes:
            node_texts.append(_norm(n.code or ""))
            node_texts.append(_norm(n.name or ""))
    missing: list[str] = []
    for step in steps:
        wanted = _norm(step)
        if not any(wanted in t for t in node_texts):
            missing.append(step)
    if not steps:
        return 100.0, []
    return round(100.0 * (len(steps) - len(missing)) / len(steps)), missing


# ── judge ─────────────────────────────────────────────────────────────────────
def parse_judge(text: str) -> Optional[dict[str, Any]]:
    if not isinstance(text, str) or not text.strip():
        return None
    raw = text.strip()
    data: Optional[Any] = None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    if data is None:
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                data = None
    if data is None:
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e > s:
            try:
                data = json.loads(raw[s:e + 1])
            except (json.JSONDecodeError, ValueError):
                data = None
    if not isinstance(data, dict):
        return None
    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        return None
    return {
        "score": max(0.0, min(100.0, score)),
        "missing": _list_of(data.get("missing")),
        "wrong": _list_of(data.get("wrong")),
        "suggestions": _list_of(data.get("suggestions")),
    }


def _normalize_judge(value: Any) -> Optional[dict[str, Any]]:
    if isinstance(value, str):
        return parse_judge(value)
    if isinstance(value, dict):
        try:
            score = float(value.get("score"))
        except (TypeError, ValueError):
            return None
        return {
            "score": max(0.0, min(100.0, score)),
            "missing": _list_of(value.get("missing")),
            "wrong": _list_of(value.get("wrong")),
            "suggestions": _list_of(value.get("suggestions")),
        }
    return None


# ── mermaid export ────────────────────────────────────────────────────────────
def mermaid_text(result: GenerationResult) -> str:
    from mudtool.generator.mermaid_exporter import MermaidExporter
    return "\n\n".join(MermaidExporter().export_result_inline(result).values())


# ── evaluate ──────────────────────────────────────────────────────────────────
def evaluate(
    result: GenerationResult,
    spec_md: str,
    requirement_ids: list[str],
    *,
    render: Optional[Callable[[str, str], tuple[bool, str]]] = None,
    judge: Optional[Callable[..., Any]] = None,
    png_path: Optional[Any] = None,
) -> dict[str, Any]:
    diagrams = _activity_diagrams(result)
    notes: list[str] = []
    problems: list[str] = []
    parts: dict[str, float] = {}

    s, sp = structure_score(diagrams)
    parts["structure"] = s
    problems.extend(sp)

    r, missing_reqs = requirement_coverage(diagrams, list(requirement_ids))
    parts["requirements"] = r

    f, missing_steps = fidelity_score(diagrams, spec_md)
    parts["fidelity"] = f

    render_out: Optional[dict[str, Any]] = None
    if render is not None:
        mmd = mermaid_text(result)
        ok, err = render(mmd, str(png_path) if png_path is not None else "")
        render_out = {"ok": bool(ok), "error": err or "", "png": str(png_path) if png_path is not None else ""}
        parts["render"] = 100.0 if ok else 0.0
        if not ok:
            problems.append(f"diagram does not render: {err}")

    judge_out: Optional[dict[str, Any]] = None
    if judge is not None:
        try:
            raw = judge(result, spec_md, list(requirement_ids))
            judge_out = _normalize_judge(raw)
        except Exception as exc:  # noqa: BLE001 - a failed judge is reported, not a zero
            notes.append(f"judge failed: {exc}")
        if judge_out is not None:
            parts["judge"] = judge_out["score"]
        else:
            notes.append("judge returned no usable score")
    else:
        notes.append("no AI judge")

    deterministic = sum(parts[k] for k in parts if k != "judge") / len([k for k in parts if k != "judge"])
    score = round((deterministic + judge_out["score"]) / 2) if judge_out is not None else round(deterministic)

    return {
        "score": score,
        "passed": score >= THRESHOLD,
        "threshold": THRESHOLD,
        "parts": parts,
        "judge": judge_out,
        "render": render_out,
        "problems": problems,
        "missing_requirements": missing_reqs,
        "missing_steps": missing_steps,
        "notes": notes,
    }


# ── report helpers ────────────────────────────────────────────────────────────
def verdict(score: float) -> str:
    if score >= 80:
        return "✅"
    if score >= 60:
        return "⚠️"
    return "❌"


def feedback_text(q: dict[str, Any]) -> str:
    out: list[str] = []
    if q.get("missing_requirements"):
        out.append("missing requirements: " + ", ".join(q["missing_requirements"]))
    if q.get("missing_steps"):
        out.append("missing steps: " + ", ".join(q["missing_steps"]))
    out.extend(q.get("problems") or [])
    j = q.get("judge")
    if isinstance(j, dict):
        if j.get("missing"):
            out.append("judge missing: " + ", ".join(j["missing"]))
        if j.get("wrong"):
            out.append("judge wrong: " + ", ".join(j["wrong"]))
    return "\n".join(out)


def markdown(q: dict[str, Any]) -> str:
    """A short report block for RUN_REPORT.md / flow_quality.md."""
    parts = q.get("parts") or {}
    lines = ["# Activity quality", "",
             f"- **Score: {q.get('score')} / 100** {verdict(q.get('score', 0))} (threshold {q.get('threshold', THRESHOLD)})"]
    for k, v in parts.items():
        lines.append(f"- {k}: {v:g}")
    if q.get("missing_requirements"):
        lines.append("- Missing requirements: " + ", ".join(q["missing_requirements"]))
    if q.get("missing_steps"):
        lines.append("- Missing Section 7 steps: " + ", ".join(q["missing_steps"]))
    if q.get("problems"):
        lines.append("- Problems: " + "; ".join(q["problems"]))
    j = q.get("judge")
    if isinstance(j, dict):
        lines.append(f"- Judge ({j.get('score'):g}): " + ("; ".join(j.get("wrong") or []) or "no wrong findings"))
    if q.get("render") is not None:
        r = q["render"]
        lines.append(f"- Render: {'ok → ' + r.get('png', '') if r.get('ok') else 'failed — ' + r.get('error', '')}")
    lines.append("")
    lines.append("_AI-assisted draft — not a requirement-verification claim._")
    return "\n".join(lines) + "\n"


_JUDGE_PROMPT = """You are a strict reviewer of an AUTOSAR activity / code-flow diagram.

Grade the diagram 0-100 on CONTENT ONLY (never layout/spacing), against these rules:
- Every requirement below is implemented by at least one node (labels and C code must match the spec steps).
- Conditional logic uses decision nodes with guarded branches; every runnable has start/end; nothing is disconnected.
- RTE calls match the spec (Rte_Read/Rte_Write names and arguments).
- Node labels are C expressions / calls, not English prose.

Requirements: {reqs}

MUD spec Section 7 (excerpt):
{spec}

Diagram (Mermaid):
```mermaid
{mmd}
```

Respond ONLY with this JSON (no prose, no markdown):
{{"score": 0, "missing": [], "wrong": [], "suggestions": []}}
- "missing": requirement IDs or spec steps the diagram omits.
- "wrong": specific content errors (wrong RTE call, missing branch, disconnected node).
- "suggestions": concrete fixes the generator can apply.
"""


def deepseek_judge(stage: str = "activity_qa", *, timeout: int = 300):
    """A judge callable for :func:`evaluate` that asks the ``activity_qa`` stage model.

    DeepSeek has no vision endpoint, so the judge reviews the Mermaid source + Section 7 +
    requirement IDs (text). The rendered PNG is produced separately for humans / the report.
    """
    def judge(result: GenerationResult, spec_md: str, requirement_ids: list[str]) -> str:
        from mudmut_core import agents, env
        from mudmut_core.llm import chat_blocking, get_providers
        env.ensure_environment()
        st = agents.get_stages().get(stage, {})
        provider_id = st.get("provider") or "deepseek"
        model = st.get("model") or ("deepseek-chat" if provider_id == "deepseek" else "")
        if not model:
            raise RuntimeError(f"activity_qa has no model for provider {provider_id} — set one on the Settings page")
        provider = get_providers().get(provider_id) or get_providers().get("deepseek")
        if provider is None:
            raise RuntimeError(f"no provider for activity_qa judge ({provider_id})")
        prompt = _JUDGE_PROMPT.format(reqs=", ".join(requirement_ids) or "(none)",
                                      spec=(spec_md or "")[:6000], mmd=mermaid_text(result)[:8000])
        return chat_blocking(provider, model, [{"role": "user", "content": prompt}],
                             max_tokens=2000, temperature=0.1, timeout=timeout)
    return judge
