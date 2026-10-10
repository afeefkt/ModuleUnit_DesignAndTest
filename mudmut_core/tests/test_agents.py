from mudmut_core import agents


def test_stage_registry_has_mud_and_mut():
    keys = {s.key for s in agents.STAGES}
    assert "planner" in keys
    assert "mud_spec_generator" in keys
    assert "test_generator" in keys
    assert "rag_embed" in keys
    assert len(keys) == 12
    sides = {s.side for s in agents.STAGES}
    assert sides == {"mud", "mut"}


def test_presets_loaded():
    presets = agents.load_presets()
    assert "local-recommended" in presets
    assert "local-fast" in presets
    assert "openrouter-free" in presets
    assert "nvidia" in presets
    assert "deepseek" in presets
    # local presets have concrete models; cloud presets reference a provider
    assert presets["local-recommended"]["stages"]["planner"]["provider"] == "ollama"
    assert presets["openrouter-free"]["stages"]["planner"]["provider"] == "openrouter"


def test_stages_file_default_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "STAGES_FILE", tmp_path / "stages.json")
    assert agents.load_stages() == {}


def test_apply_preset_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        agents.apply_preset("does-not-exist")
