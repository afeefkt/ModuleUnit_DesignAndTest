"""AI Orchestrator - routes requests to local or cloud backend.

Manages prompt rendering, response parsing, retry logic, confidence scoring,
and fallback strategies. The rest of the system is agnostic to which
inference mode is active.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

from mudtool.ai.base_backend import AIResponse, BaseAIBackend
from mudtool.ai.cloud_backend import CloudBackend
from mudtool.ai.local_backend import LocalBackend
from mudtool.ai.prompt_engine import PromptEngine
from mudtool.config.settings import AIBackend, Settings
from mudtool.models.json_uml import (
    ActivityDiagram,
    ClassDiagram,
    ComponentDiagram,
    DiagramType,
    GenerationResult,
    Provenance,
    SequenceDiagram,
    StateMachineDiagram,
)
from mudtool.models.requirements import Requirement

logger = logging.getLogger(__name__)

# Map diagram types to their Pydantic model
_DIAGRAM_MODELS = {
    DiagramType.SEQUENCE: SequenceDiagram,
    DiagramType.STATE_MACHINE: StateMachineDiagram,
    DiagramType.CLASS: ClassDiagram,
    DiagramType.COMPONENT: ComponentDiagram,
    DiagramType.ACTIVITY: ActivityDiagram,
}


class AIOrchestrator:
    """Central AI orchestration engine.

    Responsibilities:
    - Backend selection (local/cloud/auto)
    - Prompt rendering via PromptEngine
    - Response parsing and validation
    - Retry logic with configurable max retries
    - Confidence scoring and threshold enforcement
    - Fallback to partial generation on failures
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.prompt_engine = PromptEngine(settings)
        self._cloud_backend: Optional[CloudBackend] = None
        self._local_backend: Optional[LocalBackend] = None

        # Initialize backends based on settings
        self._cloud_backend = CloudBackend(settings)
        self._local_backend = LocalBackend(settings)

        # Load prompt templates
        self.prompt_engine.load_templates()

    def _get_backend(self) -> BaseAIBackend:
        """Select the active backend based on settings."""
        if self.settings.ai_backend == AIBackend.CLOUD:
            if self._cloud_backend and self._cloud_backend.is_available:
                return self._cloud_backend
            provider = self.settings.cloud_provider.value
            if provider == "openai_compatible":
                url = self.settings.openai_base_url or "http://localhost:11434/v1"
                raise RuntimeError(
                    f"Cloud backend ({provider}) configured but API key is missing. "
                    f"Check MUD_OPENAI_API_KEY in python-sidecar/.env. "
                    f"If using Ollama make sure it is running: ollama serve (target: {url})"
                )
            raise RuntimeError(
                f"Cloud backend ({provider}) configured but API key is missing. "
                "Check MUD_ANTHROPIC_API_KEY in python-sidecar/.env."
            )

        if self.settings.ai_backend == AIBackend.LOCAL:
            if self._local_backend and self._local_backend.is_available:
                return self._local_backend
            raise RuntimeError(
                "Local backend selected but not available. Check model_path configuration."
            )

        # AUTO mode: prefer cloud, fall back to local
        if self._cloud_backend and self._cloud_backend.is_available:
            return self._cloud_backend
        if self._local_backend and self._local_backend.is_available:
            logger.info("Cloud unavailable, falling back to local backend")
            return self._local_backend

        raise RuntimeError(
            "No AI backend available. Configure either cloud API key or local model path."
        )

    async def generate_diagram(
        self,
        diagram_type: DiagramType,
        requirements: list[Requirement],
        module_context: Optional[str] = None,
        existing_swcs: Optional[list[str]] = None,
        temperature: float = 0.2,
    ) -> GenerationResult:
        """Generate a single diagram from requirements.

        This is the main entry point for diagram generation.
        Handles prompt rendering, AI inference, parsing, and retries.

        Args:
            diagram_type: Type of diagram to generate.
            requirements: List of requirements to model.
            module_context: Optional module/SWC context for better results.
            existing_swcs: Optional existing SWC catalog for cross-references.
            temperature: AI sampling temperature.

        Returns:
            GenerationResult containing the generated diagram(s).
        """
        start_time = time.monotonic()
        backend = self._get_backend()

        # Render prompts
        system_prompt = self.prompt_engine.render_system_prompt(
            diagram_type,
            naming_conventions={
                "swc_regex": self.settings.swc_naming_regex,
                "runnable_regex": self.settings.runnable_naming_regex,
                "port_regex": self.settings.port_naming_regex,
            },
        )
        user_prompt = self.prompt_engine.render_user_prompt(
            diagram_type, requirements, module_context, existing_swcs
        )
        prompt_hash = self.prompt_engine.compute_prompt_hash(system_prompt, user_prompt)

        # Attempt generation with retries
        last_error: Optional[str] = None
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                logger.info(
                    f"Generation attempt {attempt}/{self.settings.max_retries} "
                    f"for {diagram_type.value} via {backend.backend_name}"
                )

                response = await backend.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=self.settings.anthropic_max_tokens,
                    temperature=temperature,
                )

                # Parse the response
                result = self._parse_response(
                    response,
                    diagram_type,
                    prompt_hash,
                    backend.backend_name,
                    req_ids=[r.req_id for r in requirements],
                )

                if result.errors and attempt < self.settings.max_retries:
                    last_error = "; ".join(result.errors)
                    logger.warning(
                        f"Attempt {attempt} produced errors: {last_error}. Retrying..."
                    )
                    # Add error context to the next attempt
                    user_prompt += (
                        f"\n\nPREVIOUS ATTEMPT FAILED with: {last_error}\n"
                        "Please fix the errors and ensure valid JSON output."
                    )
                    continue

                # Success
                total_time = int((time.monotonic() - start_time) * 1000)
                result.total_generation_time_ms = total_time
                result.analyzed_requirements = [r.req_id for r in requirements]

                logger.info(
                    f"Generated {diagram_type.value} diagram in {total_time}ms "
                    f"({len(result.diagrams)} diagrams, attempt {attempt})"
                )
                return result

            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt} failed with exception: {e}")
                if attempt >= self.settings.max_retries:
                    break

        # All retries exhausted - return partial result
        total_time = int((time.monotonic() - start_time) * 1000)
        return GenerationResult(
            errors=[
                f"Generation failed after {self.settings.max_retries} attempts. "
                f"Last error: {last_error}"
            ],
            analyzed_requirements=[r.req_id for r in requirements],
            total_generation_time_ms=total_time,
        )

    async def generate_all_diagrams(
        self,
        requirements: list[Requirement],
        diagram_types: Optional[list[DiagramType]] = None,
        module_context: Optional[str] = None,
    ) -> GenerationResult:
        """Generate multiple diagram types from requirements.

        Generates in priority order: sequence -> state_machine -> class -> component.

        Args:
            requirements: Full requirement set.
            diagram_types: Specific types to generate (default: all).
            module_context: Optional module context.

        Returns:
            Combined GenerationResult with all diagrams.
        """
        if diagram_types is None:
            diagram_types = [
                DiagramType.SEQUENCE,
                DiagramType.STATE_MACHINE,
                DiagramType.CLASS,
                DiagramType.COMPONENT,
                DiagramType.ACTIVITY,
            ]

        combined = GenerationResult(
            analyzed_requirements=[r.req_id for r in requirements]
        )
        start_time = time.monotonic()

        for dt in diagram_types:
            logger.info(f"Generating {dt.value} diagrams...")
            try:
                result = await self.generate_diagram(dt, requirements, module_context)

                combined.diagrams.extend(result.diagrams)
                combined.warnings.extend(result.warnings)
                combined.errors.extend(result.errors)

                if result.module_assignments:
                    if combined.module_assignments is None:
                        combined.module_assignments = {}
                    combined.module_assignments.update(result.module_assignments)
            except Exception as exc:
                error_msg = (
                    f"Generation of {dt.value} diagrams failed with "
                    f"unhandled error: {exc}"
                )
                logger.error(error_msg, exc_info=True)
                combined.errors.append(error_msg)

        combined.total_generation_time_ms = int(
            (time.monotonic() - start_time) * 1000
        )
        return combined

    async def analyze_requirements(
        self,
        requirements: list[Requirement],
    ) -> dict:
        """Analyze requirements: cluster into modules, identify interfaces.

        Stage 2 of the pipeline - requirement analysis and clustering.

        Returns:
            Dict with module_assignments, interface_candidates,
            sequence_hints, and state_behavior_flags.
        """
        backend = self._get_backend()

        system_prompt = """You are an AUTOSAR software architecture expert.
Analyze the given requirements and:
1. Cluster them into logical AUTOSAR Software Component (SWC) modules
2. Identify interfaces between modules (Sender-Receiver or Client-Server)
3. Extract behavioral sequences (interaction flows between components)
4. Flag state-dependent behavior (mode management, error handling, lifecycle)

Output valid JSON with this structure:
{
  "module_assignments": {"SWC_Name": ["REQ-ID-1", "REQ-ID-2"]},
  "interface_candidates": [{"from": "SWC_A", "to": "SWC_B", "type": "sender_receiver", "data": "description"}],
  "sequence_hints": [{"requirements": ["REQ-1", "REQ-2"], "description": "interaction description"}],
  "state_behavior_flags": [{"requirement": "REQ-1", "behavior": "mode_management|error_handling|lifecycle"}]
}"""

        reqs_text = "\n".join(
            f"[{r.req_id}] ({r.req_type.value}) {r.title}: {r.description}"
            for r in requirements
        )

        user_prompt = f"Analyze these AUTOSAR architecture requirements:\n\n{reqs_text}"

        response = await backend.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
        )

        try:
            return self._extract_json(response.content)
        except Exception as e:
            logger.error(f"Failed to parse analysis response: {e}")
            return {
                "module_assignments": {},
                "interface_candidates": [],
                "sequence_hints": [],
                "state_behavior_flags": [],
                "error": str(e),
            }

    def _parse_response(
        self,
        response: AIResponse,
        diagram_type: DiagramType,
        prompt_hash: str,
        backend_name: str,
        req_ids: Optional[list[str]] = None,
    ) -> GenerationResult:
        """Parse AI response into structured diagram models."""
        result = GenerationResult()

        try:
            data = self._extract_json(response.content)
        except Exception as e:
            result.errors.append(f"Failed to extract JSON from AI response: {e}")
            return result

        # Handle GenerationResult wrapper: {"diagrams": [...], "analyzed_requirements": [...]}
        # activity_diagram.yaml v2.0 instructs the AI to return this wrapper so that
        # multiple diagrams (one per runnable) can be returned in a single response.
        # Other prompt types (sequence, state_machine, class, component) return a flat
        # single-diagram object, which falls through to the else branch below.
        if isinstance(data, dict) and "diagrams" in data:
            diagrams_data = data.get("diagrams", [])
            if not isinstance(diagrams_data, list):
                diagrams_data = [diagrams_data]
        else:
            # Single diagram object or array of diagram objects
            diagrams_data = data if isinstance(data, list) else [data]

        diagram_model = _DIAGRAM_MODELS.get(diagram_type)
        if not diagram_model:
            result.errors.append(f"Unknown diagram type: {diagram_type}")
            return result

        for i, d_data in enumerate(diagrams_data):
            try:
                # Inject/override diagram_type
                d_data["diagram_type"] = diagram_type.value

                # Build provenance
                d_data.setdefault("provenance", {})
                d_data["provenance"]["ai_model"] = response.model
                d_data["provenance"]["prompt_version"] = prompt_hash
                d_data["provenance"]["backend"] = backend_name
                d_data["provenance"].setdefault("confidence", 0.7)
                d_data["provenance"]["generation_time_ms"] = response.latency_ms
                d_data["provenance"]["prompt_hash"] = prompt_hash

                # Patch sub_diagram provenance before validation so Pydantic
                # doesn't reject them for missing required fields.
                for sub_d in d_data.get("sub_diagrams", []):
                    if isinstance(sub_d, dict):
                        sub_d.setdefault("provenance", {})
                        sub_d["provenance"].setdefault("ai_model", response.model)
                        sub_d["provenance"].setdefault("prompt_version", prompt_hash)
                        sub_d["provenance"].setdefault("backend", backend_name)
                        sub_d["provenance"].setdefault("confidence", 0.7)

                diagram = diagram_model.model_validate(d_data)

                # Local models often omit trace_req / trace_reqs fields.
                # Guarantee coverage by back-filling source_requirements with
                # the requirement IDs that were fed into this generation call.
                if req_ids and not diagram.source_requirements:
                    diagram.source_requirements = list(req_ids)

                # Auto-repair activity diagrams that are missing required
                # initial / final nodes (common with smaller local models).
                if isinstance(diagram, ActivityDiagram):
                    diagram = self._repair_activity_diagram(diagram, req_ids)

                result.diagrams.append(diagram)

                # Flatten sub-diagrams into the result list
                if isinstance(diagram, ActivityDiagram) and diagram.sub_diagrams:
                    for sub in diagram.sub_diagrams:
                        # Fix child provenance if missing
                        if not sub.provenance:
                            sub.provenance = diagram.provenance
                        result.diagrams.append(sub)

            except Exception as e:
                result.errors.append(f"Failed to parse diagram {i}: {e}")
                result.warnings.append(
                    f"Partial data from diagram {i} may be recoverable"
                )

        return result

    def _repair_activity_diagram(
        self,
        diagram: ActivityDiagram,
        req_ids: Optional[list[str]],
    ) -> ActivityDiagram:
        """Auto-inject missing initial / final nodes for activity diagrams.

        Small local models (e.g. qwen2.5-coder:7b) sometimes omit the
        mandatory initial/final nodes.  When they're absent we:
          - Add a synthetic INITIAL node connected to the graph root
            (the node with no incoming edges).
          - Add a synthetic FINAL node connected from the graph leaf
            (the node with no outgoing edges).
        This prevents STR-020 validation errors and broken flowcharts.
        """
        from mudtool.models.json_uml import ActivityEdge, ActivityNode, ActivityNodeType

        if not diagram.nodes:
            return diagram

        has_initial = any(n.node_type == ActivityNodeType.INITIAL for n in diagram.nodes)
        has_final   = any(n.node_type == ActivityNodeType.FINAL   for n in diagram.nodes)

        if has_initial and has_final:
            return diagram  # nothing to repair

        trace = list(req_ids) if req_ids else diagram.source_requirements or []
        sources = {e.source for e in diagram.edges}
        targets = {e.target for e in diagram.edges}
        all_ids  = {n.id for n in diagram.nodes}

        # Mutate a copy of nodes/edges lists (Pydantic model is not frozen here)
        nodes = list(diagram.nodes)
        edges = list(diagram.edges)

        if not has_initial:
            # Root = node referenced as source but never as target (or first node)
            roots = [n for n in nodes if n.id in sources and n.id not in targets]
            first = roots[0] if roots else nodes[0]
            init_id = "N_INIT"
            # Make sure synthetic id is unique
            while init_id in all_ids:
                init_id += "_0"
            init_node = ActivityNode(
                id=init_id,
                name="Start",
                node_type=ActivityNodeType.INITIAL,
                trace_reqs=trace[:1] if trace else [],
                confidence=0.9,
            )
            nodes.insert(0, init_node)
            edges.insert(0, ActivityEdge(id="E_INIT", source=init_id, target=first.id))
            logger.info(f"Activity diagram '{diagram.name}': auto-injected INITIAL node → {first.id}")

        if not has_final:
            # Leaf = node that is a target but never a source (or last node)
            leaves = [n for n in nodes
                      if n.id in targets and n.id not in sources
                      and n.node_type != ActivityNodeType.INITIAL]
            last = leaves[-1] if leaves else nodes[-1]
            final_id = "N_FINAL"
            while final_id in {n.id for n in nodes}:
                final_id += "_0"
            final_node = ActivityNode(
                id=final_id,
                name="End",
                node_type=ActivityNodeType.FINAL,
                trace_reqs=trace[:1] if trace else [],
                confidence=0.9,
            )
            nodes.append(final_node)
            edges.append(ActivityEdge(id="E_FINAL", source=last.id, target=final_id))
            logger.info(f"Activity diagram '{diagram.name}': auto-injected FINAL node from {last.id}")

        # Return rebuilt diagram with repaired node/edge lists
        return diagram.model_copy(update={"nodes": nodes, "edges": edges})

    def _extract_json(self, text: str) -> dict | list:
        """Extract JSON from AI response text.

        The AI might wrap JSON in markdown code blocks or include
        explanatory text before/after the JSON.
        """
        # Try direct parse first
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        json_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```",
            text,
            re.DOTALL,
        )
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding JSON object/array boundaries
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = text.find(start_char)
            if start != -1:
                end = text.rfind(end_char)
                if end > start:
                    try:
                        return json.loads(text[start : end + 1])
                    except json.JSONDecodeError:
                        pass

        raise ValueError(
            "Could not extract valid JSON from AI response. "
            f"Response starts with: {text[:200]}..."
        )

    async def health_check(self) -> dict:
        """Check health of all configured backends."""
        result = {"orchestrator": "ok", "backends": {}}

        if self._cloud_backend:
            result["backends"]["cloud"] = await self._cloud_backend.health_check()
        if self._local_backend:
            result["backends"]["local"] = await self._local_backend.health_check()

        result["active_backend"] = self.settings.ai_backend.value
        result["prompt_templates_loaded"] = len(self.prompt_engine._templates)

        return result
