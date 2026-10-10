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
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, Optional

_loop: Optional[asyncio.AbstractEventLoop] = None
_lock = threading.Lock()


def run_sync(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run ``coro`` to completion on the shared, never-closed event loop."""
    global _loop
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        return _loop.run_until_complete(coro)
