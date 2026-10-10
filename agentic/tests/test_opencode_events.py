"""OpenCode event folding — payload shapes taken from the opencode serve 1.18 OpenAPI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

from opencode_client import apply_event, new_state  # noqa: E402

SID = "ses_abc"


def _tool(call: str, status: str, **state):
    return {
        "type": "message.part.updated",
        "properties": {
            "sessionID": SID,
            "time": 1,
            "part": {
                "id": f"prt_{call}", "sessionID": SID, "messageID": "msg_1", "type": "tool",
                "callID": call, "tool": "bash", "state": {"status": status, "input": {"command": "x"}, **state},
            },
        },
    }


def test_tool_calls_are_deduplicated_by_call_id_and_updated():
    s = new_state()
    apply_event(s, _tool("c1", "pending", raw=""), SID)
    apply_event(s, _tool("c1", "running", time={"start": 10}), SID)
    apply_event(s, _tool("c1", "completed", output="ok", time={"start": 10, "end": 25}), SID)
    apply_event(s, _tool("c2", "error", error="boom", time={"start": 30, "end": 31}), SID)
    assert s["order"] == ["c1", "c2"]
    assert s["tools"]["c1"]["status"] == "completed"
    assert s["tools"]["c1"]["output"] == "ok"
    assert s["tools"]["c1"]["end"] == 25
    assert s["tools"]["c2"]["error"] == "boom"
    assert s["status"] == "busy"


def test_events_of_other_sessions_are_ignored():
    s = new_state()
    other = _tool("c9", "running", time={"start": 1})
    other["properties"]["sessionID"] = "ses_other"
    other["properties"]["part"]["sessionID"] = "ses_other"
    apply_event(s, other, SID)
    assert s["tools"] == {} and s["started"] is False


def test_text_status_idle_and_error():
    s = new_state()
    apply_event(s, {"type": "session.idle", "properties": {"sessionID": SID}}, SID)
    assert s["status"] == "idle"  # idle before anything started is not "done"
    apply_event(s, {"type": "session.status", "properties": {"sessionID": SID, "status": {"type": "busy"}}}, SID)
    apply_event(s, {"type": "message.part.updated", "properties": {"sessionID": SID, "time": 1, "part": {
        "id": "prt_t", "sessionID": SID, "messageID": "msg_1", "type": "text", "text": "Done."}}}, SID)
    assert s["text"] == {"prt_t": "Done."}
    apply_event(s, {"type": "session.idle", "properties": {"sessionID": SID}}, SID)
    assert s["status"] == "done"
    apply_event(s, {"type": "session.error", "properties": {"sessionID": SID, "error": {
        "name": "ProviderAuthError", "data": {"message": "bad key"}}}}, SID)
    assert s["status"] == "error" and s["error"] == "bad key"


def test_permission_asked_then_replied():
    s = new_state()
    apply_event(s, {"type": "permission.asked", "properties": {
        "id": "per_1", "sessionID": SID, "permission": "bash", "patterns": ["rm -rf *"],
        "tool": {"messageID": "msg_1", "callID": "c1"}}}, SID)
    assert s["permissions"]["per_1"]["patterns"] == ["rm -rf *"]
    apply_event(s, {"type": "permission.replied", "properties": {
        "sessionID": SID, "requestID": "per_1", "reply": "reject"}}, SID)
    assert s["permissions"] == {}
