"""Visual QA Agent - local multimodal LLM review of rendered diagrams.

Pipeline position:
    ... → Trace → Export → [Visual QA → Visual Correction loop]

Architecture:
  1. MermaidExporter produces Mermaid text per diagram
  2. VisualQAAgent renders each diagram to PNG via Kroki.io
  3. PNG is sent to Ollama qwen2-vl (or any multimodal model) for review
  4. Structured JSON feedback is parsed: scores, layout issues, correction hints
  5. If the diagram fails QA (score < min_score), VisualCorrectionLoop:
       a. Injects correction hints into a refinement prompt
       b. Re-runs the AI generator (via existing PipelineOrchestrator refinement path)
       c. Re-exports to Mermaid, re-renders PNG, re-analyzes
       d. Repeats up to visual_qa_max_rounds times

Config (.env):
  MUD_VISUAL_QA_ENABLED=true
  MUD_VISUAL_QA_MODEL=qwen2-vl:7b     # Any Ollama multimodal model
  MUD_VISUAL_QA_MAX_ROUNDS=2          # Correction rounds per diagram
  MUD_VISUAL_QA_MIN_SCORE=0.70        # Approve if score >= this value
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
import zlib
from dataclasses import dataclass, field
from typing import Optional

import httpx

from mudtool.config.settings import Settings
from mudtool.models.json_uml import DiagramType, GenerationResult

logger = logging.getLogger(__name__)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class VisualQAResult:
    """Structured output from one visual QA analysis pass."""
    diagram_type: str
    diagram_key: str
    model_used: str
    # ── Checklist ─────────────────────────────────────────────────────────────
    has_start_node: bool = True
    has_end_node: bool = True
    has_branching: bool = True
    all_nodes_connected: bool = True
    labels_readable: bool = True
    spacing_ok: bool = True
    # ── Score & approval ──────────────────────────────────────────────────────
    quality_score: float = 0.0
    approved: bool = False
    # ── Issues ────────────────────────────────────────────────────────────────
    layout_issues: list[str] = field(default_factory=list)
    semantic_issues: list[str] = field(default_factory=list)
    correction_hints: list[str] = field(default_factory=list)
    # ── Meta ──────────────────────────────────────────────────────────────────
    skipped: bool = False
    skip_reason: Optional[str] = None
    round_num: int = 1
    duration_ms: int = 0
    raw_response: str = ""

    @property
    def has_issues(self) -> bool:
        return bool(
            self.layout_issues
            or self.semantic_issues
            or not self.approved
        )

    def to_correction_prompt_block(self) -> str:
        """Format issues as a block for injection into the AI refinement prompt."""
        if not self.correction_hints and not self.layout_issues and not self.semantic_issues:
            return ""
        lines = ["VISUAL QA FEEDBACK (fix ALL issues below in the corrected JSON output):"]
        for hint in self.correction_hints:
            lines.append(f"  - {hint}")
        for issue in self.layout_issues:
            lines.append(f"  [layout] {issue}")
        for issue in self.semantic_issues:
            lines.append(f"  [semantic] {issue}")
        return "\n".join(lines)

    def to_summary(self) -> dict:
        return {
            "diagram_key": self.diagram_key,
            "approved": self.approved,
            "quality_score": round(self.quality_score, 2),
            "has_branching": self.has_branching,
            "all_nodes_connected": self.all_nodes_connected,
            "layout_issues": self.layout_issues,
            "semantic_issues": self.semantic_issues,
            "correction_hints": self.correction_hints,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "round_num": self.round_num,
            "duration_ms": self.duration_ms,
            "model_used": self.model_used,
        }


# ── Visual QA Agent ────────────────────────────────────────────────────────────

class VisualQAAgent:
    """Renders Mermaid diagrams to PNG and analyses them with a local vision LLM.

    Backend: Ollama chat API (http://localhost:11434/api/chat)
    Vision model: qwen2-vl:7b (default) - pull with: ollama pull qwen2-vl:7b
    Render: Kroki.io (or local Mermaid CLI if Kroki is unavailable)
    """

    _OLLAMA_CHAT = "/api/chat"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = settings.visual_qa_model
        self._min_score = settings.visual_qa_min_score
        self._max_rounds = settings.visual_qa_max_rounds
        self._kroki_base = settings.kroki_base_url.rstrip("/")
        # Strip /v1 suffix if present (Ollama native API ≠ OpenAI-compat)
        base = (settings.openai_base_url or "http://localhost:11434").rstrip("/")
        self._ollama_base = base[:-3] if base.endswith("/v1") else base
        self._http_timeout = 90  # seconds - vision inference can be slow locally

    # ── Rendering ────────────────────────────────────────────────────────────

    async def _render_png(self, mermaid_text: str) -> Optional[bytes]:
        """Render Mermaid text to PNG via Kroki.io.

        Kroki accepts a zlib-compressed, base64url-encoded diagram payload
        at: https://kroki.io/mermaid/png/<encoded>
        """
        try:
            compressed = zlib.compress(mermaid_text.encode("utf-8"), 9)
            encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
            url = f"{self._kroki_base}/mermaid/png/{encoded}"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.content
                logger.warning(
                    "Kroki PNG render failed: HTTP %s for diagram len=%d",
                    resp.status_code, len(mermaid_text),
                )
        except Exception as exc:
            logger.warning("Kroki render error: %s", exc)
        return None

    # ── Vision model call ─────────────────────────────────────────────────────

    def _build_vision_prompt(
        self, diagram_type: DiagramType, diagram_key: str
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the vision model.

        The prompt is deliberately scoped to CONTENT issues that can be fixed by
        editing the diagram JSON (labels, branches, connections). Layout/spacing
        artifacts are produced by the auto-layout engine (Mermaid/Kroki) and the
        AI cannot fix them, so the model is explicitly forbidden from flagging
        them — this prevents false-positive correction rounds that would re-run
        the generator and risk regressing an already-correct diagram.
        """
        system = (
            "You are a technical diagram quality reviewer for AUTOSAR activity "
            "diagrams / flowcharts.\n"
            "CRITICAL: the diagram layout (node positions, spacing, edge routing, "
            "column vs. spread) is produced by an AUTOMATIC layout engine, NOT by "
            "a human or the AI you are reviewing. You MUST NOT penalise or comment "
            "on layout, spacing, overlap, column arrangement, or edge crossings — "
            "these are not fixable and are out of scope. A clean single vertical "
            "column is perfectly acceptable.\n"
            "Only report problems that can be fixed by editing the diagram's "
            "logical content (its nodes, labels, and connections).\n"
            "Respond ONLY with a valid JSON object — no markdown, no prose."
        )

        specific = {
            DiagramType.ACTIVITY: (
                "  - A Start node and at least one End node are present.\n"
                "  - Conditional logic uses decision diamonds with >= 2 labeled "
                "exits (e.g. Yes/No). A long chain with NO diamond when the "
                "pseudo-code clearly branches is a real issue.\n"
                "  - No node is completely disconnected (no arrows in AND out), "
                "EXCEPT Start (no in) and End (no out).\n"
                "  - Node label text is fully readable and not cut off / clipped "
                "at the node boundary."
            ),
            DiagramType.SEQUENCE: (
                "  - >= 2 named participant lifelines.\n"
                "  - Messages are labeled and readable (not clipped).\n"
                "  - No lifeline is completely messageless / orphaned."
            ),
            DiagramType.STATE_MACHINE: (
                "  - An initial pseudo-state with an outgoing arrow.\n"
                "  - >= 2 named states.\n"
                "  - Transition labels are readable.\n"
                "  - No state is completely disconnected."
            ),
        }.get(
            diagram_type,
            "  - Nodes connected by arrows.\n  - Labels readable / not clipped.\n"
            "  - No fully disconnected node."
        )

        user = (
            f"Review this {diagram_type.value} diagram image (key: {diagram_key}).\n\n"
            f"Check ONLY these content issues:\n{specific}\n\n"
            "Do NOT report: spacing, overlap, node distribution, column layout, "
            "edge crossings, or anything about visual arrangement. Those are not "
            "in scope and will be ignored.\n\n"
            "Respond ONLY with this exact JSON (fill every field):\n"
            "{\n"
            '  "has_start_node": true,\n'
            '  "has_end_node": true,\n'
            '  "has_branching": true,\n'
            '  "all_nodes_connected": true,\n'
            '  "labels_readable": true,\n'
            '  "spacing_ok": true,\n'
            '  "quality_score": 0.0,\n'
            '  "approved": false,\n'
            '  "layout_issues": [],\n'
            '  "semantic_issues": [],\n'
            '  "correction_hints": []\n'
            "}\n\n"
            "Field rules:\n"
            "  - spacing_ok: ALWAYS true unless label text literally overlaps so "
            "it is unreadable. Never set false for column/spread/spacing taste.\n"
            "  - labels_readable: false ONLY if real label text is clipped or "
            "unreadable.\n"
            "  - layout_issues: leave EMPTY unless a label is clipped. Never put "
            "spacing/arrangement complaints here.\n"
            "  - semantic_issues: missing branch, disconnected node, missing "
            "start/end only.\n"
            "  - correction_hints: must be content edits the generator can apply, "
            "e.g.:\n"
            "      'Shorten label of node Rte_Read_RP_VehicleSpeed (text clipped)'\n"
            "      'Add Yes/No branches to the SensorFault decision diamond'\n"
            "      'Connect isolated node Rte_Write(PP_Actuator) to the End node'\n"
            "    NEVER hints like 'spread nodes out', 'reduce overlap', "
            "'improve spacing'.\n"
            f"  - quality_score: 0.0=unusable … 1.0=perfect. Judge CONTENT only.\n"
            f"  - approved=true when quality_score >= {self._min_score} and there "
            "are no content issues. Layout is never a reason to reject."
        )
        return system, user

    async def _call_vision_model(
        self,
        image_bytes: bytes,
        diagram_type: DiagramType,
        diagram_key: str,
    ) -> VisualQAResult:
        """Send PNG to Ollama vision model and parse the JSON response."""
        b64 = base64.b64encode(image_bytes).decode("ascii")
        system, user = self._build_vision_prompt(diagram_type, diagram_key)

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                },
            ],
            "stream": False,
            "options": {"temperature": 0.05, "num_predict": 512},
        }

        url = f"{self._ollama_base}{self._OLLAMA_CHAT}"
        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                raw = resp.json().get("message", {}).get("content", "")
        except httpx.ConnectError:
            return VisualQAResult(
                diagram_type=diagram_type.value,
                diagram_key=diagram_key,
                model_used=self._model,
                skipped=True,
                skip_reason=(
                    f"Ollama not reachable at {self._ollama_base} - "
                    "is Ollama running? (ollama serve)"
                ),
            )
        except Exception as exc:
            logger.error("Ollama vision call failed for %s: %s", diagram_key, exc)
            return VisualQAResult(
                diagram_type=diagram_type.value,
                diagram_key=diagram_key,
                model_used=self._model,
                skipped=True,
                skip_reason=f"Ollama error: {exc}",
            )

        return self._parse_vision_response(raw, diagram_type, diagram_key)

    def _parse_vision_response(
        self, raw: str, diagram_type: DiagramType, diagram_key: str
    ) -> VisualQAResult:
        """Extract structured JSON from the vision model reply."""
        raw = raw.strip()
        parsed: Optional[dict] = None

        # Try direct parse
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass

        # Extract from markdown code block
        if parsed is None:
            m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(1).strip())
                except (json.JSONDecodeError, ValueError):
                    pass

        # Boundary scan for first JSON object
        if parsed is None:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                try:
                    parsed = json.loads(raw[start : end + 1])
                except (json.JSONDecodeError, ValueError):
                    pass

        if parsed is None:
            logger.warning(
                "VisualQA: could not parse vision response for %s; raw=%r",
                diagram_key, raw[:200],
            )
            return VisualQAResult(
                diagram_type=diagram_type.value,
                diagram_key=diagram_key,
                model_used=self._model,
                quality_score=0.3,
                approved=False,
                layout_issues=["Vision model response could not be parsed as JSON."],
                raw_response=raw,
            )

        score = float(parsed.get("quality_score", 0.0))
        return VisualQAResult(
            diagram_type=diagram_type.value,
            diagram_key=diagram_key,
            model_used=self._model,
            has_start_node=bool(parsed.get("has_start_node", True)),
            has_end_node=bool(parsed.get("has_end_node", True)),
            has_branching=bool(parsed.get("has_branching", True)),
            all_nodes_connected=bool(parsed.get("all_nodes_connected", True)),
            labels_readable=bool(parsed.get("labels_readable", True)),
            spacing_ok=bool(parsed.get("spacing_ok", True)),
            quality_score=score,
            approved=bool(parsed.get("approved", False)),
            layout_issues=list(parsed.get("layout_issues", [])),
            semantic_issues=list(parsed.get("semantic_issues", [])),
            correction_hints=list(parsed.get("correction_hints", [])),
            raw_response=raw,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    async def analyze_mermaid(
        self,
        mermaid_text: str,
        diagram_type: DiagramType,
        diagram_key: str,
        round_num: int = 1,
    ) -> VisualQAResult:
        """Render Mermaid → PNG, then analyse with vision model.

        Returns a VisualQAResult. If render or vision call fails, the result
        is marked skipped=True with a reason - generation can continue safely.
        """
        if not self.settings.visual_qa_enabled:
            return VisualQAResult(
                diagram_type=diagram_type.value,
                diagram_key=diagram_key,
                model_used="disabled",
                skipped=True,
                skip_reason="MUD_VISUAL_QA_ENABLED=false",
                approved=True,   # Don't block the pipeline
            )

        t0 = time.monotonic()
        image = await self._render_png(mermaid_text)
        if image is None:
            return VisualQAResult(
                diagram_type=diagram_type.value,
                diagram_key=diagram_key,
                model_used=self._model,
                skipped=True,
                skip_reason="PNG render failed - Kroki.io may be unreachable.",
                approved=True,   # Don't block the pipeline
            )

        result = await self._call_vision_model(image, diagram_type, diagram_key)
        result.round_num = round_num
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    async def run_visual_qa_pass(
        self,
        mermaid_diagrams: dict[str, str],
        progress_callback: Optional[callable] = None,
        round_num: int = 1,
    ) -> dict[str, VisualQAResult]:
        """Run visual QA on every diagram in the mermaid_diagrams dict.

        Returns a dict mapping diagram_key → VisualQAResult.
        Emits SSE events via progress_callback if provided.
        """
        results: dict[str, VisualQAResult] = {}

        for key, mermaid_text in mermaid_diagrams.items():
            prefix = key.split("_")[0]
            try:
                dt = DiagramType(prefix)
            except ValueError:
                dt = DiagramType.ACTIVITY

            if progress_callback:
                progress_callback({
                    "stage": "visual_qa",
                    "diagram_type": dt.value,
                    "diagram_key": key,
                    "round_num": round_num,
                    "message": (
                        f"[VisualQA r{round_num}] Rendering {key}…"
                    ),
                })

            qa = await self.analyze_mermaid(mermaid_text, dt, key, round_num=round_num)
            results[key] = qa

            status = "✓ approved" if qa.approved else (
                "skipped" if qa.skipped else f"✗ {len(qa.layout_issues + qa.semantic_issues)} issue(s)"
            )
            if progress_callback:
                progress_callback({
                    "stage": "visual_qa_result",
                    "diagram_type": dt.value,
                    "diagram_key": key,
                    "round_num": round_num,
                    "approved": qa.approved,
                    "skipped": qa.skipped,
                    "quality_score": qa.quality_score,
                    "issue_count": len(qa.layout_issues) + len(qa.semantic_issues),
                    "message": (
                        f"[VisualQA r{round_num}] {key}: "
                        f"score={qa.quality_score:.2f} {status}"
                    ),
                })

            logger.info(
                "[VisualQA r%d] %s: score=%.2f approved=%s issues=%d",
                round_num, key, qa.quality_score, qa.approved,
                len(qa.layout_issues) + len(qa.semantic_issues),
            )

        return results


# ── Visual Correction Loop ────────────────────────────────────────────────────

class VisualCorrectionLoop:
    """Runs the Visual QA → refinement → re-check correction cycle.

    When VisualQAAgent finds layout or structural issues in a rendered diagram,
    this class:
      1. Builds a correction prompt that injects the QA feedback
      2. Triggers a targeted AI refinement pass (via PipelineOrchestrator)
      3. Re-exports the corrected JSON to Mermaid
      4. Re-renders and re-analyses
      5. Repeats up to max_rounds times per diagram

    It operates on the FINAL GenerationResult after the main pipeline completes.
    The correction only modifies diagrams that failed QA; approved ones are untouched.
    """

    def __init__(
        self,
        settings: Settings,
        visual_qa_agent: VisualQAAgent,
        orchestrator,           # AIOrchestrator - avoid circular import
        mermaid_exporter,       # MermaidExporter
    ) -> None:
        self.settings = settings
        self.qa_agent = visual_qa_agent
        self.orchestrator = orchestrator
        self.mermaid_exporter = mermaid_exporter
        self._max_rounds = settings.visual_qa_max_rounds

    async def run(
        self,
        generation_result: GenerationResult,
        requirements: list,
        pipeline_config,          # PipelineConfig from pipeline.py
        progress_callback: Optional[callable] = None,
    ) -> tuple[GenerationResult, list[dict]]:
        """Run the full visual correction loop.

        Returns:
            (corrected_result, qa_summary_list)
            where qa_summary_list is a list of VisualQAResult.to_summary() dicts
            for all diagrams across all rounds.
        """
        from mudtool.ai.pipeline import PipelineOrchestrator

        pipeline_orch = PipelineOrchestrator(self.settings, self.orchestrator)
        current_result = generation_result
        all_summaries: list[dict] = []

        for round_num in range(1, self._max_rounds + 1):
            # Export current result to Mermaid inline
            mermaid_maps = self.mermaid_exporter.export_result_inline(current_result)
            if not mermaid_maps:
                logger.warning("VisualCorrectionLoop: no Mermaid diagrams to check")
                break

            # Run QA on all diagrams
            qa_results = await self.qa_agent.run_visual_qa_pass(
                mermaid_maps,
                progress_callback=progress_callback,
                round_num=round_num,
            )
            all_summaries.extend(r.to_summary() for r in qa_results.values())

            # Identify diagrams that need correction
            needs_correction = {
                key: qa
                for key, qa in qa_results.items()
                if not qa.approved and not qa.skipped and qa.correction_hints
            }

            if not needs_correction:
                logger.info(
                    "VisualCorrectionLoop round %d: all diagrams approved", round_num
                )
                break

            logger.info(
                "VisualCorrectionLoop round %d: %d diagram(s) need correction: %s",
                round_num, len(needs_correction), list(needs_correction.keys()),
            )

            # Run correction refinement for each failing diagram
            for key, qa in needs_correction.items():
                dt_str = key.split("_")[0]
                try:
                    dt = DiagramType(dt_str)
                except ValueError:
                    continue

                if progress_callback:
                    progress_callback({
                        "stage": "visual_correction",
                        "diagram_type": dt.value,
                        "diagram_key": key,
                        "round_num": round_num,
                        "message": (
                            f"[VisualQA correction r{round_num}] "
                            f"Refining {key} ({len(qa.correction_hints)} hint(s))…"
                        ),
                    })

                corrected = await self._correct_diagram(
                    dt, current_result, qa, requirements, pipeline_config, pipeline_orch
                )
                if corrected:
                    # Replace the diagram in the result
                    current_result = self._replace_diagram(
                        current_result, dt, corrected
                    )

            if round_num == self._max_rounds:
                logger.info(
                    "VisualCorrectionLoop: reached max_rounds=%d", self._max_rounds
                )

        return current_result, all_summaries

    async def _correct_diagram(
        self,
        diagram_type: DiagramType,
        current_result: GenerationResult,
        qa: VisualQAResult,
        requirements: list,
        pipeline_config,
        pipeline_orch,
    ) -> Optional[GenerationResult]:
        """Run one targeted refinement pass for a single diagram type.

        Injects the VisualQA correction hints into the refinement prompt via
        the existing _run_refinement_stage() mechanic - reuses the critique
        mechanism but with visual feedback as the 'issues'.
        """
        from mudtool.ai.pipeline import CritiqueResult

        # Synthesise a CritiqueResult from the visual QA feedback
        visual_critique = CritiqueResult(
            issues=[
                {"element": "diagram_layout", "severity": "warning", "description": hint}
                for hint in qa.correction_hints
            ] + [
                {"element": "layout", "severity": "warning", "description": issue}
                for issue in qa.layout_issues
            ] + [
                {"element": "semantic", "severity": "warning", "description": issue}
                for issue in qa.semantic_issues
            ],
            quality_score=qa.quality_score,
            approved=False,
            missing_elements=[
                h for h in qa.correction_hints
                if "add" in h.lower() or "missing" in h.lower()
            ],
            naming_violations=[],
            traceability_gaps=[],
        )

        # Find the current diagram JSON for this type
        current_diagrams = [
            d for d in current_result.diagrams
            if d.diagram_type == diagram_type
        ]
        if not current_diagrams:
            logger.warning(
                "VisualCorrection: no diagram of type %s in current result",
                diagram_type.value,
            )
            return None

        # Build a GenerationResult containing only this diagram type for refinement
        from mudtool.models.json_uml import GenerationResult as GR
        partial_result = GR(
            diagrams=current_diagrams,
            analyzed_requirements=[r.req_id for r in requirements],
        )

        try:
            stage = await pipeline_orch._run_refinement_stage(
                diagram_type=diagram_type,
                draft_result=partial_result,
                critique=visual_critique,
                requirements=requirements,
                config=pipeline_config,
                pass_num=1,
            )
            if stage.diagram_result and not stage.error:
                logger.info(
                    "VisualCorrection: refined %s, confidence=%.2f",
                    diagram_type.value,
                    pipeline_orch._extract_confidence(stage.diagram_result),
                )
                return stage.diagram_result
            else:
                logger.warning(
                    "VisualCorrection: refinement failed for %s: %s",
                    diagram_type.value, stage.error,
                )
        except Exception as exc:
            logger.error("VisualCorrection: exception for %s: %s", diagram_type.value, exc)

        return None

    @staticmethod
    def _replace_diagram(
        result: GenerationResult,
        diagram_type: DiagramType,
        corrected: GenerationResult,
    ) -> GenerationResult:
        """Replace diagrams of the given type in result with corrected versions."""
        from mudtool.models.json_uml import GenerationResult as GR

        kept = [d for d in result.diagrams if d.diagram_type != diagram_type]
        updated = kept + corrected.diagrams

        return GR(
            diagrams=updated,
            analyzed_requirements=result.analyzed_requirements,
            warnings=result.warnings + corrected.warnings,
            errors=result.errors,
            module_assignments=result.module_assignments,
            total_generation_time_ms=result.total_generation_time_ms,
        )
