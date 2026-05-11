"""Per-run structured debug trace for UI-triggered generation workflows."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LARGE_TEXT_KEYS = {
    "mud_spec_markdown",
    "current_spec_markdown",
    "requirements_text",
    "result",
    "validation_report",
    "raw_response",
    "content",
    "prompt",
}
_SECRET_MARKERS = ("api_key", "apikey", "authorization", "bearer", "token", "password", "secret")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _summarize_large_value(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {
            "omitted": True,
            "type": "str",
            "length": len(value),
            "preview": value[:240],
        }
    if isinstance(value, list):
        return {
            "omitted": True,
            "type": "list",
            "length": len(value),
        }
    if isinstance(value, dict):
        return {
            "omitted": True,
            "type": "dict",
            "keys": sorted(str(key) for key in value.keys())[:80],
        }
    return {
        "omitted": True,
        "type": type(value).__name__,
    }


def _safe_json_value(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if _is_secret_key(key):
        return "[redacted]"
    if key in _LARGE_TEXT_KEYS:
        return _summarize_large_value(value)
    if depth > 6:
        return _summarize_large_value(value)

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > 2000:
            return _summarize_large_value(value)
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        if len(value) > 120:
            return {
                "omitted_tail": len(value) - 120,
                "items": [_safe_json_value(item, depth=depth + 1) for item in value[:120]],
            }
        return [_safe_json_value(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for item_key, item_value in value.items():
            safe_key = str(item_key)
            safe[safe_key] = _safe_json_value(item_value, key=safe_key, depth=depth + 1)
        return safe
    if hasattr(value, "model_dump"):
        try:
            return _safe_json_value(value.model_dump(mode="json"), key=key, depth=depth + 1)
        except Exception:
            pass
    if hasattr(value, "to_dict"):
        try:
            return _safe_json_value(value.to_dict(), key=key, depth=depth + 1)
        except Exception:
            pass
    return str(value)


class RunDebugTrace:
    """JSONL debug trace that is recreated at the start of each UI run."""

    def __init__(
        self,
        settings: Any,
        run_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        project_root = Path(getattr(settings, "project_root", Path.cwd()))
        self.path = project_root / "output" / "debug" / "latest_run.jsonl"
        self.meta_path = project_root / "output" / "debug" / "latest_run_meta.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = uuid.uuid4().hex
        self.run_type = run_type
        self._start = time.perf_counter()
        self._seq = 0

        self.path.write_text("", encoding="utf-8")
        meta = {
            "run_id": self.run_id,
            "run_type": self.run_type,
            "started_at": _utc_now(),
            "trace_path": str(self.path),
            "metadata": _safe_json_value(metadata or {}),
        }
        self.meta_path.write_text(
            json.dumps(meta, ensure_ascii=True, indent=2, default=str),
            encoding="utf-8",
        )
        self.record("run_start", metadata=metadata or {})

    def record(self, stage: str, **data: Any) -> None:
        self._seq += 1
        item = {
            "seq": self._seq,
            "ts": _utc_now(),
            "elapsed_ms": round((time.perf_counter() - self._start) * 1000, 2),
            "run_id": self.run_id,
            "run_type": self.run_type,
            "stage": stage,
            "data": _safe_json_value(data),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=True, default=str) + "\n")

    def record_event(self, event_type: str, event: dict[str, Any]) -> None:
        stage = str(event.get("stage") or event_type)
        self.record(
            stage,
            event_type=event_type,
            event=event,
        )

    def attach_path(self, event: dict[str, Any]) -> dict[str, Any]:
        event["debug_trace_path"] = str(self.path)
        event["debug_run_id"] = self.run_id
        return event
