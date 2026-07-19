"""Tests for the traceability store."""

import pytest

from mudtool.traceability.store import TraceabilityStore, TraceLink


class TestTraceabilityStore:
    @pytest.fixture
    def store(self, test_settings):
        s = TraceabilityStore(test_settings)
        s.initialize()
        yield s
        s.close()

    def test_initialize_creates_db(self, store, test_settings):
        assert test_settings.get_db_path().exists()

    def test_add_and_retrieve_trace(self, store):
        link = TraceLink(
            requirement_id="REQ-ARCH-0001",
            element_id="ll_1",
            element_name="SWC_SensorFusion",
            element_type="lifeline",
            diagram_type="sequence",
            diagram_name="TestDiagram",
            ai_model="test-model",
            confidence=0.9,
        )
        link_id = store.add_trace_link(link)
        assert link_id > 0

        traces = store.get_traces_for_requirement("REQ-ARCH-0001")
        assert len(traces) == 1
        assert traces[0].element_name == "SWC_SensorFusion"

    def test_coverage_report(self, store):
        # Add some traces
        for req_id in ["REQ-ARCH-0001", "REQ-ARCH-0002"]:
            store.add_trace_link(TraceLink(
                requirement_id=req_id,
                element_id=f"elem_{req_id}",
                element_name=f"Element for {req_id}",
                element_type="class",
                diagram_type="class",
            ))

        coverage = store.get_coverage_report([
            "REQ-ARCH-0001", "REQ-ARCH-0002", "REQ-ARCH-0003"
        ])

        assert coverage["total_requirements"] == 3
        assert coverage["covered_requirements"] == 2
        assert coverage["uncovered_requirements"] == 1
        assert "REQ-ARCH-0003" in coverage["uncovered_ids"]

    def test_extract_traces_from_result(self, store, sample_generation_result):
        count = store.extract_and_store_traces(sample_generation_result)
        assert count > 0

        matrix = store.get_traceability_matrix()
        assert len(matrix) > 0

    def test_accept_element(self, store):
        store.add_trace_link(TraceLink(
            requirement_id="REQ-ARCH-0001",
            element_id="elem_1",
            element_name="SWC_Test",
            element_type="class",
            diagram_type="class",
        ))

        count = store.accept_element("elem_1", "test_engineer")
        assert count == 1

        traces = store.get_traces_for_element("elem_1")
        assert traces[0].accepted is True
        assert traces[0].accepted_by == "test_engineer"
