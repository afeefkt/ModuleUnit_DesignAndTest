"""Importer tolerance: DOORS / Polarion / ReqIF layouts, encodings, odd IDs."""

from pathlib import Path

from mudtool.importers.base import normalize_header, normalize_req_id, strip_markup
from mudtool.importers.factory import ImporterFactory


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_doors_default_columns_and_numeric_ids(tmp_path):
    csv = (
        "Absolute Number,Object Heading,Object Text\n"
        '1001,Init,"The SWC shall initialise on reset."\n'
        "1002,Run,The SWC shall run every 10 ms.\n"
    )
    res = ImporterFactory.import_file(_write(tmp_path, "doors.csv", csv.encode()))
    assert res.errors == [] and res.requirement_set.count == 2
    first = res.requirement_set.requirements[0]
    assert first.req_id == "REQ-1001" and first.title == "Init"
    assert "initialise" in first.description
    assert "Original ID: 1001" in (first.notes or "")


def test_polarion_html_description_is_plain_text(tmp_path):
    csv = (
        "Work Item ID;Title;Description;Status\n"
        'BMS-123;Balance;"<p>Cells shall be <b>balanced</b>&nbsp;within 5&nbsp;mV.</p><ul><li>one</li></ul>";approved\n'
    )
    res = ImporterFactory.import_file(_write(tmp_path, "pol.csv", csv.encode()))
    assert res.errors == []
    req = res.requirement_set.requirements[0]
    assert req.req_id == "BMS-123"
    assert "<" not in req.description and "balanced" in req.description
    assert "- one" in req.description


def test_bom_and_cp1252_csv(tmp_path):
    bom = ("﻿Req_ID,Title,Description\nREQ-1,Wärme,Temp shall be limited\n").encode("utf-8")
    res = ImporterFactory.import_file(_write(tmp_path, "bom.csv", bom))
    assert res.errors == [] and res.requirement_set.requirements[0].req_id == "REQ-1"

    cp = "Req_ID,Title,Description\nREQ-2,Wärme,Temp shall be limited\n".encode("cp1252")
    res = ImporterFactory.import_file(_write(tmp_path, "cp.csv", cp))
    assert res.errors == [] and res.requirement_set.requirements[0].title == "Wärme"
    assert any("cp1252" in w for w in res.warnings)


def test_csv_without_id_column_generates_ids(tmp_path):
    csv = "Title,Description\nA,Do a\nB,Do b\n"
    res = ImporterFactory.import_file(_write(tmp_path, "noid.csv", csv.encode()))
    assert res.errors == [] and [r.req_id for r in res.requirement_set.requirements] == ["REQ-001", "REQ-002"]
    assert any("generated" in w for w in res.warnings)


def test_header_and_id_normalisation():
    assert normalize_header("Object_Text") == normalize_header("object text") == "objecttext"
    assert normalize_req_id("BMS-FUNC-12") == ("BMS-FUNC-12", False)
    assert normalize_req_id("SRS_12")[0] == "SRS-12"
    assert normalize_req_id("3.2.1", 5)[0] == "IMP-0005"
    assert strip_markup("a<br/>b &amp; c") == "a\nb & c"


REQIF = """<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd" xmlns:xhtml="http://www.w3.org/1999/xhtml">
 <CORE-CONTENT><REQ-IF-CONTENT>
  <SPEC-TYPES><SPEC-OBJECT-TYPE IDENTIFIER="T1" LONG-NAME="Requirement"><SPEC-ATTRIBUTES>
    <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="AD-H" LONG-NAME="ReqIF.ChapterName"/>
    <ATTRIBUTE-DEFINITION-XHTML IDENTIFIER="AD-T" LONG-NAME="ReqIF.Text"/>
    <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="AD-I" LONG-NAME="Object Identifier"/>
  </SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE></SPEC-TYPES>
  <SPEC-OBJECTS>
   <SPEC-OBJECT IDENTIFIER="O1"><TYPE><SPEC-OBJECT-TYPE-REF>T1</SPEC-OBJECT-TYPE-REF></TYPE><VALUES>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="Init"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>AD-H</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
     <ATTRIBUTE-VALUE-XHTML><DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>AD-T</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
       <THE-VALUE><xhtml:div><xhtml:p>The SWC shall <xhtml:b>initialise</xhtml:b>.</xhtml:p></xhtml:div></THE-VALUE></ATTRIBUTE-VALUE-XHTML>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="42"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>AD-I</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
   </VALUES></SPEC-OBJECT>
   <SPEC-OBJECT IDENTIFIER="O2"><TYPE><SPEC-OBJECT-TYPE-REF>T1</SPEC-OBJECT-TYPE-REF></TYPE><VALUES>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="Folder only"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>AD-H</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
   </VALUES></SPEC-OBJECT>
  </SPEC-OBJECTS>
 </REQ-IF-CONTENT></CORE-CONTENT>
</REQ-IF>
"""


def test_reqif_import(tmp_path):
    res = ImporterFactory.import_file(_write(tmp_path, "m.reqif", REQIF.encode()))
    assert res.errors == []
    reqs = res.requirement_set.requirements
    assert [r.req_id for r in reqs] == ["REQ-42", "REQ-002"] or reqs[0].req_id == "REQ-42"
    assert reqs[0].title == "Init"
    assert "initialise" in reqs[0].description and "<" not in reqs[0].description
