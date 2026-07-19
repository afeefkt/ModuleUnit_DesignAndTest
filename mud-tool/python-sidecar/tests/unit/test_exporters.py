"""Tests for XMI and PlantUML exporters."""

import pytest
from pathlib import Path

from mudtool.generator.xmi_exporter import XMIExporter
from mudtool.generator.plantuml_exporter import PlantUMLExporter
from mudtool.models.json_uml import GenerationResult


class TestXMIExporter:
    def test_export_sequence_diagram(self, tmp_path, sample_sequence_diagram):
        result = GenerationResult(diagrams=[sample_sequence_diagram])
        exporter = XMIExporter()
        output = tmp_path / "test_model.xmi"

        path = exporter.export_result(result, output, "TestModel")

        assert path.exists()
        content = path.read_text()
        assert "xmi:XMI" in content
        assert "uml:Interaction" in content
        assert "SWC_SensorFusion" in content

    def test_export_state_machine(self, tmp_path, sample_state_machine):
        result = GenerationResult(diagrams=[sample_state_machine])
        exporter = XMIExporter()
        output = tmp_path / "sm_model.xmi"

        path = exporter.export_result(result, output)

        assert path.exists()
        content = path.read_text()
        assert "uml:StateMachine" in content
        assert "RUNNING" in content

    def test_export_class_diagram(self, tmp_path, sample_class_diagram):
        result = GenerationResult(diagrams=[sample_class_diagram])
        exporter = XMIExporter()
        output = tmp_path / "class_model.xmi"

        path = exporter.export_result(result, output)

        assert path.exists()
        content = path.read_text()
        assert "uml:Class" in content
        assert "RE_FuseSensorData" in content

    def test_export_combined(self, tmp_path, sample_generation_result):
        exporter = XMIExporter()
        output = tmp_path / "full_model.xmi"

        path = exporter.export_result(sample_generation_result, output, "FullModel")

        assert path.exists()
        content = path.read_text()
        assert "FullModel" in content


class TestPlantUMLExporter:
    def test_export_sequence(self, sample_sequence_diagram):
        exporter = PlantUMLExporter()
        text = exporter.export_diagram(sample_sequence_diagram)

        assert "@startuml" in text
        assert "@enduml" in text
        assert "SWC_SensorFusion" in text
        assert "Rte_Write" in text
        assert 'participant "SWC_SensorFusion" as ll_1' in text
        assert "note right of ll_1: <<ApplicationSWC>>" in text

    def test_export_state_machine(self, sample_state_machine):
        exporter = PlantUMLExporter()
        text = exporter.export_diagram(sample_state_machine)

        assert "@startuml" in text
        assert "RUNNING" in text
        assert "[*]" in text  # Initial state

    def test_export_class(self, sample_class_diagram):
        exporter = PlantUMLExporter()
        text = exporter.export_diagram(sample_class_diagram)

        assert "@startuml" in text
        assert "class SWC_SensorFusion" in text
        assert "RE_FuseSensorData" in text

    def test_export_to_files(self, tmp_path, sample_generation_result):
        exporter = PlantUMLExporter()
        paths = exporter.export_result(sample_generation_result, tmp_path)

        assert len(paths) == 3  # sequence + state_machine + class
        for p in paths:
            assert p.exists()
            assert p.suffix == ".puml"
