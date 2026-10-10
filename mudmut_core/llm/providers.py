"""LLM provider registry — Ollama / OpenRouter / NVIDIA NIM / DeepSeek.

Built-ins are extensible via ``config/providers.json``.  Each provider knows its
OpenAI-compatible base URL, the env var that holds its key, its privacy class,
and how to list its models.  Keys are resolved from (1) the process env, (2) the
repo-root ``.env``, or (3) the Windows *User* scope when running inside WSL —
and are never written to disk or logs.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mudmut_core.env import REPO_ROOT

BUILTIN_PROVIDERS: dict[str, dict[str, Any]] = {
    "ollama": {
        "name": "Ollama (local)",
        "base_url": "http://localhost:11434",
        "key_env": None,
        "privacy": "local",
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "privacy": "cloud",
    },
    "nvidia": {
        "name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
        "privacy": "cloud",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "key_env": "DEEPSEEK_API_KEY",
        "privacy": "cloud",
    },
}


@dataclass
class Provider:
    id: str
    name: str
    base_url: str
    key_env: Optional[str] = None
    privacy: str = "local"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_cloud(self) -> bool:
        return self.privacy == "cloud"

    @property
    def is_local(self) -> bool:
        return not self.is_cloud


def _user_providers() -> dict[str, dict[str, Any]]:
    """Merge ``config/providers.json`` (optional) over the built-ins."""
    p = REPO_ROOT / "config" / "providers.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_providers() -> dict[str, Provider]:
    """Return ``{id: Provider}`` (built-ins merged with ``config/providers.json``)."""
    merged = {k: dict(v) for k, v in BUILTIN_PROVIDERS.items()}
    for pid, cfg in _user_providers().items():
        if pid in merged:
            merged[pid].update(cfg)
        else:
            merged[pid] = cfg
    out: dict[str, Provider] = {}
    for pid, cfg in merged.items():
        out[pid] = Provider(
            id=pid,
            name=cfg.get("name", pid),
            base_url=cfg.get("base_url", ""),
            key_env=cfg.get("key_env"),
            privacy=cfg.get("privacy", "local"),
            extra={k: v for k, v in cfg.items() if k not in ("name", "base_url", "key_env", "privacy")},
        )
    return out


# ── API keys ──────────────────────────────────────────────────────────────────
def _read_root_env() -> dict[str, str]:
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return {}
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


_WINDOWS_USER_KEYS: dict[str, str] = {}


def _windows_user_env(name: str) -> Optional[str]:
    """Read a Windows *User*-scope env var via powershell (cached, in-memory)."""
    if name in _WINDOWS_USER_KEYS:
        return _WINDOWS_USER_KEYS[name]
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"[Environment]::GetEnvironmentVariable('{name}','User')"],
            capture_output=True, text=True, timeout=20,
        )
        val = proc.stdout.strip() or None
    except Exception:
        val = None
    _WINDOWS_USER_KEYS[name] = val
    return val


def resolve_key(name: Optional[str]) -> Optional[str]:
    """Resolve an API key by name; returns None (and its source) when absent."""
    if not name:
        return None
    if os.environ.get(name):
        return os.environ[name]
    root_env = _read_root_env()
    if root_env.get(name):
        return root_env[name]
    # WSL fallback: Windows user-scope variable.
    if os.environ.get("WSL_DISTRO_NAME"):
        return _windows_user_env(name)
    return None


def key_source(name: Optional[str]) -> str:
    """Human-readable source of an API key: 'process' / '.env' / 'Windows user' / missing."""
    if not name:
        return "not required (local)"
    if os.environ.get(name):
        return "process"
    if _read_root_env().get(name):
        return ".env"
    if os.environ.get("WSL_DISTRO_NAME") and _windows_user_env(name):
        return "Windows user env"
    return "missing"


def has_key(provider: Provider) -> bool:
    return provider.key_env is None or resolve_key(provider.key_env) is not None


# ── model listing / testing ───────────────────────────────────────────────────
def _http_json(url: str, *, timeout: int = 30, api_key: Optional[str] = None) -> Any:
    import urllib.request
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_models(provider: Provider) -> list[dict[str, Any]]:
    """Return ``[{id, free}]`` for the provider.  OpenRouter free models are flagged."""
    if provider.id == "ollama":
        data = _http_json(f"{provider.base_url.rstrip('/')}/api/tags")
        return [{"id": m.get("name", ""), "free": True} for m in data.get("models", [])]

    key = resolve_key(provider.key_env)
    base = provider.base_url.rstrip("/")
    data = _http_json(f"{base}/models", api_key=key)
    models = data.get("data", [])

    free_ids: set[str] = set()
    if provider.id == "openrouter":
        try:
            allm = _http_json("https://openrouter.ai/api/v1/models")
            for m in allm.get("data", []):
                pricing = (m.get("pricing") or {})
                if float(pricing.get("prompt", 0) or 0) == 0 and float(pricing.get("completion", 0) or 0) == 0:
                    free_ids.add(m.get("id", ""))
        except Exception:
            pass

    out: list[dict[str, Any]] = []
    for m in models:
        mid = m.get("id", "")
        out.append({"id": mid, "free": mid in free_ids})
    return out


def test_chat(provider: Provider, model: str) -> tuple[bool, str]:
    """One-line chat test; returns (ok, detail)."""
    try:
        from mudmut_core.llm.client import chat_sync
        reply = chat_sync(provider, model, [{"role": "user", "content": "Say OK"}], max_tokens=8)
        return bool(reply.strip()), reply.strip()[:60]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:120]
