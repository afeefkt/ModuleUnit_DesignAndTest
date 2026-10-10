"""Ensure the repo root is importable so tests can ``import mudmut_core``."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_user_config(tmp_path, monkeypatch):
    """Tests must never write the user's real config/ or outputs/ (timings, probe cache, LLM log)."""
    from mudmut_core import progress
    from mudmut_core.llm import observe, probe
    monkeypatch.setattr(progress, "TIMINGS_FILE", tmp_path / "stage_timings.json")
    monkeypatch.setattr(probe, "PROBE_FILE", tmp_path / "model_probe.json")
    monkeypatch.setattr(observe, "STATE_LOG", tmp_path / "llm_log.jsonl")
    yield
