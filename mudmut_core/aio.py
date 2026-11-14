"""One persistent asyncio event loop for synchronous callers (Streamlit, CLI).

The mud-tool orchestrator is a cached singleton whose HTTP client
(``httpx.AsyncClient``) is bound to the event loop it was first used on.
Calling ``asyncio.run()`` once per step creates and closes a new loop each
time, so the second AI step fails with "Event loop is closed".

``run_sync`` instead reuses one loop that is never closed.  The coroutine runs
in the *calling* thread, so progress callbacks can still update Streamlit
widgets (Streamlit calls only work on the script's own thread).  A lock
serialises callers — two browser tabs simply take turns, which is what a
single local Ollama does anyway.

:func:`cancel_current` cancels the coroutine that is running right now (from any thread).
An ``await`` on an HTTP request then raises ``asyncio.CancelledError`` at once and the
connection is closed, so the model server stops generating instead of finishing a
10-minute answer nobody wants.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, Optional

_loop: Optional[asyncio.AbstractEventLoop] = None
_lock = threading.Lock()
_current: Optional[asyncio.Task] = None


def run_sync(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run ``coro`` to completion on the shared, never-closed event loop."""
    global _loop, _current
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        task = _loop.create_task(coro)
        _current = task
        try:
            return _loop.run_until_complete(task)
        finally:
            _current = None


def cancel_current() -> bool:
    """Cancel the coroutine running on the shared loop (thread-safe). Returns False if none."""
    loop, task = _loop, _current
    if loop is None or task is None or task.done():
        return False
    loop.call_soon_threadsafe(task.cancel)
    return True
