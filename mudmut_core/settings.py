"""User-level build settings (``config/settings.json``, git-ignored).

Currently: where CppUTest lives. Empty means "auto-detect". The environment
variable ``MUDMUT_CPPUTEST_HOME`` overrides the file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mudmut_core import env

SETTINGS_FILE = env.REPO_ROOT / "config" / "settings.json"

DEFAULTS: dict[str, Any] = {
    "cpputest_home": "",   # folder holding include/CppUTest and lib*/libCppUTest.*
    "extra_cflags": "",    # appended to CFLAGS/CXXFLAGS in the generated Makefile
}


def get_settings() -> dict[str, Any]:
    data = dict(DEFAULTS)
    try:
        if SETTINGS_FILE.is_file():
            loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    override = os.environ.get("MUDMUT_CPPUTEST_HOME", "").strip()
    if override:
        data["cpputest_home"] = override
    return data


def save_settings(**values: Any) -> dict[str, Any]:
    """Merge ``values`` into the stored settings and write them atomically."""
    # Persist the file's own value, not the env override.
    try:
        stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.is_file() else {}
    except (OSError, ValueError):
        stored = {}
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in stored.items() if k in DEFAULTS})
    merged.update({k: str(v).strip() for k, v in values.items() if k in DEFAULTS})
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    tmp.replace(SETTINGS_FILE)
    return get_settings()
