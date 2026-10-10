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
    """Render a Mermaid diagram with zoom / pan controls (CDN mermaid.js + svg-pan-zoom).

    Mouse wheel zooms, dragging pans, double-click resets; the toolbar has + / − / Fit /
    100% / Fullscreen / Download SVG. The diagram text is HTML-escaped and rendered with
    ``securityLevel:'strict'`` so LLM text (which may contain ``<``/``>`` or markup) can't
    inject HTML.

    Streamlit loads inactive tabs/expanders at width 0, which collapses Mermaid's layout
    (a 16x16 SVG), so rendering waits until the frame has a real width.
    """
    import html
    import streamlit as st
    safe = html.escape(mmd)
    box = max(height - 36, 120)
    st.components.v1.html(
        f"""
        <style>
          body {{ margin:0; font-family:sans-serif; }}
          #bar {{ display:flex; gap:4px; padding:2px 0 4px 0; }}
          #bar button {{ border:1px solid #c8c8d0; background:#f6f6fa; border-radius:4px;
                         padding:1px 8px; cursor:pointer; font-size:12px; }}
          #bar button:hover {{ background:#e6e6f0; }}
          #wrap {{ height:{box}px; border:1px solid #e3e3ea; border-radius:4px; overflow:hidden;
                   background:#fff; }}
          #wrap svg {{ width:100%; height:100%; max-width:none !important; cursor:grab; }}
          pre.mermaid {{ margin:0; height:100%; font-size:12px; white-space:pre-wrap; }}
        </style>
        <div id="bar">
          <button id="zin" title="Zoom in">+</button><button id="zout" title="Zoom out">&minus;</button>
          <button id="fit" title="Fit to window">Fit</button><button id="one" title="Actual size">100%</button>
          <button id="full" title="Fullscreen">&#x26F6;</button><button id="dl" title="Download SVG">SVG</button>
        </div>
        <div id="wrap"><pre class="mermaid">{safe}</pre></div>
        <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{ startOnLoad: false, securityLevel: 'strict',
                               flowchart: {{ useMaxWidth: false }} }});
          let pz = null;
          const render = async () => {{
            await mermaid.run({{ querySelector: '.mermaid' }});
            const svg = document.querySelector('#wrap svg');
            if (!svg || !window.svgPanZoom) return;
            svg.removeAttribute('height'); svg.removeAttribute('width');
            pz = window.svgPanZoom(svg, {{ zoomEnabled: true, panEnabled: true, fit: true, center: true,
                                          minZoom: 0.1, maxZoom: 30, dblClickZoomEnabled: false,
                                          controlIconsEnabled: false }});
            svg.addEventListener('dblclick', () => {{ pz.resize(); pz.fit(); pz.center(); }});
            const on = (id, fn) => document.getElementById(id).addEventListener('click', fn);
            on('zin', () => pz.zoomIn()); on('zout', () => pz.zoomOut());
            on('fit', () => {{ pz.resize(); pz.fit(); pz.center(); }});
            on('one', () => {{ pz.resetZoom(); pz.center(); }});
            on('full', () => {{ const el = document.documentElement;
              (document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen?.()); }});
            on('dl', () => {{
              const blob = new Blob([new XMLSerializer().serializeToString(svg)], {{ type: 'image/svg+xml' }});
              const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
              a.download = 'diagram.svg'; a.click(); URL.revokeObjectURL(a.href); }});
            document.addEventListener('fullscreenchange', () => {{
              document.getElementById('wrap').style.height =
                document.fullscreenElement ? (window.innerHeight - 40) + 'px' : '{box}px';
              pz.resize(); pz.fit(); pz.center(); }});
          }};
          let started = false;
          const timer = setInterval(() => {{
            if (!started && document.documentElement.clientWidth > 50) {{
              started = true; clearInterval(timer); render();
            }}
          }}, 250);
        </script>
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
