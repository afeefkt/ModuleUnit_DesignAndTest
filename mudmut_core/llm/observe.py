"""Record every request to / response from a model so the UI can show it live.

Two sources feed it: mud-tool's backends (through ``mudtool.ai.observer``, registered by
:func:`register`) and ``mudmut_core.llm.client`` (unit-test generation, fix loop, test chat).
Nothing about credentials is recorded (no headers; known key values are masked in text).

* live view: an in-memory ring buffer (:func:`recent`)
* audit trail: JSONL per run (``outputs/<run>/llm_log.jsonl``) or ``outputs/_state/llm_log.jsonl``
"""

from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from mudmut_core.workspace import RUNS_ROOT

MAX_CALLS = 300          # ring buffer size
MAX_TEXT = 60_000        # characters kept per prompt / response / thinking
STATE_LOG = RUNS_ROOT / "_state" / "llm_log.jsonl"

_run_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("llm_run", default=None)
_stage_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("llm_stage", default=None)

_lock = threading.RLock()
_calls: "OrderedDict[str, LLMCall]" = OrderedDict()
_core_counter = 0


@dataclass
class LLMCall:
    id: str
    run: Optional[str]
    stage: str
    provider: str
    model: str
    kind: str                       # generate | stream | chat | manual
    started: float
    system: str = ""
    user: str = ""
    response: str = ""
    thinking: str = ""
    status: str = "running"         # running | done | empty | error
    error: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: Optional[str] = None
    latency_ms: Optional[int] = None
    first_token_ms: Optional[int] = None
    ended: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tokens_per_s"] = self.tokens_per_s
        return d

    @property
    def tokens_per_s(self) -> Optional[float]:
        if self.output_tokens and self.latency_ms:
            return round(self.output_tokens / (self.latency_ms / 1000.0), 1)
        return None


# ── context ──────────────────────────────────────────────────────────────────
@contextmanager
def context(*, run: Optional[str | Path] = None, stage: Optional[str] = None) -> Iterator[None]:
    """Tag every model call made inside the block with a run folder and a stage name."""
    tokens = []
    if run is not None:
        tokens.append((_run_ctx, _run_ctx.set(str(run))))
    if stage is not None:
        tokens.append((_stage_ctx, _stage_ctx.set(stage)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def set_run(run: Optional[str | Path]) -> None:
    _run_ctx.set(str(run) if run is not None else None)


def set_stage(stage: Optional[str]) -> None:
    _stage_ctx.set(stage)


def adopt_orphans(run: str | Path) -> int:
    """Attach finished calls recorded before the run folder existed (e.g. module planning)
    to ``run`` and write them to its log. Returns how many were adopted."""
    n = 0
    with _lock:
        for call in _calls.values():
            if call.run is None and call.status != "running":
                call.run = str(run)
                _persist(call)
                n += 1
    return n


# ── redaction / truncation ───────────────────────────────────────────────────
def _secrets() -> list[str]:
    values: list[str] = []
    try:
        from mudmut_core.llm.providers import get_providers
        for p in get_providers().values():
            v = os.environ.get(p.key_env or "")
            if v and len(v) >= 8:
                values.append(v)
    except Exception:
        pass
    return values


def _clean(text: Optional[str]) -> str:
    text = text or ""
    for secret in _secrets():
        text = text.replace(secret, "***")
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + f"\n… [truncated, {len(text) - MAX_TEXT} more characters]"
    return text


# ── provider detection ───────────────────────────────────────────────────────
def provider_for(base_url: str) -> str:
    """Provider id whose base URL matches ``base_url`` (host fallback)."""
    try:
        from mudmut_core.llm.providers import get_providers
        target = (base_url or "").rstrip("/")
        for pid, p in get_providers().items():
            base = p.base_url.rstrip("/")
            if target == base or target == base + "/v1" or target + "/v1" == base:
                return pid
    except Exception:
        pass
    return (base_url or "").split("//")[-1].split("/")[0] or "unknown"


# ── recording ────────────────────────────────────────────────────────────────
def start_call(*, call_id: Optional[str] = None, provider: str, model: str, kind: str,
               system: str = "", user: str = "", stage: Optional[str] = None,
               run: Optional[str] = None, **extra: Any) -> str:
    global _core_counter
    with _lock:
        if call_id is None:
            _core_counter += 1
            call_id = f"c{_core_counter}"
        call = LLMCall(
            id=call_id, run=run if run is not None else _run_ctx.get(),
            stage=stage or _stage_ctx.get() or "—", provider=provider, model=model, kind=kind,
            started=time.time(), system=_clean(system), user=_clean(user), extra=extra,
        )
        _calls[call_id] = call
        while len(_calls) > MAX_CALLS:
            _calls.popitem(last=False)
    return call_id


def add_chunk(call_id: str, *, text: str = "", reasoning: str = "") -> None:
    with _lock:
        call = _calls.get(call_id)
        if call is None:
            return
        if (text or reasoning) and call.first_token_ms is None:
            call.first_token_ms = int((time.time() - call.started) * 1000)
        if text and len(call.response) < MAX_TEXT:
            call.response += text
        if reasoning and len(call.thinking) < MAX_TEXT:
            call.thinking += reasoning


def end_call(call_id: str, *, content: Optional[str] = None, reasoning: Optional[str] = None,
             input_tokens: int = 0, output_tokens: int = 0, finish_reason: Optional[str] = None,
             latency_ms: Optional[int] = None) -> None:
    with _lock:
        call = _calls.get(call_id)
        if call is None:
            return
        if content is not None:
            call.response = _clean(content)
        else:
            call.response = _clean(call.response)
        if reasoning:
            call.thinking = _clean(reasoning)
        else:
            call.thinking = _clean(call.thinking)
        call.input_tokens = int(input_tokens or 0)
        call.output_tokens = int(output_tokens or 0)
        call.finish_reason = finish_reason
        call.ended = time.time()
        call.latency_ms = latency_ms if latency_ms is not None else int((call.ended - call.started) * 1000)
        if not call.output_tokens and (call.response or call.thinking):
            # rough estimate (≈4 characters per token) when the provider reports no usage
            call.output_tokens = max(1, (len(call.response) + len(call.thinking)) // 4)
            call.extra["tokens_estimated"] = True
        call.status = "done" if call.response.strip() else "empty"
        _persist(call)


def error_call(call_id: str, error: str) -> None:
    with _lock:
        call = _calls.get(call_id)
        if call is None:
            return
        call.status = "error"
        call.error = _clean(error)[:600]
        call.ended = time.time()
        call.latency_ms = int((call.ended - call.started) * 1000)
        _persist(call)


def _persist(call: LLMCall) -> None:
    try:
        path = Path(call.run) / "llm_log.jsonl" if call.run else STATE_LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(call.to_dict(), ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── mud-tool observer callback ───────────────────────────────────────────────
def handle_event(event: str, data: dict[str, Any]) -> None:
    """Callback registered with ``mudtool.ai.observer`` (events from ``CloudBackend``)."""
    cid = f"m{data.get('call_id')}"
    if event == "start":
        start_call(
            call_id=cid, provider=provider_for(data.get("base_url", "")), model=data.get("model", ""),
            kind=data.get("kind", "generate"), system=data.get("system", ""), user=data.get("user", ""),
        )
    elif event == "chunk":
        add_chunk(cid, text=data.get("text", ""), reasoning=data.get("reasoning", ""))
    elif event == "end":
        end_call(
            cid, content=data.get("content"), reasoning=data.get("reasoning"),
            input_tokens=data.get("input_tokens", 0), output_tokens=data.get("output_tokens", 0),
            finish_reason=data.get("finish_reason"), latency_ms=data.get("latency_ms"),
        )
    elif event == "error":
        error_call(cid, data.get("error", "error"))


def register() -> bool:
    """Hook ``handle_event`` into mud-tool's backends (idempotent). Returns True if hooked."""
    try:
        from mudtool.ai import observer
        observer.set_observer(handle_event)
        return True
    except Exception:
        return False


# ── reading ──────────────────────────────────────────────────────────────────
def recent(limit: int = 100, *, run: Optional[str] = None) -> list[dict[str, Any]]:
    """Newest-first snapshot of recorded calls (as dicts)."""
    with _lock:
        calls = list(_calls.values())
    if run is not None:
        calls = [c for c in calls if c.run == str(run)]
    return [c.to_dict() for c in reversed(calls)][:limit]


def summary(run: Optional[str] = None) -> dict[str, Any]:
    """Counts per stage for a run (used by the run report)."""
    with _lock:
        calls = [c for c in _calls.values() if run is None or c.run == str(run)]
    per_stage: dict[str, dict[str, Any]] = {}
    for c in calls:
        s = per_stage.setdefault(c.stage, {"calls": 0, "errors": 0, "empty": 0, "tokens_out": 0, "seconds": 0.0})
        s["calls"] += 1
        s["errors"] += c.status == "error"
        s["empty"] += c.status == "empty"
        s["tokens_out"] += c.output_tokens
        s["seconds"] += (c.latency_ms or 0) / 1000.0
    return per_stage


def clear() -> None:
    with _lock:
        _calls.clear()
