# MUD Tool Test Strategy

This suite is pytest-based and split into three practical tiers:

- `unit`: deterministic tests for models, importers, exporters, validators, prompt contracts, pipeline repair logic, and API routes with mocked dependencies.
- `integration`: local multi-module tests that exercise file, FastAPI, or pipeline boundaries without requiring a live AI server.
- `live`: opt-in tests that require a running sidecar and/or local model backend.

## Standard Commands

From `python-sidecar`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -k "not live"
.\.venv\Scripts\python.exe -m pytest tests -q --cov=mudtool --cov-report=term-missing -k "not live"
.\.venv\Scripts\python.exe -m pytest tests -q
```

From the repository root:

```powershell
.\run_tests.bat
.\run_tests.bat live
```

## Graph-Informed Coverage

`graphify-out/graph.json` is used by `tests/unit/test_framework_contract.py` to classify the most central Python modules. A central module must be either:

- `covered`, with at least one existing test file listed, or
- `planned`, with an explicit reason.

This does not replace coverage metrics. It makes architectural gaps visible, especially for highly connected modules such as API routes, orchestration, activity pipeline stages, exporters, validators, and backend adapters.

## Current Known Gaps

The framework is good enough to catch many regressions, but not yet enough to claim full product coverage. Planned gaps include mocked tests for `cloud_backend.py`, `local_backend.py`, `visual_qa.py`, `guidelines_reader.py`, `render_service.py`, `xmi_exporter.py`, `consistency_validator.py`, and deeper `mud_spec_generator.py` flows.
