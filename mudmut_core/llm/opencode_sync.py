"""Sync ``opencode.json`` providers from the LLM provider registry.

Writes the provider block for each cloud provider as an ``@ai-sdk/openai-compatible``
entry whose ``apiKey`` is ``{env:VAR}`` (no secret in the file), and an ``ollama``
provider using the ``@ai-sdk/openai-compatible`` provider with the local base URL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mudmut_core.env import REPO_ROOT
from mudmut_core.llm.providers import get_providers

OPENCODE_JSON = REPO_ROOT / "opencode.json"


def _provider_block(p: Any) -> dict[str, Any] | None:
    if p.id == "ollama":
        return {
            "npm": "@ai-sdk/openai-compatible",
            "name": "ollama",
            "options": {"baseURL": f"{p.base_url.rstrip('/')}/v1"},
        }
    return {
        "npm": "@ai-sdk/openai-compatible",
        "name": p.id,
        "options": {
            "baseURL": p.base_url.rstrip("/"),
            "apiKey": f"{{env:{p.key_env}}}",
        },
    }


def build_provider_block() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for pid, p in get_providers().items():
        block = _provider_block(p)
        if block:
            out[pid] = block
    return out


def sync() -> Path:
    """Merge the generated provider block into ``opencode.json`` and return its path."""
    providers = build_provider_block()
    data: dict[str, Any] = {}
    if OPENCODE_JSON.is_file():
        data = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
    data["provider"] = providers
    OPENCODE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return OPENCODE_JSON


if __name__ == "__main__":
    print(sync())
