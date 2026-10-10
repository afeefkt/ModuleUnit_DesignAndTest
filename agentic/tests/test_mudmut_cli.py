"""Tests for the deterministic mudmut_cli tools.

Covers: JSON envelope parsing, requirement import, activity validation
(including the broken-diagram case with a fix hint), C export, and Mermaid
rendering.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import mudmut_cli
from mudtool.models.json_uml import ActivityDiagram, GenerationResult

TOOLS = Path(__file__).resolve().parents[1] / "tools" / "mudmut_cli.py"

# A well-formed activity flow: initial → call(read) → decision → action → call(write) → final
VALID_ACTIVITY = {
    "diagram_type": "activity",
    "name": "RE_EstimateSOC_Flow",
    "owner_swc": "SWC_BatteryManagement",
    "owner_runnable": "RE_EstimateSOC",
    "source_requirements": ["REQ-BMS-002"],
    "nodes": [
        {"id": "N_01", "name": "Start", "node_type": "initial"},
        {"id": "N_02", "name": "Rte_Read_RP_SOCVoltage_Val(&l_f32Volt)", "node_type": "call",
         "rte_call": "Rte_Read", "port": "RP_SOCVoltage", "element": "Val", "trace_reqs": ["REQ-BMS-002"]},
        {"id": "N_03", "name": "l_f32Volt > 1.5f", "node_type": "decision", "description": "voltage valid"},
        {"id": "N_04", "name": "l_f32SOC = EKF_Predict()", "node_type": "action", "trace_reqs": ["REQ-BMS-002"]},
        {"id": "N_05", "name": "Rte_Write_PP_SOCPercent_Val(l_f32SOC)", "node_type": "call",
         "rte_call": "Rte_Write", "port": "PP_SOCPercent", "element": "Val", "trace_reqs": ["REQ-BMS-002"]},
        {"id": "N_06", "name": "End", "node_type": "final"},
    ],
    "edges": [
        {"id": "E_01", "source": "N_01", "target": "N_02"},
        {"id": "E_02", "source": "N_02", "target": "N_03"},
        {"id": "E_03", "source": "N_03", "target": "N_04", "guard": "[l_f32Volt > 1.5f]"},
        {"id": "E_04", "source": "N_03", "target": "N_05", "guard": "[else]"},
        {"id": "E_05", "source": "N_04", "target": "N_05"},
        {"id": "E_06", "source": "N_05", "target": "N_06"},
    ],
}

# Broken: no final node, and a decision with only ONE outgoing edge (unguarded).
BROKEN_ACTIVITY = {
    "diagram_type": "activity",
    "name": "RE_Broken_Flow",
    "owner_swc": "SWC_BatteryManagement",
    "owner_runnable": "RE_Broken",
    "source_requirements": ["REQ-BMS-002"],
    "nodes": [
        {"id": "N_01", "name": "Start", "node_type": "initial"},
        {"id": "N_02", "name": "l_f32Speed > LIMIT", "node_type": "decision"},
        {"id": "N_03", "name": "l_f32Out = 1.0f", "node_type": "action"},
    ],
    "edges": [
        {"id": "E_01", "source": "N_01", "target": "N_02"},
        {"id": "E_02", "source": "N_02", "target": "N_03"},
    ],
}


def _run(*args: str) -> subprocess.CompletedProcess:
    import os
    import tempfile
    if not hasattr(_run, "_tmp"):
        _run._tmp = tempfile.mkdtemp(prefix="mudmut_cli_test_")  # type: ignore[attr-defined]
    env = dict(os.environ)
    env["MUDMUT_RUNS_DIR"] = _run._tmp  # type: ignore[attr-defined]
    return subprocess.run(
        [sys.executable, str(TOOLS), *args],
        capture_output=True, text=True, timeout=120, env=env,
    )


def _json_of(proc: subprocess.CompletedProcess) -> dict:
    assert proc.returncode == 0, f"exit={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    return json.loads(proc.stdout)


# ── parse_generation_result ───────────────────────────────────────────────────

def test_parse_bare_diagram():
    result = mudmut_cli.parse_generation_result(VALID_ACTIVITY)
    assert isinstance(result, GenerationResult)
    assert len(result.diagrams) == 1
    assert isinstance(result.diagrams[0], ActivityDiagram)


def test_parse_wrapper_and_list():
    wrapped = mudmut_cli.parse_generation_result({"diagrams": [VALID_ACTIVITY]})
    listed = mudmut_cli.parse_generation_result([VALID_ACTIVITY])
    assert len(wrapped.diagrams) == len(listed.diagrams) == 1


# ── import-reqs ───────────────────────────────────────────────────────────────

def test_import_requirements(tmp_path):
    csv = tmp_path / "reqs.csv"
    csv.write_text(
        "Req_ID,Title,Description,Type,ASIL,Priority,Module_Hint\n"
        "REQ-BMS-001,Test SWC,\"SWC_BatteryManagement shall estimate SOC every 10ms.\",functional,QM,MUST,SWC_BatteryManagement\n"
        "REQ-BMS-002,SOC Runnable,\"RE_EstimateSOC shall run every 10 ms.\",timing,ASIL-D,MUST,SWC_BatteryManagement\n",
        encoding="utf-8",
    )
    proc = _run("import-reqs", str(csv), "--run", "t_import")
    out = _json_of(proc)
    assert out["ok"] is True
    assert out["count"] == 2
    assert out["ids"] == ["REQ-BMS-001", "REQ-BMS-002"]

    reqs_path = Path(out["run_dir"]) / "requirements.json"
    assert reqs_path.exists()


def test_show_req(tmp_path):
    csv = tmp_path / "reqs.csv"
    csv.write_text(
        "Req_ID,Title,Description,Type,ASIL,Priority,Module_Hint\n"
        "REQ-BMS-001,Test SWC,does something,functional,QM,MUST,SWC_BatteryManagement\n",
        encoding="utf-8",
    )
    _run("import-reqs", str(csv), "--run", "t_show")
    proc = _run("show-req", "REQ-BMS-001", "--run", "t_show")
    out = _json_of(proc)
    assert out["ok"] is True
    assert out["requirement"]["req_id"] == "REQ-BMS-001"
    assert out["requirement"]["description"] == "does something"


# ── validate-activity ─────────────────────────────────────────────────────────

def test_validate_valid(tmp_path):
    ajson = tmp_path / "activity.json"
    ajson.write_text(json.dumps(VALID_ACTIVITY), encoding="utf-8")
    proc = _run("validate-activity", str(ajson), "--run", "t_val_valid")
    out = _json_of(proc)
    assert out["valid"] is True
    assert out["error_count"] == 0


def test_validate_broken_flags_with_fix_hint(tmp_path):
    ajson = tmp_path / "activity.json"
    ajson.write_text(json.dumps(BROKEN_ACTIVITY), encoding="utf-8")
    proc = _run("validate-activity", str(ajson), "--run", "t_val_broken")
    out = _json_of(proc)
    assert out["valid"] is False
    assert out["error_count"] >= 1
    # At least one issue must carry an actionable fix_hint.
    hints = [i["fix_hint"] for i in out["issues"] if i["fix_hint"]]
    assert hints, f"expected at least one fix_hint, got issues={out['issues']}"


# ── export-c / render-mermaid ─────────────────────────────────────────────────

def test_export_c(tmp_path):
    ajson = tmp_path / "activity.json"
    ajson.write_text(json.dumps(VALID_ACTIVITY), encoding="utf-8")
    proc = _run("export-c", str(ajson), "--run", "t_export")
    out = _json_of(proc)
    assert out["ok"] is True
    assert len(out["files"]) == 1
    c_path = Path(next(iter(out["files"].values())))
    content = c_path.read_text(encoding="utf-8")
    assert "void RE_EstimateSOC(void)" in content
    assert "#include" in content


def test_render_mermaid(tmp_path):
    ajson = tmp_path / "activity.json"
    ajson.write_text(json.dumps(VALID_ACTIVITY), encoding="utf-8")
    proc = _run("render-mermaid", str(ajson), "--run", "t_render")
    out = _json_of(proc)
    assert out["ok"] is True
    mmd_path = Path(next(iter(out["files"].values())))
    content = mmd_path.read_text(encoding="utf-8")
    assert content.lstrip().startswith("flowchart TD")
