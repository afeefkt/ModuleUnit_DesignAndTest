"""Minimal client for `opencode serve` (headless HTTP API).

The OpenCode HTTP API is experimental, so endpoint paths are discovered from the
server's OpenAPI document at runtime (served at ``/doc``) with documented fallbacks —
the client never hard-codes guesses.

Exposes the three operations a chat UI needs:
    create_session()  -> {"id": "ses_..."}
    send_prompt(id, message) -> response bytes
    stream_events(id) -> iterator of event dicts (SSE)
"""

from __future__ import annotations

import json
import urllib.request
from typing import Iterator

DEFAULT_BASE_URL = "http://127.0.0.1:4096"

# Fallback endpoint templates (stable, non-experimental routes seen in the spec).
_FALLBACK = {
    "spec": "/doc",
    "create_session": ("POST", "/session"),
    "send_prompt": ("POST", "/session/{id}/prompt"),
    "session_events": ("GET", "/session/{id}/event"),
}


class OpenCodeClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict | None = None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            self.base_url + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()

    def discover(self) -> dict:
        """Return an endpoint map, discovered from the OpenAPI doc if possible."""
        endpoints = dict(_FALLBACK)
        try:
            raw = self._request("GET", _FALLBACK["spec"])
            spec = json.loads(raw)
            for path, ops in (spec.get("paths") or {}).items():
                for method, op in ops.items():
                    if not isinstance(op, dict):
                        continue
                    summary = (op.get("summary") or "").lower()
                    if method == "post" and "send message" in summary:
                        endpoints["send_prompt"] = ("POST", path)
                    if method == "post" and "session" in path and "create" in summary:
                        endpoints["create_session"] = ("POST", path)
                    if method == "get" and "session" in path and "subscribe" in summary:
                        endpoints["session_events"] = ("GET", path)
        except Exception:
            pass  # fall back to defaults
        return endpoints

    def create_session(self) -> dict:
        method, path = self.discover()["create_session"]
        raw = self._request(method, path, {"title": "agentic"})
        body = json.loads(raw) if raw else {}
        # Session id may be nested; accept a few shapes.
        if isinstance(body, dict):
            if "id" in body:
                return body
            for v in body.values():
                if isinstance(v, dict) and v.get("id"):
                    return v
        return body

    def send_prompt(self, session_id: str, message: str) -> bytes:
        method, path = self.discover()["send_prompt"]
        return self._request(method, path.replace("{id}", session_id),
                             {"message": message})

    def stream_events(self, session_id: str) -> Iterator[dict]:
        method, path = self.discover()["session_events"]
        url = self.base_url + path.replace("{id}", session_id)
        with urllib.request.urlopen(url, timeout=3600) as r:
            for raw_line in r:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload and payload != "[DONE]":
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        continue
