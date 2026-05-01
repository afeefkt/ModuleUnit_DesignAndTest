"""Requirement Elaboration with AI Chain-of-Thought Reasoning.

Pre-processes raw requirements into structured AUTOSAR-specific JSON
using an AI "thinking" step. The elaborated data is cached to disk and
injected into generation prompts for richer context.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from mudtool.ai.base_backend import BaseAIBackend
from mudtool.config.settings import Settings
from mudtool.models.requirements import Requirement

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"
_CACHE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "elaborated"


def _purge_stale_cache(keep: Path) -> None:
    """Delete all elaboration cache files except *keep*.

    Called after writing a fresh elaboration so that requirements from
    previous imports can never be accidentally reused and confuse the AI.
    """
    deleted = 0
    for old in _CACHE_DIR.glob("*.json"):
        if old == keep:
            continue
        try:
            old.unlink()
            deleted += 1
        except Exception as exc:
            logger.warning("Could not remove stale elaboration cache %s: %s", old.name, exc)
    if deleted:
        logger.info("Purged %d stale elaboration cache file(s) from %s", deleted, _CACHE_DIR)


class RequirementElaborator:
    """Elaborates terse requirements into structured AUTOSAR JSON.

    Uses chain-of-thought prompting so the AI reasons step-by-step
    about entities, timing, safety, and cross-requirement relationships
    before producing structured output.

    Elaborated results are cached in data/elaborated/<hash>.json.
    """

    def __init__(self, settings: Settings, backend: BaseAIBackend):
        self.settings = settings
        self.backend = backend
        self._prompt = self._load_prompt()

    @staticmethod
    def _load_prompt() -> dict:
        path = _PROMPTS_DIR / "elaboration.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Elaboration prompt not found: {path}")
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def _compute_hash(requirements: list[Requirement]) -> str:
        """Content-based hash of requirements for caching."""
        text = "\n".join(
            f"{r.req_id}|{r.req_type.value}|{r.title}|{r.description}"
            for r in sorted(requirements, key=lambda r: r.req_id)
        )
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    @staticmethod
    def get_cache_path(req_hash: str) -> Path:
        return _CACHE_DIR / f"{req_hash}.json"

    def load_cached(self, requirements: list[Requirement]) -> Optional[dict]:
        """Load previously elaborated data from cache, if it exists."""
        req_hash = self._compute_hash(requirements)
        cache_path = self.get_cache_path(req_hash)
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                if self._is_valid_elaboration(data, requirements):
                    data.setdefault("source", "cache_hit")
                    logger.info(f"Loaded elaborated data from cache: {cache_path}")
                    return data
                logger.warning(
                    f"Ignoring invalid elaboration cache: {cache_path}"
                )
            except Exception as exc:
                logger.warning(f"Failed to load elaboration cache: {exc}")
        return None

    async def elaborate(
        self,
        requirements: list[Requirement],
        progress_callback: Optional[callable] = None,
        force_refresh: bool = False,
    ) -> dict:
        """Elaborate requirements using AI chain-of-thought reasoning.

        Returns dict with keys: thinking, elaborated, req_hash
        Result is cached to data/elaborated/<hash>.json.
        """
        # Check cache first
        req_hash = self._compute_hash(requirements)
        if not force_refresh:
            cached = self.load_cached(requirements)
            if cached:
                return cached

        if progress_callback:
            progress_callback({
                "stage": "elaborate",
                "message": f"AI is reasoning about {len(requirements)} requirements...",
            })

        system_prompt = self._prompt["system_prompt"]
        reqs_text = "\n".join(
            f"[{r.req_id}] ({r.req_type.value}) {r.title}: {r.description}"
            for r in requirements
        )
        user_template = self._prompt.get("user_prompt_template", "")
        user_prompt = user_template.format(
            req_count=len(requirements),
            requirements_text=reqs_text,
        )

        # Scale max_tokens by requirement count for larger inputs
        base_max = min(self.settings.openai_max_tokens, 16384)
        max_tokens = min(2048 + 512 * len(requirements), base_max)
        logger.info(
            f"Elaborating {len(requirements)} requirements via AI "
            f"(max_tokens={max_tokens})..."
        )

        response = await self.backend.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=0.3,
        )

        # Parse JSON from AI response
        result = self._parse_response(response.content, req_hash)
        result.setdefault("model", response.model)

        # Up to 2 retries with progressive temperature reduction
        retry_temps = [0.2, 0.1]
        for retry_idx, retry_temp in enumerate(retry_temps, 1):
            if self._is_valid_elaboration(result, requirements):
                break
            logger.info(
                f"Elaboration retry {retry_idx}/{len(retry_temps)} "
                f"(temp={retry_temp})..."
            )
            strict_prompt = (
                "Return ONLY a strict JSON object with keys: "
                '"thinking", "architecture_summary", "elaborated". '
                "No markdown, no tags, no explanations. "
                "Every requirement MUST appear in elaborated[]."
            )
            response_retry = await self.backend.generate(
                system_prompt=system_prompt,
                user_prompt=f"{user_prompt}\n\n{strict_prompt}",
                max_tokens=max_tokens,
                temperature=retry_temp,
            )
            retry_result = self._parse_response(response_retry.content, req_hash)
            retry_result.setdefault("model", response_retry.model)
            if self._is_valid_elaboration(retry_result, requirements):
                result = retry_result
                break

        if self._is_valid_elaboration(result, requirements):
            result.setdefault("source", "cache_miss_regenerated")
        else:
            result.setdefault("source", "failed")

        # Cache to disk (including weak outputs; they will be ignored next time)
        self._save_cache(result, requirements)

        logger.info(
            f"Elaboration complete: {len(result.get('thinking', []))} thinking steps, "
            f"{len(result.get('elaborated', []))} elaborated requirements"
        )

        return result

    def _parse_response(self, text: str, req_hash: str) -> dict:
        """Extract JSON from AI response.

        Supports multiple formats (prioritized):
        1. Direct JSON parse (works with Ollama JSON mode)
        2. Legacy <reasoning>/<json> tags (for non-JSON-mode backends)
        3. Markdown code blocks
        4. Boundary scan ({...})
        """
        import re

        text = text.strip()
        data = None
        thinking: list[str] = []

        # Strategy 1: Direct JSON parse (preferred — works with JSON mode)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Legacy <reasoning>/<json> tags (for non-JSON-mode backends)
        if data is None:
            reasoning_match = re.search(
                r"<reasoning>(.*?)</reasoning>", text, re.DOTALL | re.IGNORECASE
            )
            if reasoning_match:
                raw_thinking = reasoning_match.group(1).strip()
                thinking = [
                    line.strip("- ").strip()
                    for line in raw_thinking.split("\n")
                    if line.strip()
                ]
            json_match = re.search(
                r"<json>(.*?)</json>", text, re.DOTALL | re.IGNORECASE
            )
            if json_match:
                try:
                    data = json.loads(json_match.group(1).strip())
                except json.JSONDecodeError:
                    pass

        # Strategy 3: Markdown code block
        if data is None:
            m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1).strip())
                except json.JSONDecodeError:
                    pass

        # Strategy 4: Boundary scan
        if data is None:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    data = json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass

        if data is None:
            logger.warning("Failed to parse elaboration response as JSON")
            parsed = {
                "thinking": thinking or ["(AI response could not be parsed)"],
                "elaborated": [],
                "req_hash": req_hash,
                "raw_response": text[:2000],
                "parse_ok": False,
                "status": "invalid",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "elaborated_count": 0,
                "quality_score": 0.0,
            }
            return parsed

        # Merge thinking from tags if the JSON didn't include it
        if thinking and "thinking" not in data:
            data["thinking"] = thinking
        # Ensure thinking key always exists
        data.setdefault("thinking", [])

        data["req_hash"] = req_hash
        data["parse_ok"] = True
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        return data

    def _save_cache(self, data: dict, requirements: list[Requirement]) -> None:
        """Save elaborated data to cache file. Only saves valid elaborations."""
        req_hash = data.get("req_hash", "unknown")
        cache_path = self.get_cache_path(req_hash)
        quality = self._compute_quality(data, requirements)
        data["quality_score"] = quality
        data["elaborated_count"] = len(data.get("elaborated", []))
        is_valid = self._is_valid_elaboration(data, requirements)
        data["status"] = "ok" if is_valid else "invalid"
        data["prompt_version"] = self._prompt.get("version", "unknown")

        # Only persist valid elaborations — don't pollute cache with failures
        if not is_valid:
            logger.warning(f"Elaboration invalid (quality={quality:.2f}), not caching.")
            return

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Saved elaboration cache: {cache_path} (quality={quality:.2f})")

        # Remove every OTHER elaboration file so stale data from previous imports
        # can never be accidentally reused. Keep only the file we just wrote.
        _purge_stale_cache(keep=cache_path)

    def _compute_quality(self, data: dict, requirements: list[Requirement]) -> float:
        """Compute a lightweight quality score for elaboration output."""
        if not isinstance(data, dict):
            return 0.0
        items = data.get("elaborated", [])
        if not isinstance(items, list):
            return 0.0
        req_ids = {r.req_id for r in requirements}
        covered = {
            i.get("req_id")
            for i in items
            if isinstance(i, dict) and i.get("req_id")
        }
        coverage = len(covered & req_ids) / max(len(req_ids), 1)
        parse_ok = 1.0 if data.get("parse_ok", True) else 0.0
        return round((0.7 * coverage) + (0.3 * parse_ok), 3)

    def _is_valid_elaboration(self, data: dict, requirements: list[Requirement]) -> bool:
        """Minimum quality gate for using elaboration cache in generation.

        Requires 70% requirement coverage (raised from 50% for better quality).
        Also invalidates cache if prompt version has changed.
        """
        if not isinstance(data, dict):
            return False
        if data.get("parse_ok") is False:
            return False
        items = data.get("elaborated", [])
        if not isinstance(items, list) or not items:
            return False
        # Invalidate if prompt version changed
        cached_version = data.get("prompt_version")
        current_version = self._prompt.get("version", "unknown")
        if cached_version and cached_version != current_version:
            logger.info(
                f"Elaboration cache version mismatch: {cached_version} vs {current_version}"
            )
            return False
        req_ids = {r.req_id for r in requirements}
        covered = {
            i.get("req_id")
            for i in items
            if isinstance(i, dict) and i.get("req_id")
        }
        coverage = len(covered & req_ids) / max(len(req_ids), 1)
        return coverage >= 0.7


_MAX_ENRICHED_CONTEXT_CHARS = 1500  # Cap to avoid overwhelming 7B model prompts


def build_enriched_context(elaborated_data: dict) -> str:
    """Build a concise Markdown block from elaborated data to inject into generation prompts.

    Only includes entries with meaningful entities. Caps total length to prevent
    overwhelming small LLM context windows.
    """
    items = elaborated_data.get("elaborated", [])
    if not items:
        return ""

    lines = [
        "### ARCHITECTURE ANALYSIS & ELABORATION GUIDANCE",
        "",
    ]

    summary = elaborated_data.get("architecture_summary")
    if summary:
        lines.append(f"**Architecture Summary:** {summary[:200]}")
        lines.append("")

    lines.append("#### Requirement Elaboration:")
    for item in items:
        req_id = item.get('req_id', '?')
        ent = item.get("entities", {})

        # Only include entries with non-empty entities
        has_entities = any(
            ent.get(k) for k in ("swc", "runnables", "ports", "interfaces")
        )
        if not has_entities:
            continue

        ent_parts = []
        if ent.get("swc"):
            ent_parts.append(f"SWC: `{ent['swc']}`")
        if ent.get("runnables"):
            ent_parts.append(f"Runnables: `{', '.join(ent['runnables'])}`")
        if ent.get("ports"):
            ent_parts.append(f"Ports: `{', '.join(ent['ports'])}`")

        lines.append(f"- **[{req_id}]**: {', '.join(ent_parts)}")

        logic = item.get("logic_flow")
        if logic:
            lines.append(f"  Logic: {logic[:120]}")

        hints = item.get("diagram_hints", {})
        if hints:
            hint_parts = ", ".join(f"{k}: {v}" for k, v in hints.items())
            lines.append(f"  Hints: {hint_parts[:200]}")

    # Include concise thinking summary (max 5 steps)
    thinking = elaborated_data.get("thinking", [])
    if thinking:
        lines.append("")
        lines.append("#### AI Reasoning:")
        for t in thinking[:5]:
            lines.append(f"  - {t[:120]}")

    lines.append("")
    lines.append("---")
    result = "\n".join(lines)

    # Truncate if too long for small model context
    if len(result) > _MAX_ENRICHED_CONTEXT_CHARS:
        result = result[:_MAX_ENRICHED_CONTEXT_CHARS] + "\n...(truncated)\n---"

    return result
