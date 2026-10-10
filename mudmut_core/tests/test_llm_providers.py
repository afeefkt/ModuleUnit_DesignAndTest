from mudmut_core.llm import client, get_providers


def test_builtin_providers():
    providers = get_providers()
    assert set(providers) == {"ollama", "openrouter", "nvidia", "deepseek"}
    assert providers["ollama"].privacy == "local"
    assert providers["openrouter"].is_cloud
    assert providers["openrouter"].key_env == "OPENROUTER_API_KEY"


def test_payload_think_only_for_local():
    providers = get_providers()
    local = providers["ollama"]
    cloud = providers["openrouter"]

    p = client._payload(local, "qwen3:8b", [{"role": "user", "content": "hi"}],
                        max_tokens=10, temperature=0.1, json_mode=False)
    assert p.get("think") is True  # reasoning model on local ollama

    p = client._payload(cloud, "openrouter/qwen3", [{"role": "user", "content": "hi"}],
                        max_tokens=10, temperature=0.1, json_mode=False)
    assert "think" not in p  # never send think to remote


def test_payload_json_mode_only_for_local():
    providers = get_providers()
    cloud = providers["openrouter"]
    p = client._payload(cloud, "x", [{"role": "user", "content": "hi"}],
                        max_tokens=10, temperature=0.1, json_mode=True)
    assert p.get("response_format") == {"type": "json_object"}
    assert "format" not in p  # "format" is an Ollama-only extension


def test_strip_thinking():
    assert client._strip_thinking("<think>reason</think>answer") == "answer"
    assert client._strip_thinking("plain") == "plain"
