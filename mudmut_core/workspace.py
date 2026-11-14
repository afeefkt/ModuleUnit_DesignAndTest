"""Persistent run workspace — outputs/<run>/.

Each pipeline run lives under ``outputs/<YYYYMMDD_HHMMSS>_<SWC>_<preset>/`` with
per-stage subfolders, and ``outputs/LATEST`` names the most recent run.
"""

from __future__ import annotations

import json
import os
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
ARCHIVE = "_archive"

# Stage subfolders (order = pipeline order).
SECTIONS = {
    "input": "00_input",
    "mud": "01_mud",
    "code": "02_code",
    "mut": "03_mut",
    "trace": "04_trace",
}


def _load_json(path: Path, default: Any) -> Any:
    """``path`` parsed as JSON; ``default`` when it is missing, unreadable or not valid JSON.

    One damaged file (a run killed while writing, a hand edit) must not break every page
    that lists runs.
    """
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _pid_alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


@dataclass
class Run:
    """A single MUD → MUT pipeline run, backed by a folder on disk."""

    swc: str
    folder: Path
    preset: str = "local"
    state: dict[str, Any] = field(default_factory=dict)
    damaged: str = ""   # why state.json could not be read ("" = fine)

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
    def open_named(cls, name: str, *, swc: str = "", preset: str = "agent",
                   root: Optional[Path] = None) -> "Run":
        """Open (creating if needed) a run folder with a caller-chosen name.

        Used by the agent CLI, whose run ids come from the agent. The folder gets
        the same numbered sections and ``state.json`` as a chain run, so it is
        listed in Runs & Reports.
        """
        base = root or RUNS_ROOT
        folder = base / name
        is_new = not (folder / STATE).is_file()
        for sub in SECTIONS.values():
            (folder / sub).mkdir(parents=True, exist_ok=True)
        run = cls.load(folder)
        if is_new:
            run.swc = swc or name
            run.preset = preset
            run.state = {"swc": run.swc, "preset": preset,
                         "created": datetime.now().strftime("%Y%m%d_%H%M%S")}
            run.save_state()
        elif swc and run.swc != swc:
            run.swc = swc
            run.save_state(swc=swc)
        run.mark_latest()
        return run

    @classmethod
    def load(cls, folder: Path | str) -> "Run":
        folder = Path(folder)
        state: dict[str, Any] = {}
        damaged = ""
        state_path = folder / STATE
        if state_path.is_file():
            loaded = _load_json(state_path, None)
            if isinstance(loaded, dict):
                state = loaded
            else:
                damaged = f"{STATE} is not readable JSON"
        return cls(
            swc=state.get("swc", folder.name),
            folder=folder,
            preset=state.get("preset", "local"),
            state=state,
            damaged=damaged,
        )

    @classmethod
    def list_runs(cls, *, root: Optional[Path] = None) -> list["Run"]:
        base = root or RUNS_ROOT
        if not base.is_dir():
            return []
        runs = [cls.load(d) for d in base.iterdir() if d.is_dir() and (d / STATE).is_file()]
        # Newest first by creation time — not by folder name, so agent runs with
        # free-form names (e.g. "eps") do not sort above newer dated runs.
        runs.sort(key=lambda r: (r.created_key, r.folder.name), reverse=True)
        return runs

    @property
    def created_key(self) -> str:
        """Sortable creation stamp (``YYYYMMDD_HHMMSS``): from state.json, else the folder time."""
        stamp = str(self.state.get("created") or "")
        if stamp:
            return stamp
        try:
            return datetime.fromtimestamp((self.folder / STATE).stat().st_mtime).strftime("%Y%m%d_%H%M%S")
        except OSError:
            return ""

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

    # ── archive (tidy the run list without deleting anything) ────────────────
    def archive(self) -> Path:
        """Move this run to ``outputs/_archive/`` (restorable) and repoint ``LATEST``."""
        import shutil
        base = self.folder.parent
        target_dir = base / ARCHIVE
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / self.folder.name
        n = 1
        while target.exists():
            n += 1
            target = target_dir / f"{self.folder.name}__{n}"
        shutil.move(str(self.folder), str(target))
        remaining = Run.list_runs(root=base)
        marker = base / LATEST
        if remaining:
            marker.write_text(remaining[0].folder.name, encoding="utf-8")
        elif marker.exists():
            marker.unlink()
        return target

    @classmethod
    def list_archived(cls, *, root: Optional[Path] = None) -> list["Run"]:
        base = (root or RUNS_ROOT) / ARCHIVE
        if not base.is_dir():
            return []
        runs = [cls.load(d) for d in base.iterdir() if d.is_dir() and (d / STATE).is_file()]
        runs.sort(key=lambda r: (r.created_key, r.folder.name), reverse=True)
        return runs

    @classmethod
    def restore_archived(cls, name: str, *, root: Optional[Path] = None) -> "Run":
        """Move an archived run back into ``outputs/`` (refuses to overwrite)."""
        import shutil
        base = root or RUNS_ROOT
        src = base / ARCHIVE / name
        if not (src / STATE).is_file():
            raise FileNotFoundError(f"no archived run '{name}'")
        head, _, tail = name.rpartition("__")
        dest = base / (head if head and tail.isdigit() else name)   # drop the "__2" added on a name clash
        if dest.exists():
            raise FileExistsError(f"a run named '{dest.name}' already exists")
        shutil.move(str(src), str(dest))
        return cls.load(dest)

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
        return _load_json(self.dir(section) / name, default)

    # ── run-level persistence helpers ─────────────────────────────────────────
    def path(self, name: str) -> Path:
        return self.folder / name

    def save_json(self, name: str, obj: Any) -> Path:
        # Write-then-rename: a run killed mid-write leaves the old file, not half a JSON document.
        p = self.path(name)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        tmp.replace(p)
        return p

    def save_text(self, name: str, text: str) -> Path:
        p = self.path(name)
        p.write_text(text, encoding="utf-8")
        return p

    def read_json(self, name: str, default: Any = None) -> Any:
        return _load_json(self.path(name), default)

    def read_text(self, name: str, default: str = "") -> str:
        p = self.path(name)
        if not p.is_file():
            return default
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return default

    def has(self, name: str) -> bool:
        return self.path(name).is_file()

    def save_state(self, **updates: Any) -> dict[str, Any]:
        self.state.update(updates)
        self.save_json(STATE, self.state)
        return self.state

    # ── run status (running / done / failed / cancelled / interrupted) ────────
    def mark_running(self) -> None:
        """Record that a process is working on this run, so a crash or restart can be detected."""
        self.save_state(status="running", pid=os.getpid())

    def mark_finished(self, status: str) -> None:
        self.save_state(status=status, pid=None)

    @property
    def status(self) -> str:
        """``running`` / ``done`` / ``failed`` / ``cancelled`` / ``interrupted`` / ``""`` (unknown, older runs).

        ``interrupted``: the state says running but the process that ran it is gone (server
        restart, crash, killed terminal) — the folder holds only part of the results.
        """
        status = str(self.state.get("status") or "")
        if status == "running" and not _pid_alive(self.state.get("pid")):
            return "interrupted"
        return status
