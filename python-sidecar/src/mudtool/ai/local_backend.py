"""Local LLM inference backend using llama-cpp-python.

Supports GGUF quantized models with GPU acceleration via CUDA/Metal.
Recommended models: Qwen2.5-Coder-7B, Mistral 7B, CodeLlama 13B.

GPU Auto-detection:
  Set MUD_LOCAL_MODEL_AUTO_GPU=true (default) to let MUD detect whether
  CUDA (NVIDIA) or Metal (Apple) is available and configure GPU layers
  automatically:
    - GPU found  → n_gpu_layers = -1  (all layers on GPU, maximum speed)
    - No GPU     → n_gpu_layers =  0  (CPU-only mode)

  Override by setting MUD_LOCAL_MODEL_N_GPU_LAYERS explicitly:
    -1 = force all-GPU, 0 = force CPU, N = N layers on GPU (rest on CPU)
"""

from __future__ import annotations

import ctypes
import logging
import platform
import time
from typing import AsyncIterator, Optional

from mudtool.ai.base_backend import AIResponse, BaseAIBackend
from mudtool.config.settings import Settings

logger = logging.getLogger(__name__)


def _detect_gpu_available() -> bool:
    """Detect whether a compatible GPU (CUDA or Metal) is available.

    Checks for:
    - NVIDIA CUDA: looks for nvcuda.dll (Windows) or libcuda.so.1 (Linux)
    - Apple Metal: macOS platform check (Metal is always available on Apple Silicon)

    Returns True if a GPU backend is detected, False for CPU-only.
    """
    system = platform.system()
    try:
        if system == "Windows":
            ctypes.WinDLL("nvcuda.dll")  # type: ignore[attr-defined]
            logger.info("GPU auto-detect: CUDA (NVIDIA) found on Windows")
            return True
        elif system == "Linux":
            ctypes.CDLL("libcuda.so.1")
            logger.info("GPU auto-detect: CUDA (NVIDIA) found on Linux")
            return True
        elif system == "Darwin":
            # Apple Silicon — Metal always available; Intel Macs have no GPU llama.cpp
            import subprocess  # noqa: PLC0415
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=3,
            )
            if "Apple" in result.stdout:
                logger.info("GPU auto-detect: Apple Silicon Metal found")
                return True
    except Exception:
        pass
    logger.info("GPU auto-detect: No compatible GPU found, using CPU mode")
    return False


class LocalBackend(BaseAIBackend):
    """Local LLM inference backend via llama-cpp-python.

    Manages model loading, inference, and resource configuration.
    The model is loaded lazily on first use.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm = None
        self._model_loaded = False

    @property
    def backend_name(self) -> str:
        return "local:llama-cpp"

    @property
    def is_available(self) -> bool:
        if not self.settings.local_model_path:
            return False
        try:
            from pathlib import Path
            return Path(self.settings.local_model_path).exists()
        except Exception:
            return False

    def _load_model(self):
        """Load the GGUF model into memory."""
        if self._model_loaded:
            return

        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python not installed. "
                "Run: pip install llama-cpp-python "
                "(with CUDA: CMAKE_ARGS='-DGGML_CUDA=on' pip install llama-cpp-python)"
            )

        model_path = self.settings.local_model_path

        # Resolve effective GPU layer count
        if self.settings.local_model_auto_gpu:
            gpu_layers = -1 if _detect_gpu_available() else 0
            logger.info(
                f"GPU auto-detect: n_gpu_layers={'all (-1)' if gpu_layers == -1 else '0 (CPU)'}"
            )
        else:
            gpu_layers = self.settings.local_model_n_gpu_layers

        logger.info(
            f"Loading local model: {model_path} "
            f"(n_gpu_layers={gpu_layers}, n_ctx={self.settings.local_model_n_ctx})"
        )

        self._llm = Llama(
            model_path=str(model_path),
            n_gpu_layers=gpu_layers,
            n_ctx=self.settings.local_model_n_ctx,
            n_batch=self.settings.local_model_n_batch,
            n_threads=self.settings.local_model_n_threads,
            verbose=self.settings.debug,
        )
        self._model_loaded = True
        logger.info("Local model loaded successfully")

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
        stop_sequences: Optional[list[str]] = None,
        response_format: str = "text",
    ) -> AIResponse:
        self._load_model()
        start_time = time.monotonic()

        # Format as chat completion
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"Local inference: max_tokens={max_tokens}, temp={temperature}")

        response = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop_sequences,
        )

        latency = int((time.monotonic() - start_time) * 1000)

        choice = response["choices"][0] if response.get("choices") else {}
        usage = response.get("usage", {})

        content = choice.get("message", {}).get("content", "")

        return AIResponse(
            content=content,
            model=f"local:{self.settings.local_model_path}",
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
        """Stream generation from local model."""
        self._load_model()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        stream = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content

    def unload_model(self):
        """Unload the model from memory to free resources."""
        if self._llm is not None:
            del self._llm
            self._llm = None
            self._model_loaded = False
            logger.info("Local model unloaded")

    async def health_check(self) -> dict:
        base = await super().health_check()
        base["model_path"] = self.settings.local_model_path
        base["model_loaded"] = self._model_loaded
        base["auto_gpu"] = self.settings.local_model_auto_gpu
        base["gpu_detected"] = _detect_gpu_available() if self.settings.local_model_auto_gpu else None
        base["gpu_layers"] = self.settings.local_model_n_gpu_layers
        base["context_length"] = self.settings.local_model_n_ctx
        return base
