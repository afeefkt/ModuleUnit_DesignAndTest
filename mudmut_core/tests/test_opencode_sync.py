from mudmut_core.llm import opencode_sync


def test_build_provider_block():
    block = opencode_sync.build_provider_block()
    assert {"ollama", "openrouter", "nvidia", "deepseek", "google"} <= set(block)
    # ollama has no apiKey; cloud providers reference {env:VAR}.
    assert "apiKey" not in block["ollama"]["options"]
    assert block["openrouter"]["options"]["apiKey"] == "{env:OPENROUTER_API_KEY}"
    assert block["nvidia"]["options"]["apiKey"] == "{env:NVIDIA_API_KEY}"
    assert block["deepseek"]["options"]["apiKey"] == "{env:DEEPSEEK_API_KEY}"
