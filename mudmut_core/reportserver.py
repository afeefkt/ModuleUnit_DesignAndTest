"""Tiny read-only HTTP server for ``outputs/`` so reports open from the web UI.

The coverage report is a multi-page HTML site and a browser will not follow a
``file://`` link from an ``http://localhost`` page (and the path is a WSL path),
so the UI links to this server instead: ``http://localhost:<port>/<run>/03_mut/...``.

Safe by construction: bound to 127.0.0.1, GET/HEAD only, no directory listings,
nothing outside ``outputs/`` (symlinks that leave it are refused), no caching.
"""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from mudmut_core.workspace import RUNS_ROOT

DEFAULT_PORT = 8502
_PORT_TRIES = 10

_lock = threading.Lock()
_server: Optional[ThreadingHTTPServer] = None
_root: Optional[Path] = None


class _Handler(SimpleHTTPRequestHandler):
    server_version = "MudMutReports/1"

    def __init__(self, *args, root: Path, **kwargs):
        self._root = root.resolve()
        super().__init__(*args, directory=str(self._root), **kwargs)

    def _inside_root(self, path: str) -> bool:
        try:
            Path(path).resolve().relative_to(self._root)
            return True
        except (ValueError, OSError):
            return False

    def send_head(self):
        translated = self.translate_path(self.path)
        if not self._inside_root(translated):
            self.send_error(404, "Not found")
            return None
        return super().send_head()

    def list_directory(self, path):  # noqa: D401 - listings are disabled on purpose
        self.send_error(403, "Directory listing is disabled")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format, *args):  # noqa: A002 - keep the Streamlit log quiet
        pass


def start(root: Optional[Path] = None, port: int = DEFAULT_PORT) -> tuple[ThreadingHTTPServer, int]:
    """Start a server on the first free port from ``port`` and return ``(server, port)``."""
    root = Path(root or RUNS_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    handler = partial(_Handler, root=root)
    last_error: Optional[Exception] = None
    for candidate in range(port, port + _PORT_TRIES):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), handler)
        except OSError as exc:
            last_error = exc
            continue
        threading.Thread(target=server.serve_forever, name=f"reports-{candidate}", daemon=True).start()
        return server, candidate
    raise OSError(f"no free port for the report server ({port}-{port + _PORT_TRIES - 1}): {last_error}")


def ensure_started() -> int:
    """Start the process-wide report server once; returns its port."""
    global _server, _root
    with _lock:
        if _server is None:
            _server, port = start(RUNS_ROOT)
            _root = RUNS_ROOT
            return port
        return _server.server_address[1]


def url_for(path: Path | str, root: Optional[Path] = None) -> Optional[str]:
    """Browser URL for a file under ``outputs/`` (None if it is outside)."""
    root = Path(root or RUNS_ROOT).resolve()
    try:
        rel = Path(path).resolve().relative_to(root)
    except (ValueError, OSError):
        return None
    port = ensure_started()
    return f"http://localhost:{port}/" + "/".join(quote(part) for part in rel.parts)
