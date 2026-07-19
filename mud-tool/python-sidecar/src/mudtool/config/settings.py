"""Application settings and configuration."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class AIBackend(str, Enum):
    """AI inference backend selection."""
    LOCAL = "local"
    CLOUD = "cloud"
    AUTO = "auto"  # Cloud primary, local fallback


class CloudProvider(str, Enum):
    """Cloud AI provider."""
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"
    DEEPSEEK = "deepseek"


def _find_env_file() -> str:
    """Locate the .env file relative to this settings module, regardless of CWD.

    The .env lives at  <project>/python-sidecar/.env
    This file lives at <project>/python-sidecar/src/mudtool/config/settings.py
    so we go four levels up: config → mudtool → src → python-sidecar
    """
    return str(Path(__file__).parent.parent.parent.parent / ".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = {"env_prefix": "MUD_", "env_file": _find_env_file(), "extra": "ignore"}

    # Server
    host: str = "127.0.0.1"
    port: int = 8042
    debug: bool = False
    log_level: str = "info"

    # AI Backend Selection
    ai_backend: AIBackend = AIBackend.CLOUD
    confidence_threshold: float = 0.8
    max_retries: int = 3

    # Cloud AI - Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-5-20250514"
    anthropic_max_tokens: int = 8192

    # Cloud AI - OpenAI Compatible
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 8192
    openai_enable_thinking: bool = False   # MUD_OPENAI_ENABLE_THINKING — pass think:true to Ollama
    openai_json_mode: bool = True           # MUD_OPENAI_JSON_MODE — force JSON output via Ollama format field

    # Cloud AI - DeepSeek (OpenAI-compatible API hosted at api.deepseek.com)
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"   # or "deepseek-reasoner" for R1-style reasoning
    deepseek_max_tokens: int = 8192

    cloud_provider: CloudProvider = CloudProvider.ANTHROPIC

    # Local LLM
    local_model_path: Optional[str] = None
    local_model_auto_gpu: bool = True        # MUD_LOCAL_MODEL_AUTO_GPU — auto-detect CUDA/Metal
    local_model_n_gpu_layers: int = -1       # -1 = all GPU; 0 = CPU; used if auto_gpu=false
    local_model_n_ctx: int = 8192
    local_model_n_batch: int = 512
    local_model_n_threads: int = 4

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)
    prompts_dir: Optional[Path] = None
    data_dir: Optional[Path] = None
    db_path: Optional[Path] = None

    # AUTOSAR Naming Conventions
    swc_naming_regex: str = r"^SWC_[A-Z][A-Za-z0-9_]+$"
    runnable_naming_regex: str = r"^RE_[A-Z][A-Za-z0-9_]+$"
    port_naming_regex: str = r"^(PP|RP)_[A-Z][A-Za-z0-9_]+$"

    # Validation
    validation_strict_mode: bool = False

    # Render service (SVG/PNG output)
    plantuml_jar_path: Optional[Path] = None   # MUD_PLANTUML_JAR_PATH
    use_kroki: bool = True                      # MUD_USE_KROKI
    kroki_base_url: str = "https://kroki.io"   # MUD_KROKI_BASE_URL

    # ── Multi-Stage Generation Pipeline ──────────────────────────────────
    # MUD_PIPELINE_ENABLED=true activates the pipeline; false = legacy single-pass
    pipeline_enabled: bool = False
    # MUD_PIPELINE_MODE: single_pass | multi_pass | two_model_fast | two_model
    pipeline_mode: str = "single_pass"
    # Model used for the code-generation stages (MUD Spec Stage 3 + Activity
    # per-runnable Stage 3) — a code-specialized model. Recommended default
    # combination: qwen2.5-coder for code, deepseek-r1 for reasoning stages.
    pipeline_generator_model: str = "qwen3:8b"
    # Model used for review/critique stages — a reasoning model.
    pipeline_reviewer_model: str = "deepseek-r1:7b"
    # Number of critique-refine cycles per diagram type (1 is enough for local hardware)
    pipeline_max_passes: int = 1
    # If draft provenance.confidence >= this value, skip critique/refine (early exit)
    pipeline_confidence_threshold: float = 0.75

    # ── Visual QA (qwen2-vl via Ollama) ──────────────────────────────────────
    # MUD_VISUAL_QA_ENABLED=true  → render every diagram to PNG and review with vision LLM
    visual_qa_enabled: bool = False
    # MUD_VISUAL_QA_MODEL  → any Ollama multimodal model (ollama pull qwen2-vl:7b)
    visual_qa_model: str = "qwen2-vl:7b"
    # MUD_VISUAL_QA_MAX_ROUNDS  → max correction-refinement rounds per diagram (1–3)
    visual_qa_max_rounds: int = 2
    # MUD_VISUAL_QA_MIN_SCORE  → approve diagram if vision score >= this (0.0–1.0)
    visual_qa_min_score: float = 0.70

    # ── Elaboration mode ─────────────────────────────────────────────────────
    # MUD_ELABORATION_MODE: "single_shot" (default, 7B+ models) or "chunked"
    # (2–3B models like Qwen 2.5 2B/3B).
    #
    # single_shot — one large prompt → one large JSON document (current behaviour).
    #               Reliable for 7B+ models; drifts/hallucinates on 2–3B.
    # chunked     — three small focused prompts assembled by Python code.
    #               Each call targets ≤ 500 tokens output, well within 2–3B
    #               reliable range.  More API calls but far higher reliability.
    elaboration_mode: str = "single_shot"

    # ── Skills (full-document injection for activity diagrams) ───────────────
    # MUD_SKILLS_ENABLED=true  -> prepend skill block to activity diagram system prompts
    skills_enabled: bool = True
    # MUD_SKILLS_DIR  -> folder containing non-chunked skill .md files
    skills_dir: Optional[Path] = None  # default: project_root / "data" / "skills"

    # ── Guidelines RAG (design document injection) ────────────────────────────
    # MUD_GUIDELINES_ENABLED=true  -> load docs from guidelines_dir before generation
    guidelines_enabled: bool = True
    # MUD_GUIDELINES_DIR  -> folder containing HTML/PDF/DOCX/TXT/MD guideline files
    guidelines_dir: Optional[Path] = None
    # MUD_GUIDELINES_CACHE_DIR  -> where chunked embeddings are cached
    guidelines_cache_dir: Optional[Path] = None
    # MUD_GUIDELINES_EMBED_MODEL  -> Ollama embedding model. bge-m3 (1024-dim)
    # gives stronger mixed semantic+code retrieval and longer context than
    # nomic-embed-text (768-dim). Pull first: ollama pull bge-m3
    guidelines_embed_model: str = "bge-m3"
    # MUD_GUIDELINES_MAX_CHUNKS  -> max chunks injected per diagram type per generation
    guidelines_max_chunks: int = 3
    # MUD_GUIDELINES_CHUNK_SIZE  -> target characters per text chunk
    guidelines_chunk_size: int = 800

    # MUD_SPEC_SKELETON_MODEL: separate model for Stage 1 skeleton in the
    # two-stage pipeline. Recommended: deepseek-r1:7b — a reasoning model gives
    # better structured-JSON completeness on 7b GPUs. Empty = use generator model.
    mud_spec_skeleton_model: str = "deepseek-r1:7b"

    # ── MUD Spec Generation Pipeline ─────────────────────────────────────────
    # MUD_SPEC_PIPELINE controls the generation mode for /modules/mud-spec:
    #   "single_pass"  — one AI call produces the full 7-section Markdown.
    #                              Fast (~1 min), good for quick iterations.
    #   "two_stage"    — Stage 1 generates a JSON skeleton (all ports/runnables/IRVs/
    #                    CalPrm/DEM events), then Stage 3 expands Section 7 pseudo-code
    #                    per runnable using exact port names from the skeleton.
    #                    Better quality, ~3× slower.  Falls back to single_pass on error.
    mud_spec_pipeline: str = "two_stage"

    # ── Activity Diagram Pipeline (multi-stage) ──────────────────────────────
    # MUD_ACTIVITY_PIPELINE_ENABLED=true → use 5-stage pipeline:
    #   Stage1 skeleton (deepseek-r1:7b) → Stage3 per-runnable diagram
    #   (qwen2.5-coder:7b) → Stage4 reviewer pass → Stage5 deterministic repair.
    # When false (default) the legacy single-call path runs unchanged.
    activity_pipeline_enabled: bool = False
    # Per-stage backend overrides. Recommended combination: deepseek-r1:7b
    # (reasoning) for skeleton + reviewer, qwen3:8b (code) for the
    # per-runnable generation stage (via pipeline_generator_model).
    activity_pipeline_skeleton_model: str = "deepseek-r1:7b"
    activity_pipeline_reviewer_model: str = "deepseek-r1:7b"
    # MUD_ACTIVITY_PIPELINE_STAGE3_TWO_PHASE=true → split Stage 3 into:
    #   Phase A: generate topology only (node types + edges, no labels)
    #   Phase B: fill in C-expression labels given the locked topology
    # Produces more consistent diagrams at the cost of one extra AI call per runnable.
    activity_pipeline_stage3_two_phase: bool = False

    def get_skills_dir(self) -> Path:
        if self.skills_dir:
            return self.skills_dir
        return self.project_root / "data" / "skills"

    def get_guidelines_dir(self) -> Path:
        if self.guidelines_dir:
            return self.guidelines_dir
        return self.project_root / "data" / "guidelines"

    def get_guidelines_cache_dir(self) -> Path:
        if self.guidelines_cache_dir:
            return self.guidelines_cache_dir
        return self.project_root / "data" / "guidelines_cache"

    def get_prompts_dir(self) -> Path:
        if self.prompts_dir:
            return self.prompts_dir
        return self.project_root / "prompts"

    def get_data_dir(self) -> Path:
        if self.data_dir:
            return self.data_dir
        return self.project_root / "data"

    def get_db_path(self) -> Path:
        if self.db_path:
            return self.db_path
        return self.get_data_dir() / "mudtool.sqlite"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings singleton."""
    return Settings()
