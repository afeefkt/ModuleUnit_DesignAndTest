"""Tests for the AUTOSAR mapper."""

import pytest

from mudtool.config.settings import Settings
from mudtool.generator.autosar_mapper import AUTOSARMapper
from mudtool.models.json_uml import (
    ClassDiagram,
    ClassElement,
    ClassOperation,
    ComponentDiagram,
    ComponentElement,
    GenerationResult,
    Lifeline,
    Message,
    PortElement,
    SequenceDiagram,
)


class TestAUTOSARMapper:
    @pytest.fixture
    def mapper(self, test_settings):
        return AUTOSARMapper(test_settings)

    def test_enforce_swc_naming(self, mapper):
        assert mapper._enforce_swc_naming("SWC_SensorFusion") == "SWC_SensorFusion"
        assert mapper._enforce_swc_naming("SensorFusion") == "SWC_Sensorfusion"
        assert mapper._enforce_swc_naming("sensor_fusion") == "SWC_SensorFusion"

    def test_enforce_runnable_naming(self, mapper):
        assert mapper._enforce_runnable_naming("RE_FuseData") == "RE_FuseData"
        assert mapper._enforce_runnable_naming("FuseData") == "RE_Fusedata"
        assert mapper._enforce_runnable_naming("fuse_sensor_data") == "RE_FuseSensorData"

    def test_enforce_port_naming(self, mapper):
        assert mapper._enforce_port_naming("PP_Data", True) == "PP_Data"
        assert mapper._enforce_port_naming("DataOutput", True) == "PP_Dataoutput"
        assert mapper._enforce_port_naming("DataInput", False) == "RP_Datainput"

    def test_normalize_rte_call(self, mapper):
        assert mapper._normalize_rte_call("rte_write") == "Rte_Write"
        assert mapper._normalize_rte_call("Rte_Read") == "Rte_Read"
        assert mapper._normalize_rte_call("RTE_CALL") == "Rte_Call"

    def test_infer_trigger_type(self, mapper):
        assert mapper._infer_trigger_type("RE_InitSensors") == "init"
        assert mapper._infer_trigger_type("RE_CyclicProcess") == "cyclic"
        assert mapper._infer_trigger_type("RE_OnDataReceive") == "on_data_reception"
        assert mapper._infer_trigger_type("RE_MainProcess") == "cyclic"

    def test_map_sequence_diagram(self, mapper):
        diagram = SequenceDiagram(
            name="test",
            lifelines=[
                Lifeline(id="ll_1", name="SensorFusion", type="Class",
                         runnable="processSensorData"),
            ],
            messages=[
                Message(id="m1", **{"from": "ll_1", "to": "ll_1"},
                        rte_call="rte_write", port="DataOut"),
            ],
        )
        result = GenerationResult(diagrams=[diagram])
        mapped = mapper.map_generation_result(result)

        mapped_diag = mapped.diagrams[0]
        assert mapped_diag.lifelines[0].name.startswith("SWC_")
        assert mapped_diag.lifelines[0].type == "ApplicationSWC"
        assert mapped_diag.lifelines[0].runnable.startswith("RE_")
        assert mapped_diag.messages[0].rte_call == "Rte_Write"

    def test_map_class_diagram(self, mapper):
        diagram = ClassDiagram(
            name="test",
            classes=[ClassElement(
                id="c1", name="SensorFusion",
                operations=[
                    ClassOperation(name="initSensors"),
                    ClassOperation(name="processCyclicData"),
                ],
            )],
        )
        result = GenerationResult(diagrams=[diagram])
        mapped = mapper.map_generation_result(result)

        cls = mapped.diagrams[0].classes[0]
        assert cls.name.startswith("SWC_")
        assert cls.stereotype == "ApplicationSWC"
        assert all(op.name.startswith("RE_") for op in cls.operations)
        # Init operation should have init trigger
        init_op = next(op for op in cls.operations if "init" in op.name.lower())
        assert init_op.trigger_type == "init"

    def test_extract_swcs(self, mapper, sample_class_diagram):
        result = GenerationResult(diagrams=[sample_class_diagram])
        result = mapper.map_generation_result(result)
        swcs = mapper.extract_swcs(result)

        assert len(swcs) >= 1
        assert swcs[0].name.startswith("SWC_")
