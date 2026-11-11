"""A stalled provider call is cancelled by a wall-clock deadline and asked again."""
import asyncio

import pytest

from mudmut_core.llm.providers import Provider
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


def test_achat_gives_up_on_a_stalled_provider(monkeypatch):
    import httpx
    from mudmut_core.llm import client

    class Hang:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): await asyncio.sleep(3600)

    monkeypatch.setattr(httpx, "AsyncClient", Hang)
    monkeypatch.setenv("MUD_CALL_DEADLINE", "0.1")
    monkeypatch.setenv("MUD_CALL_ATTEMPTS", "2")
    prov = Provider(id="deepseek", name="d", base_url="https://x/v1", key_env=None, privacy="cloud")
    with pytest.raises(RuntimeError, match="2 attempt"):
        asyncio.run(client.achat(prov, "m", [{"role": "user", "content": "hi"}], timeout=5))


def test_stream_that_goes_silent_falls_back_to_the_guarded_call(monkeypatch):
    """A stream with no data for MUD_STREAM_IDLE seconds is abandoned; the non-streaming call answers."""
    from types import SimpleNamespace

    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        async def aiter_lines(self):
            await asyncio.sleep(3600)
            yield ""

    class Ctx:
        async def __aenter__(self): return Resp()
        async def __aexit__(self, *a): return False

    class Client:
        def stream(self, *a, **k): return Ctx()

    b = _backend()
    b.settings = SimpleNamespace(cloud_provider="deepseek", openai_base_url="https://api.deepseek.com",
                                 deepseek_base_url="https://api.deepseek.com", deepseek_model="deepseek-chat",
                                 openai_model="m", openai_enable_thinking=False, deepseek_max_tokens=100)
    b._get_openai_client = lambda: Client()
    b._active_openai_model = lambda: "deepseek-chat"
    b._active_openai_base_url = lambda: "https://api.deepseek.com"
    b._effective_max_tokens = lambda n: n

    async def fake_generate(*a, **k):
        return SimpleNamespace(content="fallback answer")

    b.generate = fake_generate
    monkeypatch.setenv("MUD_STREAM_IDLE", "0.2")

    async def run():
        return [c async for c in b._stream_openai("s", "u", 100, 0.1)]

    assert asyncio.run(run()) == ["fallback answer"]
