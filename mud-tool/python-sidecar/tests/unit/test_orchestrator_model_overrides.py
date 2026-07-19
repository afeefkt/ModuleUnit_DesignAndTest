from __future__ import annotations

from mudtool.ai.cloud_backend import CloudBackend
from mudtool.ai.orchestrator import AIOrchestrator
from mudtool.config.settings import AIBackend, CloudProvider, Settings


def _deepseek_orchestrator() -> AIOrchestrator:
    settings = Settings(
        ai_backend=AIBackend.CLOUD,
        cloud_provider=CloudProvider.DEEPSEEK,
        deepseek_api_key="test-key",
        deepseek_model="deepseek-chat",
        mud_spec_skeleton_model="deepseek-reasoner",
        pipeline_reviewer_model="deepseek-reasoner",
        activity_pipeline_skeleton_model="deepseek-reasoner",
        activity_pipeline_reviewer_model="deepseek-reasoner",
    )
    return AIOrchestrator(settings)


def test_deepseek_reviewer_override_updates_deepseek_model():
    orchestrator = _deepseek_orchestrator()

    backend = orchestrator._get_reviewer_backend()

    assert isinstance(backend, CloudBackend)
    assert backend.settings.deepseek_model == "deepseek-reasoner"


def test_deepseek_local_r1_alias_maps_to_hosted_reasoner():
    settings = Settings(
        ai_backend=AIBackend.CLOUD,
        cloud_provider=CloudProvider.DEEPSEEK,
        deepseek_api_key="test-key",
        deepseek_model="deepseek-chat",
        pipeline_reviewer_model=" deepseek-r1:7b ",
    )
    orchestrator = AIOrchestrator(settings)

    backend = orchestrator._get_reviewer_backend()

    assert isinstance(backend, CloudBackend)
    assert backend.settings.deepseek_model == "deepseek-reasoner"


def test_deepseek_skeleton_override_updates_deepseek_model():
    orchestrator = _deepseek_orchestrator()

    backend = orchestrator._get_skeleton_backend()

    assert isinstance(backend, CloudBackend)
    assert backend.settings.deepseek_model == "deepseek-reasoner"


def test_deepseek_activity_override_updates_deepseek_model():
    orchestrator = _deepseek_orchestrator()

    skeleton_backend = orchestrator._get_activity_skeleton_backend()
    reviewer_backend = orchestrator._get_activity_reviewer_backend()

    assert isinstance(skeleton_backend, CloudBackend)
    assert isinstance(reviewer_backend, CloudBackend)
    assert skeleton_backend.settings.deepseek_model == "deepseek-reasoner"
    assert reviewer_backend.settings.deepseek_model == "deepseek-reasoner"


def test_local_ollama_ignores_hosted_deepseek_reviewer_alias():
    settings = Settings(
        ai_backend=AIBackend.CLOUD,
        cloud_provider=CloudProvider.OPENAI_COMPATIBLE,
        openai_api_key="ollama",
        openai_base_url="http://localhost:11434/v1",
        openai_model="mistral",
        pipeline_reviewer_model="deepseek-reasoner",
        mud_spec_skeleton_model="deepseek-chat",
        activity_pipeline_skeleton_model="deepseek-chat",
    )
    orchestrator = AIOrchestrator(settings)

    reviewer_backend = orchestrator._get_reviewer_backend()
    skeleton_backend = orchestrator._get_skeleton_backend()
    activity_backend = orchestrator._get_activity_skeleton_backend()

    assert isinstance(reviewer_backend, CloudBackend)
    assert isinstance(skeleton_backend, CloudBackend)
    assert isinstance(activity_backend, CloudBackend)
    assert reviewer_backend.settings.openai_model == "mistral"
    assert skeleton_backend.settings.openai_model == "mistral"
    assert activity_backend.settings.openai_model == "mistral"


def test_local_ollama_keeps_real_local_deepseek_r1_tag():
    settings = Settings(
        ai_backend=AIBackend.CLOUD,
        cloud_provider=CloudProvider.OPENAI_COMPATIBLE,
        openai_api_key="ollama",
        openai_base_url="http://localhost:11434/v1",
        openai_model="mistral",
        pipeline_reviewer_model="deepseek-r1:7b",
    )
    orchestrator = AIOrchestrator(settings)

    backend = orchestrator._get_reviewer_backend()

    assert isinstance(backend, CloudBackend)
    assert backend.settings.openai_model == "deepseek-r1:7b"
