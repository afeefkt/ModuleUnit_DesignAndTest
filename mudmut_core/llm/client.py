"""Thin OpenAI-compatible chat client (sync + async + streaming) over httpx / urllib.

Used by the MUT test-generation and fix-loop stages, the UI provider tests and the AI
monitor's test chat. ``think`` and ``format`` (Ollama extensions) are only sent to local
Ollama; ``<think>…</think>`` reasoning blocks are stripped from the reply. Every call is
reported to :mod:`mudmut_core.llm.observe` (no credentials are recorded).
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Iterator, Optional

from mudmut_core.llm import observe
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
             temperature: float, json_mode: bool, stream: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if stream:
        payload["stream"] = True
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


def _reasoning_of(data: dict[str, Any]) -> str:
    """The model's thinking text: a separate field, or inline ``<think>`` blocks."""
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message", {}) or {}
    reasoning = message.get("thinking") or message.get("reasoning_content") or message.get("reasoning") or ""
    if not reasoning:
        reasoning = "\n".join(re.findall(r"<think>(.*?)</think>", message.get("content", "") or "", flags=re.DOTALL)).strip()
    return reasoning


def _flatten(messages: list[dict]) -> tuple[str, str]:
    """(system text, everything else) of a message list, for the monitor."""
    system = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
    rest = [m for m in messages if m.get("role") != "system"]
    if len(rest) == 1:
        return system, rest[0].get("content", "")
    return system, "\n\n".join(f"[{m.get('role')}] {m.get('content', '')}" for m in rest)


def _begin(provider: Provider, model: str, messages: list[dict], kind: str) -> str:
    system, user = _flatten(messages)
    return observe.start_call(provider=provider.id, model=model, kind=kind, system=system, user=user)


def _finish(call_id: str, data: dict[str, Any], started: float) -> str:
    usage = data.get("usage") or {}
    choices = data.get("choices") or [{}]
    reply = _extract(data)
    observe.end_call(
        call_id, content=reply, reasoning=_reasoning_of(data),
        input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0),
        finish_reason=(choices[0] or {}).get("finish_reason"),
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    return reply


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
    call_id = _begin(provider, model, messages, "chat")
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_chat_url(provider), json=payload, headers=_headers(provider))
            _raise_for_status(resp)
            return _finish(call_id, resp.json(), started)
    except Exception as exc:
        observe.error_call(call_id, f"{type(exc).__name__}: {exc}")
        raise


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
    call_id = _begin(provider, model, messages, "chat")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _finish(call_id, json.loads(resp.read().decode("utf-8")), started)
    except urllib.error.HTTPError as exc:
        err = ProviderError(exc.code, exc.read().decode("utf-8", "replace")[:300])
        observe.error_call(call_id, str(err))
        raise err from exc
    except Exception as exc:
        observe.error_call(call_id, f"{type(exc).__name__}: {exc}")
        raise


def chat(provider: Provider, model: str, messages: list[dict], **kwargs) -> str:
    """Alias for ``chat_sync`` (synchronous chat)."""
    return chat_sync(provider, model, messages, **kwargs)


# ── streaming (AI monitor test chat) ─────────────────────────────────────────
def iter_sse_deltas(lines: Iterator[str]) -> Iterator[tuple[str, str]]:
    """Parse an OpenAI-style SSE stream into ``("reasoning" | "text", chunk)`` pairs.

    Reasoning arrives either in a separate delta field (``reasoning`` /
    ``reasoning_content`` / ``thinking``) or inline between ``<think>`` tags.
    """
    in_think = False
    for raw in lines:
        raw = raw.strip()
        if not raw.startswith("data:"):
            continue
        body = raw[5:].strip()
        if body == "[DONE]":
            return
        try:
            chunk = json.loads(body)
        except ValueError:
            continue
        delta = ((chunk.get("choices") or [{}])[0] or {}).get("delta") or {}
        reasoning = delta.get("reasoning") or delta.get("reasoning_content") or delta.get("thinking") or ""
        if reasoning:
            yield "reasoning", reasoning
        text = delta.get("content") or ""
        while text:
            if in_think:
                end = text.find("</think>")
                if end < 0:
                    yield "reasoning", text
                    text = ""
                else:
                    if end:
                        yield "reasoning", text[:end]
                    text = text[end + len("</think>"):]
                    in_think = False
            else:
                start = text.find("<think>")
                if start < 0:
                    yield "text", text
                    text = ""
                else:
                    if start:
                        yield "text", text[:start]
                    text = text[start + len("<think>"):]
                    in_think = True


def stream_blocking(provider: Provider, model: str, messages: list[dict], *, max_tokens: int = 1000,
                    temperature: float = 0.2, timeout: float = 300.0, kind: str = "manual") -> Iterator[tuple[str, str]]:
    """Stream a chat reply as ``("reasoning" | "text", chunk)`` pairs (synchronous generator).

    The call is recorded for the AI monitor (tagged ``kind``, default "manual").
    """
    payload = _payload(provider, model, messages, max_tokens=max_tokens, temperature=temperature,
                       json_mode=False, stream=True)
    req = urllib.request.Request(_chat_url(provider), data=json.dumps(payload).encode("utf-8"),
                                 headers=_headers(provider))
    call_id = _begin(provider, model, messages, kind)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            lines = (line.decode("utf-8", "replace") for line in resp)
            for part, chunk in iter_sse_deltas(lines):
                observe.add_chunk(call_id, text=chunk if part == "text" else "",
                                  reasoning=chunk if part == "reasoning" else "")
                yield part, chunk
        observe.end_call(call_id, latency_ms=int((time.monotonic() - started) * 1000))
    except urllib.error.HTTPError as exc:
        err = ProviderError(exc.code, exc.read().decode("utf-8", "replace")[:300])
        observe.error_call(call_id, str(err))
        raise err from exc
    except Exception as exc:
        observe.error_call(call_id, f"{type(exc).__name__}: {exc}")
        raise
