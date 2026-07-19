"""Web UI FastAPI router.

Serves the built-in browser dashboard at GET /.
All diagram data is fetched by the frontend via /api/v1/ endpoints.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

_TEMPLATE_DIR = Path(__file__).parent / "templates"

router = APIRouter(tags=["Web UI"])


def _read_template(name: str) -> str:
    """Read an HTML template file."""
    return (_TEMPLATE_DIR / name).read_text(encoding="utf-8")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def web_ui():
    """Serve the built-in MUD Tool Web UI dashboard."""
    return HTMLResponse(_read_template("index.html"))
