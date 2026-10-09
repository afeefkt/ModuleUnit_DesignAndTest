"""LLM client layer — providers (Ollama / OpenRouter / NVIDIA / DeepSeek) and a
thin OpenAI-compatible chat client.

Phase 0 ships only ``ollama_unload`` (used by the chain to free VRAM between
stages).  Phase 2 adds ``providers.py`` and ``client.py``.
"""

from __future__ import annotations

import json
import urllib.request


def ollama_unload(model: str, base_url: str = "http://localhost:11434") -> bool:
    """Ask Ollama to unload ``model`` from memory (``keep_alive=0``).

    Best-effort: returns True on success, False otherwise (never raises).
    """
    if not model:
        return False
    payload = json.dumps({"model": model, "keep_alive": 0}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return True
    except Exception:
        return False


def unload_many(models: list[str], base_url: str = "http://localhost:11434") -> int:
    """Unload several model names; return how many succeeded."""
    seen: set[str] = set()
    n = 0
    for m in models:
        if m and m not in seen:
            seen.add(m)
            if ollama_unload(m, base_url):
                n += 1
    return n
