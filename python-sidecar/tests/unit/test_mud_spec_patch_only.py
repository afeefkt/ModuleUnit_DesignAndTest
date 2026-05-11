from __future__ import annotations

import pytest

from mudtool.ai.mud_spec_generator import (
    SpecReviewResult,
    apply_patch_only_review_fixes,
    deterministic_requirement_coverage,
    MudSpecGenerator,
)
from mudtool.ai.base_backend import AIResponse


SPEC = """# MUD Spec: SWC_Test

## 1. Overview
| Field | Value |
|-------|-------|
| SWC Name | SWC_Test |

## 2. Ports
| Port | Interface |
|------|-----------|

## 3. Runnables
| Runnable | Trigger |
|----------|---------|
| RE_Control | Cyclic |

## 4. Inter-Runnable Variables (IRV)
| IRV | Type |
|-----|------|

## 5. Data Types
| Type | Base |
|------|------|

## 6. Error Handling & Safety
DEM handling.

## 7. Functional Description

### RE_Control
// Reads: RP_Input
// Writes: PP_Output
1. Read inputs
   Rte_Read(RP_Input, &inputValue);
2. Write outputs
   Rte_Write(PP_Output, inputValue);
"""


def test_patch_only_review_fixes_target_section7_without_rewriting_other_sections():
    review = SpecReviewResult(
        approved=False,
        coverage_pct=0,
        uncovered_req_ids=["REQ-CTRL-001"],
        coverage_gaps=["REQ-CTRL-001: missing control saturation logic"],
        patch_plan=[
            {
                "kind": "coverage_gap",
                "section": "7",
                "req_id": "REQ-CTRL-001",
                "target_runnable": "RE_Control",
            }
        ],
    )

    patched, meta = apply_patch_only_review_fixes(
        SPEC,
        "REQ-CTRL-001,Control saturation,SWC_Test shall clamp output safely",
        review,
    )

    assert meta["changed"] is True
    assert meta["mode"] == "patch_only"
    assert "Trace: REQ-CTRL-001" in patched
    assert patched.split("## 7. Functional Description", 1)[0] == SPEC.split("## 7. Functional Description", 1)[0]


def test_deterministic_coverage_detects_explicit_section7_trace():
    spec = SPEC.replace("2. Write outputs", "// Trace: REQ-CTRL-001\n2. Write outputs")

    coverage = deterministic_requirement_coverage(
        spec,
        "REQ-CTRL-001,Control saturation,SWC_Test shall clamp output safely",
        ["REQ-CTRL-001"],
    )

    assert coverage["coverage_pct"] == 100
    assert coverage["uncovered_req_ids"] == []


class _EmptyReviewBackend:
    backend_name = "empty-review"

    async def generate(self, **kwargs):
        return AIResponse(content="", model="empty-review")


class _ReviewOrchestrator:
    def _get_reviewer_backend(self):
        return _EmptyReviewBackend()


@pytest.mark.asyncio
async def test_empty_ai_review_response_is_info_when_deterministic_coverage_passes():
    spec = SPEC.replace("2. Write outputs", "// Trace: REQ-CTRL-001\n2. Write outputs")
    generator = MudSpecGenerator(_ReviewOrchestrator())

    review = await generator.review_spec(
        swc_name="SWC_Test",
        asil="ASIL-B",
        req_ids=["REQ-CTRL-001"],
        requirements_text="REQ-CTRL-001,Control saturation,SWC_Test shall clamp output safely",
        mud_spec_markdown=spec,
        temperature=0.0,
        iteration=2,
    )

    assert review.approved is True
    assert review.coverage_pct == 100
    assert review.error_count == 0
    assert review.info_count == 1
    assert "empty review response" in review.issues[0].message
