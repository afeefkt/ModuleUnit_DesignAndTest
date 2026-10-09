"""Persistent run workspace.

Each pipeline run lives under ``workspace/runs/<timestamp>_<swc>/`` and every
step persists its output there, so any single step can be inspected or re-run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mudmut_core.env import REPO_ROOT

RUNS_ROOT = REPO_ROOT / "workspace" / "runs"

# Canonical artifact filenames (order = pipeline order).
REQUIREMENTS = "requirements.json"
MUD_SPEC = "mud_spec.md"
REVIEW = "review.json"
ACTIVITY = "activity.json"
FLOW = "flow.mmd"
SKELETON = "skeleton.c"
COMPILABILITY = "compilability.json"
TESTS_DIR = "tests"
RESULTS = "results.json"
TRACE = "trace.json"
STATE = "state.json"


@dataclass
class Run:
    """A single MUD → MUT pipeline run, backed by a folder on disk."""

    swc: str
    folder: Path
    state: dict[str, Any] = field(default_factory=dict)

    # ── construction ──────────────────────────────────────────────────────────
    @classmethod
    def create(cls, swc: str, *, root: Optional[Path] = None) -> "Run":
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if (c.isalnum() or c in "_-") else "_" for c in swc)
        base = (root or RUNS_ROOT)
        base.mkdir(parents=True, exist_ok=True)
        folder = base / f"{stamp}_{safe}"
        folder.mkdir(parents=True, exist_ok=True)
        run = cls(swc=swc, folder=folder, state={"swc": swc, "created": stamp})
        run.save_state()
        return run

    @classmethod
    def load(cls, folder: Path | str) -> "Run":
        folder = Path(folder)
        state = {}
        state_path = folder / STATE
        if state_path.is_file():
            state = json.loads(state_path.read_text(encoding="utf-8"))
        return cls(swc=state.get("swc", folder.name), folder=folder, state=state)

    @classmethod
    def list_runs(cls, *, root: Optional[Path] = None) -> list["Run"]:
        base = root or RUNS_ROOT
        if not base.is_dir():
            return []
        runs = []
        for d in sorted(base.iterdir(), reverse=True):
            if d.is_dir() and (d / STATE).is_file():
                runs.append(cls.load(d))
        return runs

    # ── persistence helpers ───────────────────────────────────────────────────
    def path(self, name: str) -> Path:
        return self.folder / name

    def save_json(self, name: str, obj: Any) -> Path:
        p = self.path(name)
        p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        return p

    def save_text(self, name: str, text: str) -> Path:
        p = self.path(name)
        p.write_text(text, encoding="utf-8")
        return p

    def read_json(self, name: str, default: Any = None) -> Any:
        p = self.path(name)
        if not p.is_file():
            return default
        return json.loads(p.read_text(encoding="utf-8"))

    def read_text(self, name: str, default: str = "") -> str:
        p = self.path(name)
        if not p.is_file():
            return default
        return p.read_text(encoding="utf-8")

    def has(self, name: str) -> bool:
        return self.path(name).is_file()

    def save_state(self, **updates: Any) -> dict[str, Any]:
        self.state.update(updates)
        self.save_json(STATE, self.state)
        return self.state
