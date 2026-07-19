"""Tests for requirement importers."""

import pytest
from pathlib import Path

from mudtool.importers.text_importer import TextImporter
from mudtool.importers.csv_importer import CSVImporter
from mudtool.importers.markdown_importer import MarkdownImporter
from mudtool.importers.factory import ImporterFactory


class TestTextImporter:
    def test_pipe_delimited_format(self, tmp_path):
        content = """REQ-ARCH-0001 | functional | The system shall process sensor data at 10ms
REQ-ARCH-0002 | interface | The SWC shall provide fused data via SR interface
REQ-ARCH-0003 | safety | The system shall detect sensor failures | must | ASIL-B
"""
        file = tmp_path / "requirements.txt"
        file.write_text(content)

        importer = TextImporter()
        result = importer.import_file(file)

        assert result.success
        assert result.requirement_set.count == 3
        assert result.requirement_set.requirements[0].req_id == "REQ-ARCH-0001"
        assert result.requirement_set.requirements[2].safety_level is not None

    def test_simple_colon_format(self, tmp_path):
        content = """REQ-ARCH-0010: The sensor fusion SWC shall output fused data
REQ-ARCH-0011: The vehicle control SWC shall receive fused data
"""
        file = tmp_path / "simple.txt"
        file.write_text(content)

        importer = TextImporter()
        result = importer.import_file(file)

        assert result.success
        assert result.requirement_set.count == 2

    def test_comments_and_empty_lines(self, tmp_path):
        content = """# This is a comment
// Another comment

REQ-ARCH-0001: First requirement

REQ-ARCH-0002: Second requirement
"""
        file = tmp_path / "commented.txt"
        file.write_text(content)

        importer = TextImporter()
        result = importer.import_file(file)

        assert result.requirement_set.count == 2


class TestCSVImporter:
    def test_basic_csv(self, tmp_path):
        content = """Req_ID,Title,Description,Type,Priority
REQ-ARCH-0001,Sensor Processing,Process sensor data at 10ms,functional,must
REQ-ARCH-0002,Data Distribution,Distribute fused data via SR,interface,should
"""
        file = tmp_path / "requirements.csv"
        file.write_text(content)

        importer = CSVImporter()
        result = importer.import_file(file)

        assert result.success
        assert result.requirement_set.count == 2
        assert result.requirement_set.requirements[0].title == "Sensor Processing"

    def test_semicolon_delimiter(self, tmp_path):
        content = """Req_ID;Title;Description;Type;Priority
REQ-ARCH-0001;Sensor Proc;Process sensor data;functional;must
"""
        file = tmp_path / "semi.csv"
        file.write_text(content)

        importer = CSVImporter()
        result = importer.import_file(file)

        assert result.success
        assert result.requirement_set.count == 1


class TestMarkdownImporter:
    def test_markdown_table(self, tmp_path):
        content = """# Requirements

| Req_ID | Title | Description | Type | Priority |
|--------|-------|-------------|------|----------|
| REQ-ARCH-0001 | Sensor Fusion | Fuse sensor data | functional | must |
| REQ-ARCH-0002 | Data Output | Output fused data via SR | interface | should |
"""
        file = tmp_path / "requirements.md"
        file.write_text(content)

        importer = MarkdownImporter()
        result = importer.import_file(file)

        assert result.success
        assert result.requirement_set.count == 2

    def test_no_table_error(self, tmp_path):
        content = """# Just a document
No table here.
"""
        file = tmp_path / "no_table.md"
        file.write_text(content)

        importer = MarkdownImporter()
        result = importer.import_file(file)

        assert not result.success


class TestImporterFactory:
    def test_auto_detect_txt(self, tmp_path):
        file = tmp_path / "reqs.txt"
        file.write_text("REQ-ARCH-0001 | functional | Test requirement\n")

        result = ImporterFactory.import_file(file)
        assert result.success

    def test_auto_detect_csv(self, tmp_path):
        file = tmp_path / "reqs.csv"
        file.write_text("Req_ID,Title,Description,Type,Priority\n"
                        "REQ-ARCH-0001,Test,Test desc,functional,must\n")

        result = ImporterFactory.import_file(file)
        assert result.success

    def test_unsupported_format(self, tmp_path):
        file = tmp_path / "reqs.xml"
        file.write_text("<root/>")

        with pytest.raises(ValueError, match="Unsupported"):
            ImporterFactory.get_importer(file)

    def test_missing_file(self, tmp_path):
        result = ImporterFactory.import_file(tmp_path / "nonexistent.txt")
        assert not result.success
