from __future__ import annotations

from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[2] / "src" / "mudtool" / "web" / "templates" / "index.html"


def test_generation_quality_ui_keeps_main_canvas_clean():
    html = TEMPLATE.read_text(encoding="utf-8")

    assert "function generationSummaryText(summary)" in html
    assert "function renderGenerationDiagnostics(data, diagIssues)" in html
    assert '<details id="generationDiagnostics"' in html
    assert "Warning:</span>" not in html
    assert "Error:</span>" not in html
    assert "canvas.insertAdjacentHTML('afterbegin',\n          `<div id=\"genErrors\"" not in html
    assert "(event.errors || []).forEach" not in html
    assert "(event.warnings || []).forEach" not in html


def test_generation_quality_ui_uses_compact_status_from_summary():
    html = TEMPLATE.read_text(encoding="utf-8")

    assert "const compactSummary = generationSummaryText(generationSummary);" in html
    assert "Generated ${generated}/${planned} diagrams" in html
    assert "quality needs fix" in html
    assert "quality passed" in html
    assert "generation failed" in html


def test_mud_spec_pseudocode_blocks_are_readable_light_theme():
    html = TEMPLATE.read_text(encoding="utf-8")

    assert "#mudSpecContent pre code" in html
    assert "background: transparent;" in html
    assert "background:#f8fafc;color:#0f172a;border:1px solid #cbd5e1" in html
    assert "white-space:pre-wrap" in html
    assert "background:#1e293b;color:#e2e8f0" not in html
