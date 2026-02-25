"""Prompt Engine - manages versioned prompt templates per diagram type.

Prompts follow a structured pattern:
1. System Context: AUTOSAR domain knowledge, UML conventions, JSON-UML schema
2. Few-Shot Examples: Curated requirement-to-diagram examples
3. User Input: Actual requirements + project context
4. Output Constraints: JSON schema, provenance fields, confidence scoring
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

import yaml
from jinja2 import Environment, FileSystemLoader, Template

from mudtool.config.settings import Settings
from mudtool.models.json_uml import DiagramType
from mudtool.models.requirements import Requirement

logger = logging.getLogger(__name__)


class PromptTemplate:
    """A loaded and parsed prompt template."""

    def __init__(
        self,
        name: str,
        version: str,
        diagram_type: DiagramType,
        system_template: str,
        user_template: str,
        few_shot_examples: list[dict],
        output_schema_hint: str = "",
        metadata: Optional[dict] = None,
    ):
        self.name = name
        self.version = version
        self.diagram_type = diagram_type
        self.system_template = system_template
        self.user_template = user_template
        self.few_shot_examples = few_shot_examples
        self.output_schema_hint = output_schema_hint
        self.metadata = metadata or {}

    @property
    def version_tag(self) -> str:
        """Return a versioned identifier like 'seq-v3.2'."""
        prefix = {
            DiagramType.SEQUENCE: "seq",
            DiagramType.STATE_MACHINE: "sm",
            DiagramType.CLASS: "cls",
            DiagramType.COMPONENT: "cmp",
            DiagramType.ACTIVITY: "act",
        }.get(self.diagram_type, "gen")
        return f"{prefix}-v{self.version}"


class PromptEngine:
    """Manages prompt template loading, rendering, and versioning.

    Templates are stored as YAML files in the prompts directory.
    Each diagram type has its own template file.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.prompts_dir = settings.get_prompts_dir()
        self._templates: dict[DiagramType, PromptTemplate] = {}
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def load_templates(self) -> None:
        """Load all prompt templates from the prompts directory."""
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            return

        for yaml_file in self.prompts_dir.glob("*.yaml"):
            try:
                self._load_template_file(yaml_file)
            except Exception as e:
                logger.error(f"Failed to load prompt template {yaml_file}: {e}")

        logger.info(f"Loaded {len(self._templates)} prompt templates")

    def _load_template_file(self, path: Path) -> None:
        """Load a single YAML prompt template file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "diagram_type" not in data:
            logger.warning(f"Invalid prompt template (missing diagram_type): {path}")
            return

        try:
            diagram_type = DiagramType(data["diagram_type"])
        except ValueError:
            logger.warning(f"Unknown diagram_type '{data['diagram_type']}' in {path}")
            return

        template = PromptTemplate(
            name=data.get("name", path.stem),
            version=str(data.get("version", "1.0")),
            diagram_type=diagram_type,
            system_template=data.get("system_prompt", ""),
            user_template=data.get("user_prompt", ""),
            few_shot_examples=data.get("few_shot_examples", []),
            output_schema_hint=data.get("output_schema", ""),
            metadata=data.get("metadata", {}),
        )

        self._templates[diagram_type] = template
        logger.debug(f"Loaded template: {template.version_tag} from {path.name}")

    def get_template(self, diagram_type: DiagramType) -> Optional[PromptTemplate]:
        """Get the prompt template for a specific diagram type."""
        return self._templates.get(diagram_type)

    def render_system_prompt(
        self,
        diagram_type: DiagramType,
        naming_conventions: Optional[dict] = None,
        additional_context: Optional[str] = None,
    ) -> str:
        """Render the system prompt for a diagram type.

        Args:
            diagram_type: The type of diagram being generated.
            naming_conventions: Project naming convention overrides.
            additional_context: Additional domain context to inject.

        Returns:
            Rendered system prompt string.
        """
        template = self.get_template(diagram_type)
        if not template:
            return self._get_fallback_system_prompt(diagram_type)

        jinja_template = Template(template.system_template)

        # Build few-shot examples string
        examples_text = ""
        for i, example in enumerate(template.few_shot_examples, 1):
            examples_text += f"\n--- Example {i} ---\n"
            examples_text += f"Input: {example.get('input', '')}\n"
            examples_text += f"Output: {example.get('output', '')}\n"

        return jinja_template.render(
            naming_conventions=naming_conventions or {},
            additional_context=additional_context or "",
            few_shot_examples=examples_text,
            output_schema=template.output_schema_hint,
            swc_naming_regex=self.settings.swc_naming_regex,
            runnable_naming_regex=self.settings.runnable_naming_regex,
            port_naming_regex=self.settings.port_naming_regex,
        )

    def render_user_prompt(
        self,
        diagram_type: DiagramType,
        requirements: list[Requirement],
        module_context: Optional[str] = None,
        existing_swcs: Optional[list[str]] = None,
    ) -> str:
        """Render the user prompt with actual requirements.

        Args:
            diagram_type: The type of diagram being generated.
            requirements: List of requirements to model.
            module_context: Optional module/SWC context.
            existing_swcs: Optional list of existing SWC names for cross-references.

        Returns:
            Rendered user prompt string.
        """
        template = self.get_template(diagram_type)

        # Format requirements for the prompt
        reqs_text = self._format_requirements(requirements)

        if template and template.user_template:
            jinja_template = Template(template.user_template)
            return jinja_template.render(
                requirements=reqs_text,
                requirements_list=requirements,
                module_context=module_context or "",
                existing_swcs=existing_swcs or [],
                requirement_count=len(requirements),
            )

        return self._get_fallback_user_prompt(diagram_type, reqs_text)

    def _format_requirements(self, requirements: list[Requirement]) -> str:
        """Format requirements into a structured text block for the AI."""
        lines = []
        for req in requirements:
            lines.append(f"[{req.req_id}] ({req.req_type.value}) - {req.title}")
            lines.append(f"  Description: {req.description}")
            if req.safety_level:
                lines.append(f"  Safety: {req.safety_level.value}")
            if req.priority:
                lines.append(f"  Priority: {req.priority.value}")
            if req.module_hint:
                lines.append(f"  Module Hint: {req.module_hint}")
            if req.notes:
                lines.append(f"  Notes: {req.notes}")
            lines.append("")
        return "\n".join(lines)

    def compute_prompt_hash(self, system_prompt: str, user_prompt: str) -> str:
        """Compute SHA-256 hash of the full prompt for reproducibility tracking."""
        combined = f"{system_prompt}\n---\n{user_prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _get_fallback_system_prompt(self, diagram_type: DiagramType) -> str:
        """Fallback system prompt when no template file is available."""
        return f"""You are an AUTOSAR software architecture expert and UML modeler.
Your task is to generate {diagram_type.value} diagrams from architecture requirements.

DOMAIN CONTEXT:
- You are working in the AUTOSAR automotive software domain.
- Application SWCs contain Runnables (executable entities) triggered by the RTE.
- Communication uses Sender-Receiver (async data) or Client-Server (sync operation) patterns.
- Ports are either Provided (P-Port, sends/offers) or Required (R-Port, receives/consumes).
- RTE API calls: Rte_Read, Rte_Write (SR), Rte_Call, Rte_Result (CS).
- Runnables have triggers: Init, Cyclic (with period_ms), OnDataReception, OnModeSwitch.

OUTPUT FORMAT:
You MUST output valid JSON conforming to the JSON-UML schema.
Include provenance with confidence scores for each element.
Every model element must trace back to at least one requirement ID.

NAMING CONVENTIONS:
- SWC names: SWC_PascalCase (e.g., SWC_SensorFusion)
- Runnable names: RE_PascalCase (e.g., RE_FuseSensorData)
- P-Ports: PP_PascalCase (e.g., PP_FusedData)
- R-Ports: RP_PascalCase (e.g., RP_RawSensorInput)
- Interfaces: IF_SR_Name or IF_CS_Name

CONFIDENCE SCORING:
Rate your confidence (0.0 to 1.0) for each generated element:
- 0.9+: Directly derivable from requirements
- 0.7-0.9: Reasonable inference from context
- 0.5-0.7: Best guess, needs human review
- <0.5: Speculative, flag for mandatory review"""

    def _get_fallback_user_prompt(
        self, diagram_type: DiagramType, requirements_text: str
    ) -> str:
        """Fallback user prompt when no template file is available."""
        return f"""Generate an AUTOSAR {diagram_type.value} diagram from the following requirements.

REQUIREMENTS:
{requirements_text}

Output a valid JSON object conforming to the {diagram_type.value} schema.
Include source_requirements, provenance with confidence scores, and trace every element to requirement IDs."""
