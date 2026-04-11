from mudtool.ai.prompt_engine import PromptEngine
from mudtool.config.settings import Settings
from mudtool.models.json_uml import DiagramType
from mudtool.models.requirements import Requirement, RequirementType, Priority


def test_prompt_engine_loads_generic_profile():
    engine = PromptEngine(Settings())
    engine.load_templates()
    tmpl = engine.get_template(DiagramType.ACTIVITY, profile="generic_c")
    assert tmpl is not None
    assert tmpl.profile == "generic_c"


def test_generic_profile_changes_fallback_wording():
    engine = PromptEngine(Settings())
    reqs = [
        Requirement(
            req_id="REQ-001",
            title="Main loop",
            description="System shall process data",
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
        )
    ]
    prompt = engine.render_user_prompt(
        DiagramType.ACTIVITY,
        reqs,
        profile="generic_c",
    )
    assert "AUTOSAR" not in prompt


def test_activity_prompt_style_switches_wording():
    engine = PromptEngine(Settings())
    reqs = [
        Requirement(
            req_id="REQ-010",
            title="Compute output",
            description="System shall compute and write output",
            req_type=RequirementType.FUNCTIONAL,
            priority=Priority.MUST,
        )
    ]

    pseudo_prompt = engine.render_user_prompt(
        DiagramType.ACTIVITY,
        reqs,
        profile="autosar",
        activity_label_style="pseudocode",
    )
    callsig_prompt = engine.render_user_prompt(
        DiagramType.ACTIVITY,
        reqs,
        profile="autosar",
        activity_label_style="call_signature",
    )

    assert "Use short pseudocode-style node names" in pseudo_prompt
    assert "Use explicit call-signature labels" in callsig_prompt
