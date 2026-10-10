"""Thin OpenAI-compatible chat client (sync + async) over httpx.

Used by the MUT test-generation and fix-loop stages (and the UI provider tests).
``think`` and ``format`` (Ollama extensions) are only sent to local Ollama;
``<think>…</think>`` reasoning blocks are stripped from the reply.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Optional

from mudmut_core.llm.providers import Provider, ProviderError, resolve_key

_REASONING_KEYWORDS = ("deepseek-r1", ":r1-", "qwq", "thinking", "qwen3")


def _chat_url(provider: Provider) -> str:
    """OpenAI-compatible chat endpoint.

    Local Ollama exposes it under ``/v1``; cloud providers' ``base_url`` already
    ends in ``/v1``.
    """
    base = provider.base_url.rstrip("/")
    if provider.is_local:
        return f"{base}/v1/chat/completions"
    return f"{base}/chat/completions"


def ollama_unload(model: str, base_url: Optional[str] = None) -> bool:
    """Ask Ollama to unload ``model`` from memory (``keep_alive=0``). Best-effort."""
    if not model:
        return False
    from mudmut_core import env
    base_url = (base_url or env.ollama_host()).rstrip("/")
    payload = json.dumps({"model": model, "keep_alive": 0}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return True
    except Exception:
        return False


def unload_many(models: list[str], base_url: Optional[str] = None) -> int:
    seen: set[str] = set()
    n = 0
    for m in models:
        if m and m not in seen:
            seen.add(m)
            if ollama_unload(m, base_url):
                n += 1
    return n


def _payload(provider: Provider, model: str, messages: list[dict], *, max_tokens: int,
             temperature: float, json_mode: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if provider.is_local:
        model_lower = model.lower()
        if any(kw in model_lower for kw in _REASONING_KEYWORDS):
            payload["think"] = True
        if json_mode:
            payload["format"] = "json"
    elif json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _headers(provider: Provider) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = resolve_key(provider.key_env)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _strip_thinking(content: str) -> str:
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def _extract(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    return _strip_thinking(choices[0].get("message", {}).get("content", "") or "")


def _raise_for_status(resp) -> None:
    if getattr(resp, "status_code", 0) >= 400:
        body = ""
        try:
            body = resp.read().decode("utf-8", "replace")[:300]
        except Exception:
            body = getattr(resp, "reason_phrase", "")
        raise ProviderError(resp.status_code, body)


async def achat(provider: Provider, model: str, messages: list[dict], *, max_tokens: int = 2000,
                temperature: float = 0.2, json_mode: bool = False, timeout: float = 1800.0) -> str:
    import httpx
    payload = _payload(provider, model, messages, max_tokens=max_tokens,
                       temperature=temperature, json_mode=json_mode)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(_chat_url(provider), json=payload, headers=_headers(provider))
        _raise_for_status(resp)
        return _extract(resp.json())


def chat_sync(provider: Provider, model: str, messages: list[dict], *, max_tokens: int = 2000,
              temperature: float = 0.2, json_mode: bool = False, timeout: float = 1800.0) -> str:
    from mudmut_core import aio
    return aio.run_sync(achat(provider, model, messages, max_tokens=max_tokens,
                              temperature=temperature, json_mode=json_mode, timeout=timeout))


def chat_blocking(provider: Provider, model: str, messages: list[dict], *, max_tokens: int = 2000,
                  temperature: float = 0.2, json_mode: bool = False, timeout: float = 1800.0) -> str:
    """Synchronous chat via urllib — safe to call from inside an already-running
    asyncio loop (unlike ``chat_sync``, which needs the shared loop to be idle)."""
    payload = _payload(provider, model, messages, max_tokens=max_tokens,
                       temperature=temperature, json_mode=json_mode)
    data = json.dumps(payload).encode("utf-8")
    headers = _headers(provider)
    req = urllib.request.Request(_chat_url(provider), data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _extract(json.loads(resp.read().decode("utf-8")))
    except urllib.error.HTTPError as exc:
        raise ProviderError(exc.code, exc.read().decode("utf-8", "replace")[:300]) from exc


def chat(provider: Provider, model: str, messages: list[dict], **kwargs) -> str:
    """Alias for ``chat_sync`` (synchronous chat)."""
    return chat_sync(provider, model, messages, **kwargs)
