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


def notify(event: str, **data: Any) -> None:
    """Send ``event`` ("start" | "chunk" | "end" | "error") with ``data`` to the observer."""
    cb = _observer
    if cb is None:
        return
    try:
        cb(event, data)
    except Exception:  # noqa: BLE001 - observing must never break the call
        pass
