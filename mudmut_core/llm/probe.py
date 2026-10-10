"""Probe which listed models actually answer (free tiers list many that are rate-limited,
retired, or reply empty because they are reasoning models).

Sends only a fixed one-word test prompt — never project data. Results are cached in
``config/model_probe.json`` (git-ignored) for 24 h and shown as ✅ / ⚠️ / ❌ in the UI.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from mudmut_core.env import REPO_ROOT
from mudmut_core.llm.providers import Provider, ProviderError

PROBE_FILE = REPO_ROOT / "config" / "model_probe.json"
TTL_SECONDS = 24 * 3600

OK, RATE_LIMITED, UNAVAILABLE, EMPTY, ERROR, PAID = "ok", "rate-limited", "unavailable", "empty", "error", "paid"
ICONS = {OK: "✅", RATE_LIMITED: "⚠️", EMPTY: "⚠️", UNAVAILABLE: "❌", ERROR: "❌", PAID: "💲"}
LABELS = {
    OK: "answers",
    RATE_LIMITED: "rate-limited right now",
    UNAVAILABLE: "not hosted / retired",
    EMPTY: "empty reply (reasoning model?)",
    ERROR: "error",
    PAID: "not in the free plan (needs credits)",
}


def classify(reply: Optional[str] = None, exc: Optional[BaseException] = None) -> str:
    """Map a probe outcome to a status string."""
    if exc is not None:
        if isinstance(exc, ProviderError):
            if exc.status == 429:
                return RATE_LIMITED
            if exc.status in (404, 410):
                return UNAVAILABLE
            if exc.status in (402, 403):
                return PAID
        return ERROR
    return OK if (reply or "").strip() else EMPTY


def _load() -> dict[str, Any]:
    try:
        return json.loads(PROBE_FILE.read_text(encoding="utf-8")) if PROBE_FILE.is_file() else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict[str, Any]) -> None:
    PROBE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROBE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    tmp.replace(PROBE_FILE)


def cached_status(provider_id: str) -> dict[str, str]:
    """``{model_id: status}`` for results younger than the TTL."""
    now = time.time()
    entries = (_load().get(provider_id) or {})
    return {m: e["status"] for m, e in entries.items() if now - e.get("ts", 0) < TTL_SECONDS}


def probe_one(provider: Provider, model: str, timeout: int = 30) -> str:
    from mudmut_core.llm.client import chat_blocking
    try:
        reply = chat_blocking(
            provider, model, [{"role": "user", "content": "Say OK"}],
            max_tokens=400, temperature=0.0, timeout=timeout,
        )
        return classify(reply=reply)
    except Exception as exc:  # noqa: BLE001 - classified, never raised
        return classify(exc=exc)


def probe_models(
    provider: Provider,
    model_ids: Iterable[str],
    *,
    max_models: int = 20,
    workers: int = 4,
    timeout: int = 30,
    progress: Optional[Callable[[int, int], None]] = None,
) -> dict[str, str]:
    """Probe up to ``max_models`` models concurrently and merge the results into the cache."""
    ids = list(dict.fromkeys(model_ids))[:max_models]
    results: dict[str, str] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(probe_one, provider, m, timeout): m for m in ids}
        for fut in futures:
            results[futures[fut]] = fut.result()
            done += 1
            if progress:
                progress(done, len(ids))
    data = _load()
    entries = data.setdefault(provider.id, {})
    now = time.time()
    for model, status in results.items():
        entries[model] = {"status": status, "ts": now}
    _save(data)
    return results


_REASONING = ("r1", "reason", "thinking", "qwq", "think")


def first_working(provider_id: str, candidates: Iterable[str]) -> Optional[str]:
    """First candidate that probed ✅ and is not a reasoning model (None if none known)."""
    status = cached_status(provider_id)
    for m in candidates:
        if status.get(m) == OK and not any(tag in m.lower() for tag in _REASONING):
            return m
    return None
