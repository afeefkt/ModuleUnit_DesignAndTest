"""
HTML Test Report Generator
Generates beautiful HTML reports from CppUTest results
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def generate_html_report(
    test_result: Dict,
    test_directory: str,
    project_path: Optional[str] = None
) -> str:
    """
    Generate an HTML report from test execution results

    Args:
        test_result: Dictionary with test execution results
        test_directory: Name of the test directory
        project_path: Optional path to the source project

    Returns:
        HTML content as string
    """

    status = test_result.get("status", "unknown")
    build_output = test_result.get("build_output", "")
    build_error = test_result.get("build_error", "")
    test_output = test_result.get("test_output", "")
    test_error = test_result.get("test_error", "")
    exit_code = test_result.get("exit_code", -1)

    # Parse test results
    passed_tests = 0
    total_tests = 0
    total_checks = 0

    if status == "passed" and test_output:
        # Parse CppUTest output: "OK (4 tests, 4 ran, 4 checks, 0 ignored, 0 filtered out, 0 ms)"
        import re
        match = re.search(r'OK \((\d+) tests?, (\d+) ran, (\d+) checks?', test_output)
        if match:
            total_tests = int(match.group(1))
            passed_tests = int(match.group(2))
            total_checks = int(match.group(3))

    # Determine status color and icon (using darker, muted earth tones)
    if status == "passed":
        status_color = "#6b7d5c"  # Dark olive green (muted, earthy)
        status_icon = "✓"
        status_text = "PASSED"
    elif status == "build_failed":
        status_color = "#8b5a5a"  # Dark burgundy/brown-red (muted)
        status_icon = "✗"
        status_text = "BUILD FAILED"
    elif status == "test_failed":
        status_color = "#9a7545"  # Dark rust/brown-orange (muted)
        status_icon = "⚠"
        status_text = "TESTS FAILED"
    else:
        status_color = "#6b7280"  # Medium grey (unchanged)
        status_icon = "?"
        status_text = "UNKNOWN"

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CppUTest Report - {test_directory}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #e5e7eb;
            padding: 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #fafafa;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            overflow: hidden;
            border: 1px solid #d1d5db;
        }}

        .header {{
            background: #374151;
            color: white;
            padding: 40px;
            text-align: center;
            border-bottom: 3px solid #4b5563;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .status-banner {{
            background: {status_color};
            color: white;
            padding: 30px;
            text-align: center;
            font-size: 2em;
            font-weight: bold;
            letter-spacing: 2px;
        }}

        .status-banner .icon {{
            font-size: 1.5em;
            margin-right: 15px;
        }}

        .content {{
            padding: 40px;
        }}

        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .info-card {{
            background: #f3f4f6;
            border: 2px solid #d1d5db;
            border-radius: 12px;
            padding: 20px;
        }}

        .info-card .label {{
            color: #6b7280;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .info-card .value {{
            color: #1f2937;
            font-size: 1.5em;
            font-weight: bold;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: #d1d5db;
            color: #1f2937;
            border-radius: 8px;
            padding: 25px;
            text-align: center;
            border: 2px solid #9ca3af;
        }}

        .stat-card.success {{
            background: #e5e7eb;
            border-color: #b8bcc3;
        }}

        .stat-card.warning {{
            background: #c7cbd1;
            border-color: #9ca3af;
        }}

        .stat-card .number {{
            font-size: 3em;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .stat-card .label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}

        .section {{
            margin-bottom: 30px;
        }}

        .section-title {{
            font-size: 1.5em;
            color: #374151;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 3px solid #9ca3af;
        }}

        .output-box {{
            background: #1e293b;
            color: #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            line-height: 1.6;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        .output-box.success {{
            background: #3d4a3d;
            color: #c5d4b8;
        }}

        .output-box.error {{
            background: #5a3d3d;
            color: #ddc5c5;
        }}

        .empty {{
            color: #94a3b8;
            font-style: italic;
            text-align: center;
            padding: 20px;
        }}

        .footer {{
            background: #e5e7eb;
            padding: 20px;
            text-align: center;
            color: #6b7280;
            font-size: 0.9em;
            border-top: 2px solid #9ca3af;
        }}

        .footer a {{
            color: #374151;
            text-decoration: none;
            font-weight: 600;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 CppUTest Report</h1>
            <div class="subtitle">Automated Unit Test Results</div>
        </div>

        <div class="status-banner">
            <span class="icon">{status_icon}</span>
            {status_text}
        </div>

        <div class="content">
            <div class="info-grid">
                <div class="info-card">
                    <div class="label">Test Directory</div>
                    <div class="value">{test_directory}</div>
                </div>
                <div class="info-card">
                    <div class="label">Generated</div>
                    <div class="value">{timestamp}</div>
                </div>
                <div class="info-card">
                    <div class="label">Exit Code</div>
                    <div class="value">{exit_code}</div>
                </div>
"""

    if project_path:
        html += f"""
                <div class="info-card">
                    <div class="label">Source Project</div>
                    <div class="value">{project_path}</div>
                </div>
"""

    html += """
            </div>
"""

    # Add statistics if tests passed
    if status == "passed" and total_tests > 0:
        html += f"""
            <div class="stats-grid">
                <div class="stat-card success">
                    <div class="number">{total_tests}</div>
                    <div class="label">Total Tests</div>
                </div>
                <div class="stat-card success">
                    <div class="number">{passed_tests}</div>
                    <div class="label">Tests Passed</div>
                </div>
                <div class="stat-card success">
                    <div class="number">{total_checks}</div>
                    <div class="label">Assertions</div>
                </div>
            </div>
"""

    # Build output section
    html += """
            <div class="section">
                <h2 class="section-title">Build Output</h2>
"""

    if build_output:
        html += f"""
                <div class="output-box{'success' if status == 'passed' else ''}">{build_output}</div>
"""
    else:
        html += """
                <div class="empty">No build output available</div>
"""

    html += """
            </div>
"""

    # Build errors section (if any)
    if build_error:
        html += f"""
            <div class="section">
                <h2 class="section-title">Build Errors</h2>
                <div class="output-box error">{build_error}</div>
            </div>
"""

    # Test output section
    if status == "passed" or status == "test_failed":
        html += """
            <div class="section">
                <h2 class="section-title">Test Execution Results</h2>
"""

        if test_output:
            html += f"""
                <div class="output-box{'success' if status == 'passed' else 'error'}">{test_output}</div>
"""
        else:
            html += """
                <div class="empty">No test output available</div>
"""

        html += """
            </div>
"""

    # Test errors section (if any)
    if test_error:
        html += f"""
            <div class="section">
                <h2 class="section-title">Test Errors</h2>
                <div class="output-box error">{test_error}</div>
            </div>
"""

    # Footer
    html += f"""
        </div>

        <div class="footer">
            Generated by <a href="https://github.com/anthropics/claude-code" target="_blank">CppUTest RAG Generator</a>
            powered by Claude Code
        </div>
    </div>
</body>
</html>
"""

    return html
