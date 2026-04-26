"""API route tests covering high-value endpoint behavior and edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mudtool.api import dependencies
from mudtool.api import routes
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
from mudtool.models.validation import ValidationReport
from mudtool.traceability.store import TraceLink


class _DummyOrchestrator:
    async def health_check(self) -> dict:
        return {"backends": {"dummy": True}}

    async def generate_diagram(self, *args, **kwargs):
        return GenerationResult()


class _DummyMapper:
    pass


class _DummyValidator:
    def validate(self, result, requirement_ids=None) -> ValidationReport:
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
        assert any(edge.guard == "[false]" for edge in result.diagrams[0].edges)
        assert any("deterministic flow generated from MUD Section 7" in w for w in result.warnings)


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
