"""Test bootstrap for the agentic spike.

Makes both ``mudmut_cli`` (agentic/tools) and ``mudtool`` (the existing library)
importable without requiring a pip install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]   # agentic/tests → agentic → repo root
_TOOLS = _REPO / "agentic" / "tools"
_SRC = _REPO / "mud-tool" / "python-sidecar" / "src"

for _p in (_TOOLS, _SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
