"""Per-stage agent registry — provider + model for each pipeline stage.

Each stage (planner, mud_spec_skeleton, …, test_generator, rag_embed) has a
provider (ollama / openrouter / nvidia / deepseek) and a model.  The current
selection persists in ``config/stages.json``; presets live in
``config/presets.json``.  Applying a stage writes the corresponding env vars
(mud-tool ``MUD_*`` or cpputest-rag ``GEN_MODEL`` / ``EMBED_MODEL``) and resets
the cached orchestrator / app config so the next run uses the new selection.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from mudmut_core import env
from mudmut_core.llm.providers import get_providers, list_models

CONFIG_DIR = env.REPO_ROOT / "config"
STAGES_FILE = CONFIG_DIR / "stages.json"
PRESETS_FILE = CONFIG_DIR / "presets.json"

MUD_ENV = env.MUD_SRC.parent / ".env"  # mud-tool/python-sidecar/.env
CPPUTEST_ENV = env.REPO_ROOT / "cpputest-rag" / ".env"


@dataclass
class Stage:
    key: str
    label: str
    side: str          # "mud" | "mut"
    role: str          # code | reasoning | vision | embed
    model_env: str     # env var that holds the model
    provider_env: Optional[str]  # env var that holds the provider (None = ollama-only)
    model_setting: str  # mud-tool settings field (mut: app.config attribute)
    provider_setting: Optional[str]
    recommended: str
    description: str = ""


def shared_with(key: str) -> list[str]:
    """Other stages that read the same model setting (changing one changes them)."""
    me = STAGES_BY_KEY[key]
    return [s.key for s in STAGES if s.key != key and s.model_env == me.model_env]


# ── stage registry ────────────────────────────────────────────────────────────
STAGES: list[Stage] = [
    Stage("planner", "Module planner", "mud", "reasoning",
          "MUD_PLANNER_MODEL", "MUD_PLANNER_PROVIDER",
          "planner_model", "planner_provider", "deepseek-r1:7b",
          "Splits architectural requirements into SWC modules."),
    Stage("mud_spec_skeleton", "MUD spec skeleton (Stage 1)", "mud", "reasoning",
          "MUD_SPEC_SKELETON_MODEL", "MUD_SPEC_SKELETON_PROVIDER",
          "mud_spec_skeleton_model", "mud_spec_skeleton_provider", "deepseek-r1:7b",
          "Extracts runnables + per-runnable key steps from requirements."),
    Stage("mud_spec_generator", "MUD spec generator (Stage 3)", "mud", "code",
          "MUD_PIPELINE_GENERATOR_MODEL", "MUD_PIPELINE_GENERATOR_PROVIDER",
          "pipeline_generator_model", "pipeline_generator_provider", "qwen3:8b-ctx16384",
          "Fills runnable details: signature, pseudo-code, traceability."),
    Stage("mud_spec_reviewer", "MUD spec reviewer", "mud", "reasoning",
          "MUD_PIPELINE_REVIEWER_MODEL", "MUD_PIPELINE_REVIEWER_PROVIDER",
          "pipeline_reviewer_model", "pipeline_reviewer_provider", "deepseek-r1:7b",
          "Reviews/regenerates the MUD spec (coverage %, issues)."),
    Stage("activity_skeleton", "Activity skeleton (Stage 1)", "mud", "reasoning",
          "MUD_ACTIVITY_PIPELINE_SKELETON_MODEL", "MUD_ACTIVITY_PIPELINE_SKELETON_PROVIDER",
          "activity_pipeline_skeleton_model", "activity_pipeline_skeleton_provider", "deepseek-r1:7b",
          "Activity flow topology from Section 7."),
    Stage("activity_generator", "Activity generator (Stage 3)", "mud", "code",
          "MUD_PIPELINE_GENERATOR_MODEL", "MUD_PIPELINE_GENERATOR_PROVIDER",
          "pipeline_generator_model", "pipeline_generator_provider", "qwen3:8b-ctx16384",
          "Per-runnable code-flow diagram generation."),
    Stage("activity_reviewer", "Activity reviewer (Stage 4)", "mud", "reasoning",
          "MUD_ACTIVITY_PIPELINE_REVIEWER_MODEL", "MUD_ACTIVITY_PIPELINE_REVIEWER_PROVIDER",
          "activity_pipeline_reviewer_model", "activity_pipeline_reviewer_provider", "deepseek-r1:7b",
          "Cross-runnable activity review."),
    Stage("visual_qa", "Visual QA (optional)", "mud", "vision",
          "MUD_VISUAL_QA_MODEL", None,
          "visual_qa_model", None, "llava:7b",
          "Vision review of rendered diagrams (Ollama only — native /api/chat)."),
    Stage("guidelines_embed", "Guidelines embeddings", "mud", "embed",
          "MUD_GUIDELINES_EMBED_MODEL", None,
          "guidelines_embed_model", None, "nomic-embed-text:latest",
          "Embedding model for design-guideline RAG (Ollama only)."),
    Stage("test_generator", "Test generator", "mut", "code",
          "GEN_MODEL", "TEST_GEN_PROVIDER",
          "GEN_MODEL", None, "qwen2.5:7b",
          "Generates CppUTest cases for each function."),
    Stage("test_fixer", "Test fix loop", "mut", "code",
          "FIX_MODEL", "TEST_FIX_PROVIDER",
          "FIX_MODEL", None, "qwen2.5:7b",
          "Repairs failing-to-compile test files (defaults to the test generator)."),
    Stage("rag_embed", "RAG embeddings", "mut", "embed",
          "EMBED_MODEL", None,
          "EMBED_MODEL", None, "all-minilm:latest",
          "Embedding model for test-example RAG (Ollama only)."),
]

STAGES_BY_KEY = {s.key: s for s in STAGES}


# ── presets ───────────────────────────────────────────────────────────────────
def load_presets() -> dict[str, Any]:
    if PRESETS_FILE.is_file():
        try:
            return json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def load_stages() -> dict[str, dict[str, str]]:
    if STAGES_FILE.is_file():
        try:
            return json.loads(STAGES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_stages(data: dict[str, dict[str, str]]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def apply_stages_to_env(stages: dict[str, dict[str, str]]) -> None:
    """Export a stages map to environment variables (fresh-process bootstrap)."""
    for key, cfg in (stages or {}).items():
        stage = STAGES_BY_KEY.get(key)
        if not stage or not isinstance(cfg, dict):
            continue
        provider = cfg.get("provider") or "ollama"
        model = cfg.get("model") or ""
        if not model:
            # A stage saved without a model (e.g. a cloud stage before a model
            # was picked) must not blank out the configured/default model.
            continue
        os.environ[stage.model_env] = model
        if stage.provider_env:
            # Local ollama is the default → empty override (use global backend).
            os.environ[stage.provider_env] = "" if provider == "ollama" else provider


# ── env writing ───────────────────────────────────────────────────────────────
def _write_env(env_path: Path, updates: dict[str, str]) -> None:
    """Update key=value lines in an env file in place (append if missing)."""
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
    updated: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                updated.add(key)
                continue
        out.append(line)
    for key, val in updates.items():
        if key not in updated:
            out.append(f"{key}={val}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _current_mud_settings() -> Any:
    env.ensure_environment()
    from mudtool.config.settings import get_settings
    return get_settings()


def _stage_current(stage: Stage, settings: Any, override: dict) -> dict[str, str]:
    if stage.side == "mut":
        model = os.environ.get(stage.model_setting, "")
        provider = os.environ.get(stage.provider_env, "") if stage.provider_env else ""
    else:
        model = getattr(settings, stage.model_setting, "") or ""
        provider = getattr(settings, stage.provider_setting, "") if stage.provider_setting else ""
    # config/stages.json override wins (single source of truth for the UI/CLI).
    cfg = override.get(stage.key) or {}
    if cfg.get("model"):
        model = cfg["model"]
    if cfg.get("provider"):
        provider = cfg["provider"]
    return {"provider": provider or "ollama", "model": model}


def get_stages() -> dict[str, dict[str, Any]]:
    """Return current provider+model per stage (with label/role/recommended)."""
    settings = _current_mud_settings()
    override = load_stages()
    out: dict[str, dict[str, Any]] = {}
    for s in STAGES:
        cur = _stage_current(s, settings, override)
        out[s.key] = {
            "label": s.label,
            "side": s.side,
            "role": s.role,
            "provider": cur["provider"],
            "model": cur["model"],
            "recommended": s.recommended,
            "description": s.description,
            "is_recommended": bool(s.recommended) and cur["model"] == s.recommended,
        }
    return out


def _reset_mud_caches() -> None:
    try:
        from mudtool.config.settings import get_settings
        get_settings.cache_clear()
        from mudtool.api.dependencies import reset_orchestrator
        reset_orchestrator()
    except Exception:
        pass


def _reset_mut_caches() -> None:
    # GEN_MODEL / EMBED_MODEL are read at app.config import time; mutate the
    # shared config object in place (all modules hold the same reference).
    try:
        from app.config import config
        # no-op placeholder — the actual mutation happens in set_stage.
    except Exception:
        pass


def set_stage(key: str, provider: str, model: str) -> dict[str, Any]:
    """Set provider+model for one stage; writes env + resets caches. Returns the stage."""
    stage = STAGES_BY_KEY.get(key)
    if not stage:
        raise KeyError(f"unknown stage: {key}")
    provider = provider or "ollama"

    stages = load_stages()
    stages.setdefault(key, {})["provider"] = provider
    stages.setdefault(key, {})["model"] = model
    save_stages(stages)

    if stage.side == "mud":
        # Local ollama is the *default* provider — write an empty override so the
        # stage falls back to the global backend (avoids locking the mud-tool to
        # "ollama" and breaking the deepseek global path). Cloud providers write
        # their id so the orchestrator swaps base URL + key.
        updates: dict[str, str] = {stage.model_env: model}
        if stage.provider_env:
            updates[stage.provider_env] = "" if provider == "ollama" else provider
        _write_env(MUD_ENV, updates)
        for k, v in updates.items():
            os.environ[k] = v
        _reset_mud_caches()
    else:
        # MUT: model + provider env (single source of truth is stages.json; the
        # .env files are no longer written — nothing loads them). Mutate the
        # shared app.config in place for the attrs it owns (GEN_MODEL/EMBED_MODEL).
        os.environ[stage.model_env] = model
        if stage.provider_env:
            os.environ[stage.provider_env] = provider
        if stage.model_setting in ("GEN_MODEL", "EMBED_MODEL"):
            try:
                from app.config import config
                setattr(config, stage.model_setting, model)
            except Exception:
                pass
            if stage.model_setting == "EMBED_MODEL":
                import mudmut_core.verify as verify
                verify._index_built = False

    return get_stages()[key]


def _auto_model(provider_id: str) -> str:
    """First model of ``provider_id`` that a probe saw answering (non-reasoning), else ''."""
    try:
        from mudmut_core.llm import probe
        return probe.first_working(provider_id, sorted(probe.cached_status(provider_id))) or ""
    except Exception:
        return ""


def apply_preset(name: str) -> dict[str, Any]:
    """Apply every stage in a preset; returns the new stage map.

    A blank cloud model is filled from the probe cache (a free model that answered a
    "Say OK" probe) when one is known; otherwise the stage is skipped so a blank id is
    never sent to a cloud API.
    """
    return apply_preset_with_report(name)[0]


def apply_preset_with_report(name: str) -> tuple[dict[str, Any], list[str]]:
    """Like :func:`apply_preset`, also returning the stage keys that were skipped
    because the preset has no model for a cloud provider (so callers can warn)."""
    presets = load_presets()
    preset = presets.get(name)
    if not preset:
        raise KeyError(f"unknown preset: {name}")
    skipped: list[str] = []
    for key, cfg in preset.get("stages", {}).items():
        if key not in STAGES_BY_KEY:
            continue
        provider = cfg.get("provider", "ollama")
        model = cfg.get("model", "")
        if provider != "ollama" and not model:
            model = _auto_model(provider)  # a model a probe saw answering, if any
        if provider != "ollama" and not model:
            skipped.append(key)  # blank cloud model — leave the stage unchanged
            continue
        set_stage(key, provider, model)
    return get_stages(), skipped


def reset_defaults() -> dict[str, Any]:
    """Restore the default local preset and clear any per-stage overrides."""
    if STAGES_FILE.is_file():
        STAGES_FILE.unlink()
    try:
        return apply_preset("local-recommended")
    except KeyError:
        return get_stages()


def available_models(provider_id: str) -> list[dict[str, Any]]:
    """Live model list for a provider (with OpenRouter free flag)."""
    providers = get_providers()
    p = providers.get(provider_id)
    if not p:
        return []
    try:
        return list_models(p)
    except Exception:
        return []
