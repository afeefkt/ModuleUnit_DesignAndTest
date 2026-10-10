"""Native (no-Docker) test execution for the optional FastAPI backend.

A thin wrapper over ``mudmut_core.verify`` so ``api/test_runner.py`` builds and
runs CppUTest tests directly on the host (or via WSL on Windows) instead of
``docker exec``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

_REPO_ROOT = Path(__file__).resolve().parents[4]


def run_tests(test_dir: Path | str) -> Dict:
    """Build and run CppUTest tests in ``test_dir`` and return a result dict."""
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from mudmut_core import verify
    return verify.build_and_run(Path(test_dir))


def fix_loop(test_dir: Path | str, max_attempts: int = 2) -> Dict:
    """Build, run, and repair failing test files (same signature as verify.fix_loop)."""
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from mudmut_core import verify
    return verify.fix_loop(Path(test_dir), max_attempts=max_attempts)
