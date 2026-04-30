"""Base AI backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from pydantic import BaseModel, Field


class AIResponse(BaseModel):
    """Response from an AI backend."""
    content: str = Field(..., description="Raw text response from the AI")
    model: str = Field("", description="Model identifier used")
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: Optional[str] = None
    latency_ms: Optional[int] = None


class BaseAIBackend(ABC):
    """Abstract base class for AI inference backends."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return backend identifier (e.g., 'anthropic', 'local')."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is ready for inference."""
        ...

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
        stop_sequences: Optional[list[str]] = None,
        response_format: str = "text",
    ) -> AIResponse:
        """Generate a completion.

        Args:
            system_prompt: System/context prompt with domain knowledge.
            user_prompt: User prompt with requirements and instructions.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature (lower = more deterministic).
            stop_sequences: Optional stop sequences.
            response_format: ``"json"`` forces JSON-mode on backends that support
                it (Ollama ``format`` field).  ``"text"`` (default) leaves the
                model free to produce prose / Markdown.  NEVER pass ``"json"``
                for prompts that ask for Markdown output — it will corrupt the
                response.

        Returns:
            AIResponse with the generated text.
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        """Generate a streaming completion.

        Yields partial text chunks as they arrive.
        """
        ...
        # Make this a proper async generator
        yield ""  # pragma: no cover

    async def health_check(self) -> dict:
        """Check backend health status."""
        return {
            "backend": self.backend_name,
            "available": self.is_available,
        }
