"""Ollama Cloud provider, per-provider 'free' flags and the model probe."""

import json

import pytest

from mudmut_core import agents
from mudmut_core.llm import providers, probe
from mudmut_core.llm.client import _chat_url


def test_ollama_cloud_registered_as_cloud_with_key_var():
    p = providers.get_providers()["ollama_cloud"]
    assert p.is_cloud and p.key_env == "OLLAMA_API_KEY"
    assert _chat_url(p) == "https://ollama.com/v1/chat/completions"


def test_mud_tool_connection_for_ollama_cloud(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "k-test")
    from mudtool.config.settings import Settings
    conn = Settings().provider_connection("ollama_cloud")
    assert conn == {"base_url": "https://ollama.com/v1", "api_key": "k-test"}


def test_classify_statuses():
    assert probe.classify(reply="OK") == probe.OK
    assert probe.classify(reply="  ") == probe.EMPTY
    assert probe.classify(exc=providers.ProviderError(429, "slow down")) == probe.RATE_LIMITED
    assert probe.classify(exc=providers.ProviderError(404, "")) == probe.UNAVAILABLE
    assert probe.classify(exc=providers.ProviderError(410, "")) == probe.UNAVAILABLE
    assert probe.classify(exc=providers.ProviderError(402, "needs credits")) == probe.PAID
    assert probe.classify(exc=RuntimeError("boom")) == probe.ERROR


def test_nvidia_all_chat_models_free_and_non_chat_filtered(monkeypatch):
    monkeypatch.setattr(providers, "_http_json", lambda *a, **k: {"data": [
        {"id": "meta/llama-3.1-8b-instruct"}, {"id": "nvidia/nv-embedqa-e5-v5"}, {"id": "nvidia/llama-guard"},
    ]})
    models = providers.list_models(providers.get_providers()["nvidia"])
    assert [m["id"] for m in models] == ["meta/llama-3.1-8b-instruct"]
    assert models[0]["free"] and "trial" in models[0]["free_note"]


def test_ollama_cloud_free_only_after_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "PROBE_FILE", tmp_path / "probe.json")
    monkeypatch.setattr(providers, "_http_json", lambda *a, **k: {"data": [{"id": "gpt-oss:20b"}, {"id": "kimi-k3"}]})
    p = providers.get_providers()["ollama_cloud"]
    assert [m["free"] for m in providers.list_models(p)] == [False, False]
    monkeypatch.setattr(probe, "probe_one", lambda prov, model, timeout=30: probe.OK if model == "gpt-oss:20b" else probe.PAID)
    probe.probe_models(p, ["gpt-oss:20b", "kimi-k3"])
    assert {m["id"]: m["free"] for m in providers.list_models(p)} == {"gpt-oss:20b": True, "kimi-k3": False}


def test_probe_cache_ttl_and_first_working(tmp_path, monkeypatch):
    f = tmp_path / "probe.json"
    monkeypatch.setattr(probe, "PROBE_FILE", f)
    f.write_text(json.dumps({"x": {
        "old": {"status": "ok", "ts": 0},
        "deepseek-r1:free": {"status": "ok", "ts": 9e12},
        "good:free": {"status": "ok", "ts": 9e12},
        "bad:free": {"status": "unavailable", "ts": 9e12},
    }}))
    assert "old" not in probe.cached_status("x")
    # reasoning models are never auto-picked; unavailable ones neither
    assert probe.first_working("x", ["bad:free", "deepseek-r1:free", "good:free"]) == "good:free"


def test_preset_blank_cloud_model_uses_probe_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "STAGES_FILE", tmp_path / "stages.json")
    monkeypatch.setattr(agents, "_auto_model", lambda pid: "gpt-oss:20b" if pid == "ollama_cloud" else "")
    applied = []
    monkeypatch.setattr(agents, "set_stage", lambda key, prov, model: applied.append((key, prov, model)))
    monkeypatch.setattr(agents, "get_stages", lambda: {})
    _, skipped = agents.apply_preset_with_report("ollama-cloud")
    assert ("planner", "ollama_cloud", "gpt-oss:20b") in applied
    assert skipped == []
    assert "ollama_cloud" in {p for _, p, _ in applied}
