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
    assert "explicit if / else if / else / switch / case / default / return statements" in lowered
    assert "no arrow shorthand such as \"-> safe_state\"" in lowered
    assert "short labels such as guard / read inputs / validate / compute / write outputs" in lowered
