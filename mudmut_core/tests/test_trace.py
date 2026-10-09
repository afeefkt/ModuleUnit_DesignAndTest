from mudmut_core import trace as trace_mod
from mudmut_core.trace import build_trace, function_requirements


def test_extract_requirements_roundtrip():
    from mudmut_core.trace import extract_requirements
    code = "/* Requirements: REQ_001, REQ_002 */\nvoid f(void){ /* [REQ_003] */ }"
    reqs = extract_requirements(code)
    assert "REQ_001" in reqs
    assert "REQ_002" in reqs
    assert "REQ_003" in reqs


def test_function_requirements_maps_reqs_to_functions():
    code = (
        "void RE_A(void)\n{\n"
        "    /* [REQ_1] */\n"
        "    l_u8X = 1;\n"
        "}\n\n"
        "void RE_B(void)\n{\n"
        "    /* [REQ_2] */\n"
        "    l_u8Y = 2;\n"
        "}\n"
    )
    func_reqs = function_requirements(code)
    assert func_reqs.get("RE_A") == ["REQ_1"]
    assert func_reqs.get("RE_B") == ["REQ_2"]


def test_build_trace_links_requirement_to_test_file():
    code = (
        "/* Requirements: REQ_1 */\n"
        "void RE_A(void)\n{\n"
        "    /* [REQ_1] */\n"
        "    l_u8X = 1;\n"
        "}\n"
    )
    generation = {"output_directory": "/tmp/tests_x", "tests_generated": 1}
    record = build_trace("SWC_X", code, generation)
    assert record["module"] == "SWC_X"
    assert record["source_requirements"] == ["REQ_1"]
    assert record["trace"][0]["requirement"] == "REQ_1"
