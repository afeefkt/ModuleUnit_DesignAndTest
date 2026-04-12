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
    # Model used for Stage 1 (draft) and Stage 3 (refinement) — code-focused model
    pipeline_generator_model: str = "codellama"
    # Model used for Stage 2 (critique) in two_model / two_model_fast modes
    pipeline_reviewer_model: str = "mistral"
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

    # ── Guidelines RAG (design document injection) ────────────────────────────
    # MUD_GUIDELINES_ENABLED=true  -> load docs from guidelines_dir before generation
    guidelines_enabled: bool = True
    # MUD_GUIDELINES_DIR  -> folder containing HTML/PDF/DOCX/TXT/MD guideline files
    guidelines_dir: Optional[Path] = None
    # MUD_GUIDELINES_CACHE_DIR  -> where chunked embeddings are cached
    guidelines_cache_dir: Optional[Path] = None
    # MUD_GUIDELINES_EMBED_MODEL  -> Ollama model for embeddings (nomic-embed-text recommended)
    guidelines_embed_model: str = "nomic-embed-text"
    # MUD_GUIDELINES_MAX_CHUNKS  -> max chunks injected per diagram type per generation
    guidelines_max_chunks: int = 3
    # MUD_GUIDELINES_CHUNK_SIZE  -> target characters per text chunk
    guidelines_chunk_size: int = 800

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
