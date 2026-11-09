"""Optional observer for LLM calls (request / streamed chunks / response / error).

mud-tool stays independent of the host application: the host registers one callback
with :func:`set_observer`, and the backends call :func:`notify`. A failing observer
never breaks a model call.
"""

from __future__ import annotations

import itertools
import threading
from typing import Any, Callable, Optional

Observer = Callable[[str, dict[str, Any]], None]

_observer: Optional[Observer] = None
_counter = itertools.count(1)
_lock = threading.Lock()


def set_observer(callback: Optional[Observer]) -> None:
    """Register (or clear, with ``None``) the process-wide observer."""
    global _observer
    _observer = callback


def new_call_id() -> int:
    with _lock:
        return next(_counter)


class GenerationCancelled(BaseException):
    """The host asked to stop (raised between AI attempts / per-runnable calls).

    A ``BaseException`` on purpose: the retry loops catch ``Exception`` and must not swallow it.
    """


_cancel_check: Optional[Callable[[], bool]] = None


def set_cancel_check(check: Optional[Callable[[], bool]]) -> None:
    """Register (or clear) a callable that returns True when the current work should stop."""
    global _cancel_check
    _cancel_check = check


def check_cancel(where: str = "") -> None:
    """Raise :class:`GenerationCancelled` if the host asked to cancel."""
    check = _cancel_check
    try:
        stop = bool(check and check())
    except Exception:  # noqa: BLE001 - a broken check never cancels
        stop = False
    if stop:
        raise GenerationCancelled(f"Cancelled {where}".strip())


def notify(event: str, **data: Any) -> None:
    """Send ``event`` ("start" | "chunk" | "end" | "error") with ``data`` to the observer."""
    cb = _observer
    if cb is None:
        return
    try:
        cb(event, data)
    except Exception:  # noqa: BLE001 - observing must never break the call
        pass
