"""LLM client layer — providers (Ollama / OpenRouter / NVIDIA / DeepSeek) and a
thin OpenAI-compatible chat client.
"""

from mudmut_core.llm.client import achat, chat, chat_blocking, chat_sync, ollama_unload, unload_many  # noqa: F401
from mudmut_core.llm.providers import (  # noqa: F401
    Provider,
    ProviderError,
    get_providers,
    has_key,
    key_source,
    list_models,
    resolve_key,
    test_chat,
)

__all__ = [
    "Provider", "ProviderError", "get_providers", "has_key", "key_source",
    "list_models", "resolve_key", "test_chat",
    "achat", "chat", "chat_blocking", "chat_sync", "ollama_unload", "unload_many",
]
