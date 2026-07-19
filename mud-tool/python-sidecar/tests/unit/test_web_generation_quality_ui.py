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


def test_mud_spec_regeneration_keeps_post_review_and_status_counts():
    html = TEMPLATE.read_text(encoding="utf-8")

    assert "postReview = ev.post_review || null;" in html
    assert "remainingIssueCount = ev.remaining_issue_count || 0;" in html
    assert "resolvedIssueCount = ev.resolved_issue_count || 0;" in html
    assert "retryCount = ev.retry_count || 0;" in html
    assert "regenQualityStatus = ev.quality_status || regenQualityStatus;" in html
    assert "state.mudReview = postReview;" in html
    assert "renderReviewResults(postReview);" in html
    assert "Regenerated - resolved ${resolvedIssueCount}, remaining ${remainingIssueCount}" in html
    assert "state.mudReview = null; // clear stale review" not in html


def test_generation_stream_reports_valid_error_event_message():
    html = TEMPLATE.read_text(encoding="utf-8")

    assert "let data;" in html
    assert "data = JSON.parse(line.slice(6));" in html
    assert "throw new Error(data.message || 'Generation failed');" in html
    assert "Invalid error-event JSON: ${parseErr.message}`" in html
    assert "throw new Error(`Invalid error-event JSON: ${parseErr.message}`);\n                }\n                if (parseErr.message" in html


def test_left_sidebar_actions_use_remaining_viewport_height():
    html = TEMPLATE.read_text(encoding="utf-8")

    assert ".sidebar-actions" in html
    assert "flex: 1 1 auto;" in html
    assert "min-height: 0;" in html
    assert '<div class="sidebar-actions border-t border-slate-100">' in html
    assert 'style="max-height:320px"' not in html
