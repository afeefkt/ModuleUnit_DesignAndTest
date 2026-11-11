"""Render a Mermaid diagram to a PNG locally (no web service).

Priority: ``mmdc`` (mermaid-cli) on PATH, then Playwright Chromium with the repo's local
mermaid.js. When neither is available the renderer reports it, and the caller may choose to
skip the render part rather than penalise a missing tool.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_LOCAL_MERMAID_JS = Path(__file__).resolve().parents[2] / "launcher" / "static" / "vendor" / "mermaid-10.9.8.min.js"


def _mmdc_available() -> bool:
    return shutil.which("mmdc") is not None


def _playwright_available() -> bool:
    """Playwright is usable only when its Chromium binary is actually installed."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).is_file()
    except Exception:
        return False


def renderer_available() -> bool:
    return _mmdc_available() or _playwright_available()


def _render_via_mmdc(mermaid_text: str, out_path: Path) -> tuple[bool, str]:
    mmdc = shutil.which("mmdc")
    if not mmdc:
        return False, "mmdc not found"
    try:
        result = subprocess.run(
            [mmdc, "-i", "-", "-o", str(out_path), "-b", "transparent"],
            input=mermaid_text, capture_output=True, text=True, timeout=180,
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]
    if result.returncode == 0 and out_path.is_file():
        return True, ""
    return False, (result.stderr or result.stdout or "mmdc failed").strip()[:300]


def _render_via_playwright(mermaid_text: str, out_path: Path) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return False, f"playwright unavailable: {exc}"
    if not _LOCAL_MERMAID_JS.is_file():
        return False, "local mermaid.js not found"
    js = _LOCAL_MERMAID_JS.resolve().as_uri()
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<script src='{js}'></script></head><body>"
        "<div class='mermaid' style='background:white'></div></body></html>"
    )
    import html as _html
    body = _html.escape(mermaid_text)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1600, "height": 1200})
            page.set_content(html.replace("</div>", body + "</div>", 1), wait_until="networkidle")
            page.wait_for_selector("svg", timeout=30_000)
            page.screenshot(path=str(out_path), full_page=True)
            browser.close()
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]


def render_mermaid_png(mermaid_text: str, out_path: str) -> tuple[bool, str]:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if _mmdc_available():
        return _render_via_mmdc(mermaid_text, out)
    if _playwright_available():
        return _render_via_playwright(mermaid_text, out)
    return False, "renderer unavailable (install @mermaid-js/mermaid-cli or playwright)"
