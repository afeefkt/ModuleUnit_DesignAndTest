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


def test_stage_on_deepseek_keeps_hosted_model_when_global_is_local_ollama():
    """Regression: a DeepSeek stage got the local model name and DeepSeek answered 400."""
    settings = Settings(
        ai_backend=AIBackend.CLOUD,
        cloud_provider=CloudProvider.OPENAI_COMPATIBLE,
        openai_api_key="ollama",
        openai_base_url="http://localhost:11434/v1",
        openai_model="qwen3:8b-ctx16384",
        deepseek_api_key="test-key",
        mud_spec_skeleton_model="deepseek-reasoner",
        mud_spec_skeleton_provider="deepseek",
        pipeline_reviewer_model="deepseek-reasoner",
        pipeline_reviewer_provider="deepseek",
    )
    orchestrator = AIOrchestrator(settings)
    for backend in (orchestrator._get_skeleton_backend(), orchestrator._get_reviewer_backend()):
        assert backend.settings.openai_model == "deepseek-reasoner"
        assert "deepseek.com" in backend.settings.openai_base_url


def _local_global_deepseek_generator() -> Settings:
    return Settings(
        ai_backend=AIBackend.CLOUD,
        cloud_provider=CloudProvider.OPENAI_COMPATIBLE,
        openai_api_key="ollama",
        openai_base_url="http://localhost:11434/v1",
        openai_model="qwen3:8b-ctx16384",
        deepseek_api_key="test-key",
        pipeline_generator_model="deepseek-chat",
        pipeline_generator_provider="deepseek",
    )


def test_single_call_activity_uses_the_activity_generator_stage(monkeypatch):
    """Regression: generate_diagram(ACTIVITY) ran on the global local qwen3 although every
    stage was set to DeepSeek."""
    import asyncio
    from mudtool.ai.base_backend import AIResponse
    from mudtool.models.json_uml import DiagramType

    used = []

    async def fake_generate(self, system_prompt, user_prompt, max_tokens=8192, temperature=0.2, **kw):
        used.append((self.settings.openai_model, self.settings.openai_base_url))
        return AIResponse(content="{}", model=self.settings.openai_model, input_tokens=0, output_tokens=0,
                          finish_reason="stop", latency_ms=1)

    monkeypatch.setattr(CloudBackend, "generate", fake_generate)
    orchestrator = AIOrchestrator(_local_global_deepseek_generator())
    try:
        asyncio.run(orchestrator.generate_diagram(DiagramType.ACTIVITY, []))
    except Exception:
        pass  # parsing an empty diagram may fail; only the backend choice matters here
    assert used, "no model call was made"
    assert all(model == "deepseek-chat" and "deepseek.com" in base for model, base in used)


def test_activity_answer_cut_off_at_the_cap_is_retried_with_a_shorter_request(monkeypatch):
    """Every DeepSeek run: the activity JSON stopped at 8192 tokens (finish_reason=length) and the
    retry only said "output valid JSON", so the same request was cut off again."""
    import asyncio
    from mudtool.ai.base_backend import AIResponse
    from mudtool.models.json_uml import DiagramType

    prompts = []
    replies = [('{"diagrams": [{"diagram_type": "activity", "name": "RE_Init Code Flow", "nodes": [', "length"),
               ("{}", "stop")]

    async def fake_generate(self, system_prompt, user_prompt, max_tokens=8192, temperature=0.2, **kw):
        prompts.append(user_prompt)
        content, finish = replies.pop(0) if replies else ("{}", "stop")
        return AIResponse(content=content, model="deepseek-chat", input_tokens=0, output_tokens=8192,
                          finish_reason=finish, latency_ms=1)

    monkeypatch.setattr(CloudBackend, "generate", fake_generate)
    orchestrator = AIOrchestrator(_local_global_deepseek_generator())
    try:
        asyncio.run(orchestrator.generate_diagram(DiagramType.ACTIVITY, []))
    except Exception:
        pass
    assert len(prompts) >= 2
    assert "output limit" in prompts[1] and "shorter" in prompts[1]
    assert "output limit" not in prompts[0]


def test_cloud_reasoning_model_gets_a_token_floor_local_does_not():
    from mudtool.ai.cloud_backend import REASONING_MIN_TOKENS
    s = _local_global_deepseek_generator()
    orchestrator = AIOrchestrator(s)
    reviewer = orchestrator._make_backend_with_model("deepseek-reasoner", provider="deepseek")
    assert reviewer._effective_max_tokens(2048) == REASONING_MIN_TOKENS
    chat = orchestrator._make_backend_with_model("deepseek-chat", provider="deepseek")
    assert chat._effective_max_tokens(2048) == 2048
    local = CloudBackend(s)   # local Ollama qwen3: context is small, keep the caller's value
    assert local._effective_max_tokens(2048) == 2048
