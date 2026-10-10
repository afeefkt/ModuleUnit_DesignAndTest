"""Client for ``opencode serve`` (headless HTTP API, verified against /doc of 1.18).

Flow used by the OpenCode Agent page:

    GET  /doc                                   health check (no side effects)
    POST /session                               → {id: "ses_…"}
    GET  /event                                 SSE: ``data: {"type", "properties": {...}}``
    POST /session/{id}/prompt_async             body {parts, agent, model:{providerID, modelID}} → 204
    POST /session/{id}/permissions/{perm_id}    body {response: once|always|reject}
    POST /session/{id}/abort

The event stream is opened *before* the prompt is sent (``prompt_async``
returns immediately), and :func:`apply_event` folds events into a plain dict
the UI renders: tool calls keyed by ``callID``, assistant text, pending
permission requests and the session status.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Iterator, Optional

DEFAULT_BASE_URL = "http://127.0.0.1:4096"


class OpenCodeClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            self.base_url + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            raw = r.read()
        return json.loads(raw) if raw else None

    def healthy(self) -> bool:
        """True if the server answers ``GET /doc`` (creates nothing)."""
        try:
            with urllib.request.urlopen(self.base_url + "/doc", timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def list_agents(self) -> list[str]:
        try:
            return [a.get("name", "") for a in (self._request("GET", "/agent") or []) if a.get("name")]
        except Exception:
            return []

    def create_session(self, title: str = "mudmut") -> str:
        data = self._request("POST", "/session", {"title": title}) or {}
        return data.get("id", "")

    def prompt_async(self, session_id: str, text: str, *, agent: Optional[str] = None,
                     provider_id: Optional[str] = None, model_id: Optional[str] = None) -> None:
        payload: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if agent:
            payload["agent"] = agent
        if provider_id and model_id:
            payload["model"] = {"providerID": provider_id, "modelID": model_id}
        self._request("POST", f"/session/{session_id}/prompt_async", payload)

    def reply_permission(self, session_id: str, permission_id: str, response: str) -> None:
        if response not in ("once", "always", "reject"):
            raise ValueError(f"invalid permission response: {response}")
        self._request("POST", f"/session/{session_id}/permissions/{permission_id}", {"response": response})

    def abort(self, session_id: str) -> None:
        self._request("POST", f"/session/{session_id}/abort", {})

    def events(self) -> Iterator[dict]:
        """Yield parsed events from ``GET /event`` until the connection closes."""
        req = urllib.request.Request(self.base_url + "/event", headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=None) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    yield json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue


# ── Event folding (pure, unit-tested) ─────────────────────────────────────────
def new_state() -> dict[str, Any]:
    return {
        "status": "idle",        # idle | busy | retry | done | error
        "tools": {},             # callID → {tool, status, title, input, output, error, start, end}
        "order": [],             # callIDs in first-seen order
        "text": {},              # part id → assistant text
        "permissions": {},       # permission id → {permission, patterns, tool}
        "error": "",
        "started": False,
    }


def _session_of(props: dict) -> str:
    return props.get("sessionID") or (props.get("part") or {}).get("sessionID") or ""


def apply_event(state: dict[str, Any], event: dict, session_id: str) -> dict[str, Any]:
    """Fold one ``/event`` payload for ``session_id`` into ``state`` (in place)."""
    etype = event.get("type", "")
    props = event.get("properties") or {}
    if _session_of(props) != session_id:
        return state

    if etype == "message.part.updated":
        part = props.get("part") or {}
        ptype = part.get("type")
        if ptype == "tool":
            call = part.get("callID") or part.get("id", "")
            st = part.get("state") or {}
            if call not in state["tools"]:
                state["order"].append(call)
            times = st.get("time") or {}
            state["tools"][call] = {
                "tool": part.get("tool", "?"),
                "status": st.get("status", "pending"),
                "title": st.get("title", ""),
                "input": st.get("input") or {},
                "output": st.get("output", ""),
                "error": st.get("error", ""),
                "start": times.get("start"),
                "end": times.get("end"),
            }
        elif ptype == "text" and not part.get("synthetic"):
            state["text"][part.get("id", "")] = part.get("text", "")
        if state["status"] in ("idle", "done"):
            state["status"] = "busy"
        state["started"] = True
    elif etype == "session.status":
        kind = (props.get("status") or {}).get("type", "")
        if kind == "busy":
            state["status"], state["started"] = "busy", True
        elif kind == "retry":
            state["status"] = "retry"
            state["error"] = (props.get("status") or {}).get("message", "")
        elif kind == "idle" and state["started"]:
            state["status"] = "done"
    elif etype == "session.idle":
        if state["started"]:
            state["status"] = "done"
    elif etype == "session.error":
        err = props.get("error") or {}
        data = err.get("data") or {}
        state["status"] = "error"
        state["error"] = data.get("message") or err.get("name") or "session error"
    elif etype == "permission.asked":
        state["permissions"][props.get("id", "")] = {
            "permission": props.get("permission", ""),
            "patterns": props.get("patterns", []),
            "tool": props.get("tool") or {},
        }
    elif etype == "permission.replied":
        state["permissions"].pop(props.get("requestID", ""), None)
    return state


class EventWatcher:
    """Background thread that consumes ``/event`` for one session.

    Started *before* the prompt is sent so no early event is missed. The page
    reads :meth:`snapshot` on every rerun; the thread outlives reruns because the
    watcher is kept in ``st.session_state``.
    """

    def __init__(self, client: OpenCodeClient, session_id: str):
        self.client = client
        self.session_id = session_id
        self._lock = threading.Lock()
        self._state = new_state()
        self._stop = threading.Event()
        self.connected = threading.Event()
        self._thread = threading.Thread(target=self._run, name="opencode-events", daemon=True)

    def start(self) -> "EventWatcher":
        self._thread.start()
        self.connected.wait(timeout=5)
        return self

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                for event in self.client.events():
                    self.connected.set()
                    if self._stop.is_set():
                        return
                    with self._lock:
                        apply_event(self._state, event, self.session_id)
            except Exception as exc:  # connection dropped — retry unless stopped
                with self._lock:
                    self._state["error"] = f"event stream: {exc}"
                time.sleep(1)

    def stop(self) -> None:
        self._stop.set()

    def reset(self) -> None:
        """Clear per-prompt state (keep the stream) before sending a new prompt."""
        with self._lock:
            self._state = new_state()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state, default=str))
