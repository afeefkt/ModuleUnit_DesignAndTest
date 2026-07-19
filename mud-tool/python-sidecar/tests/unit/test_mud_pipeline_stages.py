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
