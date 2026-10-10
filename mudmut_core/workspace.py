"""Persistent run workspace — outputs/<run>/.

Each pipeline run lives under ``outputs/<YYYYMMDD_HHMMSS>_<SWC>_<preset>/`` with
per-stage subfolders, and ``outputs/LATEST`` names the most recent run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mudmut_core.env import REPO_ROOT

RUNS_ROOT = REPO_ROOT / "outputs"
LATEST = "LATEST"
RUN_REPORT = "RUN_REPORT.md"
RUN_JSON = "run.json"
STATE = "state.json"

# Stage subfolders (order = pipeline order).
SECTIONS = {
    "input": "00_input",
    "mud": "01_mud",
    "code": "02_code",
    "mut": "03_mut",
    "trace": "04_trace",
}


@dataclass
class Run:
    """A single MUD → MUT pipeline run, backed by a folder on disk."""

    swc: str
    folder: Path
    preset: str = "local"
    state: dict[str, Any] = field(default_factory=dict)

    # ── construction ──────────────────────────────────────────────────────────
    @classmethod
    def create(cls, swc: str, *, preset: str = "local", root: Optional[Path] = None) -> "Run":
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if (c.isalnum() or c in "_-") else "_" for c in swc)
        safe_preset = "".join(c if (c.isalnum() or c in "_-") else "_" for c in preset)
        base = root or RUNS_ROOT
        base.mkdir(parents=True, exist_ok=True)
        folder = base / f"{stamp}_{safe}_{safe_preset}"
        folder.mkdir(parents=True, exist_ok=True)
        for sub in SECTIONS.values():
            (folder / sub).mkdir(parents=True, exist_ok=True)
        run = cls(swc=swc, folder=folder, preset=preset,
                  state={"swc": swc, "preset": preset, "created": stamp})
        run.save_state()
        run.mark_latest()
        return run

    @classmethod
    def load(cls, folder: Path | str) -> "Run":
        folder = Path(folder)
        state = {}
        state_path = folder / STATE
        if state_path.is_file():
            state = json.loads(state_path.read_text(encoding="utf-8"))
        return cls(
            swc=state.get("swc", folder.name),
            folder=folder,
            preset=state.get("preset", "local"),
            state=state,
        )

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

    @classmethod
    def latest(cls, *, root: Optional[Path] = None) -> Optional["Run"]:
        base = root or RUNS_ROOT
        marker = base / LATEST
        if not marker.is_file():
            return None
        name = marker.read_text(encoding="utf-8").strip()
        folder = base / name
        if folder.is_dir():
            return cls.load(folder)
        return None

    def mark_latest(self) -> None:
        marker = self.folder.parent / LATEST
        marker.write_text(self.folder.name, encoding="utf-8")

    # ── section helpers ───────────────────────────────────────────────────────
    def dir(self, section: str) -> Path:
        """Path to a stage subfolder (``input`` / ``mud`` / ``code`` / ``mut`` / ``trace``)."""
        return self.folder / SECTIONS[section]

    def save_in(self, section: str, name: str, text: str) -> Path:
        p = self.dir(section) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def save_json_in(self, section: str, name: str, obj: Any) -> Path:
        return self.save_in(section, name, json.dumps(obj, indent=2, default=str))

    def read_in(self, section: str, name: str, default: str = "") -> str:
        p = self.dir(section) / name
        return p.read_text(encoding="utf-8") if p.is_file() else default

    def read_json_in(self, section: str, name: str, default: Any = None) -> Any:
        p = self.dir(section) / name
        if not p.is_file():
            return default
        return json.loads(p.read_text(encoding="utf-8"))

    # ── run-level persistence helpers ─────────────────────────────────────────
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
