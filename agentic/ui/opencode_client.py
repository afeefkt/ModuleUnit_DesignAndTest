"""Client for `opencode serve` (headless HTTP API).

`opencode serve` exposes an OpenAI-schema OpenAPI at ``/doc``.  The chat flow is:

    POST /session                       → { id: "ses_…" }
    POST /session/{id}/message          body: { parts: [{type:"text",text}], agent, model:{providerID,modelID} }
    GET  /event                         SSE stream; filter by sessionID

Tool actions stream as ``message.part.updated`` events whose part carries
``tool``, ``state.status``, ``state.input`` and ``state.output``.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Iterator, Optional

DEFAULT_BASE_URL = "http://127.0.0.1:4096"

# Stable routes (verified against the `opencode serve` OpenAPI doc).
ROUTES = {
    "spec": "/doc",
    "create_session": ("POST", "/session"),
    "send_message": ("POST", "/session/{id}/message"),
    "events": ("GET", "/event"),
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

    def create_session(self, title: str = "mudmut") -> dict:
        raw = self._request(*ROUTES["create_session"], {"title": title})
        return json.loads(raw) if raw else {}

    def send_message(self, session_id: str, message: str, *,
                     agent: Optional[str] = None,
                     model: Optional[dict] = None) -> bytes:
        """Send a text part to a session. ``model`` is ``{providerID, modelID}``."""
        payload: dict = {"parts": [{"type": "text", "text": message}]}
        if agent:
            payload["agent"] = agent
        if model:
            payload["model"] = model
        return self._request(
            "POST", ROUTES["send_message"][1].replace("{id}", session_id), payload,
        )

    def stream_events(self, session_id: Optional[str] = None) -> Iterator[dict]:
        """Yield event dicts from the SSE feed, optionally filtered to a session."""
        url = self.base_url + ROUTES["events"][1]
        with urllib.request.urlopen(url, timeout=3600) as r:
            for raw_line in r:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload and payload != "[DONE]":
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if session_id and event.get("sessionID", event.get("session_id")) != session_id:
                        continue
                    yield event


# ── Event helpers (used by the UI timeline) ───────────────────────────────────
def event_type(event: dict) -> str:
    return event.get("type", "")


def is_tool_event(event: dict) -> bool:
    part = event.get("part") or {}
    return part.get("tool") is not None


def tool_state(event: dict) -> dict:
    part = event.get("part") or {}
    state = part.get("state") or {}
    return {
        "tool": part.get("tool"),
        "status": state.get("status"),
        "input": state.get("input"),
        "output": state.get("output"),
        "title": state.get("title"),
    }
