from mudtool.ai.mud_pipeline_stages import _SECTION7_SYSTEM
from mudtool.ai.mud_spec_generator import _GEN_SYSTEM_PROMPT


def test_section7_two_stage_prompt_requires_strict_code_like_format():
    lowered = _SECTION7_SYSTEM.lower()

    assert "one executable statement per line" in lowered
    assert "explicit if / else if / else / switch / case / default / return" in lowered
    assert "no mixed prose + code on the same line" in lowered
    assert 'no arrow shorthand like "-> safe_state"' in lowered


def test_single_pass_mud_prompt_requires_short_section7_labels_and_no_arrow_shorthand():
    lowered = _GEN_SYSTEM_PROMPT.lower()

    assert "one executable statement per line" in lowered
    # The prompt forbids prose — at least one of these control-flow rule phrases must be present
    assert (
        "explicit if / else if / else / switch / case / default / return statements" in lowered
        or "explicit control keyword" in lowered
        or "if( / else {" in lowered.replace(" ", "").replace("\n", "")
        or "if / else if / else / switch" in lowered
    ), "GEN_SYSTEM_PROMPT must require explicit C control-flow keywords in Section 7"
    # Arrow shorthand must be forbidden
    assert (
        "no arrow shorthand" in lowered
        or "arrow shorthand" in lowered
    ), "GEN_SYSTEM_PROMPT must forbid arrow shorthand (-> SAFE_STATE)"
    # Guard / Read / Compute / Write structure must be mentioned
    assert (
        "short labels such as guard" in lowered
        or "guard → read inputs" in lowered
        or "guard" in lowered and "read inputs" in lowered and "compute" in lowered
    ), "GEN_SYSTEM_PROMPT must describe structural step labels (Guard, Read, Compute, Write)"
