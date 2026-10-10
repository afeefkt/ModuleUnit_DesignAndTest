"""Shared helpers for the Streamlit launcher pages."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mudmut_core import env, toolchain  # noqa: E402
from mudmut_core.workspace import Run  # noqa: E402


def bootstrap() -> str:
    """Configure the in-process environment and return the Ollama host."""
    return env.ollama_host()


def toolchain_report():
    try:
        return toolchain.check_toolchain()
    except Exception as exc:  # noqa: BLE001
        return None


def _get_json(url: str, timeout: int = 4):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ollama_models(url: str) -> list[str]:
    try:
        data = _get_json(f"{url}/api/tags", timeout=4)
        return [m.get("name", "?") for m in data.get("models", [])]
    except Exception:  # noqa: BLE001
        return []


def list_runs() -> list[Run]:
    return Run.list_runs()


def run_toolchain_install_hint() -> str:
    return toolchain.APT_INSTALL_CPPUTEST_LCOV


def render_mermaid(mmd: str, height: int = 500) -> None:
    """Render a Mermaid diagram via an HTML component (CDN mermaid.js).

    The diagram text is HTML-escaped and rendered with ``securityLevel:'strict'``
    so LLM text (which may contain ``<``/``>`` or markup) can't inject HTML.
    """
    import html
    import streamlit as st
    safe = html.escape(mmd)
    st.components.v1.html(
        f"""
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{ startOnLoad: false, securityLevel: 'strict' }});
          mermaid.run({{ querySelector: '.mermaid' }});
        </script>
        <pre class="mermaid" style="font-size:12px;white-space:pre-wrap">{safe}</pre>
        """,
        height=height,
    )


def run_picker(key: str = "run_selector"):
    """A selectbox over existing runs, keyed by run-folder name (stable)."""
    import streamlit as st
    runs = list_runs()
    if not runs:
        st.info("No runs yet — create one on the Design or Full Chain page.")
        return None
    by_name = {r.folder.name: r for r in runs}
    names = list(by_name.keys())
    chosen = st.selectbox(
        "Run", names,
        format_func=lambda n: f"{n}  ({by_name[n].swc})",
        key=key,
    )
    return by_name[chosen]


def run_latest():
    return Run.latest()
