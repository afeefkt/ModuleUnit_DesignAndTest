"""A stalled provider call is cancelled by a wall-clock deadline and asked again."""
import asyncio

import pytest

from mudtool.ai.cloud_backend import CloudBackend


class _Resp:
    def __init__(self, code):
        self.status_code = code


class _Client:
    def __init__(self, behaviours):
        self.behaviours, self.calls = list(behaviours), 0

    async def post(self, url, json=None):
        self.calls += 1
        b = self.behaviours.pop(0)
        if b == "hang":
            await asyncio.sleep(3600)
        return _Resp(b)


def _backend():
    return CloudBackend.__new__(CloudBackend)


def test_hung_call_is_retried(monkeypatch):
    monkeypatch.setenv("MUD_CALL_DEADLINE", "0.2")
    monkeypatch.setenv("MUD_CALL_ATTEMPTS", "3")
    c = _Client(["hang", 200])
    resp = asyncio.run(_backend()._post_with_deadline(c, {}))
    assert resp.status_code == 200 and c.calls == 2


def test_gives_up_after_the_attempt_cap(monkeypatch):
    monkeypatch.setenv("MUD_CALL_DEADLINE", "0.1")
    monkeypatch.setenv("MUD_CALL_ATTEMPTS", "2")
    c = _Client(["hang", "hang"])
    with pytest.raises(RuntimeError, match="2 attempt"):
        asyncio.run(_backend()._post_with_deadline(c, {}))


def test_server_error_is_retried(monkeypatch):
    monkeypatch.setenv("MUD_CALL_ATTEMPTS", "2")
    real_sleep = asyncio.sleep

    async def _fast(_s):
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", _fast)
    c = _Client([503, 200])
    assert asyncio.run(_backend()._post_with_deadline(c, {})).status_code == 200
