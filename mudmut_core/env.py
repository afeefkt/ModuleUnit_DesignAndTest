"""Bootstrap the in-process MUD + MUT environment.

Adds the two halves of the monorepo to ``sys.path`` and sets the cpputest-rag
environment variables to absolute paths before any ``app.*`` import, so both
halves run in-process regardless of the caller's working directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MUD_SRC = REPO_ROOT / "mud-tool" / "python-sidecar" / "src"
CPPUTEST_BACKEND = REPO_ROOT / "cpputest-rag" / "backend"

_LOADED = False


def _read_root_env() -> dict[str, str]:
    """Read the repo-root ``.env`` (plain ``KEY=VALUE`` lines) without a dependency."""
    values: dict[str, str] = {}
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def ensure_environment() -> str:
    """Idempotently configure ``sys.path`` + cpputest-rag env vars.

    Returns the resolved ``OLLAMA_URL`` (with the ``/api`` suffix stripped for
    the plain host URL used by the MUD toolchain).
    """
    global _LOADED
    if _LOADED:
        return os.environ.get("OLLAMA_URL", "http://localhost:11434/api")

    for p in (str(MUD_SRC), str(CPPUTEST_BACKEND)):
        if p not in sys.path:
            sys.path.insert(0, p)

    root_env = _read_root_env()
    # A real environment variable wins over the repo-root .env file.
    ollama_url = (
        os.environ.get("OLLAMA_URL")
        or root_env.get("OLLAMA_URL")
        or "http://localhost:11434/api"
    )

    # cpputest-rag ``app.config.Config()`` is built at import time from env vars
    # with relative defaults, so absolute paths must be set BEFORE ``import app.*``.
    os.environ["OLLAMA_URL"] = ollama_url
    os.environ["TEST_EXAMPLES_DIR"] = str(REPO_ROOT / "inputs" / "test_examples")
    # Runs pass their own 03_mut dir; this default only serves the optional FastAPI backend.
    os.environ["OUTPUT_DIR"] = str(REPO_ROOT / "outputs" / "_state" / "generated_tests")
    os.environ.setdefault("DATABASE_PATH", str(REPO_ROOT / "outputs" / "_state" / "cpputest.db"))
    os.environ.setdefault("EMBED_MODEL", root_env.get("EMBED_MODEL", "all-minilm:latest"))
    os.environ.setdefault("GEN_MODEL", root_env.get("GEN_MODEL", "qwen2.5:7b"))
    # mud-tool design assets now live under inputs/ — set them so guidelines and
    # skills are actually loaded (the defaults pointed at python-sidecar/data/*).
    os.environ.setdefault("MUD_GUIDELINES_DIR", str(REPO_ROOT / "inputs" / "guidelines"))
    os.environ.setdefault("MUD_SKILLS_DIR", str(REPO_ROOT / "inputs" / "skills"))
    # Request timeouts: cpputest-rag reads REQUEST_TIMEOUT; mud-tool reads MUD_REQUEST_TIMEOUT.
    os.environ.setdefault("REQUEST_TIMEOUT", root_env.get("REQUEST_TIMEOUT", "1800"))
    os.environ.setdefault("MUD_REQUEST_TIMEOUT", root_env.get("MUD_REQUEST_TIMEOUT", "1800"))

    # Apply the saved stage selection (config/stages.json) to env vars so a fresh
    # process picks up the user's provider+model choices (deferred import).
    try:
        from mudmut_core import agents
        agents.apply_stages_to_env(agents.load_stages())
    except Exception:
        pass

    # Export provider keys before anything reads (and caches) mud-tool settings.
    _export_keys()

    _LOADED = True
    return ollama_url


def _export_keys() -> list[str]:
    """Put resolved provider keys into ``os.environ`` (process only, never a file).

    Returns the names newly added. mud-tool reads the shared names
    (``OPENROUTER_API_KEY`` …) via ``validation_alias``; WSL does not inherit
    Windows user variables, so they are resolved env → .env → Windows User scope.
    """
    added: list[str] = []
    try:
        from mudmut_core.llm.providers import get_providers, resolve_key
        for p in get_providers().values():
            if p.key_env and not os.environ.get(p.key_env):
                key = resolve_key(p.key_env)
                if key:
                    os.environ[p.key_env] = key
                    added.append(p.key_env)
    except Exception:
        pass
    return added


def export_provider_keys() -> None:
    """Ensure provider keys are exported; refresh mud-tool settings if a key was
    only found now (settings are cached and would otherwise miss it)."""
    ensure_environment()
    if _export_keys():
        try:
            from mudtool.config.settings import get_settings
            get_settings.cache_clear()
            from mudtool.api.dependencies import reset_orchestrator
            reset_orchestrator()
        except Exception:
            pass


def ollama_host() -> str:
    """Return the bare Ollama host (``http://host:port``, no ``/api``)."""
    url = ensure_environment()
    return url.split("/api")[0].rstrip("/")


def import_mudtool():
    """Configure the environment and return the ``mudtool`` package."""
    ensure_environment()
    import mudtool  # noqa: F401
    return mudtool
