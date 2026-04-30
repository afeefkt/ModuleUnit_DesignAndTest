from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SIDECAR_ROOT = REPO_ROOT / "python-sidecar"
GRAPH_PATH = REPO_ROOT / "graphify-out" / "graph.json"


# Graphify identifies these as central source files. Each one must be classified
# so test gaps are visible and intentional instead of quietly forgotten.
GRAPH_COVERAGE_MANIFEST = {
    "python-sidecar\\src\\mudtool\\api\\routes.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_api_routes.py"],
    },
    "python-sidecar\\src\\mudtool\\ai\\orchestrator.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/test_activity_pipeline.py"],
    },
    "python-sidecar\\src\\mudtool\\generator\\autosar_mapper.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_autosar_mapper.py"],
    },
    "python-sidecar\\src\\mudtool\\ai\\pipeline.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/test_activity_pipeline.py"],
    },
    "python-sidecar\\src\\mudtool\\ai\\mud_activity_context.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_mud_activity_context.py"],
    },
    "python-sidecar\\src\\mudtool\\validation\\autosar_validator.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_validation.py"],
    },
    "python-sidecar\\src\\mudtool\\traceability\\store.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_traceability.py"],
    },
    "python-sidecar\\src\\mudtool\\ai\\visual_qa.py": {
        "status": "planned",
        "reason": "Needs mocked render and vision backend tests.",
    },
    "python-sidecar\\src\\mudtool\\generator\\drawio_exporter.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_exporters.py"],
    },
    "python-sidecar\\src\\mudtool\\validation\\structural_validator.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_validation.py"],
    },
    "python-sidecar\\src\\mudtool\\importers\\base.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_importers.py"],
    },
    "python-sidecar\\src\\mudtool\\generator\\xmi_exporter.py": {
        "status": "planned",
        "reason": "Needs XMI snapshot/structure tests.",
    },
    "python-sidecar\\src\\mudtool\\ai\\activity_pipeline_stages.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_activity_pipeline_cfg.py"],
    },
    "python-sidecar\\src\\mudtool\\ai\\module_planner.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_module_planner.py"],
    },
    "python-sidecar\\src\\mudtool\\ai\\cloud_backend.py": {
        "status": "planned",
        "reason": "Needs httpx MockTransport tests for errors, JSON mode, and Ollama 404 retry.",
    },
    "python-sidecar\\src\\mudtool\\ai\\chunked_elaborator.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/test_elaborator_enhanced.py"],
    },
    "python-sidecar\\src\\mudtool\\models\\json_uml.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_models.py"],
    },
    "python-sidecar\\src\\mudtool\\ai\\prompt_engine.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_prompt_profiles.py"],
    },
    "python-sidecar\\src\\mudtool\\validation\\consistency_validator.py": {
        "status": "planned",
        "reason": "Needs requirement-to-diagram consistency edge-case tests.",
    },
    "python-sidecar\\src\\mudtool\\ai\\guidelines_reader.py": {
        "status": "planned",
        "reason": "Needs parser/cache/RAG fallback tests with temporary guideline files.",
    },
    "python-sidecar\\src\\mudtool\\generator\\render_service.py": {
        "status": "planned",
        "reason": "Needs mocked Kroki/PlantUML rendering tests.",
    },
    "python-sidecar\\src\\mudtool\\ai\\elaborator.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/test_elaborator_enhanced.py"],
    },
    "python-sidecar\\src\\mudtool\\ai\\mud_spec_generator.py": {
        "status": "planned",
        "reason": "Needs deterministic backend tests for Section 7 and markdown assembly.",
    },
    "python-sidecar\\src\\mudtool\\models\\autosar.py": {
        "status": "covered",
        "tests": ["python-sidecar/tests/unit/test_models.py"],
    },
    "python-sidecar\\src\\mudtool\\generator\\mermaid_exporter.py": {
        "status": "covered",
        "tests": [
            "python-sidecar/tests/unit/test_exporters.py",
            "python-sidecar/tests/unit/test_mermaid_exporter_preview.py",
        ],
    },
}


def _top_graph_source_files(limit: int = 25) -> list[str]:
    if not GRAPH_PATH.exists():
        pytest.skip("graphify-out/graph.json is not available")

    with GRAPH_PATH.open(encoding="utf-8") as handle:
        graph = json.load(handle)

    edge_counts = Counter()
    for edge in graph.get("links", []):
        source_file = str(edge.get("source_file") or "")
        if source_file.startswith("python-sidecar\\src\\mudtool\\") and source_file.endswith(".py"):
            edge_counts[source_file] += 1
    return [source_file for source_file, _ in edge_counts.most_common(limit)]


def test_graph_central_modules_are_classified_in_test_manifest():
    missing = [
        source_file
        for source_file in _top_graph_source_files()
        if source_file not in GRAPH_COVERAGE_MANIFEST
    ]

    assert missing == []


def test_manifest_covered_entries_point_to_existing_tests():
    missing_tests = []
    for entry in GRAPH_COVERAGE_MANIFEST.values():
        if entry["status"] != "covered":
            continue
        for test_path in entry.get("tests", []):
            if not (REPO_ROOT / test_path).exists():
                missing_tests.append(test_path)

    assert missing_tests == []


def test_python_sources_and_tests_parse_cleanly():
    syntax_errors = []
    for root in (SIDECAR_ROOT / "src" / "mudtool", SIDECAR_ROOT / "tests"):
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                syntax_errors.append(f"{path.relative_to(REPO_ROOT)}:{exc.lineno}: {exc.msg}")

    assert syntax_errors == []
