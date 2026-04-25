"""Cloud AI backend supporting Anthropic Claude and OpenAI-compatible APIs."""

from __future__ import annotations

import asyncio
import json as _json
import logging
import re
import time
from typing import AsyncIterator, Optional

from mudtool.ai.base_backend import AIResponse, BaseAIBackend
from mudtool.config.settings import CloudProvider, Settings

logger = logging.getLogger(__name__)


class CloudBackend(BaseAIBackend):
    """Cloud AI inference backend.

    Supports:
    - Anthropic Claude API (primary, recommended)
    - OpenAI-compatible endpoints (Azure, vLLM, etc.)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._anthropic_client = None
        self._openai_client = None

    @property
    def backend_name(self) -> str:
        return f"cloud:{self.settings.cloud_provider.value}"

    @property
    def is_available(self) -> bool:
        if self.settings.cloud_provider == CloudProvider.ANTHROPIC:
            return bool(self.settings.anthropic_api_key)
        return bool(self.settings.openai_api_key)

    def _get_anthropic_client(self):
        """Lazy-initialize Anthropic client."""
        if self._anthropic_client is None:
            try:
                import anthropic
                self._anthropic_client = anthropic.AsyncAnthropic(
                    api_key=self.settings.anthropic_api_key
                )
            except ImportError:
                raise RuntimeError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
        return self._anthropic_client

    def _get_openai_client(self):
        """Lazy-initialize OpenAI-compatible client."""
        if self._openai_client is None:
            try:
                import httpx
                self._openai_client = httpx.AsyncClient(
                    base_url=self.settings.openai_base_url or "https://api.openai.com/v1",
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=600.0,
                )
            except ImportError:
                raise RuntimeError("httpx package not installed. Run: pip install httpx")
        return self._openai_client

    def _is_local_ollama(self) -> bool:
        """Return True if the configured endpoint looks like a local Ollama instance."""
        base = self.settings.openai_base_url or ""
        return any(h in base for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))

    async def _pull_ollama_model(self, model_name: str) -> bool:
        """Pull a missing Ollama model via 'ollama pull <model>'.

        Only attempted for local Ollama endpoints.
        Streams progress lines to the logger so the user can follow download progress.
        Returns True if the pull succeeded, False otherwise.
        """
        if not self._is_local_ollama():
            return False

        logger.info(f"Model '{model_name}' not found — auto-pulling: ollama pull {model_name}")
        logger.info("Download may take several minutes depending on model size and connection speed.")

        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "pull", model_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Stream output lines so progress is visible in server logs
            assert proc.stdout is not None
            async for line in proc.stdout:
                text = line.decode(errors="replace").rstrip()
                if text:
                    logger.info(f"[ollama pull {model_name}] {text}")

            await asyncio.wait_for(proc.wait(), timeout=600)

            if proc.returncode == 0:
                logger.info(f"ollama pull {model_name}: completed successfully")
                return True

            logger.error(f"ollama pull {model_name}: exited with code {proc.returncode}")
            return False

        except asyncio.TimeoutError:
            logger.error(f"ollama pull {model_name}: timed out after 600 s")
            return False
        except FileNotFoundError:
            logger.error(
                f"ollama pull {model_name}: 'ollama' command not found. "
                "Is Ollama installed and on PATH?"
            )
            return False
        except Exception as exc:
            logger.error(f"ollama pull {model_name}: unexpected error: {exc}")
            return False

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
        stop_sequences: Optional[list[str]] = None,
        response_format: str = "text",
    ) -> AIResponse:
        start_time = time.monotonic()

        if self.settings.cloud_provider == CloudProvider.ANTHROPIC:
            return await self._generate_anthropic(
                system_prompt, user_prompt, max_tokens, temperature,
                stop_sequences, start_time,
            )
        else:
            return await self._generate_openai(
                system_prompt, user_prompt, max_tokens, temperature,
                stop_sequences, start_time,
                response_format=response_format,
            )

    async def _generate_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        stop_sequences: Optional[list[str]],
        start_time: float,
    ) -> AIResponse:
        """Generate using Anthropic Claude API."""
        client = self._get_anthropic_client()

        kwargs = {
            "model": self.settings.anthropic_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences

        logger.info(f"Anthropic API call: model={self.settings.anthropic_model}")

        response = await client.messages.create(**kwargs)

        latency = int((time.monotonic() - start_time) * 1000)

        return AIResponse(
            content=response.content[0].text if response.content else "",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason,
            latency_ms=latency,
        )

    async def _generate_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        stop_sequences: Optional[list[str]],
        start_time: float,
        response_format: str = "text",
    ) -> AIResponse:
        """Generate using OpenAI-compatible API."""
        client = self._get_openai_client()

        payload = {
            "model": self.settings.openai_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        # Enable thinking for reasoning models (deepseek-r1, qwq, etc.) automatically,
        # or for any model when MUD_OPENAI_ENABLE_THINKING=true is set explicitly.
        _REASONING_KEYWORDS = ("deepseek-r1", ":r1-", "qwq", "thinking")
        model_lower = payload["model"].lower()
        is_reasoning_model = any(kw in model_lower for kw in _REASONING_KEYWORDS)
        if self.settings.openai_enable_thinking or is_reasoning_model:
            payload["think"] = True    # Ollama extension: enables chain-of-thought reasoning

        # Only inject format:json when the CALLER explicitly requests JSON output.
        # NEVER apply to Markdown / prose generation — it corrupts the response.
        if response_format == "json" and self.settings.openai_json_mode and self._is_local_ollama():
            payload["format"] = "json"

        if stop_sequences:
            payload["stop"] = stop_sequences

        logger.info(
            f"OpenAI-compatible API call: model={self.settings.openai_model} "
            f"response_format={response_format}"
        )

        response = await client.post("/chat/completions", json=payload)

        # Auto-pull missing Ollama models and retry once
        if response.status_code == 404 and self._is_local_ollama():
            model_name = payload["model"]
            pulled = await self._pull_ollama_model(model_name)
            if pulled:
                response = await client.post("/chat/completions", json=payload)

        response.raise_for_status()
        data = response.json()

        latency = int((time.monotonic() - start_time) * 1000)

        choice = data["choices"][0] if data.get("choices") else {}
        usage = data.get("usage", {})

        # Ollama <0.6.2 includes <think>...</think> reasoning blocks inside message.content
        # instead of separating them into message.thinking.  Strip them so downstream JSON
        # extraction sees only the actual response text.
        raw_content = choice.get("message", {}).get("content", "") or ""
        content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()

        return AIResponse(
            content=content,
            model=data.get("model", self.settings.openai_model),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason"),
            latency_ms=latency,
        )

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        """Stream generation token-by-token.

        Uses native SSE streaming for both Anthropic and OpenAI-compatible
        backends so tokens arrive incrementally rather than all-at-once.
        This gives the user real-time feedback during long generations.
        """
        if self.settings.cloud_provider == CloudProvider.ANTHROPIC:
            async for chunk in self._stream_anthropic(
                system_prompt, user_prompt, max_tokens, temperature
            ):
                yield chunk
        else:
            async for chunk in self._stream_openai(
                system_prompt, user_prompt, max_tokens, temperature
            ):
                yield chunk

    async def _stream_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        """Stream from Anthropic API."""
        client = self._get_anthropic_client()

        async with client.messages.stream(
            model=self.settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _stream_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        """Stream token-by-token from an OpenAI-compatible endpoint (Ollama, vLLM, etc.).

        Sends ``stream: true`` and parses the ``text/event-stream`` SSE response.
        Filters out ``<think>...</think>`` blocks from reasoning models so only the
        final answer text is yielded.

        Falls back to a single non-streaming call if the endpoint does not support
        streaming (e.g. older Ollama versions).
        """
        client = self._get_openai_client()

        payload = {
            "model": self.settings.openai_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        # Enable reasoning for deepseek-r1 / qwq style models
        _REASONING_KEYWORDS = ("deepseek-r1", ":r1-", "qwq", "thinking")
        if self.settings.openai_enable_thinking or any(
            kw in payload["model"].lower() for kw in _REASONING_KEYWORDS
        ):
            payload["think"] = True

        # Never inject format:json for streaming — it prevents proper SSE streaming
        # and would corrupt Markdown output.

        logger.info(
            f"OpenAI-compatible STREAM: model={self.settings.openai_model}"
        )

        try:
            in_think_block = False
            async with client.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code == 404 and self._is_local_ollama():
                    # Model not found — try pulling, then fall back to non-streaming
                    pulled = await self._pull_ollama_model(payload["model"])
                    if pulled:
                        async for chunk in self._stream_openai(
                            system_prompt, user_prompt, max_tokens, temperature
                        ):
                            yield chunk
                        return
                    else:
                        raise RuntimeError(
                            f"Model '{payload['model']}' not found and pull failed"
                        )

                resp.raise_for_status()

                async for raw_line in resp.aiter_lines():
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    if not raw_line.startswith("data: "):
                        continue
                    chunk_str = raw_line[6:]
                    if chunk_str == "[DONE]":
                        break
                    try:
                        chunk = _json.loads(chunk_str)
                    except _json.JSONDecodeError:
                        continue

                    delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                    text = delta.get("content") or ""
                    if not text:
                        continue

                    # Filter <think>...</think> from reasoning models
                    if "<think>" in text:
                        in_think_block = True
                    if in_think_block:
                        if "</think>" in text:
                            in_think_block = False
                            text = text[text.index("</think>") + len("</think>"):]
                        else:
                            continue

                    if text:
                        yield text

        except Exception as exc:
            logger.warning(
                "OpenAI streaming failed (%s), falling back to non-streaming", exc
            )
            # Graceful fallback: collect the full response in one shot
            response = await self.generate(
                system_prompt, user_prompt, max_tokens, temperature,
                response_format="text",
            )
            yield response.content

    async def health_check(self) -> dict:
        base = await super().health_check()
        base["provider"] = self.settings.cloud_provider.value
        base["model"] = (
            self.settings.anthropic_model
            if self.settings.cloud_provider == CloudProvider.ANTHROPIC
            else self.settings.openai_model
        )
        return base
