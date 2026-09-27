"""Path confinement for request-supplied names.

Every project / test-directory / file name that arrives over HTTP is resolved
here and must land inside the configured root (C_PROJECT_DIR or OUTPUT_DIR).
The backend can drive Docker, so an unchecked ``../`` or absolute path would
let a request read, analyse or execute anything on the machine.
"""

import re
from pathlib import Path

from fastapi import HTTPException

from app.config import config

# A single path segment: no separators, no "..", no shell metacharacters.
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$")


def safe_name(name: str, what: str = "name") -> str:
    """Validate a single directory/file name segment."""
    name = (name or "").strip()
    if not _SAFE_NAME_RE.fullmatch(name) or ".." in name:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {what} {name!r}: use letters, digits, '_', '-', '.' only",
        )
    return name


def within(root: Path, candidate: Path) -> bool:
    """True if ``candidate`` resolves to ``root`` itself or somewhere below it."""
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_project_dir(project_path: str) -> Path:
    """Resolve a project reference to a directory inside C_PROJECT_DIR.

    Accepts a bare project name (``SWC_Foo``), a path relative to the working
    directory (``./c_projects/SWC_Foo``) or an absolute path — as long as it
    ends up inside C_PROJECT_DIR.
    """
    root = config.C_PROJECT_DIR
    raw = (project_path or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="project_path is required")

    given = Path(raw)
    candidates = [given] if given.is_absolute() else [root / given, Path.cwd() / given]
    # Legacy behaviour: fall back to the last segment under C_PROJECT_DIR
    candidates.append(root / given.name)

    for cand in candidates:
        if cand.is_dir() and within(root, cand):
            return cand.resolve()

    if any(cand.exists() for cand in candidates[:-1]):
        raise HTTPException(
            status_code=403,
            detail=f"Project path must be inside {root}",
        )
    raise HTTPException(status_code=404, detail=f"Project not found in {root}: {raw}")


def resolve_test_dir(test_directory: str) -> Path:
    """Resolve a generated-tests directory name to a directory inside OUTPUT_DIR."""
    name = safe_name(Path((test_directory or "").strip()).name, "test_directory")
    test_dir = config.OUTPUT_DIR / name
    if not test_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Test directory not found: {name}")
    return test_dir


def resolve_file_within(root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``root``, rejecting anything that escapes it."""
    target = root / (relative or "")
    if not within(root, target):
        raise HTTPException(status_code=403, detail="Path escapes the allowed directory")
    return target
