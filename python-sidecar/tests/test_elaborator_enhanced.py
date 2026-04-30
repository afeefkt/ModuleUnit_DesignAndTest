import pytest
import json
from mudtool.ai.elaborator import RequirementElaborator, build_enriched_context
from mudtool.models.requirements import Requirement, RequirementType, Priority

def test_parse_response_with_tags():
    elaborator = RequirementElaborator.__new__(RequirementElaborator)
    text = """
    <reasoning>
    - Identified SWC_Control for REQ-001.
    - Needs a periodic trigger.
    </reasoning>
    <json>
    {
        "architecture_summary": "Test Summary",
        "elaborated": [
            {
                "req_id": "REQ-001",
                "entities": {"swc": "SWC_Control"},
                "logic_flow": "Do X then Y"
            }
        ]
    }
    </json>
    """
    result = elaborator._parse_response(text, "hash123")
    assert result["architecture_summary"] == "Test Summary"
    assert result["elaborated"][0]["req_id"] == "REQ-001"
    assert "Identified SWC_Control" in result["thinking"][0]

def test_parse_response_fallback():
    elaborator = RequirementElaborator.__new__(RequirementElaborator)
    text = '{"elaborated": [{"req_id": "REQ-002"}]}'
    result = elaborator._parse_response(text, "hash456")
    assert result["elaborated"][0]["req_id"] == "REQ-002"
    assert result["req_hash"] == "hash456"

def test_build_enriched_context():
    data = {
        "architecture_summary": "System Alpha",
        "elaborated": [
            {
                "req_id": "REQ-001",
                "entities": {"swc": "SWC_1", "ports": ["P1"]},
                "logic_flow": "Flow A",
                "diagram_hints": {"activity": "Use decision node"}
            }
        ],
        "thinking": ["Think 1"]
    }
    context = build_enriched_context(data)
    assert "### ARCHITECTURE ANALYSIS" in context
    assert "System Alpha" in context
    assert "SWC: `SWC_1`" in context
    assert "Flow A" in context
    assert "Use decision node" in context
    assert "Think 1" in context


def test_elaboration_quality_gate_invalid_when_parse_failed():
    elaborator = RequirementElaborator.__new__(RequirementElaborator)
    reqs = [
        Requirement(
            req_id="REQ-001",
            title="A",
            description="B",
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
        )
    ]
    data = {
        "parse_ok": False,
        "elaborated": [{"req_id": "REQ-001"}],
    }
    assert elaborator._is_valid_elaboration(data, reqs) is False


def test_elaboration_quality_score_uses_coverage():
    elaborator = RequirementElaborator.__new__(RequirementElaborator)
    reqs = [
        Requirement(
            req_id="REQ-001",
            title="A",
            description="B",
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
        ),
        Requirement(
            req_id="REQ-002",
            title="C",
            description="D",
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
        ),
    ]
    data = {
        "parse_ok": True,
        "elaborated": [{"req_id": "REQ-001"}],
    }
    score = elaborator._compute_quality(data, reqs)
    assert score > 0.0
    assert score < 1.0
