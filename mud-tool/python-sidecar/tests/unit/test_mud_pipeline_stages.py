from mudtool.ai.mud_pipeline_stages import _assemble_markdown


def test_assemble_markdown_wraps_section7_steps_in_fenced_c_blocks():
    skeleton = {
        "swc_name": "SWC_Test",
        "asil": "QM",
        "description": "Readability check",
        "runnables": [
            {
                "name": "RE_Test",
                "trigger": "Cyclic",
                "period": "10 ms",
                "asil": "QM",
                "description": "Main runnable",
            }
        ],
        "ports": [],
        "calibrations": [],
        "signals": [],
    }
    section7_map = {
        "RE_Test": {
            "steps": [
                {
                    "step_num": "1",
                    "label": "Read inputs",
                    "code": "speed = Rte_IRead(RP_Speed);\nassist = CalcAssist(speed);",
                },
                {
                    "step_num": "2",
                    "label": "Write output",
                    "code": "Rte_IWrite(PP_Assist, assist);",
                },
            ]
        }
    }

    markdown = _assemble_markdown(skeleton, section7_map, [])

    assert "**1. Read inputs**" in markdown
    assert "```c\nspeed = Rte_IRead(RP_Speed);\nassist = CalcAssist(speed);\n```" in markdown
    assert "\n```\n\n**2. Write output**\n```c\n" in markdown


# ── Truncated skeleton answers (provider output cap, finish_reason=length) ────
# Seen with DeepSeek on the 120-requirement AEB set: the JSON was cut off, one inner object
# (a port) was salvaged as "the skeleton", and the spec came out with no runnables.
import json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from mudtool.ai.mud_pipeline_stages import MudSpecPipeline, _skeleton_problems  # noqa: E402

GOOD_SKELETON = {
    "swc_name": "SWC_T", "asil": "QM", "description": "d",
    "ports": [{"name": "RP_Speed", "direction": "required"}],
    "runnables": [{"name": "RE_Main", "trigger": "Cyclic", "period": "10 ms"}],
    "irvs": [], "calparms": [], "dem_events": [],
}
TRUNCATED = json.dumps(GOOD_SKELETON)[:120]      # cut inside the document; one inner {...} is still valid


class _Backend:
    backend_name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        content, finish = self.replies.pop(0)
        return SimpleNamespace(content=content, finish_reason=finish)


async def _skeleton(backend):
    pipe = MudSpecPipeline(backend=backend, skeleton_backend=backend)
    return await pipe._stage1_skeleton("SWC_T", "d", "QM", ["RE_Main"], ["R-1"], "[R-1] text", 0.1)


async def test_truncated_skeleton_is_retried_with_more_room():
    backend = _Backend([(TRUNCATED, "length"), (json.dumps(GOOD_SKELETON), "stop")])
    skeleton = await _skeleton(backend)
    assert [r["name"] for r in skeleton["runnables"]] == ["RE_Main"]
    assert backend.calls[1]["max_tokens"] > backend.calls[0]["max_tokens"]


async def test_skeleton_still_truncated_is_rejected_not_salvaged():
    backend = _Backend([(TRUNCATED, "length"), (TRUNCATED, "length")])
    assert await _skeleton(backend) is None      # caller falls back to the single-pass spec


async def test_empty_answer_at_the_cap_is_not_asked_again():
    backend = _Backend([("", "length")])          # reasoning model used the whole budget thinking
    assert await _skeleton(backend) is None
    assert len(backend.calls) == 1


async def test_fragment_without_skeleton_keys_is_not_a_skeleton():
    backend = _Backend([('noise {"name": "RP_Speed", "direction": "required"} noise {', "stop")] * 2)
    assert await _skeleton(backend) is None


async def test_two_stage_pipeline_reaches_section7_and_assembles_a_spec():
    """The Section 7 system prompt was built with str.format() over text that contains C braces
    ("unmatched '{' in format spec"), so the two-stage pipeline crashed for every runnable and
    every "two-stage" spec was in fact the single-pass fallback (seen in run 20261111_002323,
    the first run whose skeleton call succeeded)."""
    section7 = {"runnable_name": "RE_Main", "steps": [
        {"step_num": 1, "label": "Compute", "code": "l_f32Out = Rte_IRead(RP_Speed) * 2.0F;"}]}
    backend = _Backend([(json.dumps(GOOD_SKELETON), "stop"), (json.dumps(section7), "stop")])
    pipe = MudSpecPipeline(backend=backend, skeleton_backend=backend)
    spec = await pipe.generate("SWC_T", "d", "QM", ["RE_Main"], ["R-1"], "[R-1] text")
    assert "RE_Main" in spec and "l_f32Out = Rte_IRead(RP_Speed) * 2.0F;" in spec
    assert "REFERENCE EXAMPLE" in backend.calls[1]["system_prompt"]
    assert "{few_shot_example}" not in backend.calls[1]["system_prompt"]

    # The assembled spec ("**1. Compute**" + a fenced code block) must be readable by the step
    # parser the spec check and the flow builder use. Run 20261111_003217: the first two-stage
    # spec that was ever assembled was rejected with "13 runnables have no steps".
    from mudtool.ai.mud_activity_context import build_mud_activity_context, runnable_flow_quality
    ctx = build_mud_activity_context(spec, "SWC_T")
    assert [r.name for r in ctx.runnables] == ["RE_Main"]
    assert runnable_flow_quality(ctx.runnables[0]) == "logic"


def test_cross_ref_check_reads_mixed_case_dem_event_ids():
    """Run 20261111_003755 reported 18 x "DEM event 'SWC_DEM_E_B' not defined": the pattern
    stopped at the first lowercase letter of SWC_DEM_E_BrakeFault, which is defined."""
    from mudtool.ai.mud_pipeline_stages import _validate_cross_refs
    skeleton = dict(GOOD_SKELETON, dem_events=[{"event_id": "SWC_DEM_E_BrakeFault"}])
    s7 = {"RE_Main": {"steps": [{"step_num": 1, "code":
          "Dem_ReportErrorStatus(SWC_DEM_E_BrakeFault, DEM_EVENT_STATUS_FAILED);\n"
          "Dem_ReportErrorStatus(SWC_DEM_E_Missing2, DEM_EVENT_STATUS_FAILED);"}]}}
    issues = _validate_cross_refs(skeleton, s7)
    assert len(issues) == 1 and "'SWC_DEM_E_Missing2'" in issues[0]


def test_skeleton_without_runnables_is_a_problem():
    empty = dict(GOOD_SKELETON, runnables=[])
    assert any("runnables" in p for p in _skeleton_problems(empty, "QM"))
    assert not _skeleton_problems(GOOD_SKELETON, "QM")


async def test_skeleton_without_runnables_after_retry_is_rejected():
    empty = json.dumps(dict(GOOD_SKELETON, runnables=[]))
    backend = _Backend([(empty, "stop"), (empty, "stop")])
    assert await _skeleton(backend) is None
