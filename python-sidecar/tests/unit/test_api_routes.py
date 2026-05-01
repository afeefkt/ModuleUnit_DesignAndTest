"""API route tests covering high-value endpoint behavior and edge cases."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mudtool.api import dependencies
from mudtool.api import routes
from mudtool.ai.base_backend import AIResponse
from mudtool.importers.base import ImportResult
from mudtool.main import create_app
from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityEdge,
    ActivityNode,
    ActivityNodeType,
    GenerationResult,
)
from mudtool.models.requirements import Priority, Requirement, RequirementSet, RequirementStatus, RequirementType
from mudtool.models.validation import ValidationIssue, ValidationReport, ValidationSeverity
from mudtool.traceability.store import TraceLink


class _DummyOrchestrator:
    async def health_check(self) -> dict:
        return {"backends": {"dummy": True}}

    async def generate_diagram(self, *args, **kwargs):
        return GenerationResult()


class _DummyMapper:
    def map_generation_result(self, result):
        return result


class _DummyValidator:
    def validate(self, result, requirement_ids=None, **kwargs) -> ValidationReport:
        return ValidationReport(
            diagrams_checked=len(result.diagrams),
            elements_checked=sum(
                len(getattr(diagram, "nodes", [])) + len(getattr(diagram, "classes", []))
                for diagram in result.diagrams
            ),
            passed=True,
        )


class _DummyRenderService:
    async def render_all(self, result, output_path, fmt):
        return [Path(output_path) / f"dummy.{fmt}"]

    async def render_mermaid_to_svg(self, mermaid_text):
        return b"<svg xmlns='http://www.w3.org/2000/svg'><text x='0' y='14'>ok</text></svg>"


class _FakeTraceStore:
    def __init__(self, matrix=None, coverage=None, traces_by_requirement=None, accept_counts=None):
        self._matrix = matrix or []
        self._coverage = coverage or {}
        self._traces_by_requirement = traces_by_requirement or {}
        self._accept_counts = accept_counts or {}

    def get_traceability_matrix(self):
        return self._matrix

    def get_coverage_report(self, requirement_ids):
        return self._coverage

    def get_traces_for_requirement(self, req_id):
        return self._traces_by_requirement.get(req_id, [])

    def accept_element(self, element_id, accepted_by="engineer"):
        return self._accept_counts.get(element_id, 0)

    def extract_and_store_traces(self, result):
        return 0


class _FailingTraceStore(_FakeTraceStore):
    def extract_and_store_traces(self, result):
        raise OSError("disk I/O error")


def _complete_event_payload(stream_text: str) -> dict:
    for chunk in stream_text.split("\n\n"):
        if "event: complete" not in chunk:
            continue
        for line in chunk.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
    raise AssertionError("complete event not found")


@pytest.fixture
def api_client(monkeypatch):
    """Create a FastAPI test client with lightweight service stubs."""
    monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _DummyOrchestrator())
    monkeypatch.setattr(dependencies, "get_mapper", lambda: _DummyMapper())
    monkeypatch.setattr(dependencies, "get_validator", lambda: _DummyValidator())
    monkeypatch.setattr(dependencies, "get_render_service", lambda: _DummyRenderService())

    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_activity_result() -> GenerationResult:
    diagram = ActivityDiagram(
        name="RE_Test Code Flow",
        owner_swc="SWC_Test",
        owner_runnable="RE_Test",
        source_requirements=["REQ-ARCH-0142"],
        nodes=[
            ActivityNode(
                id="N_01",
                name="Start",
                node_type=ActivityNodeType.INITIAL,
                trace_reqs=["REQ-ARCH-0142"],
            ),
            ActivityNode(
                id="N_02",
                name="Compute assist torque",
                node_type=ActivityNodeType.ACTION,
                trace_reqs=["REQ-ARCH-0142"],
            ),
            ActivityNode(
                id="N_03",
                name="End",
                node_type=ActivityNodeType.FINAL,
                trace_reqs=["REQ-ARCH-0142"],
            ),
        ],
        edges=[
            ActivityEdge(source="N_01", target="N_02"),
            ActivityEdge(source="N_02", target="N_03"),
        ],
    )
    return GenerationResult(diagrams=[diagram], analyzed_requirements=["REQ-ARCH-0142"])


class TestImportRoutes:
    def test_import_text_csv_form_success(self, api_client):
        response = api_client.post(
            "/api/v1/requirements/import/text",
            data={
                "requirements_text": (
                    "Req_ID,Title,Description,Type,Priority\n"
                    "REQ-ARCH-1001,Detect speed,Measure wheel speed,functional,must\n"
                ),
                "format": "csv",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["rows_processed"] == 1
        assert payload["requirement_set"]["requirements"][0]["req_id"] == "REQ-ARCH-1001"

    def test_import_upload_rejects_invalid_column_mapping_json(self, api_client):
        response = api_client.post(
            "/api/v1/requirements/import",
            files={"file": ("reqs.csv", b"Req_ID,Title,Description\nREQ-1,Title,Desc", "text/csv")},
            data={"column_mapping": "{not-json"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid column_mapping JSON"

    def test_import_upload_returns_importer_errors(self, api_client, monkeypatch):
        def fake_import_file(*args, **kwargs):
            return ImportResult(
                requirement_set=RequirementSet(source_file="reqs.csv", source_format="csv"),
                errors=["Required column 'Req_ID' not found"],
            )

        monkeypatch.setattr("mudtool.importers.factory.ImporterFactory.import_file", fake_import_file)

        response = api_client.post(
            "/api/v1/requirements/import",
            files={"file": ("reqs.csv", b"Title,Description\nOnly title,Only desc", "text/csv")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is False
        assert payload["errors"] == ["Required column 'Req_ID' not found"]


class TestGenerateAndValidateRoutes:
    def test_generate_rejects_invalid_diagram_type(self, api_client, sample_requirement_set):
        response = api_client.post(
            "/api/v1/generate",
            json={
                "requirements": sample_requirement_set.model_dump(mode="json"),
                "diagram_types": ["invalid-diagram"],
            },
        )

        assert response.status_code == 400
        assert "Invalid diagram type" in response.json()["detail"]

    def test_generate_rejects_activity_without_mud_spec(self, api_client, sample_requirement_set):
        response = api_client.post(
            "/api/v1/generate",
            json={
                "requirements": sample_requirement_set.model_dump(mode="json"),
                "diagram_types": ["activity"],
                "activity_source": "mud_spec",
            },
        )

        assert response.status_code == 400
        assert "mud_spec_markdown" in response.json()["detail"]

    def test_validate_returns_report(self, api_client, sample_generation_result):
        response = api_client.post(
            "/api/v1/validate",
            json={"result": sample_generation_result.model_dump(mode="json")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["passed"] is True
        assert payload["diagrams_checked"] == len(sample_generation_result.diagrams)

    def test_generate_tolerates_traceability_store_failure(
        self, monkeypatch, sample_requirement_set, sample_generation_result
    ):
        async def _fake_generate_activity_from_mud(*args, **kwargs):
            return sample_generation_result

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _DummyOrchestrator())
        monkeypatch.setattr(dependencies, "get_mapper", lambda: _DummyMapper())
        monkeypatch.setattr(dependencies, "get_validator", lambda: _DummyValidator())
        monkeypatch.setattr(dependencies, "get_render_service", lambda: _DummyRenderService())
        monkeypatch.setattr(dependencies, "get_trace_store", lambda: _FailingTraceStore())
        monkeypatch.setattr(routes, "_generate_activity_from_mud", _fake_generate_activity_from_mud)
        monkeypatch.setattr(
            routes,
            "_ensure_elaboration_data",
            lambda *args, **kwargs: __import__("asyncio").sleep(
                0,
                result={"source": "test", "status": "ok", "elaborated": [], "req_hash": "test", "quality_score": 1.0},
            ),
        )

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/generate",
                json={
                    "requirements": sample_requirement_set.model_dump(mode="json"),
                    "diagram_types": ["activity"],
                    "module_context": "SWC_Test",
                    "mud_spec_markdown": """
# MUD Spec: SWC_Test

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Test | Cyclic | 10 ms | QM | Simple path |

## 7. Functional Description
### RE_Test
1. Start processing
2. Write output
3. End
""",
                    "activity_source": "mud_spec",
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["result"]["diagrams"]
        assert any("Traceability persistence failed" in warning for warning in payload["result"]["warnings"])

    def test_generate_tolerates_traceability_store_initialization_failure(
        self, monkeypatch, sample_requirement_set, sample_generation_result
    ):
        async def _fake_generate_activity_from_mud(*args, **kwargs):
            return sample_generation_result

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _DummyOrchestrator())
        monkeypatch.setattr(dependencies, "get_mapper", lambda: _DummyMapper())
        monkeypatch.setattr(dependencies, "get_validator", lambda: _DummyValidator())
        monkeypatch.setattr(dependencies, "get_render_service", lambda: _DummyRenderService())
        monkeypatch.setattr(dependencies, "get_trace_store", lambda: (_ for _ in ()).throw(OSError("disk I/O error")))
        monkeypatch.setattr(routes, "_generate_activity_from_mud", _fake_generate_activity_from_mud)
        monkeypatch.setattr(
            routes,
            "_ensure_elaboration_data",
            lambda *args, **kwargs: __import__("asyncio").sleep(
                0,
                result={"source": "test", "status": "ok", "elaborated": [], "req_hash": "test", "quality_score": 1.0},
            ),
        )

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/generate",
                json={
                    "requirements": sample_requirement_set.model_dump(mode="json"),
                    "diagram_types": ["activity"],
                    "module_context": "SWC_Test",
                    "mud_spec_markdown": """
# MUD Spec: SWC_Test

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Test | Cyclic | 10 ms | QM | Simple path |

## 7. Functional Description
### RE_Test
1. Start processing
2. Write output
3. End
""",
                    "activity_source": "mud_spec",
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["result"]["diagrams"]
        assert any("Traceability persistence failed: disk I/O error" in warning for warning in payload["result"]["warnings"])

    def test_generate_stream_activity_emits_complete_event(self, monkeypatch):
        activity_result = GenerationResult(
            diagrams=[
                ActivityDiagram(
                    name="RE_Stream Code Flow",
                    owner_swc="SWC_Stream",
                    owner_runnable="RE_Stream",
                    source_requirements=["REQ-STREAM-1"],
                    nodes=[
                        ActivityNode(id="N_00", name="Start", node_type=ActivityNodeType.INITIAL),
                        ActivityNode(id="N_01", name="Compute", node_type=ActivityNodeType.ACTION),
                        ActivityNode(id="N_02", name="End", node_type=ActivityNodeType.FINAL),
                    ],
                    edges=[
                        ActivityEdge(source="N_00", target="N_01"),
                        ActivityEdge(source="N_01", target="N_02"),
                    ],
                )
            ],
            analyzed_requirements=["REQ-STREAM-1"],
        )

        class _StreamingOrchestrator(_DummyOrchestrator):
            async def generate_diagram(self, *args, **kwargs):
                return activity_result

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _StreamingOrchestrator())
        monkeypatch.setattr(dependencies, "get_mapper", lambda: _DummyMapper())
        monkeypatch.setattr(dependencies, "get_validator", lambda: _DummyValidator())
        monkeypatch.setattr(dependencies, "get_render_service", lambda: _DummyRenderService())
        monkeypatch.setattr(dependencies, "get_trace_store", lambda: _FakeTraceStore())
        monkeypatch.setattr(
            routes,
            "_ensure_elaboration_data",
            lambda *args, **kwargs: __import__("asyncio").sleep(
                0,
                result={"source": "test", "status": "ok", "elaborated": [], "req_hash": "test", "quality_score": 1.0},
            ),
        )

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/generate/stream",
                json={
                    "requirements": {
                        "requirements": [
                            {
                                "req_id": "REQ-STREAM-1",
                                "title": "Stream test",
                                "description": "Generate a simple activity.",
                                "req_type": "functional",
                                "priority": "must",
                                "status": "approved",
                            }
                        ]
                    },
                    "diagram_types": ["activity"],
                    "module_context": "SWC_Stream",
                    "mud_spec_markdown": """
# MUD Spec: SWC_Stream

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Stream | Cyclic | 10 ms | QM | Simple stream path |

## 7. Functional Description
### RE_Stream
1. Start processing
2. Write output
3. End
""",
                    "activity_source": "mud_spec",
                },
            )

        assert response.status_code == 200
        assert "event: complete" in response.text
        payload = _complete_event_payload(response.text)
        summary = payload["generation_summary"]
        assert summary["planned_count"] == 1
        assert summary["generated_count"] == 1
        assert summary["rendered_count"] == 1
        assert summary["failed_count"] == 0
        assert summary["quality_status"] == "pass"

    def test_generation_summary_marks_validation_warnings_as_needs_fix(self, sample_activity_result):
        report = ValidationReport(
            issues=[
                ValidationIssue(
                    rule_id="AUT-010",
                    severity=ValidationSeverity.WARNING,
                    category="Traceability",
                    message="Coverage gap",
                )
            ],
            passed=True,
        )

        summary = routes._build_generation_summary(
            planned_count=2,
            planned_items=["RE_One", "RE_Two"],
            result=GenerationResult(diagrams=[sample_activity_result.diagrams[0], sample_activity_result.diagrams[0]]),
            rendered_count=2,
            validation_report=report,
            lint_results={},
        )

        assert summary["planned_count"] == 2
        assert summary["generated_count"] == 2
        assert summary["quality_status"] == "needs_fix"
        assert summary["warning_count"] == 1

    def test_generation_summary_marks_missing_planned_diagram_as_failed(self, sample_activity_result):
        summary = routes._build_generation_summary(
            planned_count=2,
            planned_items=["RE_One", "RE_Two"],
            result=sample_activity_result,
            rendered_count=1,
            validation_report=ValidationReport(passed=True),
            lint_results={},
        )

        assert summary["generated_count"] == 1
        assert summary["failed_count"] == 1
        assert summary["failed_items"] == ["RE_Two"]
        assert summary["quality_status"] == "failed"

    def test_generation_summary_counts_lint_findings(self, sample_activity_result):
        summary = routes._build_generation_summary(
            planned_count=1,
            planned_items=["RE_Test"],
            result=sample_activity_result,
            rendered_count=1,
            validation_report=ValidationReport(passed=True),
            lint_results={"RE_Test": SimpleNamespace(errors=[], warnings=["long label"])},
        )

        assert summary["generated_count"] == 1
        assert summary["quality_status"] == "needs_fix"
        assert summary["warning_count"] == 1

    @pytest.mark.xfail(reason="Latest UI contract also asks generation_summary to expose error_count.")
    def test_generation_summary_contract_exposes_error_count_for_ui(self, sample_activity_result):
        result = GenerationResult(
            diagrams=sample_activity_result.diagrams,
            errors=["blocking Mermaid render failure"],
            warnings=["validation warning"],
        )

        summary = routes._build_generation_summary(
            planned_count=1,
            planned_items=["RE_Test"],
            result=result,
            rendered_count=1,
            validation_report=ValidationReport(passed=True),
            lint_results={},
        )

        assert summary["generated_count"] == 1
        assert summary["error_count"] == 1
        assert summary["warning_count"] == 1
        assert summary["quality_status"] == "needs_fix"

    def test_generate_stream_activity_sanitizes_nan_in_final_payload(self, monkeypatch):
        activity_result = GenerationResult(
            diagrams=[
                ActivityDiagram(
                    name="RE_Stream Code Flow",
                    owner_swc="SWC_Stream",
                    owner_runnable="RE_Stream",
                    source_requirements=["REQ-STREAM-1"],
                    nodes=[
                        ActivityNode(id="N_00", name="Start", node_type=ActivityNodeType.INITIAL, confidence=0.9),
                        ActivityNode(id="N_01", name="Compute", node_type=ActivityNodeType.ACTION, confidence=0.9),
                        ActivityNode(id="N_02", name="End", node_type=ActivityNodeType.FINAL, confidence=0.9),
                    ],
                    edges=[
                        ActivityEdge(source="N_00", target="N_01"),
                        ActivityEdge(source="N_01", target="N_02"),
                    ],
                )
            ],
            analyzed_requirements=["REQ-STREAM-1"],
        )

        async def _fake_generate_activity_from_mud(*args, **kwargs):
            return activity_result

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _DummyOrchestrator())
        monkeypatch.setattr(dependencies, "get_mapper", lambda: _DummyMapper())
        monkeypatch.setattr(dependencies, "get_validator", lambda: _DummyValidator())
        monkeypatch.setattr(dependencies, "get_render_service", lambda: _DummyRenderService())
        monkeypatch.setattr(dependencies, "get_trace_store", lambda: _FakeTraceStore())
        monkeypatch.setattr(routes, "_generate_activity_from_mud", _fake_generate_activity_from_mud)
        monkeypatch.setattr(
            routes,
            "_ensure_elaboration_data",
            lambda *args, **kwargs: __import__("asyncio").sleep(
                0,
                result={"source": "test", "status": "ok", "elaborated": [], "req_hash": "test", "quality_score": float("nan")},
            ),
        )

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/generate/stream",
                json={
                    "requirements": {
                        "requirements": [
                            {
                                "req_id": "REQ-STREAM-1",
                                "title": "Stream test",
                                "description": "Generate a simple activity.",
                                "req_type": "functional",
                                "priority": "must",
                                "status": "approved",
                            }
                        ]
                    },
                    "diagram_types": ["activity"],
                    "module_context": "SWC_Stream",
                    "mud_spec_markdown": """
# MUD Spec: SWC_Stream

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Stream | Cyclic | 10 ms | QM | Simple stream path |

## 7. Functional Description
### RE_Stream
1. Start processing
2. Write output
3. End
""",
                    "activity_source": "mud_spec",
                },
            )

        assert response.status_code == 200
        assert "event: complete" in response.text
        assert "NaN" not in response.text

    @pytest.mark.asyncio
    async def test_generate_activity_from_mud_replaces_placeholder_with_branched_fallback(self):
        class _PlaceholderOrchestrator(_DummyOrchestrator):
            async def generate_diagram(self, *args, **kwargs):
                return GenerationResult(
                    diagrams=[
                        ActivityDiagram(
                            name="RE_Control Code Flow",
                            owner_swc="SWC_BrakeAssist",
                            owner_runnable="RE_Control",
                            nodes=[
                                ActivityNode(id="N_00", name="Start", node_type=ActivityNodeType.INITIAL),
                                ActivityNode(id="N_01", name="Action", node_type=ActivityNodeType.ACTION),
                                ActivityNode(id="N_02", name="End", node_type=ActivityNodeType.FINAL),
                            ],
                            edges=[
                                ActivityEdge(source="N_00", target="N_01"),
                                ActivityEdge(source="N_01", target="N_02"),
                            ],
                        )
                    ],
                    analyzed_requirements=["REQ-201"],
                )

        requirement = Requirement(
            req_id="REQ-201",
            title="Brake assist branching",
            description="Generate brake assist flow.",
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
            status=RequirementStatus.APPROVED,
        )
        request = routes.GenerateRequest(
            requirements=RequirementSet(requirements=[requirement]),
            diagram_types=["activity"],
            module_context="SWC_BrakeAssist",
            mud_spec_markdown="""
# MUD Spec: SWC_BrakeAssist

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Control | Cyclic | 10 ms | ASIL-C | Branching flow |

## 7. Functional Description
### RE_Control
1. If brakeRequest > threshold
1.1. Rte_Write(PP_BrakeAssistCmd, TRUE)
2. Else
2.1. Dem_ReportErrorStatus(Event_BrakeAssist, DEM_EVENT_STATUS_FAILED)
3. End If
4. Rte_Write(PP_Status, status)
""",
            activity_source="mud_spec",
        )

        result = await routes._generate_activity_from_mud(
            _PlaceholderOrchestrator(),
            [requirement],
            request,
        )

        assert any(n.node_type == ActivityNodeType.DECISION for n in result.diagrams[0].nodes)
        assert any((edge.guard or "") == "[else]" or "brakeRequest > threshold" in (edge.guard or "") for edge in result.diagrams[0].edges)
        assert any("deterministic flow generated from MUD Section 7" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_generate_activity_from_mud_normalizes_section7_before_context_build(self):
        class _PlaceholderOrchestrator(_DummyOrchestrator):
            async def generate_diagram(self, *args, **kwargs):
                return GenerationResult(
                    diagrams=[
                        ActivityDiagram(
                            name="RE_Stream Code Flow",
                            owner_swc="SWC_Stream",
                            owner_runnable="RE_Stream",
                            nodes=[
                                ActivityNode(id="N_00", name="Start", node_type=ActivityNodeType.INITIAL),
                                ActivityNode(id="N_01", name="Action", node_type=ActivityNodeType.ACTION),
                                ActivityNode(id="N_02", name="End", node_type=ActivityNodeType.FINAL),
                            ],
                            edges=[
                                ActivityEdge(source="N_00", target="N_01"),
                                ActivityEdge(source="N_01", target="N_02"),
                            ],
                        )
                    ],
                    analyzed_requirements=["REQ-301"],
                )

        requirement = Requirement(
            req_id="REQ-301",
            title="Stream branch",
            description="Normalize section 7 before activity generation.",
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
            status=RequirementStatus.APPROVED,
        )
        request = routes.GenerateRequest(
            requirements=RequirementSet(requirements=[requirement]),
            diagram_types=["activity"],
            module_context="SWC_Stream",
            mud_spec_markdown="""
# MUD Spec: SWC_Stream

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Stream | Cyclic | 10 ms | ASIL-B | Stream flow |

## 7. Functional Description
### RE_Stream
1. Guard: mode check: if (RteIRead(RP_IgnitionStatus) == false) { RteIWrite(PP_EPSStatus, 0); return; }
2. Continue: RteWrite(PP_AssistLevel, assistLevel)
""",
            activity_source="mud_spec",
        )

        result = await routes._generate_activity_from_mud(
            _PlaceholderOrchestrator(),
            [requirement],
            request,
        )

        diagram = result.diagrams[0]
        assert any(node.node_type == ActivityNodeType.DECISION for node in diagram.nodes)
        assert any((node.rte_call or "") == "Rte_IWrite" for node in diagram.nodes)
        assert not any("normalization failed" in warning.lower() for warning in result.warnings)


class TestModulePlanningRoutes:
    def test_modules_plan_recovers_when_ai_returns_empty(self, monkeypatch):
        class _PlannerBackend:
            async def generate(self, **kwargs):
                return AIResponse(content="", model="test-model")

        class _PlannerOrchestrator(_DummyOrchestrator):
            def _get_backend(self):
                return _PlannerBackend()

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _PlannerOrchestrator())
        monkeypatch.setattr(dependencies, "get_mapper", lambda: _DummyMapper())
        monkeypatch.setattr(dependencies, "get_validator", lambda: _DummyValidator())
        monkeypatch.setattr(dependencies, "get_render_service", lambda: _DummyRenderService())

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/modules/plan",
                json={
                    "requirements_text": (
                        "req_id,title,description,req_type,safety_level,priority,module_hint,notes\n"
                        "REQ-EPS-001,EPS SWC Architecture,SWC_ElectricPowerSteering shall be implemented,"
                        "FUNCTIONAL,ASIL-D,MUST,SWC_ElectricPowerSteering,Single SWC\n"
                        "REQ-EPS-002,Control Torque Runnable,RE_ControlTorque shall execute cyclically,"
                        "TIMING,ASIL-D,MUST,SWC_ElectricPowerSteering,5ms\n"
                    ),
                    "temperature": 0.1,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["module_count"] == 1
        assert payload["modules"][0]["swc_name"] == "SWC_ElectricPowerSteering"
        assert "RE_ControlTorque" in payload["modules"][0]["runnables"]


class TestMudSpecRoutes:
    @staticmethod
    def _complete_event_payload(response_text: str) -> dict:
        for line in response_text.splitlines():
            if line.startswith("data: ") and '"_final":true' in line.replace(" ", ""):
                return json.loads(line[6:])
        raise AssertionError(f"No complete payload found in SSE response:\n{response_text}")

    def test_mud_spec_stream_emits_section7_normalization_metadata(self, monkeypatch):
        spec_text = """
# MUD Spec: SWC_Stream

## 1. Overview
| Field | Value |
|-------|-------|
| SWC Name | SWC_Stream |

## 3. Runnables
| Runnable | Trigger | Period | ASIL | Description |
|----------|---------|--------|------|-------------|
| RE_Stream | Cyclic | 10 ms | ASIL-B | Stream flow |

## 7. Functional Description
### RE_Stream
1. Guard: mode check: if (RteIRead(RP_IgnitionStatus) == false) { RteIWrite(PP_EPSStatus, 0); return; }
"""

        class _SpecBackend:
            backend_name = "test-backend"

            async def generate_stream(self, **kwargs):
                yield spec_text

        class _SpecOrchestrator(_DummyOrchestrator):
            def _get_backend(self):
                return _SpecBackend()

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _SpecOrchestrator())
        monkeypatch.setattr(dependencies, "get_mapper", lambda: _DummyMapper())
        monkeypatch.setattr(dependencies, "get_validator", lambda: _DummyValidator())
        monkeypatch.setattr(dependencies, "get_render_service", lambda: _DummyRenderService())

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/modules/mud-spec",
                json={
                    "swc_name": "SWC_Stream",
                    "description": "Stream flow",
                    "asil": "ASIL-B",
                    "runnables": ["RE_Stream"],
                    "req_ids": ["REQ-STREAM-1"],
                    "requirements_text": "REQ-STREAM-1 stream behavior",
                    "spec_pipeline": "single_pass",
                },
            )

        assert response.status_code == 200
        assert "event: complete" in response.text
        assert "section7_normalization" in response.text

    def test_mud_spec_regenerate_verifies_post_review_without_retry(self, monkeypatch):
        from mudtool.ai import mud_spec_generator as msg

        class _FakeMudSpecGenerator:
            def __init__(self, orchestrator):
                self.last_normalization_result = SimpleNamespace(to_dict=lambda: {"changed": False})

            async def regenerate_spec(self, **kwargs):
                return kwargs["current_spec_markdown"] + "\n\n## 7. Functional Description\nfixed"

            async def review_spec(self, **kwargs):
                return msg.SpecReviewResult(approved=True, coverage_pct=100, iteration=kwargs["iteration"])

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _DummyOrchestrator())
        monkeypatch.setattr(msg, "MudSpecGenerator", _FakeMudSpecGenerator)

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/modules/mud-spec/regenerate",
                json={
                    "swc_name": "SWC_Test",
                    "asil": "ASIL-B",
                    "req_ids": ["REQ-1"],
                    "requirements_text": "REQ-1 do control",
                    "current_spec_markdown": "# MUD Spec: SWC_Test",
                    "review": {
                        "approved": False,
                        "coverage_pct": 80,
                        "issues": [
                            {"severity": "warning", "section": "7", "message": "Missing DEM event"}
                        ],
                        "suggestions": [],
                        "uncovered_req_ids": [],
                        "coverage_gaps": [],
                        "iteration": 1,
                    },
                },
            )

        assert response.status_code == 200
        payload = self._complete_event_payload(response.text)
        assert payload["retry_count"] == 0
        assert payload["remaining_issue_count"] == 0
        assert payload["resolved_issue_count"] == 1
        assert payload["quality_status"] == "pass"
        assert payload["post_review"]["approved"] is True

    def test_mud_spec_regenerate_retries_once_for_repeated_issue(self, monkeypatch):
        from mudtool.ai import mud_spec_generator as msg

        calls = {"regen": 0, "review": 0}

        class _FakeMudSpecGenerator:
            def __init__(self, orchestrator):
                self.last_normalization_result = SimpleNamespace(to_dict=lambda: {"changed": False})

            async def regenerate_spec(self, **kwargs):
                calls["regen"] += 1
                return kwargs["current_spec_markdown"] + f"\nretry-pass-{calls['regen']}"

            async def review_spec(self, **kwargs):
                calls["review"] += 1
                if calls["review"] == 1:
                    return msg.SpecReviewResult(
                        approved=False,
                        coverage_pct=80,
                        issues=[msg.ReviewIssue("warning", "7", "Missing DEM event")],
                        iteration=kwargs["iteration"],
                    )
                return msg.SpecReviewResult(approved=True, coverage_pct=100, iteration=kwargs["iteration"])

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _DummyOrchestrator())
        monkeypatch.setattr(msg, "MudSpecGenerator", _FakeMudSpecGenerator)

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/modules/mud-spec/regenerate",
                json={
                    "swc_name": "SWC_Test",
                    "asil": "ASIL-B",
                    "req_ids": ["REQ-1"],
                    "requirements_text": "REQ-1 do control",
                    "current_spec_markdown": "# MUD Spec: SWC_Test",
                    "review": {
                        "approved": False,
                        "coverage_pct": 80,
                        "issues": [
                            {"severity": "warning", "section": "7", "message": "Missing DEM event"}
                        ],
                        "suggestions": [],
                        "uncovered_req_ids": [],
                        "coverage_gaps": [],
                        "iteration": 1,
                    },
                },
            )

        assert response.status_code == 200
        payload = self._complete_event_payload(response.text)
        assert calls == {"regen": 2, "review": 2}
        assert payload["retry_count"] == 1
        assert payload["remaining_issue_count"] == 0
        assert payload["resolved_issue_count"] == 1
        assert payload["quality_status"] == "pass"

    def test_mud_spec_regenerate_stops_after_one_failed_retry(self, monkeypatch):
        from mudtool.ai import mud_spec_generator as msg

        calls = {"regen": 0, "review": 0}

        class _FakeMudSpecGenerator:
            def __init__(self, orchestrator):
                self.last_normalization_result = SimpleNamespace(to_dict=lambda: {"changed": False})

            async def regenerate_spec(self, **kwargs):
                calls["regen"] += 1
                return kwargs["current_spec_markdown"] + f"\nfailed-pass-{calls['regen']}"

            async def review_spec(self, **kwargs):
                calls["review"] += 1
                return msg.SpecReviewResult(
                    approved=False,
                    coverage_pct=80,
                    issues=[msg.ReviewIssue("warning", "7", "Missing DEM event")],
                    iteration=kwargs["iteration"],
                )

        monkeypatch.setattr(dependencies, "get_orchestrator", lambda: _DummyOrchestrator())
        monkeypatch.setattr(msg, "MudSpecGenerator", _FakeMudSpecGenerator)

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/modules/mud-spec/regenerate",
                json={
                    "swc_name": "SWC_Test",
                    "asil": "ASIL-B",
                    "req_ids": ["REQ-1"],
                    "requirements_text": "REQ-1 do control",
                    "current_spec_markdown": "# MUD Spec: SWC_Test",
                    "review": {
                        "approved": False,
                        "coverage_pct": 80,
                        "issues": [
                            {"severity": "warning", "section": "7", "message": "Missing DEM event"}
                        ],
                        "suggestions": [],
                        "uncovered_req_ids": [],
                        "coverage_gaps": [],
                        "iteration": 1,
                    },
                },
            )

        assert response.status_code == 200
        payload = self._complete_event_payload(response.text)
        assert calls == {"regen": 2, "review": 2}
        assert payload["retry_count"] == 1
        assert payload["remaining_issue_count"] == 1
        assert payload["repeated_issue_count"] == 1
        assert payload["quality_status"] == "needs_fix"


class TestExportRoutes:
    def test_export_mermaid_inline_returns_diagrams(self, api_client, sample_generation_result):
        response = api_client.post(
            "/api/v1/export/mermaid/inline",
            json={"result": sample_generation_result.model_dump(mode="json")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["diagrams"]
        assert any("sequenceDiagram" in text for text in payload["diagrams"].values())

    def test_export_rejects_unsupported_format(self, api_client, sample_generation_result, tmp_path):
        response = api_client.post(
            "/api/v1/export",
            json={
                "result": sample_generation_result.model_dump(mode="json"),
                "output_path": str(tmp_path),
                "format": "pdf",
            },
        )

        assert response.status_code == 400
        assert "Unsupported export format" in response.json()["detail"]

    def test_export_c_skeleton_returns_files_for_activity_result(
        self, api_client, sample_activity_result
    ):
        response = api_client.post(
            "/api/v1/export/c-skeleton",
            json={"result": sample_activity_result.model_dump(mode="json")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["files"]
        file_text = next(iter(payload["files"].values()))
        assert "void RE_Test(void)" in file_text
        assert "Compute assist torque;" in file_text

    def test_export_c_skeleton_rejects_non_activity_result(self, api_client, sample_generation_result):
        response = api_client.post(
            "/api/v1/export/c-skeleton",
            json={"result": sample_generation_result.model_dump(mode="json")},
        )

        assert response.status_code == 400
        assert "No ActivityDiagram found" in response.json()["detail"]

    def test_render_rejects_invalid_format(self, api_client, sample_generation_result, tmp_path):
        response = api_client.post(
            "/api/v1/render",
            json={
                "result": sample_generation_result.model_dump(mode="json"),
                "output_path": str(tmp_path),
                "format": "gif",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "format must be 'svg' or 'png'"

    def test_render_mermaid_returns_svg(self, api_client):
        response = api_client.post(
            "/api/v1/render/mermaid",
            json={"mermaid_text": "flowchart TD\nA-->B"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/svg+xml")
        assert "<svg" in response.text

    def test_render_mermaid_rejects_empty_text(self, api_client):
        response = api_client.post(
            "/api/v1/render/mermaid",
            json={"mermaid_text": "   "},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "mermaid_text must not be empty"


class TestTraceabilityAndConfigRoutes:
    def test_traceability_endpoints_return_matrix_and_coverage(
        self, api_client, monkeypatch
    ):
        store = _FakeTraceStore(
            matrix=[
                {
                    "requirement_id": "REQ-ARCH-0142",
                    "elements": [
                        {
                            "element_name": "SWC_SensorFusion",
                            "element_type": "lifeline",
                            "diagram_type": "sequence",
                            "diagram_name": "SensorFusion_DataDistribution",
                            "confidence": 0.9,
                            "accepted": False,
                        }
                    ],
                }
            ],
            coverage={
                "total_requirements": 2,
                "covered_requirements": 1,
                "uncovered_requirements": 1,
                "coverage_percentage": 50.0,
                "uncovered_ids": ["REQ-ARCH-9999"],
            },
            traces_by_requirement={
                "REQ-ARCH-0142": [
                    TraceLink(
                        id=1,
                        requirement_id="REQ-ARCH-0142",
                        element_id="ll_1",
                        element_name="SWC_SensorFusion",
                        element_type="lifeline",
                        diagram_type="sequence",
                        diagram_name="SensorFusion_DataDistribution",
                        ai_model="test-model",
                        confidence=0.9,
                        prompt_version="seq-v1.0",
                    )
                ]
            },
        )
        monkeypatch.setattr(dependencies, "get_trace_store", lambda: store)

        matrix_response = api_client.get("/api/v1/traceability")
        coverage_response = api_client.get(
            "/api/v1/traceability",
            params={"requirement_ids": "REQ-ARCH-0142,REQ-ARCH-9999"},
        )
        single_response = api_client.get("/api/v1/traceability/requirement/REQ-ARCH-0142")

        assert matrix_response.status_code == 200
        assert matrix_response.json()["matrix"]

        coverage_payload = coverage_response.json()["coverage"]
        assert coverage_payload["total_requirements"] == 2
        assert "REQ-ARCH-9999" in coverage_payload["uncovered_ids"]

        assert single_response.status_code == 200
        assert single_response.json()["requirement_id"] == "REQ-ARCH-0142"
        assert single_response.json()["traces"]

    def test_accept_element_updates_trace_links(self, api_client, monkeypatch):
        store = _FakeTraceStore(accept_counts={"ll_1": 2})
        monkeypatch.setattr(dependencies, "get_trace_store", lambda: store)

        response = api_client.post(
            "/api/v1/traceability/accept",
            json={"element_id": "ll_1", "accepted_by": "qa"},
        )

        assert response.status_code == 200
        assert response.json()["links_updated"] == 2

    def test_get_config_returns_non_sensitive_fields(self, api_client, monkeypatch, test_settings):
        monkeypatch.setattr(routes, "get_settings", lambda: test_settings)

        response = api_client.get("/api/v1/config")

        assert response.status_code == 200
        payload = response.json()
        assert "anthropic_model" in payload
        assert "anthropic_api_key" not in payload

    def test_config_update_rejects_unknown_backend(self, api_client):
        response = api_client.post(
            "/api/v1/config/update",
            json={"backend_type": "mysterybox"},
        )

        assert response.status_code == 400
        assert "Unknown backend_type" in response.json()["detail"]


class TestEnvWriter:
    def test_write_env_updates_replaces_existing_and_appends_missing(self, tmp_path, monkeypatch):
        env_path = tmp_path / ".env"
        env_path.write_text(
            "MUD_AI_BACKEND=cloud\n"
            "# MUD_OPENAI_MODEL=commented\n"
            "MUD_MAX_RETRIES=3\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        routes._write_env_updates(
            {
                "MUD_AI_BACKEND": "local",
                "MUD_OPENAI_MODEL": "llama3.2",
                "MUD_MAX_RETRIES": "5",
            }
        )

        content = env_path.read_text(encoding="utf-8")
        assert "MUD_AI_BACKEND=local" in content
        assert "MUD_MAX_RETRIES=5" in content
        assert "MUD_OPENAI_MODEL=llama3.2" in content
