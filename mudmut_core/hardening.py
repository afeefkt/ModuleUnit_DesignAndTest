"""Bridge to the requirements hardening tool (``requirements_hardening/``) for the web UI.

Hardening turns a raw requirement export into a reviewable baseline (acceptance criteria,
verification methods, trace, test design, review packet). It is deterministic and does not
change the original file. Runs land in ``outputs/req_hardening/<time>_<set>/`` and the hardened
baseline in ``inputs/requirements_hardened/<set>/``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from mudmut_core.env import REPO_ROOT

TOOL_DIR = REPO_ROOT / "requirements_hardening"
RUNS_DIR = REPO_ROOT / "outputs" / "req_hardening"
HARDENED_DIR = REPO_ROOT / "inputs" / "requirements_hardened"

# Default input per set (from requirements_hardening/README.md); any file can be chosen instead.
DEFAULT_INPUTS = {
    "aeb": "inputs/requirements/aeb/aeb_requirements.csv",
    "bms": "inputs/requirements/samples/bms_requirements.csv",
    "eps": "inputs/requirements/samples/eps_requirements.csv",
    "foc": "inputs/requirements/samples/Motcontrolcomp.csv",
}


def available() -> bool:
    return (TOOL_DIR / "cli.py").is_file()


def list_sets() -> list[str]:
    """Requirement sets the tool has curated data for (``data/<set>_*.json``)."""
    data = TOOL_DIR / "data"
    if not data.is_dir():
        return []
    return sorted({p.name.split("_", 1)[0] for p in data.glob("*_*.json")})


def default_input(set_name: str) -> str:
    rel = DEFAULT_INPUTS.get(set_name, "")
    return rel if rel and (REPO_ROOT / rel).is_file() else ""


def run(input_path: str | Path, set_name: str) -> dict[str, Any]:
    """Run the full ingest → audit → author → review → export flow; returns the run manifest."""
    if not available():
        raise RuntimeError("requirements_hardening/ is not in this checkout")
    from requirements_hardening.cli import run as _run
    path = Path(input_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"requirement file not found: {path}")
    # Absolute roots: never chdir (the web server runs several threads in one process).
    return _run(str(path), set_name, str(RUNS_DIR), str(HARDENED_DIR))


def list_runs() -> list[dict[str, Any]]:
    """Newest-first hardening runs with their manifest (``run.json``)."""
    if not RUNS_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for d in sorted((p for p in RUNS_DIR.iterdir() if p.is_dir()), reverse=True):
        manifest = d / "run.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        data["folder"] = d
        out.append(data)
    return out


def resolve(path: Optional[str]) -> Optional[Path]:
    """A manifest path (repo-relative or absolute) as an absolute Path, if it exists."""
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p if p.exists() else None


def hardened_csv(manifest: dict[str, Any]) -> Optional[Path]:
    """The hardened CSV a run produced (the input for the MUD_MUT pipeline)."""
    return resolve((manifest.get("paths") or {}).get("hardened_csv"))
